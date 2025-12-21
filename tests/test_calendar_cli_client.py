import datetime as dt
import json
from pathlib import Path

import pytest

from bigdaisyswarm import CalendarError, Event, InMemoryCalendarStorage, Participant
from bigdaisyswarm.calendar import OccurrenceOverride
from calendar_cli_client import cli
from calendar_cli_client.storage import dump_storage, load_storage


def seed_storage() -> InMemoryCalendarStorage:
    storage = InMemoryCalendarStorage()
    storage.save_calendar({"id": "work", "name": "Work", "owners": ["alice@example.com"], "description": ""})
    return storage


def test_cli_run_updates_storage_and_prints_state(tmp_path, capsys):
    storage_path = tmp_path / "state.json"
    commands_path = tmp_path / "commands.dsl"

    storage = seed_storage()
    event = Event(
        id="evt-seed",
        calendar_id="work",
        title="Planning",
        start=dt.datetime(2025, 1, 1, 10, 0, tzinfo=dt.timezone.utc),
        end=dt.datetime(2025, 1, 1, 11, 0, tzinfo=dt.timezone.utc),
        timezone="UTC",
    )
    storage.save_event(event)
    dump_storage(storage, storage_path)

    commands_path.write_text(
        "\n".join(
            [
                "ADD_PARTICIPANT event=evt-seed participant=alice name=Alice email=alice@example.com response=accepted",
                "CANCEL_EVENT event=evt-seed occurrence=2025-01-02",
                "LIST_EVENTS calendar=work",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = cli.main(
        ["run", "--storage", str(storage_path), "--commands", str(commands_path), "--print-state"]
    )
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "PARTICIPANT alice ADDED" in captured.out
    assert "CANCELED evt-seed" in captured.out
    assert "EVENTS evt-seed" in captured.out

    # Extract the trailing JSON block that represents state.
    json_start = captured.out.index("{")
    state = json.loads(captured.out[json_start:])
    assert state["calendars"][0]["id"] == "work"
    assert state["events"][0]["participants"]["alice"]["response"] == "accepted"
    assert "2025-01-02" in state["events"][0]["overrides"]

    reloaded = load_storage(storage_path)
    event_after = reloaded.get_event("evt-seed")
    assert event_after is not None
    assert "alice" in event_after.participants
    assert dt.date(2025, 1, 2) in event_after.canceled_occurrences


def test_cli_run_handles_errors_without_overwriting_storage(tmp_path, capsys):
    storage_path = tmp_path / "state.json"
    commands_path = tmp_path / "commands.dsl"

    storage = seed_storage()
    dump_storage(storage, storage_path)
    original_text = storage_path.read_text(encoding="utf-8")

    commands_path.write_text(
        "CREATE_EVENT calendar=work title=Broken end=2025-01-01T11:00Z timezone=UTC\n",
        encoding="utf-8",
    )

    exit_code = cli.main(["run", "--storage", str(storage_path), "--commands", str(commands_path)])
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "missing required arguments" in captured.err
    assert storage_path.read_text(encoding="utf-8") == original_text


def test_cli_show_state_supports_empty_and_invalid_storage(tmp_path, capsys):
    exit_code = cli.main(["show-state"])
    assert exit_code == 0
    empty_output = json.loads(capsys.readouterr().out)
    assert empty_output == {"calendars": [], "events": []}

    bad_path = tmp_path / "broken.json"
    bad_path.write_text("{not-json", encoding="utf-8")
    exit_code = cli.main(["show-state", "--storage", str(bad_path)])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "invalid JSON" in captured.err


def test_storage_round_trip_preserves_overrides(tmp_path):
    storage = seed_storage()
    event = Event(
        id="evt-round",
        calendar_id="work",
        title="Round Trip",
        start=dt.datetime(2025, 1, 3, 9, 0, tzinfo=dt.timezone.utc),
        end=dt.datetime(2025, 1, 3, 10, 0, tzinfo=dt.timezone.utc),
        timezone="UTC",
        metadata={"team": "core"},
        overrides={
            dt.date(2025, 1, 4): OccurrenceOverride(
                occurrence_date=dt.date(2025, 1, 4),
                start=dt.datetime(2025, 1, 4, 12, 0, tzinfo=dt.timezone.utc),
                end=dt.datetime(2025, 1, 4, 13, 0, tzinfo=dt.timezone.utc),
                canceled=False,
            )
        },
        participants={"bob": Participant(id="bob", name="Bob", email="bob@example.com", response="accepted")},
    )
    storage.save_event(event)

    storage_path = tmp_path / "round.json"
    dump_storage(storage, storage_path)

    reloaded = load_storage(storage_path)
    reloaded_event = reloaded.get_event("evt-round")
    assert reloaded_event is not None
    assert reloaded_event.metadata["team"] == "core"
    assert dt.date(2025, 1, 4) in reloaded_event.overrides
    override = reloaded_event.overrides[dt.date(2025, 1, 4)]
    assert override.start.hour == 12
    assert "bob" in reloaded_event.participants


def test_load_storage_rejects_invalid_override_payload(tmp_path):
    payload = {
        "calendars": [{"id": "work", "name": "Work", "owners": ["alice@example.com"], "description": ""}],
        "events": [
            {
                "id": "evt-bad",
                "calendar_id": "work",
                "title": "Broken",
                "start": "2025-01-01T10:00:00+00:00",
                "end": "2025-01-01T11:00:00+00:00",
                "timezone": "UTC",
                "overrides": {"2025-01-02": {"start": "2025-01-02T12:00:00+00:00"}},
            }
        ],
    }
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with pytest.raises(CalendarError):
        load_storage(path)
