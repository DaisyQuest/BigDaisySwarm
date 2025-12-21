import json
from pathlib import Path

import pytest

from bigdaisyswarm.project import (
    DEFAULT_MEETING_ID,
    append_summary_update,
    create_meeting,
    kickoff_task,
    load_team_config,
    next_meeting_id,
    record_summary_update,
    scaffold_project,
    validate_project_teamconfig,
    write_team_config,
    _slugify,
)
from bigdaisyswarm.agents import default_team_config


def test_scaffold_project_creates_structure(tmp_path):
    project_root = tmp_path / "CalendarApp"
    scaffold_project(project_root)

    team_config_path = project_root / "teamconfig.json"
    assert team_config_path.is_file()

    agents_md = project_root / "AGENTS.md"
    assert agents_md.is_file()
    assert "Agent instructions for CalendarApp" in agents_md.read_text(encoding="utf-8")

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

    summary_file = meeting_dir / "summary.md"
    assert summary_file.is_file()
    summary_content = summary_file.read_text(encoding="utf-8")
    assert f"Meeting: {DEFAULT_MEETING_ID}" in summary_content

    opinion_files = list(meeting_dir.glob("*.opinion"))
    assert len(opinion_files) == len(default_agents)

    for opinion_file in opinion_files:
        content = opinion_file.read_text(encoding="utf-8")
        assert "Opinion" in content
        assert f"Meeting: {DEFAULT_MEETING_ID}" in content
        assert f"Agent: {opinion_file.stem}" in content
        assert "Context:" in content


def test_write_team_config_rejects_invalid_configuration(tmp_path):
    config_path = tmp_path / "teamconfig.json"
    invalid_config = default_team_config()
    invalid_config = [entry for entry in invalid_config if entry["type"] != "Architect"]

    with pytest.raises(ValueError):
        write_team_config(config_path, invalid_config)


def test_scaffold_project_preserves_existing_agents_md(tmp_path):
    project_root = tmp_path / "CalendarApp"
    project_root.mkdir(parents=True)
    custom_agents = project_root / "AGENTS.md"
    custom_agents.write_text("Keep me", encoding="utf-8")

    scaffold_project(project_root)

    assert custom_agents.read_text(encoding="utf-8") == "Keep me"


def test_create_meeting_preserves_existing_opinions(tmp_path):
    meeting_root = tmp_path / "meetings"
    agent_ids = ["ArchitectA", "Developer"]
    # Seed one opinion file to ensure we do not overwrite content.
    meeting_path = meeting_root / "0001-seeded"
    meeting_path.mkdir(parents=True)
    seeded = meeting_path / "ArchitectA.opinion"
    seeded.write_text("Keep this", encoding="utf-8")
    summary = meeting_path / "summary.md"
    summary.write_text("Do not overwrite summary", encoding="utf-8")

    create_meeting(meeting_root, "0001-seeded", agent_ids)

    assert seeded.read_text(encoding="utf-8") == "Keep this"
    developer_file = meeting_path / "Developer.opinion"
    assert developer_file.exists()
    developer_content = developer_file.read_text(encoding="utf-8")
    assert "Meeting: 0001-seeded" in developer_content
    assert "Agent: Developer" in developer_content
    assert summary.read_text(encoding="utf-8") == "Do not overwrite summary"


def test_next_meeting_id_increments_existing_structure(tmp_path):
    opinion_root = tmp_path / "meetings"
    opinion_root.mkdir()
    (opinion_root / "0001-kickoff").mkdir()
    (opinion_root / "0005-design").mkdir()

    assert next_meeting_id(opinion_root, slug="task") == "0006-task"


def test_next_meeting_id_defaults_to_first(tmp_path):
    opinion_root = tmp_path / "meetings"
    assert next_meeting_id(opinion_root, slug="task") == "0001-task"


def test_kickoff_task_creates_new_meeting_with_task(tmp_path):
    project_root = tmp_path / "CalendarApp"
    scaffold_project(project_root)

    meeting_path = kickoff_task(project_root, task="Continue developing the software")
    assert meeting_path.is_dir()
    assert meeting_path.name.startswith("0002-continue-developing-the-software")

    summary_file = meeting_path / "summary.md"
    assert summary_file.exists()
    summary_content = summary_file.read_text(encoding="utf-8")
    assert f"Meeting: {meeting_path.name}" in summary_content
    assert "Task: Continue developing the software" in summary_content

    opinion_files = list(meeting_path.glob("*.opinion"))
    assert opinion_files, "expected opinion files to be created"
    for opinion_file in opinion_files:
        content = opinion_file.read_text(encoding="utf-8")
        assert "Task: Continue developing the software" in content
        assert "Recommendations:" in content
        assert f"Meeting: {meeting_path.name}" in content


def test_kickoff_task_respects_custom_meeting_id_and_existing_opinion(tmp_path):
    project_root = tmp_path / "CalendarApp"
    scaffold_project(project_root)
    custom_meeting = project_root / "meetings" / "0100-custom"
    custom_meeting.mkdir(parents=True)
    preexisting = custom_meeting / "ArchitectA.opinion"
    preexisting.write_text("Do not overwrite", encoding="utf-8")

    kickoff_task(project_root, task="Ship it", meeting_id="0100-custom")

    assert preexisting.read_text(encoding="utf-8") == "Do not overwrite"
    # Other agents should get files created with the task
    developer_file = custom_meeting / "Developer.opinion"
    developer_content = developer_file.read_text(encoding="utf-8")
    assert developer_content.startswith("# Opinion")
    assert "Task: Ship it" in developer_content
    assert "Meeting: 0100-custom" in developer_content
    summary_file = custom_meeting / "summary.md"
    assert summary_file.exists()
    summary_content = summary_file.read_text(encoding="utf-8")
    assert "Meeting: 0100-custom" in summary_content
    assert "Task: Ship it" in summary_content


def test_kickoff_task_requires_team_config(tmp_path):
    project_root = tmp_path / "MissingConfig"
    project_root.mkdir()

    with pytest.raises(ValueError):
        kickoff_task(project_root, task="Work")


def test_kickoff_task_rejects_invalid_meeting_id(tmp_path):
    project_root = tmp_path / "CalendarApp"
    scaffold_project(project_root)

    with pytest.raises(ValueError) as excinfo:
        kickoff_task(project_root, task="Work", meeting_id="custom-id")

    assert "numeric prefix" in str(excinfo.value)


def test_kickoff_task_cli(tmp_path, monkeypatch):
    project_root = tmp_path / "CalendarApp"
    scaffold_project(project_root)

    # Run the CLI in a subprocess-like way by calling main directly
    from bigdaisyswarm import cli

    cli.main(
        [
            "--project-root",
            str(project_root),
            "--task",
            "continue developing the software",
        ]
    )

    meetings = sorted((project_root / "meetings").iterdir())
    assert meetings[-1].name.startswith("0002-continue-developing-the-software")

    summary_file = meetings[-1] / "summary.md"
    assert summary_file.exists()
    assert "continue developing the software" in summary_file.read_text(encoding="utf-8")


def test_cli_reports_errors(tmp_path, capsys):
    project_root = tmp_path / "CalendarApp"
    project_root.mkdir()

    from bigdaisyswarm import cli

    with pytest.raises(SystemExit) as excinfo:
        cli.main(
            [
                "--project-root",
                str(project_root),
                "--task",
                "continue developing the software",
            ]
        )

    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "teamconfig.json not found" in captured.err
    assert captured.out == ""


def test_slugify_handles_blank_text():
    assert _slugify("   ") == "meeting"
    assert _slugify("Task!! Name") == "task-name"


def test_create_meeting_rejects_duplicate_or_empty_agents(tmp_path):
    opinion_root = tmp_path / "meetings"
    with pytest.raises(ValueError):
        create_meeting(opinion_root, "0001-kickoff", [])

    with pytest.raises(ValueError):
        create_meeting(opinion_root, "0001-kickoff", ["Dev", "Dev"])


def test_validate_project_teamconfig_accepts_valid_config(tmp_path):
    project_root = tmp_path / "CalendarApp"
    scaffold_project(project_root)

    validate_project_teamconfig(project_root)
    assert load_team_config(project_root)  # confirm the configuration is still readable


def test_validate_project_teamconfig_detects_missing_agent(tmp_path):
    project_root = tmp_path / "CalendarApp"
    scaffold_project(project_root)

    config_path = project_root / "teamconfig.json"
    with config_path.open(encoding="utf-8") as config_file:
        data = json.load(config_file)
    data["agents"] = [entry for entry in data["agents"] if entry["type"] != "NoteTaker"]
    config_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ValueError) as excinfo:
        validate_project_teamconfig(project_root)

    assert "Missing required agent types" in str(excinfo.value)


def test_validate_project_teamconfig_detects_parameter_out_of_range(tmp_path):
    project_root = tmp_path / "CalendarApp"
    scaffold_project(project_root)

    config_path = project_root / "teamconfig.json"
    with config_path.open(encoding="utf-8") as config_file:
        data = json.load(config_file)
    data["agents"][0]["parameters"]["preferSimplicityLevel"] = 1.5
    config_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ValueError) as excinfo:
        validate_project_teamconfig(project_root)

    assert "must be <= 1.0" in str(excinfo.value)


def test_validate_project_teamconfig_requires_agents_list(tmp_path):
    project_root = tmp_path / "CalendarApp"
    scaffold_project(project_root)
    config_path = project_root / "teamconfig.json"
    config_path.write_text(json.dumps({"agents": "not-a-list"}, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ValueError) as excinfo:
        validate_project_teamconfig(project_root)

    assert "must include an 'agents' list" in str(excinfo.value)


def test_validate_project_teamconfig_rejects_invalid_agent_definitions(tmp_path):
    project_root = tmp_path / "CalendarApp"
    scaffold_project(project_root)
    bad_definitions = tmp_path / "AGENTS.json"
    bad_definitions.write_text(
        json.dumps(
            {
                "Architect": {
                    "description": "Broken",
                    "parameters": {
                        "preferSimplicityLevel": {
                            "type": "",
                            "min": 0.0,
                            "max": 1.0,
                            "default": 0.5,
                        }
                    },
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as excinfo:
        validate_project_teamconfig(project_root, agent_definitions_path=bad_definitions)

    assert "must declare a string 'type'" in str(excinfo.value)


def test_validate_project_teamconfig_requires_all_agent_definitions(tmp_path):
    project_root = tmp_path / "CalendarApp"
    scaffold_project(project_root)
    missing_definitions = tmp_path / "AGENTS-missing.json"
    missing_definitions.write_text(
        json.dumps({"Architect": {"description": "Only one", "parameters": {}}}, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as excinfo:
        validate_project_teamconfig(project_root, agent_definitions_path=missing_definitions)

    assert "Agent definitions missing required types" in str(excinfo.value)


def test_cli_validate_config(tmp_path, capsys):
    project_root = tmp_path / "CalendarApp"
    scaffold_project(project_root)

    from bigdaisyswarm import cli

    cli.main(
        [
            "--project-root",
            str(project_root),
            "--validate-config",
        ]
    )

    captured = capsys.readouterr()
    assert "Team configuration is valid." in captured.out


def test_cli_validate_config_reports_errors(tmp_path, capsys):
    project_root = tmp_path / "CalendarApp"
    scaffold_project(project_root)
    config_path = project_root / "teamconfig.json"
    with config_path.open(encoding="utf-8") as config_file:
        data = json.load(config_file)
    data["agents"] = [entry for entry in data["agents"] if entry["type"] != "Critic"]
    config_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    from bigdaisyswarm import cli

    with pytest.raises(SystemExit) as excinfo:
        cli.main(
            [
                "--project-root",
                str(project_root),
                "--validate-config",
            ]
        )

    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "Missing required agent types" in captured.err
def test_append_summary_creates_missing_summary(tmp_path):
    meeting_path = tmp_path / "meetings" / "0003-summary"
    meeting_path.mkdir(parents=True)

    summary_path = append_summary_update(
        meeting_path,
        outcomes=["Delivered MVP"],
        decisions=["Ship to beta users"],
        next_steps=["Monitor feedback"],
        task="Release MVP",
    )

    content = summary_path.read_text(encoding="utf-8")
    assert "Meeting: 0003-summary" in content
    assert "Task: Release MVP" in content
    assert "- Delivered MVP" in content
    assert "- Ship to beta users" in content
    assert "- Monitor feedback" in content


def test_append_summary_appends_without_overwriting_existing_sections(tmp_path):
    meeting_path = tmp_path / "meetings" / "0004-existing"
    meeting_path.mkdir(parents=True)
    summary_file = meeting_path / "summary.md"
    summary_file.write_text(
        "# Meeting Summary\n\n"
        "Meeting: 0004-existing\n"
        "Task: Existing work\n\n"
        "## Outcomes\n"
        "- Kept legacy behavior\n\n"
        "## Decisions\n"
        "- Proceed cautiously\n\n"
        "## Next steps\n"
        "- Document risks\n",
        encoding="utf-8",
    )

    append_summary_update(
        meeting_path,
        outcomes=["Added new capability"],
        decisions=["Revisit rollout plan"],
        next_steps=["Schedule postmortem"],
    )

    updated = summary_file.read_text(encoding="utf-8")
    assert "- Kept legacy behavior" in updated
    assert "- Added new capability" in updated
    assert updated.index("- Kept legacy behavior") < updated.index("- Added new capability")
    assert "- Proceed cautiously" in updated
    assert "- Revisit rollout plan" in updated
    assert "- Document risks" in updated
    assert "- Schedule postmortem" in updated


def test_record_summary_update_handles_missing_sections_and_requires_meeting(tmp_path):
    project_root = tmp_path / "CalendarApp"
    meeting_path = project_root / "meetings" / "0005-missing"
    meeting_path.mkdir(parents=True)
    summary_file = meeting_path / "summary.md"
    summary_file.write_text(
        "# Meeting Summary\n\n"
        "Meeting: 0005-missing\n"
        "Task: Partial summary\n\n"
        "## Outcomes\n"
        "- Initial outcome\n",
        encoding="utf-8",
    )

    updated_path = record_summary_update(
        project_root,
        "0005-missing",
        outcomes=["Follow-up outcome"],
        decisions=["Capture decision later"],
        next_steps=["Add retrospective notes"],
    )

    assert updated_path == summary_file
    updated = summary_file.read_text(encoding="utf-8")
    assert "- Initial outcome" in updated
    assert "- Follow-up outcome" in updated
    assert "## Decisions" in updated
    assert "- Capture decision later" in updated
    assert "## Next steps" in updated
    assert "- Add retrospective notes" in updated

    with pytest.raises(ValueError):
        record_summary_update(project_root, "9999-missing")
