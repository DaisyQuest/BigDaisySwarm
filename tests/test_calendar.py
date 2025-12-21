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

    results = executor.execute(["CREATE_CALENDAR name=Work owners=alice@example.com,bob@example.com"])
    calendar_id = results[0].split()[1]
    event_result = executor.execute(
        [f"CREATE_EVENT calendar={calendar_id} title=Kickoff start=2025-01-01T10:00Z end=2025-01-01T11:00Z timezone=UTC"]
    )
    assert event_result[0].startswith("EVENT")

    with pytest.raises(CalendarError):
        executor.execute(["CANCEL_EVENT"])  # missing args

    with pytest.raises(CalendarError):
        executor._execute_line("UNKNOWN_CMD foo=bar")


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
    assert "Invalid datetime format" in str(excinfo.value)

    calendar_id = calendar_service.create_calendar("Work", owners=["alice@example.com"])
    with pytest.raises(CalendarError) as excinfo:
        executor.execute([f"CANCEL_EVENT event={calendar_id} occurrence=13-2025-01"])
    assert "Invalid occurrence date" in str(excinfo.value)
