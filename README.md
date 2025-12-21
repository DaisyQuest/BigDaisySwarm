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
