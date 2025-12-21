import datetime as dt

import pytest

from bigdaisyswarm.calendar import (
    CalendarError,
    CalendarService,
    DSLExecutor,
    EventService,
    Participant,
    ParticipantService,
)


def make_services():
    calendar_service = CalendarService()
    event_service = EventService(calendar_service)
    participant_service = ParticipantService(event_service)
    calendar_id = calendar_service.create_calendar("Work", owners=["alice@example.com"])
    return calendar_service, event_service, participant_service, calendar_id


def test_create_and_list_calendar():
    calendar_service = CalendarService()
    calendar_id = calendar_service.create_calendar("Work", owners=["alice@example.com"], description="Team calendar")
    calendars = calendar_service.list_calendars()
    assert calendars[0]["id"] == calendar_id
    assert calendars[0]["description"] == "Team calendar"
    owner_calendars = calendar_service.list_calendars(owner="alice@example.com")
    assert len(owner_calendars) == 1
    assert owner_calendars[0]["id"] == calendar_id


def test_create_event_validates_inputs():
    _, event_service, _, calendar_id = make_services()
    start = dt.datetime(2025, 1, 1, 10, 0, tzinfo=dt.timezone.utc)
    end = dt.datetime(2025, 1, 1, 11, 0, tzinfo=dt.timezone.utc)

    event_id = event_service.create_event(calendar_id, "Standup", start, end, timezone="UTC")
    events = event_service.list_events(calendar_id)
    assert events[0].id == event_id
    assert events[0].title == "Standup"

    with pytest.raises(CalendarError):
        event_service.create_event(calendar_id, "", start, end, timezone="UTC")

    with pytest.raises(CalendarError):
        event_service.create_event(calendar_id, "Bad", end, start, timezone="UTC")

    naive_start = dt.datetime(2025, 1, 1, 10, 0)
    with pytest.raises(CalendarError):
        event_service.create_event(calendar_id, "Bad", naive_start, end, timezone="UTC")

    with pytest.raises(CalendarError):
        event_service.create_event(calendar_id, "Bad", "not-a-datetime", end, timezone="UTC")  # type: ignore[arg-type]

    with pytest.raises(CalendarError):
        event_service.create_event(calendar_id, "Bad", start, end, timezone="UTC", metadata="metadata")  # type: ignore[arg-type]


def test_update_and_cancel_event():
    _, event_service, _, calendar_id = make_services()
    start = dt.datetime(2025, 1, 1, 10, 0, tzinfo=dt.timezone.utc)
    end = dt.datetime(2025, 1, 1, 11, 0, tzinfo=dt.timezone.utc)
    event_id = event_service.create_event(calendar_id, "Standup", start, end, timezone="UTC")

    new_end = dt.datetime(2025, 1, 1, 12, 0, tzinfo=dt.timezone.utc)
    event_service.update_event(event_id, end=new_end, metadata={"note": "extended"})
    event = event_service.list_events(calendar_id)[0]
    assert event.end == new_end
    assert event.metadata["note"] == "extended"

    with pytest.raises(CalendarError):
        event_service.update_event(event_id, metadata="not-a-mapping")

    event_service.cancel_event(event_id)
    assert event.canceled is True

    event_service.cancel_event(event_id, occurrence=dt.date(2025, 1, 2))
    assert dt.date(2025, 1, 2) in event.canceled_occurrences


def test_event_range_filtering():
    _, event_service, _, calendar_id = make_services()
    start = dt.datetime(2025, 1, 1, 10, 0, tzinfo=dt.timezone.utc)
    end = dt.datetime(2025, 1, 1, 11, 0, tzinfo=dt.timezone.utc)
    event_service.create_event(calendar_id, "Standup", start, end, timezone="UTC")
    event_service.create_event(
        calendar_id,
        "Retro",
        start + dt.timedelta(days=10),
        end + dt.timedelta(days=10),
        timezone="UTC",
    )

    window = event_service.list_events(
        calendar_id,
        range_start=start + dt.timedelta(days=9),
        range_end=end + dt.timedelta(days=11),
    )
    assert len(window) == 1
    assert window[0].title == "Retro"

    start_only = event_service.list_events(calendar_id, range_start=start - dt.timedelta(hours=1))
    assert len(start_only) == 2

    end_only = event_service.list_events(calendar_id, range_end=end - dt.timedelta(minutes=30))
    assert len(end_only) == 1


def test_participant_operations():
    _, event_service, participant_service, calendar_id = make_services()
    start = dt.datetime(2025, 1, 1, 10, 0, tzinfo=dt.timezone.utc)
    end = dt.datetime(2025, 1, 1, 11, 0, tzinfo=dt.timezone.utc)
    event_id = event_service.create_event(calendar_id, "Standup", start, end, timezone="UTC")

    participant = Participant(id="alice", name="Alice", email="alice@example.com")
    participant_service.add_participant(event_id, participant)
    event = event_service.list_events(calendar_id)[0]
    assert "alice" in event.participants

    participant_service.update_participant(event_id, "alice", response="accepted")
    assert event.participants["alice"].response == "accepted"

    participant_service.remove_participant(event_id, "alice")
    assert "alice" not in event.participants

    with pytest.raises(CalendarError):
        participant_service.update_participant(event_id, "missing", response="accepted")

    with pytest.raises(CalendarError):
        participant_service.add_participant(
            event_id, Participant(id="bob", name="Bob", email="")
        )


def test_dsl_executor_success_and_errors():
    calendar_service = CalendarService()
    event_service = EventService(calendar_service)
    executor = DSLExecutor(calendar_service, event_service)

    results = executor.execute(['CREATE_CALENDAR name="Team Calendar" owners=alice@example.com,bob@example.com'])
    calendar_id = results[0].split()[1]
    list_result = executor.execute([f"LIST_CALENDARS owner=bob@example.com"])
    assert calendar_id in list_result[0]

    event_result = executor.execute(
        [
            f'CREATE_EVENT calendar={calendar_id} title="Kickoff Meeting" start=2025-01-01T10:00Z '
            f'end=2025-01-01T11:00Z timezone=UTC recurrence="RRULE:FREQ=DAILY;COUNT=3" metadata=\'{{\"team\":\"core\"}}\''
        ]
    )
    event_id = event_result[0].split()[1]
    assert event_service.list_events(calendar_id)[0].recurrence == "RRULE:FREQ=DAILY;COUNT=3"
    assert event_service.list_events(calendar_id)[0].metadata["team"] == "core"

    # Create a second event so LIST_EVENTS filtering has something to omit.
    executor.execute(
        [
            f"CREATE_EVENT calendar={calendar_id} title=Retro start=2025-01-10T10:00Z "
            f"end=2025-01-10T11:00Z timezone=UTC"
        ]
    )

    filtered = executor.execute(
        [
            f"LIST_EVENTS calendar={calendar_id} range_start=2025-01-01T00:00Z range_end=2025-01-02T00:00Z",
        ]
    )
    assert f"EVENTS {event_id}" == filtered[0]

    update_result = executor.execute(
        [
            f'UPDATE_EVENT event={event_id} title="Updated Kickoff" metadata=\'{{\"status\":\"final\"}}\' '
            f"recurrence=RRULE:FREQ=WEEKLY;COUNT=2 end=2025-01-01T12:00Z"
        ]
    )
    assert update_result[0] == f"EVENT {event_id} UPDATED"
    updated_event = event_service.list_events(calendar_id)[0]
    assert updated_event.title == "Updated Kickoff"
    assert updated_event.metadata["status"] == "final"
    assert updated_event.recurrence == "RRULE:FREQ=WEEKLY;COUNT=2"
    assert updated_event.end == dt.datetime(2025, 1, 1, 12, 0, tzinfo=dt.timezone.utc)

    cancel_result = executor.execute([f"CANCEL_EVENT event={event_id} occurrence=2025-01-02"])
    assert cancel_result[0] == f"CANCELED {event_id}"
    assert dt.date(2025, 1, 2) in updated_event.canceled_occurrences

    with pytest.raises(CalendarError) as excinfo:
        executor.execute([f"CREATE_EVENT calendar={calendar_id} title=MissingArgs end=2025-01-01T11:00Z timezone=UTC"])
    assert "missing required arguments" in str(excinfo.value)
    assert "Line 1" in str(excinfo.value)

    with pytest.raises(CalendarError) as excinfo:
        executor.execute([f"CREATE_EVENT calendar={calendar_id} title=Bad start=not-a-date end=2025-01-01T11:00Z timezone=UTC"])
    assert "Invalid datetime format" in str(excinfo.value)
    assert "Line 1" in str(excinfo.value)

    with pytest.raises(CalendarError) as excinfo:
        executor._execute_line("UNKNOWN_CMD foo=bar")
    assert "Unknown command" in str(excinfo.value)


def test_calendar_validation_errors():
    calendar_service = CalendarService()
    with pytest.raises(CalendarError):
        calendar_service.create_calendar("", owners=[])

    # Calendar existence checks
    event_service = EventService(calendar_service)
    with pytest.raises(CalendarError):
        event_service.list_events("missing")

    with pytest.raises(CalendarError):
        event_service.create_event(
            "missing",
            "title",
            dt.datetime.now(tz=dt.timezone.utc),
            dt.datetime.now(tz=dt.timezone.utc) + dt.timedelta(hours=1),
            timezone="UTC",
        )


def test_list_events_rejects_invalid_range():
    _, event_service, _, calendar_id = make_services()
    start = dt.datetime(2025, 1, 1, 10, 0, tzinfo=dt.timezone.utc)
    end = dt.datetime(2025, 1, 1, 11, 0, tzinfo=dt.timezone.utc)
    event_service.create_event(calendar_id, "Standup", start, end, timezone="UTC")

    with pytest.raises(CalendarError) as excinfo:
        event_service.list_events(
            calendar_id,
            range_start=end + dt.timedelta(hours=1),
            range_end=start - dt.timedelta(hours=1),
        )

    assert "range_start must be before range_end" in str(excinfo.value)


def test_dsl_executor_reports_parsing_errors():
    calendar_service = CalendarService()
    event_service = EventService(calendar_service)
    executor = DSLExecutor(calendar_service, event_service)

    with pytest.raises(CalendarError) as excinfo:
        executor.execute(["CREATE_EVENT calendar=missing title=Bad start=not-a-date end=2025-01-01T11:00Z timezone=UTC"])
    assert "Line 1" in str(excinfo.value)
    assert "Invalid datetime format for start" in str(excinfo.value)

    calendar_id = calendar_service.create_calendar("Work", owners=["alice@example.com"])
    with pytest.raises(CalendarError) as excinfo:
        executor.execute([f"CANCEL_EVENT event={calendar_id} occurrence=13-2025-01"])
    assert "Expected YYYY-MM-DD" in str(excinfo.value)

    with pytest.raises(CalendarError) as excinfo:
        executor.execute([f"CREATE_EVENT calendar={calendar_id} title=Bad end=2025-01-01T11:00Z timezone=UTC"])
    assert "missing required arguments: start" in str(excinfo.value)

    with pytest.raises(CalendarError) as excinfo:
        executor.execute([f"UPDATE_EVENT event={calendar_id}"])
    assert "requires a field to update" in str(excinfo.value)

    with pytest.raises(CalendarError) as excinfo:
        executor.execute([f"CREATE_EVENT calendar={calendar_id} title=Bad start=2025-01-01T10:00Z end=2025-01-01T11:00Z extra=value"])
    assert "unknown arguments" in str(excinfo.value)

    with pytest.raises(CalendarError) as excinfo:
        executor.execute(['CREATE_CALENDAR name=Work invalid'])
    assert "Invalid token" in str(excinfo.value)
    assert "Line 1" in str(excinfo.value)

    with pytest.raises(CalendarError) as excinfo:
        executor.execute(['CREATE_CALENDAR name="Missing end quote owners=alice@example.com'])
    assert "Unable to parse line" in str(excinfo.value)


def test_dsl_executor_participant_commands():
    calendar_service = CalendarService()
    event_service = EventService(calendar_service)
    participant_service = ParticipantService(event_service)
    executor = DSLExecutor(calendar_service, event_service, participant_service=participant_service)

    results = executor.execute(["CREATE_CALENDAR name=Work owners=alice@example.com"])
    calendar_id = results[0].split()[1]
    event_result = executor.execute(
        [f"CREATE_EVENT calendar={calendar_id} title=Kickoff start=2025-01-01T10:00Z end=2025-01-01T11:00Z timezone=UTC"]
    )
    event_id = event_result[0].split()[1]

    add_result = executor.execute(
        [f"ADD_PARTICIPANT event={event_id} participant=alice name=Alice email=alice@example.com response=accepted"]
    )
    assert add_result[0] == "PARTICIPANT alice ADDED"

    update_result = executor.execute(
        [f"UPDATE_PARTICIPANT event={event_id} participant=alice response=declined"]
    )
    assert update_result[0] == "PARTICIPANT alice UPDATED"

    remove_result = executor.execute(
        [f"REMOVE_PARTICIPANT event={event_id} participant=alice"]
    )
    assert remove_result[0] == "PARTICIPANT alice REMOVED"
    assert "alice" not in event_service.list_events(calendar_id)[0].participants

    with pytest.raises(CalendarError) as excinfo:
        executor.execute(["ADD_PARTICIPANT participant=missing name=Nope email=nope@example.com"])
    assert "missing required arguments" in str(excinfo.value)


def test_dsl_executor_rejects_metadata_and_participant_misuse():
    calendar_service = CalendarService()
    event_service = EventService(calendar_service)
    executor = DSLExecutor(calendar_service, event_service, participant_service=None)

    calendar_id = calendar_service.create_calendar("Work", owners=["alice@example.com"])
    event_id = event_service.create_event(
        calendar_id,
        "Standalone",
        dt.datetime(2025, 1, 1, 10, 0, tzinfo=dt.timezone.utc),
        dt.datetime(2025, 1, 1, 11, 0, tzinfo=dt.timezone.utc),
        timezone="UTC",
    )

    with pytest.raises(CalendarError) as excinfo:
        executor.execute(
            [
                f"CREATE_EVENT calendar={calendar_id} title=Bad metadata=not-json start=2025-02-01T10:00Z end=2025-02-01T11:00Z timezone=UTC"
            ]
        )
    assert "metadata must be valid JSON object" in str(excinfo.value)
    assert "Line 1" in str(excinfo.value)

    with pytest.raises(CalendarError) as excinfo:
        executor.execute(
            [
                f"CREATE_EVENT calendar={calendar_id} title=Bad metadata=5 start=2025-02-02T10:00Z end=2025-02-02T11:00Z timezone=UTC"
            ]
        )
    assert "metadata must be a JSON object mapping keys to values" in str(excinfo.value)

    with pytest.raises(CalendarError) as excinfo:
        executor.execute([f"ADD_PARTICIPANT event={event_id} participant=alice name=Alice email=alice@example.com"])
    assert "Participant service is not configured" in str(excinfo.value)
    assert "Line 1" in str(excinfo.value)
