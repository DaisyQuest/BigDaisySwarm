from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass
from typing import Iterable, Mapping, MutableMapping, Sequence

from .calendar import CalendarService, DSLExecutor, EventService, Participant, ParticipantService
from .storage import CalendarStorage, InMemoryCalendarStorage


@dataclass(frozen=True)
class SmokeStep:
    """Represents a single smoke-test command and its result."""

    command: str
    result: str


@dataclass(frozen=True)
class SmokeReport:
    """Container for smoke-test outputs."""

    success: bool
    steps: Sequence[SmokeStep]
    state: Mapping[str, object]
    errors: Sequence[str]

    def to_json(self) -> str:
        return json.dumps(
            {
                "success": self.success,
                "steps": [asdict(step) for step in self.steps],
                "state": self.state,
                "errors": list(self.errors),
            },
            indent=2,
        )


def _serialize_state(storage: CalendarStorage) -> MutableMapping[str, object]:
    calendars = storage.list_calendars()
    events = []
    for event in storage.list_events(calendars[0]["id"] if calendars else ""):
        overrides = {
            date.isoformat(): {
                "start": override.start.isoformat() if override.start else None,
                "end": override.end.isoformat() if override.end else None,
                "canceled": override.canceled,
            }
            for date, override in event.overrides.items()
        }
        events.append(
            {
                "id": event.id,
                "title": event.title,
                "start": event.start.isoformat(),
                "end": event.end.isoformat(),
                "participants": {pid: participant.email for pid, participant in event.participants.items()},
                "overrides": overrides,
            }
        )
    return {"calendars": calendars, "events": events}


def run_smoke_test(storage: CalendarStorage | None = None) -> SmokeReport:
    """Execute a staging-style smoke test using the in-memory services."""
    storage = storage or InMemoryCalendarStorage()
    calendar_service = CalendarService(storage)
    event_service = EventService(calendar_service, storage)
    participant_service = ParticipantService(event_service)
    executor = DSLExecutor(calendar_service, event_service, participant_service=participant_service)

    steps: list[SmokeStep] = []
    errors: list[str] = []

    commands: Iterable[str] = [
        'CREATE_CALENDAR name="Smoke Calendar" owners=smoke@example.com',
        (
            "CREATE_EVENT calendar={calendar} title=Planning start=2025-05-01T09:00Z end=2025-05-01T10:00Z "
            "timezone=UTC participants='[{\"id\":\"alice\",\"name\":\"Alice\",\"email\":\"alice@example.com\"}]'"
        ),
        "CREATE_EVENT calendar={calendar} title=Retro start=2025-05-02T09:00Z end=2025-05-02T10:00Z timezone=UTC",
        "LIST_EVENTS calendar={calendar}",
        "CANCEL_EVENT event={event2} occurrence=2025-05-02",
        "LIST_EVENTS calendar={calendar} range_start=2025-05-02T00:00Z range_end=2025-05-03T00:00Z",
    ]

    calendar_id = ""
    first_event = ""
    second_event = ""

    for raw in commands:
        try:
            formatted = raw
            if "{calendar}" in raw and calendar_id:
                formatted = formatted.replace("{calendar}", calendar_id)
            if "{event1}" in raw and first_event:
                formatted = formatted.replace("{event1}", first_event)
            if "{event2}" in raw and second_event:
                formatted = formatted.replace("{event2}", second_event)

            results = executor.execute([formatted])
            steps.append(SmokeStep(command=formatted, result=results[0]))

            if not calendar_id and results and results[0].startswith("CALENDAR "):
                calendar_id = results[0].split()[1]
            if results and results[0].startswith("EVENT "):
                if not first_event:
                    first_event = results[0].split()[1]
                elif not second_event:
                    second_event = results[0].split()[1]
        except Exception as exc:  # pragma: no cover - captured in report for tests
            errors.append(f"{raw}: {exc}")

    success = not errors
    state = _serialize_state(storage)
    return SmokeReport(success=success, steps=steps, state=state, errors=errors)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the smoke test and print a JSON report."""
    report = run_smoke_test()
    print(report.to_json())
    return 0 if report.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
