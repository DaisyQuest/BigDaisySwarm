# Meeting Summary

Meeting: 0008-add-login-flow-and-bot-matchmaking
Task: Add login flow and bot matchmaking

## Outcomes
- Added login navigation/panel with client-side currentUser tracking, removing manual player ID entry for matchmaking and profile updates.
- Introduced bot matchmaking via a playBot flag, provisioning a sanitized bot user and hydrating matches immediately for human-vs-bot testing.
- Expanded match service tests for bot creation/reuse and validation, keeping npm test (c8 --100) and repo-level `pytest --maxfail=1` green at 100% coverage.

## Decisions
- Reuse the existing matchmaking endpoint with a bot flag instead of a new route, keeping queue logic centralized.
- Require authenticated state for queueing, avatar updates, and history loads, surfacing clear feedback when unauthenticated.
- Ensure bot users are created once and sanitized playerProfiles are returned with each match payload.

## Next steps
- Monitor UX to see if a logout flow or persistent sessions are needed beyond the current in-memory user state.
- Consider server-side bot difficulty tuning (move selection) if human-vs-bot usage grows beyond smoke testing.
