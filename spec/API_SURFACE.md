# CalendarApp Backend API Surface

This reference summarizes the backend contracts that every client implementation (web, Swing, CLI, Rust, mobile) should use. It covers the Python services and the DSL executor so client teams can build against the same behaviors and validation rules.

## Python service layer

- **CalendarService**
  - `create_calendar(name, owners, description=None) -> calendar_id`
    - Requires a non-empty name and at least one owner email.
  - `list_calendars(owner=None) -> list[dict]`
    - Filters by owner when provided.
- **EventService**
  - `create_event(calendar_id, title, start, end, timezone, recurrence=None, participants=None, metadata=None) -> event_id`
    - Validates the calendar exists, title is non-empty, times are timezone-aware and ordered, and metadata is a mapping.
    - `participants` accepts an iterable of `Participant` instances and stores them on creation.
  - `update_event(event_id, **fields) -> None`
    - Supports `title`, `start`, `end`, `timezone`, `recurrence`, and `metadata` updates with the same validation as creation.
  - `cancel_event(event_id, occurrence=None) -> None`
    - Cancels the series or a single occurrence via overrides.
  - `reschedule_event(event_id, occurrence, start, end) -> None`
    - Replaces a single occurrence with new times; overrides reject conflicting changes.
  - `list_events(calendar_id, range_start=None, range_end=None) -> list[Event]`
    - Expands overrides and filters occurrences within the optional window.
- **ParticipantService**
  - `add_participant(event_id, participant)`
  - `update_participant(event_id, participant_id, response=None)`
  - `remove_participant(event_id, participant_id)`

Errors are raised as `CalendarError` with actionable messages so transport layers can return consistent responses to clients.

## DSL executor commands

The DSL uses `COMMAND key=value ...` lines. Values containing JSON should be wrapped in single quotes to avoid shell parsing. Commands:

- `CREATE_CALENDAR name=<name> owners=<email,email,...> [description=<text>]`
- `LIST_CALENDARS [owner=<email>]`
- `CREATE_EVENT calendar=<id> title=<text> start=<iso> end=<iso> [timezone=<tz>] [recurrence=<rrule>] [metadata='<json>'] [participants='<json array>']`
  - `participants` accepts an array like `[{"id":"alice","name":"Alice","email":"alice@example.com","response":"accepted"}]`.
- `UPDATE_EVENT event=<id> [title=<text>] [start=<iso>] [end=<iso>] [timezone=<tz>] [recurrence=<rrule>] [metadata='<json>']`
- `CANCEL_EVENT event=<id> [occurrence=<YYYY-MM-DD>]`
- `RESCHEDULE_EVENT event=<id> occurrence=<YYYY-MM-DD> start=<iso> end=<iso>`
- `LIST_EVENTS calendar=<id> [range_start=<iso>] [range_end=<iso>]`
- `ADD_PARTICIPANT event=<id> participant=<id> name=<name> email=<email> [response=<status>]`
- `UPDATE_PARTICIPANT event=<id> participant=<id> [response=<status>]`
- `REMOVE_PARTICIPANT event=<id> participant=<id>`

## Authentication and authorization
- All HTTP or gRPC transports must require a valid OIDC access token (see `SECURITY_AND_IDENTITY.md`).
- Tokens are validated for issuer, audience, expiry, and scopes:
  - `calendar.read` for read-only endpoints (e.g., `LIST_EVENTS`, `LIST_CALENDARS`).
  - `calendar.write` for mutations (create/update/cancel/reschedule, participant commands).
  - `calendar.admin` for administrative or migration endpoints.
- Include the trace id in responses to help clients correlate failures with logs.
- Health endpoints:
  - `/healthz` should return `summarize([liveness_check()])` with HTTP 200.
  - `/readyz` should return `summarize([liveness_check(), readiness_check(storage)])` with HTTP 200 when healthy, 503 otherwise.
- Operators must ensure staging-slot health checks pass before swapping to production (see `PRODUCTION_READINESS.md`).

### Example session

```
CREATE_CALENDAR name="Work" owners=alice@example.com,bob@example.com
CREATE_EVENT calendar=<id> title="Planning" start=2025-04-01T09:00Z end=2025-04-01T10:00Z timezone=UTC \
  participants='[{"id":"alice","name":"Alice","email":"alice@example.com"},{"id":"bob","name":"Bob","email":"bob@example.com","response":"accepted"}]'
RESCHEDULE_EVENT event=<event-id> occurrence=2025-04-01 start=2025-04-02T09:00Z end=2025-04-02T10:00Z
LIST_EVENTS calendar=<id> range_start=2025-04-01T00:00Z range_end=2025-04-03T00:00Z
```

The executor annotates failures with line numbers (e.g., `Line 2: ...`) so clients can surface precise feedback when batching scripts.

## Implementation guidance for clients

- Transport layers (HTTP, CLI, Rust bindings, Swing adapters) should delegate validation to these services and forward `CalendarError` messages verbatim to keep parity.
- Include timezone offsets on all datetimes; store or transmit in UTC and localize at the presentation layer.
- Use additive changes wherever possible (reschedules and cancellations operate on overrides rather than mutating existing occurrences).
- When creating events in one call, prefer the `participants` JSON payload to seed invitees alongside the event and reduce round trips.
- End-to-end tests should cover success and error cases for each command to preserve behavior across client implementations.
