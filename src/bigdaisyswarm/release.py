from __future__ import annotations

import argparse
import json
import urllib.request
from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ReleaseVerificationResult:
    success: bool
    health_status: Mapping[str, object]
    ready_status: Mapping[str, object]
    errors: Sequence[str]

    def to_json(self) -> str:
        return json.dumps(
            {
                "success": self.success,
                "health": self.health_status,
                "ready": self.ready_status,
                "errors": list(self.errors),
            },
            indent=2,
        )


def _fetch_json(url: str, *, timeout: float = 5.0) -> Mapping[str, object]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        payload = response.read()
        try:
            return json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError as exc:  # pragma: no cover - validated via failure path
            raise ValueError(f"Invalid JSON from {url}: {exc}") from exc


def verify_release(base_url: str, *, timeout: float = 5.0) -> ReleaseVerificationResult:
    errors: list[str] = []

    def check(endpoint: str) -> Mapping[str, object]:
        url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        try:
            return _fetch_json(url, timeout=timeout)
        except Exception as exc:  # pragma: no cover - exercised via tests that assert errors
            errors.append(f"{endpoint}: {exc}")
            return {}

    health_status = check("healthz")
    ready_status = check("readyz")

    def ok(status: Mapping[str, object]) -> bool:
        return bool(status) and status.get("status") == "ok"

    if not ok(health_status):
        errors.append("healthz returned non-ok status")
    if not ok(ready_status):
        errors.append("readyz returned non-ok status")

    success = not errors
    return ReleaseVerificationResult(
        success=success,
        health_status=health_status,
        ready_status=ready_status,
        errors=errors,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify production readiness via health endpoints.")
    parser.add_argument("--base-url", required=True, help="Base URL of the deployment (e.g., https://app.azurewebsites.net)")
    parser.add_argument("--timeout", type=float, default=5.0, help="Timeout in seconds for each endpoint request (default: 5)")
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = verify_release(args.base_url, timeout=args.timeout)
    print(result.to_json())
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
