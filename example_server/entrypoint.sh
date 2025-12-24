#!/usr/bin/env bash
set -euo pipefail

DATA_DIR="${PGDATA:-/var/lib/postgresql/data}"
DB_NAME="${POSTGRES_DB:-calendarapp}"
DB_USER="${POSTGRES_USER:-postgres}"
DB_PASSWORD="${POSTGRES_PASSWORD:-postgres}"
DB_PORT="${POSTGRES_PORT:-5432}"

if [[ ! -s "${DATA_DIR}/PG_VERSION" ]]; then
  mkdir -p "${DATA_DIR}"
  chown -R postgres:postgres "${DATA_DIR}"
  su -s /bin/bash postgres -c "/usr/lib/postgresql/16/bin/initdb -D '${DATA_DIR}'"
fi

stop_postgres() {
  su -s /bin/bash postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D '${DATA_DIR}' -m fast stop" >/dev/null 2>&1 || true
}
trap stop_postgres EXIT

su -s /bin/bash postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D '${DATA_DIR}' -o \"-p ${DB_PORT} -c listen_addresses='*'\" -w start"

if ! su -s /bin/bash postgres -c "psql -tAc \"SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'\" | grep -q 1"; then
  su -s /bin/bash postgres -c "createdb -p ${DB_PORT} ${DB_NAME}"
fi
su -s /bin/bash postgres -c "psql -p ${DB_PORT} -c \"ALTER USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';\""

export DATABASE_URL="${DATABASE_URL:-postgresql://${DB_USER}:${DB_PASSWORD}@localhost:${DB_PORT}/${DB_NAME}}"

exec "$@"
