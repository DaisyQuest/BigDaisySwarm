# Deployment Guide

Use this guide to stand up the CalendarApp backend in both Azure and local environments while honoring the deployment specification. The initial rollout favors low-cost, low-complexity options: Azure App Service for Containers and Azure Database for PostgreSQL.

## Prerequisites
- Docker/Compose for local builds; Azure CLI (`az`) for cloud operations.
- Access to Azure: ability to create Resource Groups, App Service plans, App Services, Azure Database for PostgreSQL Flexible Server, and Key Vault.
- OIDC provider with a client registered for `calendar-api` (authorization code + PKCE).
- TLS certificates:
  - Cloud: managed automatically by App Service.
  - Local: self-signed certificates acceptable; distribute the CA to local trust stores when testing mTLS.

## Main cloud server (Azure App Service) rollout
1. **Build and publish images**
   - `docker build -t <acr-name>.azurecr.io/calendar-api:$GIT_SHA .`
   - `az acr login --name <acr-name>`
   - `docker push <acr-name>.azurecr.io/calendar-api:$GIT_SHA`
2. **Provision resources**
   - `az group create --name rg-calendar --location eastus`
   - `az postgres flexible-server create --name cal-postgres --resource-group rg-calendar --sku-name B1MS --storage-size 32 --backup-retention 7 --public-access 0.0.0.0-0.0.0.0`
   - `az keyvault create --name kv-calendar --resource-group rg-calendar`
   - `az appservice plan create --name plan-calendar --resource-group rg-calendar --is-linux --sku B1`
   - `az webapp create --resource-group rg-calendar --plan plan-calendar --name calendar-api --deployment-container-image-name <acr-name>.azurecr.io/calendar-api:$GIT_SHA`
   - Add a **staging slot** for the testing surface: `az webapp deployment slot create --name calendar-api --resource-group rg-calendar --slot staging`
3. **Configure secrets and settings**
   - Store `DATABASE_URL`, `OIDC_ISSUER`, `OIDC_AUDIENCE`, `OIDC_JWKS_URL`, and optional `APPINSIGHTS_CONNECTION_STRING` in Key Vault.
   - Grant the App Service managed identity access: `az webapp identity assign --name calendar-api --resource-group rg-calendar`
   - Add app settings (production and staging slots): `az webapp config appsettings set --name calendar-api --resource-group rg-calendar --settings KEY_VAULT_URI=https://kv-calendar.vault.azure.net/ FEATURE_FLAGS=enable_smoke_tests`
4. **Deploy to staging slot**
   - `az webapp config container set --name calendar-api --resource-group rg-calendar --slot staging --docker-custom-image-name <acr-name>.azurecr.io/calendar-api:$GIT_SHA`
   - Run **migrations** via an Azure Container Instance job or a one-off App Service slot start using the same image.
5. **Validate the testing surface**
   - Hit `https://calendar-api-staging.azurewebsites.net/readyz`.
   - Run DSL smoke tests against the staging slot; example: `PYTHONPATH=src python -m tests.smoke.dsl --base-url https://calendar-api-staging.azurewebsites.net`.
   - Confirm OIDC token validation end-to-end.
6. **Swap to production**
   - `az webapp deployment slot swap --resource-group rg-calendar --name calendar-api --slot staging --target-slot production`
   - Monitor Application Insights for errors; roll back by swapping slots if needed.

## Local build (developer + CI)
1. **Start dependencies**
   - `docker compose -f docker-compose.local.yml up -d postgres`
2. **Prepare identity**
   - Run a local OIDC provider (e.g., Keycloak) or serve a static JWKS for development tokens.
   - Export `OIDC_ISSUER`, `OIDC_AUDIENCE`, and `OIDC_JWKS_URL` to point at the local issuer.
3. **Launch services**
   - `docker compose -f docker-compose.local.yml up -d calendar-api`
   - Alternatively: `PYTHONPATH=src uvicorn calendarapp.server:app --reload --port 8080`
4. **Smoke test**
   - `curl -H "Authorization: Bearer <token>" http://localhost:8080/healthz`
   - Run DSL scripts with `python -m bigdaisyswarm.cli --project-root CalendarApp --task "local smoke"` to create meetings and seed opinions.
   - Wire `/healthz` and `/readyz` to `bigdaisyswarm.health.liveness_check` and `readiness_check`, returning the JSON from `summarize` with HTTP 200/503 from `http_status_code`.
   - Run the built-in smoke harness locally: `PYTHONPATH=src python -m bigdaisyswarm.smoke` and inspect the JSON report for overrides and participant handling.
   - Validate release readiness locally or in staging: `PYTHONPATH=src python -m bigdaisyswarm.release --base-url http://localhost:8080` (expects `status=ok` responses).
5. **Debugging tips**
   - Set `LOG_LEVEL=DEBUG` and tail logs with `docker compose logs -f calendar-api`.
   - Use `FEATURE_FLAGS=disable_notifications` when background hooks are unavailable.

## Backup and recovery
- **PostgreSQL:** schedule nightly dumps to encrypted Azure Storage; enable point-in-time recovery. Verify restores quarterly.
- **Disaster recovery drill:** rehearse recreating the App Service and restoring the database into a fresh Resource Group, then repointing DNS.
 - See `PRODUCTION_READINESS.md` for restore validation criteria and monthly chaos drills.

## Operational runbook (high level)
- Investigate elevated latency by checking:
  - App Service diagnostics -> API saturation -> database health -> downstream IdP status.
- Security incident:
  - Rotate signing keys in the IdP and update JWKS; force token invalidation via short-lived access tokens and revoked refresh tokens.
  - Rotate database credentials in Key Vault and restart slots to pick up changes.
- Scaling:
  - Increase App Service plan size or scale-out instance count; monitor Application Insights (p95 latency, failure rates) to trigger adjustments.
