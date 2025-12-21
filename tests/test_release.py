import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict

import pytest

from bigdaisyswarm.release import _fetch_json, main, verify_release


class _StubHandler(BaseHTTPRequestHandler):
    RESPONSES: Dict[str, Dict[str, object]] = {}

    def do_GET(self):  # noqa: N802
        if self.path in self.RESPONSES:
            body = json.dumps(self.RESPONSES[self.path]).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):  # noqa: A003
        return


def _start_server(responses):
    _StubHandler.RESPONSES = responses
    server = HTTPServer(("localhost", 0), _StubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_fetch_json_success():
    server, thread = _start_server({"/ok": {"status": "ok"}})
    try:
        url = f"http://{server.server_address[0]}:{server.server_address[1]}/ok"
        payload = _fetch_json(url)
        assert payload["status"] == "ok"
    finally:
        server.shutdown()
        thread.join()


def test_verify_release_success_path():
    server, thread = _start_server({"/healthz": {"status": "ok"}, "/readyz": {"status": "ok"}})
    try:
        base_url = f"http://{server.server_address[0]}:{server.server_address[1]}"
        result = verify_release(base_url)
        assert result.success is True
        assert result.errors == []
    finally:
        server.shutdown()
        thread.join()


def test_verify_release_failure_path():
    server, thread = _start_server({"/healthz": {"status": "error"}, "/readyz": {}})
    try:
        base_url = f"http://{server.server_address[0]}:{server.server_address[1]}"
        result = verify_release(base_url)
        assert result.success is False
        assert result.errors
    finally:
        server.shutdown()
        thread.join()


def test_main_outputs_json(monkeypatch, capsys):
    server, thread = _start_server({"/healthz": {"status": "ok"}, "/readyz": {"status": "ok"}})
    try:
        base_url = f"http://{server.server_address[0]}:{server.server_address[1]}"
        exit_code = main(["--base-url", base_url, "--timeout", "3.5"])
        output = capsys.readouterr().out
        parsed = json.loads(output)
        assert exit_code == 0
        assert parsed["success"] is True
        assert parsed["health"]["status"] == "ok"
    finally:
        server.shutdown()
        thread.join()


def test_main_passes_timeout(monkeypatch, capsys):
    calls = {}

    class DummyResult:
        def __init__(self):
            self.success = True

        def to_json(self):
            return json.dumps({"success": True})

    def fake_verify(base_url, *, timeout):
        calls["base_url"] = base_url
        calls["timeout"] = timeout
        return DummyResult()

    monkeypatch.setattr("bigdaisyswarm.release.verify_release", fake_verify)
    exit_code = main(["--base-url", "http://example.com", "--timeout", "7"])
    assert exit_code == 0
    assert calls["base_url"] == "http://example.com"
    assert calls["timeout"] == 7
