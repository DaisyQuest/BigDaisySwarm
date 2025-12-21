from __future__ import annotations

from typing import Dict, List, Optional, Protocol


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


# Deferred import to avoid circular dependency for type checking.
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bigdaisyswarm.calendar import Event

