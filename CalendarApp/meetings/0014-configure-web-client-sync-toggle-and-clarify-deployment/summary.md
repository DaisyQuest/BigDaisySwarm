# Meeting Summary

Meeting: 0014-configure-web-client-sync-toggle-and-clarify-deployment
Task: configure web client sync toggle and clarify deployment

## Outcomes
- Chose to add a configuration module enabling a runtime sync toggle and pluggable remote adapter while keeping a local-first fallback.
- Decided to expose warnings and status text indicating sync mode for transparency.
- Planned to document Azure deployment alongside configuration steps to streamline publishing.

## Decisions
- Introduce `config.mjs` to merge defaults with `window.__CALENDAR_APP_CONFIG__` and construct storage according to sync mode.
- Keep all storage operations synchronous; remote adapters must expose `load`/`save` and fall back to local storage on error.
- Add documentation for Azure deployment and configuration without adding build steps.

## Next steps
- Implement config-driven storage selection, update status messaging, and expand Node-driven tests for remote adapter and fallback paths.
- Add configuration and Azure deployment docs to the `web_client` folder.
- Run full pytest with `--maxfail=1` before publishing.
