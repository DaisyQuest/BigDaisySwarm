from __future__ import annotations

import argparse
import datetime as dt
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional
from urllib.parse import urlparse

from .calendar import CalendarError, CalendarService, DSLExecutor, EventService, Participant, ParticipantService
from .health import http_status_code, liveness_check, readiness_check, summarize
from .serialization import hydrate_storage, serialize_storage
from .storage import CalendarStorage, InMemoryCalendarStorage


class ExampleServer:
    """Minimal HTTP server that exposes health checks, DSL execution, and state inspection."""

    def __init__(self, *, storage: Optional[CalendarStorage] = None, seed: bool = True, enable_cors: bool = True):
        self._storage = storage or InMemoryCalendarStorage()
        self._calendar_service = CalendarService(self._storage)
        self._event_service = EventService(self._calendar_service, self._storage)
        self._participant_service = ParticipantService(self._event_service)
        self.executor = DSLExecutor(
            self._calendar_service, self._event_service, participant_service=self._participant_service
        )
        self.enable_cors = enable_cors
        if seed:
            self._seed_if_empty()
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def _seed_if_empty(self) -> None:
        calendars = self._calendar_service.list_calendars()
        if calendars:
            return

        studio = self._calendar_service.create_calendar(
            "Studio Rituals", owners=["studio@example.com", "ops@example.com"], description="Example calendar seed"
        )
        cadence_start = dt.datetime(2025, 1, 6, 15, 0, tzinfo=dt.timezone.utc)
        cadence_end = cadence_start + dt.timedelta(hours=1)
        self._event_service.create_event(
            studio,
            title="Weekly Cadence",
            start=cadence_start,
            end=cadence_end,
            timezone="UTC",
            recurrence="RRULE:FREQ=WEEKLY;BYDAY=MO",
            metadata={"location": "Studio"},
            participants=[
                Participant(id="lead", name="Studio Lead", email="lead@example.com"),
                Participant(id="ops", name="Ops Partner", email="ops@example.com", response="accepted"),
            ],
        )

        showcase_start = dt.datetime(2025, 1, 9, 17, 0, tzinfo=dt.timezone.utc)
        showcase_end = showcase_start + dt.timedelta(hours=2)
        self._event_service.create_event(
            studio,
            title="Showcase",
            start=showcase_start,
            end=showcase_end,
            timezone="UTC",
            metadata={"location": "Gallery", "tags": ["demo", "community"]},
        )

    def _handler(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            def _write_json(self, payload: dict, status: int = 200) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                if server.enable_cors:
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
                    self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,OPTIONS")
                self.end_headers()
                self.wfile.write(body)

            def _dsl_commands(self, body: str) -> str:
                content_type = self.headers.get("Content-Type", "")
                if content_type.startswith("application/json"):
                    try:
                        payload = json.loads(body or "{}")
                    except json.JSONDecodeError as exc:
                        raise CalendarError(f"Invalid JSON payload: {exc.msg}") from exc
                    commands = payload.get("commands")
                    if isinstance(commands, list):
                        return "\n".join(str(entry) for entry in commands)
                    if isinstance(commands, str):
                        return commands
                    return ""
                return body

            def _respond_not_found(self, path: str) -> None:
                self._write_json({"error": "Not found", "path": path}, status=404)

            def do_OPTIONS(self) -> None:  # noqa: N802
                path = urlparse(self.path).path
                if path in {"/dsl", "/healthz", "/readyz", "/state"}:
                    self.send_response(204)
                    if server.enable_cors:
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
                        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,OPTIONS")
                    self.end_headers()
                    return
                self._respond_not_found(path)

            def do_GET(self) -> None:  # noqa: N802
                path = urlparse(self.path).path
                if path == "/healthz":
                    summary = summarize([liveness_check()])
                    self._write_json(summary, status=http_status_code(summary))
                    return

                if path == "/readyz":
                    summary = summarize([liveness_check(), readiness_check(server._storage)])
                    self._write_json(summary, status=http_status_code(summary))
                    return

                if path == "/state":
                    try:
                        snapshot = serialize_storage(server._storage)
                        self._write_json(snapshot)
                    except Exception as exc:
                        self._write_json({"error": f"Failed to read state: {exc}"}, status=500)
                    return

                self._respond_not_found(path)

            def do_POST(self) -> None:  # noqa: N802
                path = urlparse(self.path).path
                if path != "/dsl":
                    self._respond_not_found(path)
                    return

                length = int(self.headers.get("Content-Length") or 0)
                raw_body = self.rfile.read(length).decode("utf-8") if length else ""
                try:
                    commands_block = self._dsl_commands(raw_body)
                except CalendarError as exc:
                    self._write_json({"error": str(exc)}, status=400)
                    return

                if not commands_block.strip():
                    self._write_json({"error": "commands payload required"}, status=400)
                    return

                try:
                    results = server.executor.execute(commands_block.splitlines())
                except CalendarError as exc:
                    self._write_json({"error": str(exc)}, status=400)
                    return

                try:
                    snapshot = serialize_storage(server._storage)
                    self._write_json({"results": results, "state": snapshot})
                except Exception as exc:
                    self._write_json({"results": results, "state": {"error": str(exc)}}, status=500)

            def do_PUT(self) -> None:  # noqa: N802
                path = urlparse(self.path).path
                if path != "/state":
                    self._respond_not_found(path)
                    return

                length = int(self.headers.get("Content-Length") or 0)
                raw_body = self.rfile.read(length).decode("utf-8") if length else ""
                try:
                    payload = json.loads(raw_body or "{}")
                except json.JSONDecodeError as exc:
                    self._write_json({"error": f"Invalid JSON payload: {exc.msg}"}, status=400)
                    return

                try:
                    hydrate_storage(server._storage, payload)
                    snapshot = serialize_storage(server._storage)
                except CalendarError as exc:
                    self._write_json({"error": str(exc)}, status=400)
                    return
                except Exception as exc:
                    self._write_json({"error": f"Failed to persist state: {exc}"}, status=500)
                    return

                self._write_json({"state": snapshot}, status=200)

            def log_message(self, format, *args):  # noqa: A003
                return

        return Handler

    def _create_httpd(self, host: str, port: int) -> ThreadingHTTPServer:
        ThreadingHTTPServer.allow_reuse_address = True
        httpd = ThreadingHTTPServer((host, port), self._handler())
        self._httpd = httpd
        return httpd

    def serve(self, host: str = "0.0.0.0", port: int = 8080) -> None:
        httpd = self._create_httpd(host, port)
        try:
            httpd.serve_forever()
        finally:
            httpd.server_close()

    def serve_in_thread(self, host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
        httpd = self._create_httpd(host, port)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        self._thread = thread
        return httpd

    def shutdown(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    @property
    def server_address(self) -> tuple[str, int]:
        if not self._httpd:
            raise RuntimeError("Server has not been started")
        host, port = self._httpd.server_address
        return str(host), int(port)

    @property
    def base_url(self) -> str:
        host, port = self.server_address
        return f"http://{host}:{port}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run an example HTTP server for the CalendarApp DSL with health probes."
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host/IP to bind")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind")
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="Disable default seed data (useful when loading from external storage).",
    )
    parser.add_argument(
        "--disable-cors",
        action="store_true",
        help="Disable permissive CORS headers. Enabled by default for browser demos.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    server = ExampleServer(seed=not args.no_seed, enable_cors=not args.disable_cors)
    try:
        server.serve(host=args.host, port=args.port)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
