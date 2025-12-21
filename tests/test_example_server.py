import json
import urllib.error
import urllib.request

import pytest

from bigdaisyswarm.example_server import ExampleServer
from bigdaisyswarm.storage import CalendarStorage


def _fetch(url: str, *, method: str = "GET", data: bytes | None = None, headers: dict | None = None):
    request = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, response.read(), response.headers
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), exc.headers


def _fetch_json(url: str, *, method: str = "GET", data: bytes | None = None, headers: dict | None = None):
    status, body, headers = _fetch(url, method=method, data=data, headers=headers)
    payload = json.loads(body.decode("utf-8")) if body else {}
    return status, payload, headers


class BrokenStorage(CalendarStorage):
    def save_calendar(self, calendar):
        raise RuntimeError("unimplemented")

    def get_calendar(self, calendar_id):
        return None

    def list_calendars(self, owner=None):
        raise RuntimeError("storage offline")

    def save_event(self, event):
        raise RuntimeError("unimplemented")

    def get_event(self, event_id):
        return None

    def list_events(self, calendar_id):
        return []


def test_health_and_ready_endpoints_report_ok():
    server = ExampleServer()
    server.serve_in_thread()
    try:
        health_status, health_payload, _ = _fetch_json(f"{server.base_url}/healthz")
        assert health_status == 200
        assert health_payload["status"] == "ok"

        ready_status, ready_payload, _ = _fetch_json(f"{server.base_url}/readyz")
        assert ready_status == 200
        assert ready_payload["status"] == "ok"
        calendar_detail = next(check for check in ready_payload["checks"] if check["name"] == "readiness")
        assert calendar_detail["details"]["calendars"] >= 1
    finally:
        server.shutdown()


def test_ready_endpoint_surfaces_storage_failures():
    server = ExampleServer(storage=BrokenStorage(), seed=False)
    server.serve_in_thread()
    try:
        status, payload, _ = _fetch_json(f"{server.base_url}/readyz")
        assert status == 503
        assert payload["status"] == "error"
        readiness = next(check for check in payload["checks"] if check["name"] == "readiness")
        assert "storage offline" in readiness["details"]["error"]
    finally:
        server.shutdown()


def test_dsl_endpoint_executes_and_returns_state():
    server = ExampleServer()
    server.serve_in_thread()
    try:
        initial_state_status, initial_state, _ = _fetch_json(f"{server.base_url}/state")
        assert initial_state_status == 200
        seeded_calendar_id = initial_state["calendars"][0]["id"]

        commands = [
            "CREATE_CALENDAR name=PublicDemo owners=demo@example.com",
            f"CREATE_EVENT calendar={seeded_calendar_id} title=Webinar start=2025-02-01T16:00Z end=2025-02-01T17:00Z timezone=UTC",
            f"LIST_EVENTS calendar={seeded_calendar_id}",
        ]

        body = json.dumps({"commands": commands}).encode("utf-8")
        status, payload, headers = _fetch_json(
            f"{server.base_url}/dsl", method="POST", data=body, headers={"Content-Type": "application/json"}
        )
        assert status == 200
        assert headers.get("Access-Control-Allow-Origin") == "*"
        assert payload["results"][0].startswith("CALENDAR")
        assert payload["results"][-1].startswith("EVENTS")

        calendar_names = {calendar["name"] for calendar in payload["state"]["calendars"]}
        assert "PublicDemo" in calendar_names
    finally:
        server.shutdown()


def test_dsl_endpoint_reports_errors_and_invalid_json():
    server = ExampleServer()
    server.serve_in_thread()
    try:
        status, payload, _ = _fetch_json(
            f"{server.base_url}/dsl",
            method="POST",
            data=b"{not-json",
            headers={"Content-Type": "application/json"},
        )
        assert status == 400
        assert "Invalid JSON payload" in payload["error"]

        status, payload, _ = _fetch_json(
            f"{server.base_url}/dsl", method="POST", data=b"", headers={"Content-Type": "text/plain"}
        )
        assert status == 400
        assert "commands payload required" in payload["error"]
    finally:
        server.shutdown()


def test_cors_and_options_requests():
    server = ExampleServer(enable_cors=True)
    server.serve_in_thread()
    try:
        status, body, headers = _fetch(f"{server.base_url}/dsl", method="OPTIONS")
        assert status == 204
        assert headers.get("Access-Control-Allow-Origin") == "*"
        assert body == b""

        status, _, headers = _fetch_json(
            f"{server.base_url}/healthz", headers={"Origin": "https://example.com"}
        )
        assert status == 200
        assert headers.get("Access-Control-Allow-Origin") == "*"
    finally:
        server.shutdown()


def test_cors_can_be_disabled():
    server = ExampleServer(enable_cors=False)
    server.serve_in_thread()
    try:
        status, _, headers = _fetch_json(f"{server.base_url}/healthz")
        assert status == 200
        assert headers.get("Access-Control-Allow-Origin") is None
    finally:
        server.shutdown()
