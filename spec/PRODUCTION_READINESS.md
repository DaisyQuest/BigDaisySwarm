# Production Readiness Guide

This guide lists the checks required before promoting the CalendarApp backend to production on Azure App Service. It complements `DEPLOYMENT_SPEC.md`, `DEPLOYMENT_GUIDE.md`, and `SECURITY_AND_IDENTITY.md`.

## Service-level objectives (SLOs)
- **Availability:** 99.9% monthly for the API.
- **Latency:** p95 < 250ms for `/healthz`, p95 < 500ms for CRUD and DSL endpoints under normal load.
- **Error budget policy:** pause feature rollouts if more than 20% of the monthly error budget is consumed in any 7-day window.

## Testing surface
- **Staging slot smoke tests (blocking):**
  - `curl -f https://<app>-staging.azurewebsites.net/healthz`
  - `curl -f https://<app>-staging.azurewebsites.net/readyz`
  - DSL script that creates a calendar, creates two events (one with participants), lists events, cancels an occurrence, and verifies JSON responses.
  - Run `PYTHONPATH=src python -m bigdaisyswarm.smoke` against staging to capture a JSON report; store the report with the release artifacts.
- **Release verification (blocking):**
  - `PYTHONPATH=src python -m bigdaisyswarm.release --base-url https://<app>-staging.azurewebsites.net`
  - Requires `status=ok` from both `/healthz` and `/readyz`; failure blocks slot swap.
- **Load tests (non-blocking but required each release branch):**
  - 10 req/s for 10 minutes on CRUD endpoints; verify p95 latency < 500ms and error rate < 0.1%.
  - Token validation: mix valid/expired tokens to ensure 401/403 paths are stable.
- **Chaos drills (monthly):**
  - Database failover or restart of Azure Flexible Server; ensure readiness reflects DB unavailability and recovers automatically.
  - Slot swap rollback: swap staging -> production -> staging and confirm traffic recovery.

## Preflight checklist
- Secrets fetched via Managed Identity from Key Vault; no secrets in environment variables or code.
- Database migrations applied in staging and verified against production schema compatibility.
- Health endpoints wired to `bigdaisyswarm.health` with HTTP 200/503 semantics.
- Application Insights dashboards updated (latency, errors, token failures, DB connectivity).
- SBOMs and supply-chain attestations published with the release artifacts.
- Backups enabled and tested (restore into a throwaway database).

## Release steps (slot-based)
1. Deploy image to **staging** slot.
2. Run staging smoke tests and DSL script.
3. Run database migration job (if needed) against production database.
4. Run release verification: `python -m bigdaisyswarm.release --base-url https://<app>-staging.azurewebsites.net`.
5. Swap staging -> production.
6. Monitor for 30 minutes (availability, latency, token failures, DB errors).
7. If issues arise, swap back to staging and open an incident.
5. Monitor for 30 minutes (availability, latency, token failures, DB errors).
6. If issues arise, swap back to staging and open an incident.

## Incident response
- **Alerting thresholds:**
  - Availability < 99.9% over 15 minutes.
  - p95 latency > 800ms for 5 minutes.
  - Token validation failures > 2% of requests over 10 minutes.
  - Ready checks failing for > 2 minutes.
- **On-call steps:**
  1. Check `/healthz` and `/readyz` on production and staging.
  2. Inspect Application Insights traces for failing dependencies.
  3. Swap back to staging if production is unstable.
  4. If DB issues, fail over or restart Flexible Server; validate readiness recovers.
  5. Open a root-cause ticket with timeline and impact.

## Security and compliance
- Enforce HTTPS-only and minimum TLS 1.3 in App Service configuration.
- Validate OIDC tokens for issuer, audience, expiry, scopes per `SECURITY_AND_IDENTITY.md`.
- Rotate signing keys and database credentials quarterly; document key-rotation drills.
- Log redaction verified in staging before production swaps.

## Cost and scaling guardrails
- Start with App Service plan B1; scale up or out only after p95 latency exceeds targets under expected load.
- Enable autoscale rules based on CPU (70%) and p95 latency (>500ms).
- Monitor PostgreSQL storage and connections; alert when within 20% of limits.

## Data management
- Daily encrypted backups with 7-day retention; weekly restore tests.
- Schema changes must be additive-first; breaking changes require dual-read/dual-write or feature flags.

## Runbook references
- Deployment steps: `DEPLOYMENT_GUIDE.md`
- Security posture: `SECURITY_AND_IDENTITY.md`
- API surface and health endpoints: `API_SURFACE.md`
