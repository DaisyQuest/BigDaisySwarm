# Deployment Specification

This document defines the target runtime expectations for the CalendarApp backend so teams can ship both a **main cloud server** on Azure and a **local build** that remain interoperable. The initial deployment emphasizes low cost, portability, and security without Kubernetes or Redis.

## Environments
- **Main cloud server (production + staging):** Azure App Service for Containers (Linux) running a single container image that serves HTTP traffic and background tasks. A staging slot provides the testing surface before swapping to production.
- **Local build:** Docker Compose (or `uvicorn` directly) for developers and CI to run the API plus PostgreSQL on a single host.

## Services and responsibilities
- **API container (`calendar-api`):** Exposes the CalendarApp backend over HTTP and drives the DSL executor for scripted operations. The same image powers both staging and production slots.
- **Background execution:** For low complexity, cron-like jobs or asynchronous hooks run inside the API container (single process model) or via Azure Container Instances for one-off tasks (e.g., migrations). Avoids maintaining a separate worker fleet initially.
- **Persistence:** Azure Database for PostgreSQL Flexible Server (basic tier) for durable storage. No cache layer is required for the first release; feature flags can gate caching if added later.
- **Secrets:** Azure Key Vault stores database credentials, OIDC secrets, and TLS materials. Managed Identity is used to fetch secrets at runtime when available.

## Networking and endpoints
- All public traffic is HTTPS via App Service-managed TLS 1.3 certificates.
- Optional mutual TLS for admin endpoints can be enabled via App Service client certificates; otherwise, rely on OIDC scopes for protection.
- Health probes (mapped to App Service `WEBSITE_HEALTHCHECK_MAXPINGFAILURES` expectations):
  - **Liveness:** `/healthz` returns 200 when the process is alive.
  - **Readiness:** `/readyz` verifies database connectivity and returns structured JSON (see `bigdaisyswarm.health.readiness_check`).

## Configuration contract
- Environment variables (cloud and local):
  - `DATABASE_URL` – PostgreSQL connection string (TLS enabled, `sslmode=require`).
  - `OIDC_ISSUER`, `OIDC_AUDIENCE`, `OIDC_JWKS_URL` – identity configuration for validating tokens.
  - `API_BASE_URL` – public URL used when generating links.
  - `LOG_LEVEL` – defaults to `INFO`; supports `DEBUG` for diagnostics.
  - `FEATURE_FLAGS` – comma-delimited toggles for staged rollouts (e.g., `enforce_mtls,enable_notifications`).
- Azure-specific:
  - `KEY_VAULT_URI` – when set, the service uses Managed Identity to load secrets from Key Vault at startup.
  - `APPINSIGHTS_CONNECTION_STRING` – enables telemetry export to Azure Application Insights.
- Secrets are injected via Key Vault or App Service configuration (Application Settings); never checked into source control.

## Observability and operations
- Metrics: Application Insights standard metrics; expose a `/metrics` endpoint for optional Prometheus scraping in future phases.
- Tracing: OpenTelemetry with W3C trace-context propagation; spans must include calendar and event identifiers when available.
- Logging: JSON logs with request ids; redact PII at the boundary. App Service captures stdout/stderr for download.
- Dashboards: provide Application Insights workbooks for latency, error rates, token validation failures, and health probe status.

## Deployment policies
- **Additive releases first:** Favor backward-compatible changes; breaking migrations require feature flags and staged rollouts.
- **Slot-based canary:** Deploy to the staging slot, run smoke tests, then swap with production.
- **Data migrations:** Run schema migrations as separate tasks (e.g., Azure Container Instance job) prior to slot swap; ensure downgrade scripts exist for critical paths.
- **Backups:** Daily encrypted snapshots of PostgreSQL Flexible Server; document point-in-time recovery in the deployment guide.

## Local build parity
- Provide a Docker Compose profile (`docker-compose.local.yml`) that starts `calendar-api` and PostgreSQL with seeded data.
- Local builds must support the same OIDC validation flow using a development issuer or static JWKS.

## Release artifacts
- Container images tagged with git SHA and semantic version, pushed to Azure Container Registry.
- SBOMs are generated for each image and published alongside build artifacts.
- Provenance: supply-chain attestation (e.g., in-toto/SLSA) is attached to release manifests.
- Releases must pass the production readiness checklist in `PRODUCTION_READINESS.md` before staging-to-production slot swaps.
