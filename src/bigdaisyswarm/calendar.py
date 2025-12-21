from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field, replace
from typing import Dict, Iterable, List, Mapping, Optional


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
class OccurrenceOverride:
    occurrence_date: dt.date
    start: Optional[dt.datetime] = None
    end: Optional[dt.datetime] = None
    canceled: bool = False

    def is_cancellation(self) -> bool:
        return self.canceled


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
    overrides: Dict[dt.date, OccurrenceOverride] = field(default_factory=dict)
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
            return
        _require(isinstance(occurrence, dt.date), "occurrence must be a date")
        override = OccurrenceOverride(occurrence_date=occurrence, canceled=True)
        self._set_override(override)

    def reschedule(self, occurrence: dt.date, start: dt.datetime, end: dt.datetime) -> None:
        _require(isinstance(occurrence, dt.date), "occurrence must be a date")
        normalized_start = _normalize_datetime(start)
        normalized_end = _normalize_datetime(end)
        _require(normalized_start < normalized_end, "start must be before end")
        override = OccurrenceOverride(
            occurrence_date=occurrence,
            start=normalized_start,
            end=normalized_end,
            canceled=False,
        )
        self._set_override(override)

    def _set_override(self, override: OccurrenceOverride) -> None:
        existing = self.overrides.get(override.occurrence_date)
        if existing and existing != override:
            if existing.is_cancellation() != override.is_cancellation():
                self.overrides[override.occurrence_date] = override
                return
            raise CalendarError(f"Conflicting override for {override.occurrence_date.isoformat()}")
        self.overrides[override.occurrence_date] = override


class CalendarService:
    def __init__(self) -> None:
        self._calendars: Dict[str, Dict[str, object]] = {}

    def create_calendar(self, name: str, owners: Iterable[str], description: Optional[str] = None) -> str:
        _require(name, "calendar name is required")
        owners = list(owners)
        _require(owners, "at least one owner is required")
        calendar_id = uuid.uuid4().hex
        self._calendars[calendar_id] = {
            "id": calendar_id,
            "name": name,
            "owners": owners,
            "description": description or "",
        }
        return calendar_id

    def list_calendars(self, owner: Optional[str] = None) -> List[Dict[str, object]]:
        if owner is None:
            return list(self._calendars.values())
        return [c for c in self._calendars.values() if owner in c["owners"]]

    def ensure_calendar_exists(self, calendar_id: str) -> None:
        _require(calendar_id in self._calendars, f"calendar '{calendar_id}' does not exist")


class EventService:
    def __init__(self, calendar_service: CalendarService) -> None:
        self._calendar_service = calendar_service
        self._events: Dict[str, Event] = {}

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

        self._events[event_id] = Event(
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
        return event_id

    def update_event(self, event_id: str, **fields: object) -> None:
        event = self._get_event(event_id)
        event.update(**fields)

    def cancel_event(self, event_id: str, occurrence: Optional[dt.date] = None) -> None:
        event = self._get_event(event_id)
        event.cancel(occurrence=occurrence)

    def reschedule_event(
        self, event_id: str, occurrence: dt.date, start: dt.datetime, end: dt.datetime
    ) -> None:
        event = self._get_event(event_id)
        event.reschedule(occurrence=occurrence, start=start, end=end)

    def list_events(
        self,
        calendar_id: str,
        range_start: Optional[dt.datetime] = None,
        range_end: Optional[dt.datetime] = None,
    ) -> List[Event]:
        self._calendar_service.ensure_calendar_exists(calendar_id)
        events = [event for event in self._events.values() if event.calendar_id == calendar_id]
        if range_start or range_end:
            if range_start:
                range_start = _normalize_datetime(range_start)
            if range_end:
                range_end = _normalize_datetime(range_end)
            if range_start and range_end:
                _require(range_start < range_end, "range_start must be before range_end")

        def overlaps(start: dt.datetime, end: dt.datetime) -> bool:
            if range_start and end < range_start:
                return False
            if range_end and start > range_end:
                return False
            return True

        results: List[Event] = []
        for event in events:
            occurrences = self._render_occurrences(event)
            for occurrence in occurrences:
                if range_start or range_end:
                    if not overlaps(occurrence.start, occurrence.end):
                        continue
                results.append(occurrence)
        return results

    def _get_event(self, event_id: str) -> Event:
        _require(event_id in self._events, f"event '{event_id}' does not exist")
        return self._events[event_id]

    def _render_occurrences(self, event: Event) -> List[Event]:
        base_date = event.start.date()
        occurrences: List[Event] = []

        def add_occurrence(override: Optional[OccurrenceOverride], *, is_base: bool) -> None:
            if override and override.is_cancellation():
                return
            if override and override.start and override.end:
                occurrences.append(replace(event, start=override.start, end=override.end))
            elif is_base:
                occurrences.append(replace(event))
            elif override:
                raise CalendarError("Override must include start and end for rescheduled occurrences")

        add_occurrence(event.overrides.get(base_date), is_base=True)

        for date, override in event.overrides.items():
            if date == base_date:
                continue
            add_occurrence(override, is_base=False)

        if not occurrences and not event.overrides:
            occurrences.append(replace(event))
        return occurrences


class ParticipantService:
    def __init__(self, event_service: EventService) -> None:
        self._event_service = event_service

    def add_participant(self, event_id: str, participant: Participant) -> None:
        event = self._event_service._get_event(event_id)
        _require(participant.email, "participant email is required")
        event.participants[participant.id] = participant

    def remove_participant(self, event_id: str, participant_id: str) -> None:
        event = self._event_service._get_event(event_id)
        if participant_id in event.participants:
            del event.participants[participant_id]

    def update_participant(self, event_id: str, participant_id: str, response: Optional[str] = None) -> None:
        event = self._event_service._get_event(event_id)
        _require(participant_id in event.participants, "participant does not exist on event")
        event.participants[participant_id] = event.participants[participant_id].update(response=response)


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
            occurrence_date = self._parse_date(occurrence) if occurrence else None
            self.event_service.cancel_event(event_id, occurrence=occurrence_date)
            return f"CANCELED {event_id}"
        if command == "RESCHEDULE_EVENT":
            event_id = args.get("event")
            _require(event_id, "event is required for RESCHEDULE_EVENT")
            occurrence = self._parse_date(args.get("occurrence"))
            start = self._parse_datetime(args.get("start"))
            end = self._parse_datetime(args.get("end"))
            self.event_service.reschedule_event(event_id, occurrence=occurrence, start=start, end=end)
            return f"RESCHEDULED {event_id}"
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

    @staticmethod
    def _parse_date(value: Optional[str]) -> dt.date:
        _require(value, "occurrence is required")
        try:
            return dt.date.fromisoformat(value)
        except ValueError as exc:
            raise CalendarError(f"Invalid occurrence date: '{value}'") from exc

    def _require_participant_service(self) -> ParticipantService:
        if self.participant_service is None:
            raise CalendarError("Participant service is not configured")
        return self.participant_service
