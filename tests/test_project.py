import json
from pathlib import Path

import pytest

from bigdaisyswarm.project import (
    DEFAULT_MEETING_ID,
    create_meeting,
    scaffold_project,
    write_team_config,
)
from bigdaisyswarm.agents import default_team_config


def test_scaffold_project_creates_structure(tmp_path):
    project_root = tmp_path / "CalendarApp"
    scaffold_project(project_root)

    team_config_path = project_root / "teamconfig.json"
    assert team_config_path.is_file()

    with team_config_path.open(encoding="utf-8") as config_file:
        data = json.load(config_file)
    default_agents = default_team_config()
    assert len(data["agents"]) == len(default_agents)
    assert {entry["type"] for entry in data["agents"]} >= {
        "Architect",
        "Developer",
        "TestEngineer",
        "Critic",
        "NoteTaker",
        "Arbiter",
    }
    architect_ids = [entry["id"] for entry in data["agents"] if entry["type"] == "Architect"]
    assert len(architect_ids) == 2

    meeting_dir = project_root / "meetings" / DEFAULT_MEETING_ID
    assert meeting_dir.is_dir()

    opinion_files = list(meeting_dir.glob("*.opinion"))
    assert len(opinion_files) == len(default_agents)

    for opinion_file in opinion_files:
        content = opinion_file.read_text(encoding="utf-8")
        assert "Opinion" in content


def test_write_team_config_rejects_invalid_configuration(tmp_path):
    config_path = tmp_path / "teamconfig.json"
    invalid_config = default_team_config()
    invalid_config = [entry for entry in invalid_config if entry["type"] != "Architect"]

    with pytest.raises(ValueError):
        write_team_config(config_path, invalid_config)



def test_create_meeting_preserves_existing_opinions(tmp_path):
    meeting_root = tmp_path / "meetings"
    agent_ids = ["ArchitectA", "Developer"]
    # Seed one opinion file to ensure we do not overwrite content.
    meeting_path = meeting_root / "0001-seeded"
    meeting_path.mkdir(parents=True)
    seeded = meeting_path / "ArchitectA.opinion"
    seeded.write_text("Keep this", encoding="utf-8")

    create_meeting(meeting_root, "0001-seeded", agent_ids)

    assert seeded.read_text(encoding="utf-8") == "Keep this"
    assert (meeting_path / "Developer.opinion").exists()
