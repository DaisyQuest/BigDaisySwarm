from __future__ import annotations

import contextlib
import datetime as dt
from typing import Dict, Iterable, List, Optional, Protocol

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from psycopg.types.json import Json


class CalendarStorage(Protocol):
    """Transport-agnostic storage for calendars and events."""

    def save_calendar(self, calendar: Dict[str, object]) -> None:
        ...

    def get_calendar(self, calendar_id: str) -> Optional[Dict[str, object]]:
        ...

    def list_calendars(self, owner: Optional[str] = None) -> List[Dict[str, object]]:
        ...

    def save_event(self, event: "Event") -> None:
        ...

    def get_event(self, event_id: str) -> Optional["Event"]:
        ...

    def list_events(self, calendar_id: str) -> List["Event"]:
        ...


class InMemoryCalendarStorage(CalendarStorage):
    """Default in-memory storage backend."""

    def __init__(self) -> None:
        self._calendars: Dict[str, Dict[str, object]] = {}
        self._events: Dict[str, "Event"] = {}

    def save_calendar(self, calendar: Dict[str, object]) -> None:
        self._calendars[calendar["id"]] = dict(calendar)

    def get_calendar(self, calendar_id: str) -> Optional[Dict[str, object]]:
        return self._calendars.get(calendar_id)

    def list_calendars(self, owner: Optional[str] = None) -> List[Dict[str, object]]:
        calendars = list(self._calendars.values())
        if owner is None:
            return calendars
        return [calendar for calendar in calendars if owner in calendar.get("owners", [])]

    def save_event(self, event: "Event") -> None:
        self._events[event.id] = event

    def get_event(self, event_id: str) -> Optional["Event"]:
        return self._events.get(event_id)

    def list_events(self, calendar_id: str) -> List["Event"]:
        return [event for event in self._events.values() if event.calendar_id == calendar_id]


class PostgresCalendarStorage(CalendarStorage):
    """PostgreSQL-backed storage."""

    def __init__(self, conninfo: str, *, create_schema: bool = True) -> None:
        self._pool = ConnectionPool(conninfo, open=False)
        self._pool.open()
        if create_schema:
            self._initialize_schema()

    def close(self) -> None:
        self._pool.close()

    def _initialize_schema(self) -> None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS calendars (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        owners TEXT[] NOT NULL,
                        description TEXT NOT NULL DEFAULT ''
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS events (
                        id TEXT PRIMARY KEY,
                        calendar_id TEXT NOT NULL REFERENCES calendars(id) ON DELETE CASCADE,
                        title TEXT NOT NULL,
                        start_ts TIMESTAMPTZ NOT NULL,
                        end_ts TIMESTAMPTZ NOT NULL,
                        timezone TEXT NOT NULL,
                        recurrence TEXT NULL,
                        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                        canceled BOOLEAN NOT NULL DEFAULT FALSE
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS participants (
                        event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                        participant_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        email TEXT NOT NULL,
                        response TEXT NULL,
                        PRIMARY KEY (event_id, participant_id)
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS overrides (
                        event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                        occurrence_date DATE NOT NULL,
                        start_ts TIMESTAMPTZ NULL,
                        end_ts TIMESTAMPTZ NULL,
                        canceled BOOLEAN NOT NULL DEFAULT FALSE,
                        PRIMARY KEY (event_id, occurrence_date)
                    );
                    """
                )
                cur.execute("CREATE INDEX IF NOT EXISTS idx_events_calendar ON events (calendar_id);")

    def save_calendar(self, calendar: Dict[str, object]) -> None:
        owners = [str(owner) for owner in calendar.get("owners", [])]
        description = str(calendar.get("description", ""))
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                self._write_calendar(cur, calendar_id=calendar["id"], name=calendar["name"], owners=owners, description=description)

    def get_calendar(self, calendar_id: str) -> Optional[Dict[str, object]]:
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT id, name, owners, description FROM calendars WHERE id = %s", (calendar_id,))
                row = cur.fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "name": row["name"],
            "owners": row["owners"],
            "description": row["description"],
        }

    def list_calendars(self, owner: Optional[str] = None) -> List[Dict[str, object]]:
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                if owner is None:
                    cur.execute("SELECT id, name, owners, description FROM calendars ORDER BY id")
                else:
                    cur.execute(
                        "SELECT id, name, owners, description FROM calendars WHERE %s = ANY(owners) ORDER BY id",
                        (owner,),
                    )
                rows = cur.fetchall()
        return [
            {"id": row["id"], "name": row["name"], "owners": row["owners"], "description": row["description"]}
            for row in rows
        ]

    def save_event(self, event: "Event") -> None:
        with self._pool.connection() as conn, conn.transaction():
            with conn.cursor() as cur:
                self._write_event(cur, event)

    def get_event(self, event_id: str) -> Optional["Event"]:
        events = self._load_events(where_clause=sql.SQL("WHERE e.id = %s"), params=[event_id])
        return events[0] if events else None

    def list_events(self, calendar_id: str) -> List["Event"]:
        return self._load_events(where_clause=sql.SQL("WHERE e.calendar_id = %s"), params=[calendar_id])

    def replace_state(self, payload: Dict[str, object]) -> None:
        from .serialization import hydrate_storage

        memory_storage = InMemoryCalendarStorage()
        hydrate_storage(memory_storage, payload)

        with self._pool.connection() as conn, conn.transaction():
            with conn.cursor() as cur:
                cur.execute("DELETE FROM overrides")
                cur.execute("DELETE FROM participants")
                cur.execute("DELETE FROM events")
                cur.execute("DELETE FROM calendars")
                for calendar in memory_storage.list_calendars():
                    owners = [str(owner) for owner in calendar.get("owners", [])]
                    description = str(calendar.get("description", ""))
                    self._write_calendar(
                        cur,
                        calendar_id=calendar["id"],
                        name=calendar["name"],
                        owners=owners,
                        description=description,
                    )
                for calendar in memory_storage.list_calendars():
                    for event in memory_storage.list_events(calendar["id"]):
                        self._write_event(cur, event)

    def _load_events(self, *, where_clause: sql.SQL, params: Iterable[object]) -> List["Event"]:
        from .calendar import Event, OccurrenceOverride, Participant

        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    sql.SQL(
                        """
                        SELECT e.id, e.calendar_id, e.title, e.start_ts, e.end_ts, e.timezone,
                               e.recurrence, e.metadata, e.canceled
                        FROM events e
                        {}
                        ORDER BY e.start_ts, e.id
                        """
                    ).format(where_clause),
                    params,
                )
                events = cur.fetchall()

                if not events:
                    return []

                event_ids = tuple(row["id"] for row in events)
                cur.execute(
                    """
                    SELECT event_id, participant_id, name, email, response
                    FROM participants
                    WHERE event_id = ANY(%s)
                    """,
                    (list(event_ids),),
                )
                participants = cur.fetchall()

                cur.execute(
                    """
                    SELECT event_id, occurrence_date, start_ts, end_ts, canceled
                    FROM overrides
                    WHERE event_id = ANY(%s)
                    """,
                    (list(event_ids),),
                )
                overrides = cur.fetchall()

        participants_by_event: Dict[str, Dict[str, "Participant"]] = {}
        for row in participants:
            participant = Participant(
                id=row["participant_id"],
                name=row["name"],
                email=row["email"],
                response=row["response"],
            )
            participants_by_event.setdefault(row["event_id"], {})[participant.id] = participant

        overrides_by_event: Dict[str, Dict[dt.date, "OccurrenceOverride"]] = {}
        for row in overrides:
            occurrence = dt.date.fromisoformat(row["occurrence_date"].isoformat())
            overrides_by_event.setdefault(row["event_id"], {})[occurrence] = OccurrenceOverride(
                occurrence_date=occurrence,
                start=row["start_ts"],
                end=row["end_ts"],
                canceled=row["canceled"],
            )

        loaded_events: List["Event"] = []
        for row in events:
            loaded_events.append(
                Event(
                    id=row["id"],
                    calendar_id=row["calendar_id"],
                    title=row["title"],
                    start=row["start_ts"],
                    end=row["end_ts"],
                    timezone=row["timezone"],
                    recurrence=row["recurrence"],
                    metadata=dict(row["metadata"] or {}),
                    participants=participants_by_event.get(row["id"], {}),
                    overrides=overrides_by_event.get(row["id"], {}),
                    canceled=row["canceled"],
                )
            )
        return loaded_events

    def _write_calendar(self, cur, *, calendar_id: str, name: str, owners: List[str], description: str) -> None:
        cur.execute(
            """
            INSERT INTO calendars (id, name, owners, description)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE
            SET name = EXCLUDED.name,
                owners = EXCLUDED.owners,
                description = EXCLUDED.description;
            """,
            (calendar_id, name, owners, description),
        )

    def _write_event(self, cur, event: "Event") -> None:
        cur.execute(
            """
            INSERT INTO events (
                id, calendar_id, title, start_ts, end_ts, timezone, recurrence, metadata, canceled
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE
            SET calendar_id = EXCLUDED.calendar_id,
                title = EXCLUDED.title,
                start_ts = EXCLUDED.start_ts,
                end_ts = EXCLUDED.end_ts,
                timezone = EXCLUDED.timezone,
                recurrence = EXCLUDED.recurrence,
                metadata = EXCLUDED.metadata,
                canceled = EXCLUDED.canceled;
            """,
            (
                event.id,
                event.calendar_id,
                event.title,
                event.start,
                event.end,
                event.timezone,
                event.recurrence,
                Json(event.metadata),
                event.canceled,
            ),
        )
        cur.execute("DELETE FROM participants WHERE event_id = %s", (event.id,))
        if event.participants:
            participant_rows = [
                (event.id, participant.id, participant.name, participant.email, participant.response)
                for participant in event.participants.values()
            ]
            cur.executemany(
                """
                INSERT INTO participants (event_id, participant_id, name, email, response)
                VALUES (%s, %s, %s, %s, %s)
                """,
                participant_rows,
            )
        cur.execute("DELETE FROM overrides WHERE event_id = %s", (event.id,))
        if event.overrides:
            override_rows = [
                (
                    event.id,
                    occurrence_date,
                    override.start,
                    override.end,
                    override.canceled,
                )
                for occurrence_date, override in event.overrides.items()
            ]
            cur.executemany(
                """
                INSERT INTO overrides (event_id, occurrence_date, start_ts, end_ts, canceled)
                VALUES (%s, %s, %s, %s, %s)
                """,
                override_rows,
            )

    def __enter__(self) -> "PostgresCalendarStorage":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


# Deferred import to avoid circular dependency for type checking.
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bigdaisyswarm.calendar import Event, OccurrenceOverride, Participant
