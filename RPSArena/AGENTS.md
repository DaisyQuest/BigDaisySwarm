# Agent instructions for RPSArena

Scope: applies to everything under `RPSArena/`.

## Meeting workflow
- Kick off new work by creating a fresh meeting with the CLI so each agent has a task-scoped opinion file:
  - `python -m bigdaisyswarm.cli --project-root RPSArena --task "<task description>"`
  - Optionally pass `--meeting-id` to target a specific numeric id + slug; otherwise the CLI picks the next available id.
- Never overwrite existing opinions. If a meeting folder already contains content, create a new meeting instead of editing past notes.
- Keep meeting folders zero-padded and sortable (e.g., `0001-kickoff`, `0002-continue-developing-the-software`).

## Team configuration
- `RPSArena/teamconfig.json` should always include one entry per required agent type (Architect, Developer, TestEngineer, Critic, NoteTaker, Arbiter). Use the library validation when modifying it.
- Preserve custom parameter values; update both the JSON and related tests when changing agent parameters.

## Testing and quality
- Run `pytest --maxfail=1` from the repo root after any change that touches this project.
- Add tests for new behaviors (meeting creation, validation, CLI usage) before depending on them in workflows.
