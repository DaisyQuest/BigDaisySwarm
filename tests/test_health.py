import pytest

from bigdaisyswarm.health import HealthCheckResult, http_status_code, liveness_check, readiness_check, summarize
from bigdaisyswarm.storage import CalendarStorage, InMemoryCalendarStorage


class FailingStorage(CalendarStorage):
    def save_calendar(self, calendar):
        raise RuntimeError("unimplemented")

    def get_calendar(self, calendar_id):
        raise RuntimeError("unimplemented")

    def list_calendars(self, owner=None):
        raise ValueError("boom")

    def save_event(self, event):
        raise RuntimeError("unimplemented")

    def get_event(self, event_id):
        raise RuntimeError("unimplemented")

    def list_events(self, calendar_id):
        raise RuntimeError("unimplemented")


def test_liveness_always_ok():
    result = liveness_check()
    assert isinstance(result, HealthCheckResult)
    assert result.name == "liveness"
    assert result.ok is True
    assert result.details == {}


def test_readiness_ok_and_counts_calendars():
    storage = InMemoryCalendarStorage()
    result = readiness_check(storage)
    assert result.ok is True
    assert result.details["calendars"] == 0


def test_readiness_reports_errors():
    storage = FailingStorage()
    result = readiness_check(storage)
    assert result.ok is False
    assert "boom" in result.details["error"]


def test_summarize_and_http_status_code():
    healthy = summarize([liveness_check(), readiness_check(InMemoryCalendarStorage())])
    assert healthy["status"] == "ok"
    assert http_status_code(healthy) == 200

    unhealthy = summarize([liveness_check(), readiness_check(FailingStorage())])
    assert unhealthy["status"] == "error"
    assert http_status_code(unhealthy) == 503
    assert any(check["ok"] is False for check in unhealthy["checks"])
