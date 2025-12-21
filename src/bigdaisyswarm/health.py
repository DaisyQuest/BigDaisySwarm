from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, MutableMapping

from .storage import CalendarStorage


@dataclass(frozen=True)
class HealthCheckResult:
    """Represents the outcome of a single health probe."""

    name: str
    ok: bool
    details: Mapping[str, object]


def liveness_check() -> HealthCheckResult:
    """Always succeeds; used to prove the process is running."""
    return HealthCheckResult(name="liveness", ok=True, details={})


def readiness_check(storage: CalendarStorage) -> HealthCheckResult:
    """Validate that required dependencies are reachable."""
    try:
        calendars = storage.list_calendars()
        count = len(calendars)
        return HealthCheckResult(name="readiness", ok=True, details={"calendars": count})
    except Exception as exc:  # pragma: no cover - exercised via tests that inspect details
        return HealthCheckResult(name="readiness", ok=False, details={"error": str(exc)})


def summarize(checks: Iterable[HealthCheckResult]) -> MutableMapping[str, object]:
    """Summarize multiple checks for easy HTTP responses."""
    check_list = [
        {"name": check.name, "ok": check.ok, "details": dict(check.details)} for check in checks
    ]
    status = "ok" if all(check["ok"] for check in check_list) else "error"
    return {"status": status, "checks": check_list}


def http_status_code(summary: Mapping[str, object]) -> int:
    """Return 200 for healthy responses; 503 otherwise."""
    return 200 if summary.get("status") == "ok" else 503
