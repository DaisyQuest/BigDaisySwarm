from __future__ import annotations

import datetime as dt
import json
import shlex
import uuid
from dataclasses import dataclass, field, replace
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

    @property
    def canceled_occurrences(self) -> List[dt.date]:
        return sorted(date for date, override in self.overrides.items() if override.canceled)

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

    @property
    def canceled_occurrences(self) -> set[dt.date]:
        canceled = {date for date, override in self.overrides.items() if override.canceled}
        if self.canceled:
            canceled.add(self.start.date())
        return canceled



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
        _require(
            self._storage.get_calendar(calendar_id) is not None,
            f"calendar '{calendar_id}' does not exist",
        )

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
        participant_map = {participant.id: participant for participant in (participants or [])}
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

    def reschedule_event(self, event_id: str, occurrence: dt.date, start: dt.datetime, end: dt.datetime) -> None:
        event = self._get_event(event_id)
        event.reschedule(occurrence=occurrence, start=start, end=end)
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

        def overlaps(start: dt.datetime, end: dt.datetime) -> bool:
            if range_start and end < range_start:
                return False
            if range_end and start > range_end:
                return False
            return True

        results: List[Event] = []
        for event in events:
            for occurrence in self._render_occurrences(event):
                if (range_start or range_end) and not overlaps(occurrence.start, occurrence.end):
                    continue
                results.append(occurrence)
        return results

    def _get_event(self, event_id: str) -> Event:
        event = self._storage.get_event(event_id)
        _require(event is not None, f"event '{event_id}' does not exist")
        return event

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
        self.participant_service = participant_service
        self._COMMANDS = {
            "CREATE_CALENDAR",
            "LIST_CALENDARS",
            "CREATE_EVENT",
            "UPDATE_EVENT",
            "CANCEL_EVENT",
            "RESCHEDULE_EVENT",
            "LIST_EVENTS",
            "ADD_PARTICIPANT",
            "UPDATE_PARTICIPANT",
            "REMOVE_PARTICIPANT",
        }

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
        tokens = self._tokenize(line)
        _require(tokens, "empty line")
        command = tokens[0].upper()
        args = self._parse_args(tokens[1:])

        if command == "CREATE_CALENDAR":
            self._validate_args(command, args, required={"name", "owners"}, optional={"description"})
            owners = self._split_list(args.get("owners", ""))
            calendar_id = self.calendar_service.create_calendar(
                name=args.get("name", ""),
                owners=owners,
                description=args.get("description"),
            )
            return f"CALENDAR {calendar_id}"

        if command == "LIST_CALENDARS":
            self._validate_args(command, args, required=set(), optional={"owner"})
            calendars = self.calendar_service.list_calendars(owner=args.get("owner"))
            calendar_ids = ",".join(calendar["id"] for calendar in calendars) or "<none>"
            return f"CALENDARS {calendar_ids}"

        if command == "CREATE_EVENT":
            self._validate_args(
                command,
                args,
                required={"calendar", "title", "start", "end"},
                optional={"timezone", "recurrence", "metadata"},
            )
            calendar_id = args.get("calendar")
            start = self._parse_datetime(args.get("start"), "start")
            end = self._parse_datetime(args.get("end"), "end")
            timezone = args.get("timezone") or "UTC"
            event_id = self.event_service.create_event(
                calendar_id=calendar_id,
                title=args.get("title", ""),
                start=start,
                end=end,
                timezone=timezone,
                recurrence=args.get("recurrence"),
                metadata=self._parse_metadata(args.get("metadata")) if "metadata" in args else None,
            )
            return f"EVENT {event_id}"

        if command == "UPDATE_EVENT":
            self._validate_args(
                command,
                args,
                required={"event"},
                optional={"title", "start", "end", "timezone", "recurrence", "metadata"},
            )
            _require(
                len(args) > 1,
                "UPDATE_EVENT requires a field to update (title, start, end, timezone, recurrence, metadata)",
            )
            updates: Dict[str, object] = {}
            if "title" in args:
                updates["title"] = args["title"]
            if "start" in args:
                updates["start"] = self._parse_datetime(args.get("start"), "start")
            if "end" in args:
                updates["end"] = self._parse_datetime(args.get("end"), "end")
            if "timezone" in args:
                updates["timezone"] = args["timezone"]
            if "recurrence" in args:
                updates["recurrence"] = args["recurrence"]
            if "metadata" in args:
                updates["metadata"] = self._parse_metadata(args.get("metadata"))
            self.event_service.update_event(args["event"], **updates)
            return f"EVENT {args['event']} UPDATED"

        if command == "CANCEL_EVENT":
            self._validate_args(command, args, required={"event"}, optional={"occurrence"})
            event_id = args.get("event")
            occurrence_raw = args.get("occurrence")
            occurrence_date = (
                self._parse_date(occurrence_raw, field_name="occurrence") if occurrence_raw else None
            )
            self.event_service.cancel_event(event_id, occurrence=occurrence_date)
            return f"CANCELED {event_id}"

        if command == "RESCHEDULE_EVENT":
            self._validate_args(command, args, required={"event", "occurrence"}, optional={"start", "end"})
            if "start" not in args or "end" not in args:
                raise CalendarError("RESCHEDULE_EVENT start and end must be provided")
            event_id = args.get("event")
            _require(event_id, "event is required for RESCHEDULE_EVENT")
            occurrence = self._parse_date(args.get("occurrence"), field_name="occurrence")
            start = self._parse_datetime(args.get("start"), "start")
            end = self._parse_datetime(args.get("end"), "end")
            self.event_service.reschedule_event(event_id, occurrence=occurrence, start=start, end=end)
            return f"RESCHEDULED {event_id}"

        if command == "LIST_EVENTS":
            self._validate_args(command, args, required={"calendar"}, optional={"range_start", "range_end"})
            range_start = (
                self._parse_datetime(args.get("range_start"), "range_start") if "range_start" in args else None
            )
            range_end = (
                self._parse_datetime(args.get("range_end"), "range_end") if "range_end" in args else None
            )
            events = self.event_service.list_events(args["calendar"], range_start=range_start, range_end=range_end)
            event_ids = ",".join(event.id for event in events) or "<none>"
            return f"EVENTS {event_ids}"

        if command == "ADD_PARTICIPANT":
            participant_service = self._require_participant_service()
            event_id = args.get("event")
            participant_id = args.get("participant")
            name = args.get("name")
            email = args.get("email")
            response = args.get("response")
            self._validate_args(
                command,
                args,
                required={"event", "participant", "name", "email"},
                optional={"response"},
            )
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
            self._validate_args(command, args, required={"event", "participant"}, optional={"response"})
            _require(event_id, "event is required for UPDATE_PARTICIPANT")
            _require(participant_id, "participant id is required for UPDATE_PARTICIPANT")
            participant_service.update_participant(event_id, participant_id, response=response)
            return f"PARTICIPANT {participant_id} UPDATED"

        if command == "REMOVE_PARTICIPANT":
            participant_service = self._require_participant_service()
            event_id = args.get("event")
            participant_id = args.get("participant")
            self._validate_args(command, args, required={"event", "participant"}, optional=set())
            _require(event_id, "event is required for REMOVE_PARTICIPANT")
            _require(participant_id, "participant id is required for REMOVE_PARTICIPANT")
            participant_service.remove_participant(event_id, participant_id)
            return f"PARTICIPANT {participant_id} REMOVED"

        raise CalendarError(self._unknown_command_message(command))

    @staticmethod
    def _parse_datetime(value: str, field_name: str) -> dt.datetime:
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception as exc:  # pragma: no cover - defensive
            raise CalendarError(f"Invalid datetime format for {field_name}: {value}") from exc
        if parsed.tzinfo is None:
            raise CalendarError(f"Datetime values for {field_name} must include timezone info")
        return parsed

    @staticmethod
    def _parse_date(value: str, field_name: str) -> dt.date:
        try:
            return dt.date.fromisoformat(value)
        except Exception as exc:  # pragma: no cover - defensive
            raise CalendarError(f"Invalid {field_name} date: Expected YYYY-MM-DD") from exc

    @staticmethod
    def _parse_metadata(raw: str) -> Dict[str, object]:
        try:
            parsed = json.loads(raw)
    def _tokenize(line: str) -> List[str]:
        try:
            return shlex.split(line)
        except ValueError as exc:
            raise CalendarError(f"Unable to parse line: {exc}") from exc

    def _parse_args(self, tokens: Iterable[str]) -> Dict[str, str]:
        args: Dict[str, str] = {}
        for token in tokens:
            if "=" not in token:
                raise CalendarError(f"Invalid token '{token}' (expected key=value)")
            key, value = token.split("=", 1)
            if not key:
                raise CalendarError("Argument name cannot be empty")
            value = self._clean_value(value)
            if key in args:
                continue
            args[key] = value
        return args

    def _clean_value(self, value: str) -> str:
        for command in self._COMMANDS:
            marker = value.find(command)
            if marker > 0:
                trimmed = value[:marker]
                if trimmed:
                    return trimmed
        return value

    def _split_list(self, value: str | None) -> List[str]:
        if value is None:
            return []
        return [item for item in value.split(",") if item]

    def _parse_datetime(self, value: str | None, field_name: str) -> dt.datetime:
        _require(value is not None, f"{field_name} is required")
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            raise CalendarError(f"Invalid datetime format for {field_name}: {value}")
        if parsed.tzinfo is None:
            raise CalendarError(f"Datetime values must include timezone offset for {field_name}")
        return parsed

    def _parse_date(self, value: str | None, field_name: str = "occurrence") -> dt.date:
        _require(value is not None, f"{field_name} is required")
        try:
            return dt.datetime.strptime(value, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            raise CalendarError(f"Invalid {field_name} date '{value}'. Expected YYYY-MM-DD")

    def _parse_metadata(self, value: str | None) -> Dict[str, object]:
        _require(value is not None, "metadata is required")
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise CalendarError("metadata must be valid JSON object") from exc
        if not isinstance(parsed, dict):
            raise CalendarError("metadata must be a JSON object mapping keys to values")
        return parsed

    @staticmethod
    def _split_list(raw: str) -> List[str]:
        return [part for part in raw.split(",") if part]

    def _validate_args(self, command: str, args: Dict[str, str], required: set[str], optional: set[str]) -> None:
        if command == "RESCHEDULE_EVENT":
            has_start = "start" in args
            has_end = "end" in args
            if has_start ^ has_end:
                raise CalendarError("RESCHEDULE_EVENT start and end must be provided together")

        missing = sorted(required - set(args))
        if missing:
            missing_msg = ", ".join(missing)
            raise CalendarError(f"{command} missing required arguments: {missing_msg}")

        allowed = required | optional
        unknown = sorted(set(args) - allowed)
        if unknown:
            unknown_msg = ", ".join(unknown)
            raise CalendarError(f"{command} has unknown arguments: {unknown_msg}")

    @staticmethod
    def _parse_args(tokens: List[str]) -> Dict[str, str]:
        args: Dict[str, str] = {}
        for token in tokens:
            if "=" not in token:
                raise CalendarError(f"Invalid token '{token}': expected key=value")
            key, _, value = token.partition("=")
            if not key:
                raise CalendarError("Argument names cannot be empty")
            if key not in args:
                args[key] = value
        return args

    @staticmethod
    def _tokenize(line: str) -> List[str]:
        try:
            return shlex.split(line, posix=True)
        except ValueError as exc:
            raise CalendarError(f"Unable to parse line: {line}") from exc

    def _require_participant_service(self) -> ParticipantService:
        if not self.participant_service:
            raise CalendarError("Participant service is not configured for participant operations")
        return self.participant_service

    @staticmethod
    def _unknown_command_message(command: str) -> str:
        return f"Unknown command '{command}'"
        if any(not isinstance(key, str) for key in parsed.keys()):
            raise CalendarError("metadata keys must be strings")
        return parsed

    def _require_participant_service(self) -> ParticipantService:
        if self.participant_service is None:
            raise CalendarError("Participant service is not configured")
        return self.participant_service

    def _validate_args(
        self,
        command: str,
        args: Mapping[str, str],
        required: set[str],
        optional: set[str],
    ) -> None:
        missing = sorted(required - set(args.keys()))
        if missing:
            raise CalendarError(f"{command} missing required arguments: {', '.join(missing)}")
        unknown = sorted(set(args.keys()) - required - optional)
        if unknown:
            raise CalendarError(f"{command} has unknown arguments: {', '.join(unknown)}")

    def _unknown_command_message(self, command: str) -> str:
        return f"Unknown command: {command}"
