from pathlib import Path

import pytest

from bigdaisyswarm import cli
from bigdaisyswarm.project import kickoff_task, scaffold_project


def test_cli_list_and_latest(tmp_path, capsys):
    project_root = tmp_path / "CalendarApp"
    scaffold_project(project_root)
    newest = kickoff_task(project_root, task="Continue building features")

    cli.main(["list", "--project-root", str(project_root)])
    captured = capsys.readouterr()
    lines = captured.out.strip().splitlines()
    assert Path(lines[0]).name == "0001-kickoff"
    assert Path(lines[-1]) == newest

    cli.main(["latest", "--project-root", str(project_root)])
    latest = capsys.readouterr().out.strip()
    assert Path(latest) == newest


def test_cli_list_reports_missing_meetings(tmp_path, capsys):
    project_root = tmp_path / "CalendarApp"
    project_root.mkdir()

    with pytest.raises(SystemExit) as excinfo:
        cli.main(["list", "--project-root", str(project_root)])

    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "meetings directory not found" in captured.err
    assert captured.out == ""


def test_cli_dry_run_and_invalid_meeting_id(tmp_path, capsys):
    project_root = tmp_path / "CalendarApp"
    scaffold_project(project_root)

    cli.main(
        [
            "kickoff",
            "--project-root",
            str(project_root),
            "--task",
            "Continue iterating",
            "--dry-run",
        ]
    )
    planned = capsys.readouterr().out.strip()
    assert not Path(planned).exists()

    with pytest.raises(SystemExit) as excinfo:
        cli.main(
            [
                "kickoff",
                "--project-root",
                str(project_root),
                "--task",
                "Continue iterating",
                "--meeting-id",
                "custom-id",
            ]
        )

    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "numeric prefix" in captured.err
    assert captured.out == ""
