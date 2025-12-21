from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional

from .storage import CalendarStorage, InMemoryCalendarStorage


class CalendarError(ValueError):
    """Base class for calendar-specific validation errors."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CalendarError(message)


def _normalize_datetime(value: dt.datetime) -> dt.datetime:
    _require(isinstance(value, dt.datetime), "Datetime values must be datetime objects")
    if value.tzinfo is None:
        raise CalendarError("Datetime values must be timezone-aware (tzinfo required)")
    return value.astimezone(dt.timezone.utc)


@dataclass(frozen=True)
class Participant:
    id: str
    name: str
    email: str
    response: Optional[str] = None

    def update(self, response: Optional[str] = None) -> "Participant":
        return Participant(id=self.id, name=self.name, email=self.email, response=response)


@dataclass
class Event:
    id: str
    calendar_id: str
    title: str
    start: dt.datetime
    end: dt.datetime
    timezone: str
    recurrence: Optional[str] = None
    participants: Dict[str, Participant] = field(default_factory=dict)
    metadata: Dict[str, object] = field(default_factory=dict)
    canceled_occurrences: List[dt.date] = field(default_factory=list)
    canceled: bool = False

    def update(self, **fields: object) -> None:
        if "title" in fields:
            _require(fields["title"], "title cannot be empty")
            self.title = str(fields["title"])
        if "start" in fields or "end" in fields:
            new_start = _normalize_datetime(fields.get("start", self.start))
            new_end = _normalize_datetime(fields.get("end", self.end))
            _require(new_start < new_end, "start must be before end")
            self.start = new_start
            self.end = new_end
        if "timezone" in fields:
            _require(fields["timezone"], "timezone cannot be empty")
            self.timezone = str(fields["timezone"])
        if "recurrence" in fields:
            self.recurrence = fields["recurrence"]
        if "metadata" in fields:
            _require(isinstance(fields["metadata"], Mapping), "metadata must be a mapping")
            self.metadata = dict(fields["metadata"])

    def cancel(self, occurrence: Optional[dt.date] = None) -> None:
        if occurrence is None:
            self.canceled = True
        else:
            if occurrence not in self.canceled_occurrences:
                self.canceled_occurrences.append(occurrence)


class CalendarService:
    def __init__(self, storage: Optional[CalendarStorage] = None) -> None:
        self._storage = storage or InMemoryCalendarStorage()

    def create_calendar(self, name: str, owners: Iterable[str], description: Optional[str] = None) -> str:
        _require(name, "calendar name is required")
        owners = list(owners)
        _require(owners, "at least one owner is required")
        calendar_id = uuid.uuid4().hex
        calendar = {
            "id": calendar_id,
            "name": name,
            "owners": owners,
            "description": description or "",
        }
        self._storage.save_calendar(calendar)
        return calendar_id

    def list_calendars(self, owner: Optional[str] = None) -> List[Dict[str, object]]:
        return self._storage.list_calendars(owner=owner)

    def ensure_calendar_exists(self, calendar_id: str) -> None:
        _require(self._storage.get_calendar(calendar_id) is not None, f"calendar '{calendar_id}' does not exist")

    @property
    def storage(self) -> CalendarStorage:
        return self._storage


class EventService:
    def __init__(self, calendar_service: CalendarService, storage: Optional[CalendarStorage] = None) -> None:
        self._calendar_service = calendar_service
        self._storage = storage or calendar_service.storage

    def create_event(
        self,
        calendar_id: str,
        title: str,
        start: dt.datetime,
        end: dt.datetime,
        timezone: str,
        recurrence: Optional[str] = None,
        participants: Optional[Iterable[Participant]] = None,
        metadata: Optional[Mapping[str, object]] = None,
    ) -> str:
        self._calendar_service.ensure_calendar_exists(calendar_id)
        _require(title, "title is required")
        start_utc = _normalize_datetime(start)
        end_utc = _normalize_datetime(end)
        _require(start_utc < end_utc, "start must be before end")
        _require(timezone, "timezone is required")
        if metadata is not None:
            _require(isinstance(metadata, Mapping), "metadata must be a mapping")

        event_id = uuid.uuid4().hex
        participant_map = {
            participant.id: participant for participant in (participants or [])
        }
        for participant in participant_map.values():
            _require(participant.email, "participant email is required")

        event = Event(
            id=event_id,
            calendar_id=calendar_id,
            title=title,
            start=start_utc,
            end=end_utc,
            timezone=timezone,
            recurrence=recurrence,
            participants=participant_map,
            metadata=dict(metadata or {}),
        )
        self._storage.save_event(event)
        return event_id

    def update_event(self, event_id: str, **fields: object) -> None:
        event = self._get_event(event_id)
        event.update(**fields)
        self._storage.save_event(event)

    def cancel_event(self, event_id: str, occurrence: Optional[dt.date] = None) -> None:
        event = self._get_event(event_id)
        event.cancel(occurrence=occurrence)
        self._storage.save_event(event)

    def list_events(
        self,
        calendar_id: str,
        range_start: Optional[dt.datetime] = None,
        range_end: Optional[dt.datetime] = None,
    ) -> List[Event]:
        self._calendar_service.ensure_calendar_exists(calendar_id)
        events = self._storage.list_events(calendar_id)
        if range_start or range_end:
            if range_start:
                range_start = _normalize_datetime(range_start)
            if range_end:
                range_end = _normalize_datetime(range_end)
            if range_start and range_end:
                _require(range_start < range_end, "range_start must be before range_end")
            events = [
                event
                for event in events
                if (range_start is None or event.end >= range_start)
                and (range_end is None or event.start <= range_end)
            ]
        return events

    def _get_event(self, event_id: str) -> Event:
        event = self._storage.get_event(event_id)
        _require(event is not None, f"event '{event_id}' does not exist")
        return event


class ParticipantService:
    def __init__(self, event_service: EventService) -> None:
        self._event_service = event_service

    def add_participant(self, event_id: str, participant: Participant) -> None:
        event = self._event_service._get_event(event_id)
        _require(participant.email, "participant email is required")
        event.participants[participant.id] = participant
        self._event_service._storage.save_event(event)

    def remove_participant(self, event_id: str, participant_id: str) -> None:
        event = self._event_service._get_event(event_id)
        if participant_id in event.participants:
            del event.participants[participant_id]
            self._event_service._storage.save_event(event)

    def update_participant(self, event_id: str, participant_id: str, response: Optional[str] = None) -> None:
        event = self._event_service._get_event(event_id)
        _require(participant_id in event.participants, "participant does not exist on event")
        event.participants[participant_id] = event.participants[participant_id].update(response=response)
        self._event_service._storage.save_event(event)


class DSLExecutor:
    """Parse and execute simple DSL commands against the services."""

    def __init__(
        self,
        calendar_service: CalendarService,
        event_service: EventService,
        participant_service: Optional[ParticipantService] = None,
    ) -> None:
        self.calendar_service = calendar_service
        self.event_service = event_service
        self.participant_service = participant_service or ParticipantService(event_service)

    def execute(self, lines: Iterable[str]) -> List[str]:
        results: List[str] = []
        for line_no, raw in enumerate(lines, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            try:
                result = self._execute_line(line)
                results.append(result)
            except CalendarError as exc:
                raise CalendarError(f"Line {line_no}: {exc}") from exc
        return results

    def _execute_line(self, line: str) -> str:
        tokens = line.split()
        _require(tokens, "empty line")
        command = tokens[0].upper()
        args = self._parse_args(tokens[1:])
        if command == "CREATE_CALENDAR":
            owners = args.get("owners", "").split(",") if args.get("owners") else []
            calendar_id = self.calendar_service.create_calendar(
                name=args.get("name", ""),
                owners=owners,
                description=args.get("description"),
            )
            return f"CALENDAR {calendar_id}"
        if command == "CREATE_EVENT":
            calendar_id = args.get("calendar")
            start = self._parse_datetime(args.get("start"))
            end = self._parse_datetime(args.get("end"))
            timezone = args.get("timezone") or "UTC"
            event_id = self.event_service.create_event(
                calendar_id=calendar_id,
                title=args.get("title", ""),
                start=start,
                end=end,
                timezone=timezone,
                recurrence=args.get("recurrence"),
            )
            return f"EVENT {event_id}"
        if command == "CANCEL_EVENT":
            event_id = args.get("event")
            occurrence = args.get("occurrence")
            if occurrence:
                try:
                    occurrence_date = dt.date.fromisoformat(occurrence)
                except ValueError as exc:
                    raise CalendarError(f"Invalid occurrence date: '{occurrence}'") from exc
            else:
                occurrence_date = None
            self.event_service.cancel_event(event_id, occurrence=occurrence_date)
            return f"CANCELED {event_id}"
        if command == "ADD_PARTICIPANT":
            participant_service = self._require_participant_service()
            event_id = args.get("event")
            participant_id = args.get("participant")
            name = args.get("name")
            email = args.get("email")
            response = args.get("response")
            _require(event_id, "event is required for ADD_PARTICIPANT")
            _require(participant_id, "participant id is required for ADD_PARTICIPANT")
            _require(name, "participant name is required for ADD_PARTICIPANT")
            _require(email, "participant email is required for ADD_PARTICIPANT")
            participant = Participant(id=participant_id, name=name, email=email, response=response)
            participant_service.add_participant(event_id, participant)
            return f"PARTICIPANT {participant_id} ADDED"
        if command == "UPDATE_PARTICIPANT":
            participant_service = self._require_participant_service()
            event_id = args.get("event")
            participant_id = args.get("participant")
            response = args.get("response")
            _require(event_id, "event is required for UPDATE_PARTICIPANT")
            _require(participant_id, "participant id is required for UPDATE_PARTICIPANT")
            participant_service.update_participant(event_id, participant_id, response=response)
            return f"PARTICIPANT {participant_id} UPDATED"
        if command == "REMOVE_PARTICIPANT":
            participant_service = self._require_participant_service()
            event_id = args.get("event")
            participant_id = args.get("participant")
            _require(event_id, "event is required for REMOVE_PARTICIPANT")
            _require(participant_id, "participant id is required for REMOVE_PARTICIPANT")
            participant_service.remove_participant(event_id, participant_id)
            return f"PARTICIPANT {participant_id} REMOVED"
        raise CalendarError(f"Unknown command '{command}'")

    @staticmethod
    def _parse_args(tokens: List[str]) -> Dict[str, str]:
        args: Dict[str, str] = {}
        for token in tokens:
            if "=" not in token:
                raise CalendarError(f"Invalid token '{token}'")
            key, value = token.split("=", 1)
            args[key] = value.strip('"')
        return args

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> dt.datetime:
        _require(value, "start and end must be provided")
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise CalendarError(f"Invalid datetime format: '{value}'") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed

    def _require_participant_service(self) -> ParticipantService:
        if self.participant_service is None:
            raise CalendarError("Participant service is not configured")
        return self.participant_service
