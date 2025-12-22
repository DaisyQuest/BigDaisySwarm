import datetime as dt

import pytest

from bigdaisyswarm.calendar import CalendarError
from bigdaisyswarm.serialization import hydrate_storage, serialize_storage
from bigdaisyswarm.storage import CalendarStorage, InMemoryCalendarStorage


class StubStorage(CalendarStorage):
    def save_calendar(self, calendar):
        raise RuntimeError("unimplemented")

    def get_calendar(self, calendar_id):
        return None

    def list_calendars(self, owner=None):
        return []

    def save_event(self, event):
        raise RuntimeError("unimplemented")

    def get_event(self, event_id):
        return None

    def list_events(self, calendar_id):
        return []


def test_hydrate_storage_replaces_state_and_overrides():
    storage = InMemoryCalendarStorage()
    storage.save_calendar({"id": "old", "name": "Old", "owners": ["old@example.com"]})

    payload = {
        "calendars": [{"id": "demo", "name": "Demo", "owners": ["demo@example.com"]}],
        "events": [
            {
                "id": "evt-1",
                "calendar_id": "demo",
                "title": "Sync",
                "start": "2025-01-01T10:00:00+00:00",
                "end": "2025-01-01T11:00:00+00:00",
                "timezone": "UTC",
                "participants": {
                    "host": {
                        "id": "host",
                        "name": "Host",
                        "email": "host@example.com",
                        "response": "accepted",
                    }
                },
                "overrides": {
                    "2025-01-02": {"start": None, "end": None, "canceled": True},
                },
            }
        ],
    }

    hydrate_storage(storage, payload)
    snapshot = serialize_storage(storage)

    assert {calendar["id"] for calendar in snapshot["calendars"]} == {"demo"}
    event = storage.list_events("demo")[0]
    assert event.participants["host"].response == "accepted"
    assert dt.date(2025, 1, 2) in event.overrides
    assert event.overrides[dt.date(2025, 1, 2)].canceled is True


def test_hydrate_storage_rejects_non_memory_storage():
    storage = StubStorage()
    payload = {"calendars": [], "events": []}
    with pytest.raises(CalendarError):
        hydrate_storage(storage, payload)
