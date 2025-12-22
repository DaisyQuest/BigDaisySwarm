# Meeting Summary

Meeting: 0026-ensure-calendar-sync-basic-auth-and-cloud
Task: ensure calendar sync basic auth and cloud

## Outcomes
- Added Basic-auth sync path with scoped local storage per user, remote adapter Basic support, and manual sync controls/status in the web client.
- CalendarModel now exports/replaces snapshots to hydrate from remote state without invasive refactors.
- Remote sync is tolerant to outages (e.g., missing Mongo), falling back to local use while surfacing status.

## Decisions
- Sync remains local-first with optional remote adapter; failures no longer block app usage.
- Basic auth headers are accepted for remote sync when OIDC is absent; Bearer tokens still require JWKS validation.
- UI now exposes a Sync button and sync status text in the hero shell.

## Next steps
- Consider merge/conflict awareness for manual sync operations.
- Evaluate allowing safe links in status messages for authentication prompts.
- Maintain full pytest coverage on future sync/storage changes.
