# Big Daisy Swarm

Big Daisy Swarm coordinates multiple AI agents to design, implement, and govern projects. This repository defines the shared specifications, agent profiles, and project scaffolding used to launch individual initiatives.

## Key folders
- `spec/`: Human-readable specifications that describe the agent ecosystem and project structure.
- `agents/`: Canonical definitions of each agent type and their parameters.
- `CalendarApp/`: The first project workspace, including its meeting log and team configuration.
- `src/`: Python library that enforces the specification and helps scaffold project directories.
- `tests/`: Automated tests that validate the implementation and configuration tooling.

`spec/API_SURFACE.md` documents the backend API and DSL so client teams can build compatible transports without re-reading the source. Deployment and security guidance lives in `spec/DEPLOYMENT_SPEC.md`, `spec/DEPLOYMENT_GUIDE.md`, `spec/SECURITY_AND_IDENTITY.md`, and the production checklist in `spec/PRODUCTION_READINESS.md`, with Azure-first, low-complexity rollout steps, health-check wiring, and testing-surface expectations.

Local smoke harness: `PYTHONPATH=src python -m bigdaisyswarm.smoke` generates a JSON report that mirrors the staging smoke tests in the production readiness checklist.
Release verification harness: `PYTHONPATH=src python -m bigdaisyswarm.release --base-url https://<app>` asserts healthy `/healthz` and `/readyz` responses before slot swaps.

Project-specific plans live under `spec/`, such as `spec/CALENDAR_APP.md` for the CalendarApp roadmap, backend API principles, and frontend delivery order. The `bigdaisyswarm.calendar` module implements an in-memory backend with Calendar, Event, Participant services, plus a lightweight DSL executor to script calendar operations.

## Azure-ready examples
- **Web client container**: `web_client/Dockerfile` packages the static HTML/JS client behind NGINX with a `/healthz` responder for Azure App Service health checks. See `web_client/DEPLOY_AZURE.md` (Option 3) for build and release steps.
- **Example server container**: `example_server/Dockerfile` runs `python -m bigdaisyswarm.example_server`, exposing `/healthz`, `/readyz`, `/state`, and `/dsl` for a public demo. Deployment guidance lives in `example_server/DEPLOY_AZURE.md`.
- **GitHub Actions deploy**: `.github/workflows/azure-containers.yml` builds and pushes both images to an Azure Container Registry, then updates the App Services using repository secrets (`AZURE_CREDENTIALS`, `ACR_NAME`, `ACR_LOGIN_SERVER`, `AZURE_RESOURCE_GROUP`, `WEB_CLIENT_APP_NAME`, `EXAMPLE_SERVER_APP_NAME`).

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
