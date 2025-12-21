# CalendarApp Project Plan

This document outlines the CalendarApp vision, backend API principles, and the frontend delivery order. It complements the shared project specification in `PROJECT_SPEC.md` by adding CalendarApp-specific expectations.

## Goals
- Provide a strong and flexible backend API that can power multiple frontends without duplication.
- Support multiple agent perspectives, including **two Architects** who debate design trade-offs to improve robustness.
- Deliver frontends in the following order: **HTML + JS**, **React**, **Java Swing**, **Command Line**, **Android**, **iOS**.
- Explore a domain-specific language (DSL) to express calendar operations (creation, recurrence, sharing) in a backend-agnostic way.

## Backend principles
- **Transport-agnostic API**: Core logic should be implemented as reusable Python modules that can be exposed via HTTP, CLI, or other transports without rewriting business rules.
- **Stable resource model**: Events, calendars, and participants are first-class types with immutable identifiers and auditable updates.
- **Recurrence and exceptions**: Recurring events support overrides (e.g., cancel or reschedule a single occurrence) without duplicating the series definition.
- **Time zones and locales**: All times are stored in UTC with explicit time zone metadata; presentation layers perform localization.
- **Idempotent operations**: Creation, update, and deletion APIs should be idempotent where possible to simplify client retries.
- **Validation-first**: Payloads are validated at the boundary; errors are descriptive and include actionable remediation guidance.

## Proposed API surface (backend library)
- `CalendarService`
  - `create_calendar(name, owners, description=None)`
  - `list_calendars(owner=None)`
- `EventService`
  - `create_event(calendar_id, title, start, end, timezone, recurrence=None, participants=None, metadata=None)`
  - `update_event(event_id, **fields)`
  - `cancel_event(event_id, occurrence=None)`
  - `list_events(calendar_id, range_start=None, range_end=None)`
- `ParticipantService`
  - `add_participant(event_id, participant)`
  - `remove_participant(event_id, participant_id)`
  - `update_participant(event_id, participant_id, response=None)`

These services should share a storage-agnostic interface so frontends can swap persistence layers (in-memory, file-based, database) without altering callers.

## DSL concept
- **Purpose:** Provide a concise, declarative way to describe calendar operations for automation and cross-frontend parity.
- **Format:** Textual commands, one per line, with JSON-like payloads for complex fields. Example:
  - `CREATE_EVENT calendar=work title="Standup" start=2025-01-10T14:00Z end=2025-01-10T14:15Z recurrence="RRULE:FREQ=DAILY;COUNT=5"`
  - `CANCEL_EVENT event=evt_123 occurrence=2025-01-12`
- **Execution:** The backend parses DSL statements into service calls. Errors include line numbers and hints (e.g., missing required fields, invalid recurrence rules).

## Frontend order and expectations
1. **HTML + JS (vanilla):** Proves the API and DSL in a simple, portable environment.
2. **React:** Reuses the API client; introduces state management and component abstractions.
3. **Java Swing:** Demonstrates desktop support with the same backend contracts.
4. **Command Line:** Offers scripting and automation hooks (pairs well with the DSL).
5. **Android:** Mobile implementation leveraging the shared API/DSL.
6. **iOS:** Mirrors Android parity and validates API neutrality.

## Meeting structure
- Maintain two Architect instances (e.g., `ArchitectA`, `ArchitectB`) in `teamconfig.json` and ensure they both contribute opinion files for each meeting.
- NoteTaker synthesizes divergent architect opinions for the Arbiter to adjudicate next steps.
