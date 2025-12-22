# Meeting Summary

Meeting: 0006-resolve-ssl-insecure-deployment-errors-on-azure
Task: resolve SSL/insecure deployment errors on Azure

## Outcomes
- Added an env utility to resolve PORT vs WEBSITES_PORT and Mongo TLS/timeouts, wiring it into server/bootstrap with Mongo fallback logging.
- Made MongoClient options configurable via env (TLS enablement, CA bundle, invalid cert toggle) and refreshed deployment docs/HTML to call out Azure port/TLS requirements.
- Expanded tests (env helper, bootstrap forwarding, Mongo client options, doc content) and reran npm test plus repo-level `pytest --maxfail=1` with full coverage.

## Decisions
- Prefer env-driven configuration for Azure specifics instead of hardcoded TLS bypass; keep defaults strict while allowing explicit overrides for self-signed/testing cases.
- Treat SSL/protocol errors as hosting/configuration issues first (port binding, Mongo TLS handshake) and surface diagnostics through logging and documentation.

## Next steps
- Redeploy with WEBSITES_PORT (if provided by Azure) and appropriate MONGODB_TLS* settings; verify Mongo connectivity/logs post-deploy.
- Encourage operators to supply CA bundles rather than enabling invalid-cert mode in production; collect Azure logs if SSL errors persist. 
