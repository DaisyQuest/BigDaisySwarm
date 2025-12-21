# Meeting Summary

Meeting: 0009-design-web-client-architecture
Task: design web client architecture

## Outcomes
- Locked in a three-part architecture: CalendarModel for data + validation, ui_templates for pure HTML generation, and app.js as the controller.
- Defined deterministic color selection based on calendar id hashes to keep visual identity stable across renders.
- Settled on seed data reflecting existing rituals plus adapters for storage so tests and browsers share code paths.

## Decisions
- Use .mjs modules to allow Node imports without extra tooling while remaining browser-friendly via type="module".
- Keep normalization helpers (_parseDate, _normalizeTags, _normalizeOwners) centralized in the model.
- Provide agenda grouping and insight calculations to power both UI cards and automated tests.

## Next steps
- Implement the modules as designed with thorough validation messages.
- Wire the controller to forms/selectors with resilient empty states and status messaging.
- Prepare Node-driven tests that cover agenda grouping, range validation, storage fallback, and template rendering.
