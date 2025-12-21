# Agent instructions (repo-wide)

These instructions apply to all files in this repository unless a subdirectory contains its own `AGENTS.md` with more specific guidance.

## Development workflow
- Always run the full test suite with `pytest --maxfail=1` before delivering changes. Add or update tests alongside code to keep behavior well covered.
- Use the provided CLI to kick off meetings for a task so opinion files exist before agents contribute:
  - `python -m bigdaisyswarm.cli --project-root CalendarApp --task "continue developing the software"`
  - Include `--meeting-id` only when you must override the next numeric id.
- Preserve existing opinion content when updating meetings; create new meeting folders instead of overwriting prior ones.
- Keep `agents/AGENTS.json` and the Python definitions in sync when adjusting agent types or parameters.

## Code and style
- Prefer clear, explicit Python that matches existing patterns. Avoid unnecessary dependencies.
- Maintain stable JSON formatting (2-space indents with trailing newline) when writing configuration files.
- Ensure new utilities are exercised by tests that cover both success paths and error handling.

## Project scaffolding
- When creating a new project workspace, use the `scaffold_project` helper (or mirror its behavior) so the project root includes `teamconfig.json`, `meetings/`, and a project-scoped `AGENTS.md`.
- Meeting directories should be named with zero-padded numeric prefixes (e.g., `0001-kickoff`). Use the CLI or library helpers to allocate the next id.
