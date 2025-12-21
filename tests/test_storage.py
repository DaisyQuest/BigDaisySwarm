import datetime as dt

import pytest

from bigdaisyswarm.calendar import CalendarError, CalendarService, EventService, Participant, ParticipantService
from bigdaisyswarm.storage import CalendarStorage, InMemoryCalendarStorage


class RecordingStorage(CalendarStorage):
    def __init__(self) -> None:
        self.saved_calendars = {}
        self.saved_events = {}

    def save_calendar(self, calendar: dict) -> None:
        self.saved_calendars[calendar["id"]] = dict(calendar)

    def get_calendar(self, calendar_id: str):
        return self.saved_calendars.get(calendar_id)

    def list_calendars(self, owner=None):
        calendars = list(self.saved_calendars.values())
        if owner is None:
            return calendars
        return [calendar for calendar in calendars if owner in calendar.get("owners", [])]

    def save_event(self, event):
        self.saved_events[event.id] = event

    def get_event(self, event_id):
        return self.saved_events.get(event_id)

    def list_events(self, calendar_id):
        return [event for event in self.saved_events.values() if event.calendar_id == calendar_id]


def test_inmemory_storage_round_trip():
    storage = InMemoryCalendarStorage()
    calendar_service = CalendarService(storage)
    event_service = EventService(calendar_service, storage)
    participant_service = ParticipantService(event_service)

    calendar_id = calendar_service.create_calendar("Work", owners=["alice@example.com"], description="Team")
    start = dt.datetime(2024, 5, 1, 9, 0, tzinfo=dt.timezone.utc)
    end = dt.datetime(2024, 5, 1, 10, 0, tzinfo=dt.timezone.utc)
    event_id = event_service.create_event(
        calendar_id,
        "Planning",
        start,
        end,
        timezone="UTC",
        recurrence="weekly",
        metadata={"room": "A"},
    )

    participant = Participant(id="alice", name="Alice", email="alice@example.com")
    participant_service.add_participant(event_id, participant)
    event_service.update_event(event_id, title="Planning v2", recurrence="monthly")
    event_service.cancel_event(event_id, occurrence=dt.date(2024, 5, 8))

    stored_events = storage.list_events(calendar_id)
    assert len(stored_events) == 1
    stored_event = stored_events[0]
    assert stored_event.id == event_id
    assert stored_event.title == "Planning v2"
    assert stored_event.recurrence == "monthly"
    assert stored_event.metadata["room"] == "A"
    assert dt.date(2024, 5, 8) in stored_event.canceled_occurrences
    assert "alice" in stored_event.participants


def test_inmemory_storage_filters_by_owner():
    storage = InMemoryCalendarStorage()
    calendar_service = CalendarService(storage)
    first = calendar_service.create_calendar("Work", owners=["alice@example.com"])
    second = calendar_service.create_calendar("Personal", owners=["bob@example.com"])

    assert {cal["id"] for cal in calendar_service.list_calendars()} == {first, second}
    alice_cals = calendar_service.list_calendars(owner="alice@example.com")
    assert len(alice_cals) == 1 and alice_cals[0]["id"] == first
    assert calendar_service.list_calendars(owner="carol@example.com") == []


def test_services_use_shared_storage_for_validation():
    storage = RecordingStorage()
    calendar_service = CalendarService(storage)
    event_service = EventService(calendar_service, storage)

    with pytest.raises(CalendarError):
        event_service.list_events("missing")

    calendar_id = calendar_service.create_calendar("Work", owners=["owner@example.com"])
    start = dt.datetime(2024, 6, 1, 9, 0, tzinfo=dt.timezone.utc)
    end = dt.datetime(2024, 6, 1, 10, 0, tzinfo=dt.timezone.utc)
    event_id = event_service.create_event(calendar_id, "Check", start, end, timezone="UTC")

    # Ensure CalendarService sees calendar via storage
    assert storage.get_calendar(calendar_id)["name"] == "Work"
    # Ensure EventService reads/writes via storage
    assert storage.get_event(event_id) is not None

    with pytest.raises(CalendarError):
        event_service.update_event("missing", title="Nope")

    with pytest.raises(CalendarError):
        event_service.cancel_event("missing")

    with pytest.raises(CalendarError):
        ParticipantService(event_service).update_participant(event_id, "missing", response="accepted")


class CountingStorage(InMemoryCalendarStorage):
    def __init__(self) -> None:
        super().__init__()
        self.saved_events: list[str] = []

    def save_event(self, event):
        super().save_event(event)
        self.saved_events.append(event.id)


def test_custom_storage_participant_mutations_saved():
    storage = CountingStorage()
    calendar_service = CalendarService(storage)
    event_service = EventService(calendar_service, storage)
    participant_service = ParticipantService(event_service)
    calendar_id = calendar_service.create_calendar("Work", owners=["owner@example.com"])
    start = dt.datetime(2024, 7, 1, 9, 0, tzinfo=dt.timezone.utc)
    end = dt.datetime(2024, 7, 1, 10, 0, tzinfo=dt.timezone.utc)
    event_id = event_service.create_event(calendar_id, "Sync", start, end, timezone="UTC")

    participant = Participant(id="bob", name="Bob", email="bob@example.com")
    participant_service.add_participant(event_id, participant)
    participant_service.update_participant(event_id, "bob", response="declined")
    participant_service.remove_participant(event_id, "bob")

    stored_event = storage.get_event(event_id)
    assert stored_event is not None
    assert "bob" not in stored_event.participants
    assert storage.saved_events.count(event_id) == 4

    participant_service.remove_participant(event_id, "missing")
    assert storage.saved_events.count(event_id) == 4
