# Big Daisy Swarm Specification

This document defines the shared structure for Big Daisy Swarm projects and the agents that participate in them. It describes how to create new projects, what artifacts belong in each project directory, and the expected responsibilities of each agent type.

## Directory layout

All repositories that host swarm projects should adopt the following top-level layout:

```
/spec                 # Human-authored specifications and conventions
/agents               # Canonical agent type definitions
/<ProjectName>/       # Individual project workspace (e.g., CalendarApp)
```

Each project workspace **must** contain:

```
/meetings/{meetingId}/{agentId}.opinion  # One opinion file per agent per meeting
/teamconfig.json                         # Map of participating agent types and their parameter values
```

- `meetingId` should be descriptive and sortable (e.g., `0001-kickoff`, `0002-architecture`).
- `agentId` corresponds to a participating agent instance. Use the agent type name when a single agent of that type participates (e.g., `Architect.opinion`).

## Agent types

All projects share the same set of agent types. Agent types are defined in the `/agents` folder and codified in the Python library under `bigdaisyswarm.agents`. Each agent type may declare parameters that tune its behavior.

### Architect
- **Role:** Maintain the project specification and determine whether work meets the spec.
- **Parameters:**
  - `preferSimplicityLevel` (`double`, `0.0`–`1.0`): Higher values prioritize simple, easy-to-maintain solutions.
  - `preferHomebakedCodeLevel` (`double`, `0.0`–`1.0`): Higher values prefer bespoke implementations over third-party libraries.

### Developer
- **Role:** Implement features to satisfy the specification; responsible for committing code.
- **Parameters:**
  - `preferSimplicityLevel` (`double`, `0.0`–`1.0`): Higher values favor straightforward implementations.
  - `preferHomebakedCodeLevel` (`double`, `0.0`–`1.0`): Higher values favor custom code over dependencies.

### TestEngineer
- **Role:** Develops tests aiming for comprehensive coverage and recommends testability improvements.
- **Parameters:** None; defaults to pursuing high coverage and clarity.

### Critic
- **Role:** Identify risks, maintainability concerns, and potential flaws.
- **Parameters:** None.

### NoteTaker
- **Role:** Summarize meetings and prepare reports for the Arbiter.
- **Parameters:** None.

### Arbiter
- **Role:** Review opinion files and call for next actions or resolutions.
- **Parameters:** None.

## Team configuration

Each project includes a `teamconfig.json` file that lists **agent instances**. Each instance declares a unique `id`, references a known agent `type`, and provides parameter values that match the type specification. This allows multiple instances of the same agent type (for example, two Architects who debate design choices).

```json
{
  "agents": [
    {
      "id": "ArchitectA",
      "type": "Architect",
      "parameters": {
        "preferSimplicityLevel": 0.6,
        "preferHomebakedCodeLevel": 0.4
      }
    },
    {
      "id": "ArchitectB",
      "type": "Architect",
      "parameters": {
        "preferSimplicityLevel": 0.3,
        "preferHomebakedCodeLevel": 0.7
      }
    },
    {
      "id": "Developer",
      "type": "Developer",
      "parameters": {
        "preferSimplicityLevel": 0.5,
        "preferHomebakedCodeLevel": 0.5
      }
    },
    { "id": "TestEngineer", "type": "TestEngineer", "parameters": {} },
    { "id": "Critic", "type": "Critic", "parameters": {} },
    { "id": "NoteTaker", "type": "NoteTaker", "parameters": {} },
    { "id": "Arbiter", "type": "Arbiter", "parameters": {} }
  ]
}
```

Constraints enforced by the library:
- At least one instance of every required agent type must appear in `teamconfig.json`.
- Instance IDs must be unique.
- Parameter values must fall within their declared ranges.
- Unknown agent types or parameters are rejected to maintain consistency with the spec.

## Meetings and opinions

Meetings are organized under the `meetings/` directory. For each meeting:
- Create a subfolder named `{meetingId}`.
- Within that folder, include one `{agentId}.opinion` file per participating agent.
- Opinion files are free-form text but should clearly identify the topic, reasoning, and recommendations.

### Suggested meeting cadence
1. **Kickoff:** Architect and Developer propose approach; Critic flags risks; NoteTaker records; Arbiter sets next steps.
2. **Checkpoints:** After major milestones or test runs, gather opinions and adjust course.
3. **Retrospective:** Summarize lessons learned and update the project spec if needed.

## Extending the spec

- Add new agent types in `/agents` and reflect them in the Python library to keep validation in sync.
- When introducing new parameters, document their ranges and defaults. Update `teamconfig.json` templates accordingly.
- Keep tests aligned with the spec to prevent configuration drift across projects.
