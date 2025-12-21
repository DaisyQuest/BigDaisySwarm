# Meeting Summary

Meeting: 0010-plan-testing-for-web-client
Task: plan testing for web client

## Outcomes
- Established Node-driven test harness invoked from pytest to exercise JS modules directly.
- Defined coverage goals: validation errors, agenda grouping, insights math, template empty states, and HTML shell hooks.
- Chose to parse JSON emitted by Node scripts to avoid brittle stdout parsing and keep assertions clear.

## Decisions
- Use `node --input-type=module` so ES modules load without a bundler and align with browser behavior.
- Assert specific error strings for invalid ranges, missing owners, and unknown calendars to mirror backend messaging.
- Include HTML shell checks to ensure controller hooks remain present after refactors.

## Next steps
- Implement the Node helper and write tests for model behaviors, template rendering, and shell structure.
- Keep storage adapter behavior under test (memory fallback when localStorage is absent).
- Run full pytest with `--maxfail=1` before delivery.
