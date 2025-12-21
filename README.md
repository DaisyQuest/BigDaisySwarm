# Big Daisy Swarm

Big Daisy Swarm coordinates multiple AI agents to design, implement, and govern projects. This repository defines the shared specifications, agent profiles, and project scaffolding used to launch individual initiatives.

## Key folders
- `spec/`: Human-readable specifications that describe the agent ecosystem and project structure.
- `agents/`: Canonical definitions of each agent type and their parameters.
- `CalendarApp/`: The first project workspace, including its meeting log and team configuration.
- `src/`: Python library that enforces the specification and helps scaffold project directories.
- `tests/`: Automated tests that validate the implementation and configuration tooling.

Project-specific plans live under `spec/`, such as `spec/CALENDAR_APP.md` for the CalendarApp roadmap, backend API principles, and frontend delivery order. The `bigdaisyswarm.calendar` module implements an in-memory backend with Calendar, Event, Participant services, plus a lightweight DSL executor to script calendar operations.

## Development
Install dependencies and run the test suite:

```bash
python -m pip install -e .[dev]
pytest
```

## Kick off a new agent meeting for a task

After scaffolding a project, you can open a fresh meeting for a task so each agent has an opinion file pre-populated with the task context:

```bash
python -m bigdaisyswarm.cli --project-root CalendarApp --task "continue developing the software"
# -> outputs the new meeting folder path, e.g., CalendarApp/meetings/0002-continue-developing-the-software
```

This command:
- Reads `teamconfig.json` to determine participating agents.
- Creates the next numbered meeting folder under `meetings/` (or uses `--meeting-id` if you supply one).
- Seeds each `{agentId}.opinion` file with the task so agents can record their positions and recommendations.
