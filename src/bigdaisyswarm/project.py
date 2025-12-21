from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .agents import AgentType, default_agent_types, default_team_config, validate_team_config


DEFAULT_MEETING_ID = "0001-kickoff"


def write_team_config(path: Path, team_config: Sequence[Mapping[str, object]]) -> None:
    """Write the team configuration to a JSON file with stable formatting."""
    validate_team_config(team_config)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as config_file:
        json.dump({"agents": team_config}, config_file, indent=2)
        config_file.write("\n")


def create_meeting(opinion_root: Path, meeting_id: str, agent_ids: Sequence[str]) -> Path:
    """Create a meeting folder with blank opinion files for the provided agents."""
    meeting_path = opinion_root / meeting_id
    meeting_path.mkdir(parents=True, exist_ok=True)

    for agent_id in agent_ids:
        opinion_file = meeting_path / f"{agent_id}.opinion"
        if not opinion_file.exists():
            opinion_file.write_text(
                "# Opinion\n\n" "Context: \n" "Position: \n" "Recommendations: \n",
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

    team_config = default_team_config(agent_types)
    write_team_config(project_root / "teamconfig.json", team_config)

    create_meeting(
        opinion_root=project_root / "meetings",
        meeting_id=initial_meeting_id,
        agent_ids=[entry["id"] for entry in team_config],
    )
