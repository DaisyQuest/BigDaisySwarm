import datetime as dt
import os
import shutil
import subprocess
import uuid

import psycopg
from psycopg import sql

import pytest

from bigdaisyswarm import CalendarError
from bigdaisyswarm.calendar import CalendarService, EventService, Participant, ParticipantService
from bigdaisyswarm.serialization import serialize_storage
from bigdaisyswarm.storage import PostgresCalendarStorage


def _ensure_cluster_running() -> None:
    if shutil.which("pg_isready") is None:
        pytest.skip("PostgreSQL tools not available")
    check = subprocess.run(["pg_isready", "-q"], capture_output=True)
    if check.returncode != 0:
        start = subprocess.run(["pg_ctlcluster", "16", "main", "start"], capture_output=True)
        if start.returncode != 0:
            pytest.skip("Unable to start PostgreSQL cluster for tests")
    subprocess.run(
        ["su", "-s", "/bin/bash", "postgres", "-c", "psql -c \"ALTER USER postgres WITH PASSWORD 'postgres';\""],
        check=True,
        capture_output=True,
    )


@pytest.fixture()
def postgres_conninfo():
    _ensure_cluster_running()
    admin_conninfo = os.getenv("PG_ADMIN_CONNINFO", "postgresql://postgres:postgres@localhost/postgres")
    db_name = f"calendar_test_{uuid.uuid4().hex}"

    with psycopg.connect(admin_conninfo, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))

    conninfo = f"postgresql://postgres:postgres@localhost/{db_name}"
    try:
        yield conninfo
    finally:
        with psycopg.connect(admin_conninfo, autocommit=True) as conn:
            conn.execute(
                sql.SQL("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s"),
                (db_name,),
            )
            conn.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(db_name)))


def test_postgres_storage_round_trip(postgres_conninfo):
    with PostgresCalendarStorage(postgres_conninfo) as storage:
        calendar_service = CalendarService(storage)
        event_service = EventService(calendar_service, storage)
        calendar_id = calendar_service.create_calendar(
            "Work",
            owners=["owner@example.com", "viewer@example.com"],
            description="DB-backed",
        )
        start = dt.datetime(2025, 1, 1, 9, 0, tzinfo=dt.timezone.utc)
        end = dt.datetime(2025, 1, 1, 10, 0, tzinfo=dt.timezone.utc)
        event_id = event_service.create_event(calendar_id, "Planning", start, end, timezone="UTC")
        participant = Participant(id="alice", name="Alice", email="alice@example.com")
        participant_service = ParticipantService(event_service)
        participant_service.add_participant(event_id, participant)
        event_service.cancel_event(event_id)

    with PostgresCalendarStorage(postgres_conninfo) as storage:
        calendars = storage.list_calendars(owner="viewer@example.com")
        assert calendars and calendars[0]["id"] == calendar_id
        event = storage.get_event(event_id)
        assert event is not None
        assert event.canceled is True
        assert "alice" in event.participants


def test_postgres_replace_state(postgres_conninfo):
    payload = {
        "calendars": [{"id": "demo", "name": "Demo", "owners": ["demo@example.com"]}],
        "events": [
            {
                "id": "evt-1",
                "calendar_id": "demo",
                "title": "Sync",
                "start": "2025-03-01T10:00:00+00:00",
                "end": "2025-03-01T11:00:00+00:00",
                "timezone": "UTC",
                "metadata": {"room": "A"},
                "participants": {
                    "host": {
                        "id": "host",
                        "name": "Host",
                        "email": "host@example.com",
                        "response": "accepted",
                    }
                },
                "overrides": {"2025-03-02": {"start": None, "end": None, "canceled": True}},
            }
        ],
    }

    with PostgresCalendarStorage(postgres_conninfo) as storage:
        storage.replace_state(payload)
        snapshot = serialize_storage(storage)

    assert {calendar["id"] for calendar in snapshot["calendars"]} == {"demo"}
    event = next(iter(snapshot["events"]))
    assert event["metadata"]["room"] == "A"
    assert event["participants"]["host"]["email"] == "host@example.com"
    assert event["overrides"]["2025-03-02"]["canceled"] is True


def test_postgres_storage_validates_dates(postgres_conninfo):
    payload = {
        "calendars": [{"id": "demo", "name": "Demo", "owners": ["demo@example.com"]}],
        "events": [
            {
                "id": "evt-1",
                "calendar_id": "demo",
                "title": "Sync",
                "start": "2025-03-01T11:00:00+00:00",
                "end": "2025-03-01T10:00:00+00:00",
                "timezone": "UTC",
            }
        ],
    }

    with PostgresCalendarStorage(postgres_conninfo) as storage:
        with pytest.raises(CalendarError):
            storage.replace_state(payload)
