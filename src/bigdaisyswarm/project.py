from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .agents import (
    DEFAULT_AGENT_DEFINITIONS_PATH,
    AgentType,
    default_agent_types,
    default_team_config,
    load_agent_types_from_file,
    validate_team_config,
)


DEFAULT_MEETING_ID = "0001-kickoff"


def _project_agents_content(project_name: str) -> str:
    return textwrap.dedent(
        f"""
        # Agent instructions for {project_name}

        Scope: applies to everything under `{project_name}/`.

        ## Meeting workflow
        - Kick off new work by creating a fresh meeting with the CLI so each agent has a task-scoped opinion file:
          - `python -m bigdaisyswarm.cli --project-root {project_name} --task "<task description>"`
          - Optionally pass `--meeting-id` to target a specific numeric id + slug; otherwise the CLI picks the next available id.
        - Never overwrite existing opinions. If a meeting folder already contains content, create a new meeting instead of editing past notes.
        - Keep meeting folders zero-padded and sortable (e.g., `0001-kickoff`, `0002-continue-developing-the-software`).

        ## Team configuration
        - `{project_name}/teamconfig.json` should always include one entry per required agent type (Architect, Developer, TestEngineer, Critic, NoteTaker, Arbiter). Use the library validation when modifying it.
        - Preserve custom parameter values; update both the JSON and related tests when changing agent parameters.

        ## Testing and quality
        - Run `pytest --maxfail=1` from the repo root after any change that touches this project.
        - Add tests for new behaviors (meeting creation, validation, CLI usage) before depending on them in workflows.
        """
    ).strip() + "\n"


def _ensure_project_agents_file(project_root: Path) -> None:
    agents_md = project_root / "AGENTS.md"
    if agents_md.exists():
        return

    agents_md.write_text(_project_agents_content(project_root.name), encoding="utf-8")


def load_team_config(project_root: Path) -> Sequence[Mapping[str, object]]:
    team_config_path = project_root / "teamconfig.json"
    if not team_config_path.is_file():
        raise ValueError(f"teamconfig.json not found at {team_config_path}")

    with team_config_path.open(encoding="utf-8") as config_file:
        data = json.load(config_file)

    if "agents" not in data or not isinstance(data["agents"], list):
        raise ValueError("teamconfig.json must include an 'agents' list")

    return data["agents"]


def validate_project_teamconfig(
    project_root: Path, *, agent_definitions_path: Path | None = None
) -> None:
    agent_types = load_agent_types_from_file(agent_definitions_path or DEFAULT_AGENT_DEFINITIONS_PATH)
    agents = load_team_config(project_root)
    validate_team_config(agents, agent_types=agent_types)


def write_team_config(path: Path, team_config: Sequence[Mapping[str, object]]) -> None:
    """Write the team configuration to a JSON file with stable formatting."""
    validate_team_config(team_config)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as config_file:
        json.dump({"agents": team_config}, config_file, indent=2)
        config_file.write("\n")


def _slugify(text: str) -> str:
    """Convert text into a filesystem-friendly slug."""
    slug = re.sub(r"[^A-Za-z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or "meeting"


def _extract_index(name: str) -> int | None:
    match = re.match(r"(\d+)", name)
    return int(match.group(1)) if match else None


def next_meeting_id(opinion_root: Path, *, slug: str) -> str:
    """Pick the next meeting id based on existing numbered folders."""
    highest_index = 0
    if opinion_root.is_dir():
        for child in opinion_root.iterdir():
            if not child.is_dir():
                continue
            index = _extract_index(child.name)
            if index is not None:
                highest_index = max(highest_index, index)
    return f"{highest_index + 1:04d}-{slug}"


def create_meeting(opinion_root: Path, meeting_id: str, agent_ids: Sequence[str], *, task: str | None = None) -> Path:
    """Create a meeting folder with blank opinion files for the provided agents."""
    if not agent_ids:
        raise ValueError("At least one agent id is required to create a meeting")
    if len(set(agent_ids)) != len(agent_ids):
        raise ValueError("Agent ids must be unique within a meeting")

    meeting_path = opinion_root / meeting_id
    meeting_path.mkdir(parents=True, exist_ok=True)

    summary_file = meeting_path / "summary.md"
    if not summary_file.exists():
        summary_file.write_text(
            "# Meeting Summary\n\n"
            f"Meeting: {meeting_id}\n"
            f"Task: {task or ''}\n\n"
            "## Outcomes\n"
            "- \n\n"
            "## Decisions\n"
            "- \n\n"
            "## Next steps\n"
            "- \n",
            encoding="utf-8",
        )

    for agent_id in agent_ids:
        opinion_file = meeting_path / f"{agent_id}.opinion"
        if not opinion_file.exists():
            opinion_file.write_text(
                "# Opinion\n\n"
                f"Meeting: {meeting_id}\n"
                f"Agent: {agent_id}\n"
                f"Task: {task or ''}\n"
                "Context:\n"
                "Position:\n"
                "Recommendations:\n",
                encoding="utf-8",
            )

    return meeting_path


def scaffold_project(
    project_root: Path,
    agent_types: Iterable[AgentType] | None = None,
    initial_meeting_id: str = DEFAULT_MEETING_ID,
) -> None:
    """Create the required folder structure and team configuration for a project."""
    agent_types = list(agent_types) if agent_types is not None else default_agent_types()
    project_root.mkdir(parents=True, exist_ok=True)

    _ensure_project_agents_file(project_root)

    team_config = default_team_config(agent_types)
    write_team_config(project_root / "teamconfig.json", team_config)

    create_meeting(
        opinion_root=project_root / "meetings",
        meeting_id=initial_meeting_id,
        agent_ids=[entry["id"] for entry in team_config],
    )


def kickoff_task(project_root: Path, task: str, meeting_id: str | None = None) -> Path:
    """Create a new meeting for a task and populate opinion files with the task context."""
    if not task:
        raise ValueError("task is required to kickoff work")

    if meeting_id and _extract_index(meeting_id) is None:
        raise ValueError("meeting_id must start with a numeric prefix")

    agents = load_team_config(project_root)
    agent_types = load_agent_types_from_file(DEFAULT_AGENT_DEFINITIONS_PATH)
    validate_team_config(agents, agent_types=agent_types)
    agent_ids = [entry["id"] for entry in agents]

    opinion_root = project_root / "meetings"
    slug = _slugify(task)
    meeting_identifier = meeting_id or next_meeting_id(opinion_root, slug=slug)

    return create_meeting(opinion_root, meeting_identifier, agent_ids, task=task)
