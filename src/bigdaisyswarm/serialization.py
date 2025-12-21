from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Dict, Mapping, Optional

from .calendar import CalendarError, Event, Participant, OccurrenceOverride
from .storage import CalendarStorage, InMemoryCalendarStorage


def _parse_datetime(value: object, *, field_name: str) -> dt.datetime:
    if not isinstance(value, str):
        raise CalendarError(f"{field_name} must be an ISO 8601 string")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CalendarError(f"{field_name} must be an ISO 8601 datetime") from exc
    if parsed.tzinfo is None:
        raise CalendarError(f"{field_name} must include timezone info")
    return parsed


def _parse_date(value: object, *, field_name: str) -> dt.date:
    if not isinstance(value, str):
        raise CalendarError(f"{field_name} must be a date string")
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise CalendarError(f"{field_name} must use YYYY-MM-DD format") from exc


def _deserialize_event(raw: Mapping[str, object]) -> Event:
    required_fields = ["id", "calendar_id", "title", "start", "end", "timezone"]
    for field_name in required_fields:
        if field_name not in raw:
            raise CalendarError(f"Stored event is missing required field '{field_name}'")

    event_id = str(raw["id"])
    start = _parse_datetime(raw["start"], field_name=f"event {event_id} start")
    end = _parse_datetime(raw["end"], field_name=f"event {event_id} end")
    if start >= end:
        raise CalendarError(f"event {event_id} start must be before end")
    metadata = raw.get("metadata", {})
    if not isinstance(metadata, Mapping):
        raise CalendarError("Event metadata must be a mapping when loading storage")

    participants_data = raw.get("participants", {})
    if not isinstance(participants_data, Mapping):
        raise CalendarError("Event participants must be stored as a mapping")
    participants: Dict[str, Participant] = {}
    for participant_id, participant_raw in participants_data.items():
        if not isinstance(participant_raw, Mapping):
            raise CalendarError("Participant entries must be mappings")
        participants[participant_id] = Participant(
            id=str(participant_raw.get("id", participant_id)),
            name=str(participant_raw.get("name", "")),
            email=str(participant_raw.get("email", "")),
            response=participant_raw.get("response"),
        )

    overrides_raw = raw.get("overrides", {})
    if not isinstance(overrides_raw, Mapping):
        raise CalendarError("Event overrides must be stored as a mapping")
    overrides: Dict[dt.date, OccurrenceOverride] = {}
    for date_str, override_raw in overrides_raw.items():
        occurrence_date = _parse_date(date_str, field_name="override date")
        if not isinstance(override_raw, Mapping):
            raise CalendarError("Override entries must be mappings")
        canceled = bool(override_raw.get("canceled", False))
        start_override = override_raw.get("start")
        end_override = override_raw.get("end")
        if canceled:
            start_dt = _parse_datetime(start_override, field_name="override start") if start_override else None
            end_dt = _parse_datetime(end_override, field_name="override end") if end_override else None
        else:
            if (start_override is None) != (end_override is None):
                raise CalendarError("Rescheduled occurrences must include start and end times")
            start_dt = _parse_datetime(start_override, field_name="override start") if start_override else None
            end_dt = _parse_datetime(end_override, field_name="override end") if end_override else None
        overrides[occurrence_date] = OccurrenceOverride(
            occurrence_date=occurrence_date,
            start=start_dt,
            end=end_dt,
            canceled=canceled,
        )

    return Event(
        id=event_id,
        calendar_id=str(raw["calendar_id"]),
        title=str(raw["title"]),
        start=start,
        end=end,
        timezone=str(raw["timezone"]),
        recurrence=raw.get("recurrence"),
        participants=participants,
        metadata=dict(metadata),
        overrides=overrides,
        canceled=bool(raw.get("canceled", False)),
    )


def serialize_event(event: Event) -> Dict[str, object]:
    overrides = {
        date.isoformat(): {
            "start": override.start.isoformat() if override.start else None,
            "end": override.end.isoformat() if override.end else None,
            "canceled": override.canceled,
        }
        for date, override in event.overrides.items()
    }
    participants = {
        participant_id: {
            "id": participant.id,
            "name": participant.name,
            "email": participant.email,
            "response": participant.response,
        }
        for participant_id, participant in event.participants.items()
    }
    return {
        "id": event.id,
        "calendar_id": event.calendar_id,
        "title": event.title,
        "start": event.start.isoformat(),
        "end": event.end.isoformat(),
        "timezone": event.timezone,
        "recurrence": event.recurrence,
        "participants": participants,
        "metadata": event.metadata,
        "overrides": overrides,
        "canceled": event.canceled,
    }


def serialize_storage(storage: CalendarStorage) -> Dict[str, object]:
    calendars = storage.list_calendars()
    events = []
    for calendar in calendars:
        for event in storage.list_events(calendar["id"]):
            events.append(serialize_event(event))
    return {"calendars": calendars, "events": events}


def load_storage(path: Optional[Path]) -> InMemoryCalendarStorage:
    storage = InMemoryCalendarStorage()
    if path is None or not path.exists():
        return storage

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CalendarError(f"Failed to read calendar storage from {path}: invalid JSON") from exc

    calendars = raw.get("calendars", [])
    if not isinstance(calendars, list):
        raise CalendarError("Stored calendars must be a list")
    for calendar in calendars:
        storage.save_calendar(calendar)

    events = raw.get("events", [])
    if not isinstance(events, list):
        raise CalendarError("Stored events must be a list")
    for event_raw in events:
        if not isinstance(event_raw, Mapping):
            raise CalendarError("Each stored event entry must be a mapping")
        event = _deserialize_event(event_raw)
        storage.save_event(event)

    return storage


def dump_storage(storage: InMemoryCalendarStorage, path: Path) -> None:
    payload = serialize_storage(storage)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output:
        json.dump(payload, output, indent=2)
        output.write("\n")

