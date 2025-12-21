import json

from bigdaisyswarm.smoke import main, run_smoke_test


def test_run_smoke_test_produces_successful_report():
    report = run_smoke_test()
    assert report.success is True
    assert report.errors == []
    assert any(step.command.startswith("CREATE_CALENDAR") for step in report.steps)
    assert report.state["calendars"]
    assert len(report.state["events"]) == 2
    # One event canceled on the second occurrence; verify override is present.
    canceled_event = next(event for event in report.state["events"] if event["title"] == "Retro")
    assert "2025-05-02" in canceled_event["overrides"]


def test_main_outputs_json(monkeypatch, capsys):
    monkeypatch.setattr("bigdaisyswarm.smoke.run_smoke_test", lambda: run_smoke_test())
    exit_code = main([])
    captured = capsys.readouterr().out
    loaded = json.loads(captured)
    assert exit_code == 0
    assert loaded["success"] is True
    assert loaded["steps"]
