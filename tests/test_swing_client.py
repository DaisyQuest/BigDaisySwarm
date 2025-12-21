import subprocess
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parents[1] / "swing" / "src"


def compile_swing_sources(tmp_path: Path) -> Path:
    java_files = [str(path) for path in SRC_ROOT.rglob("*.java")]
    assert java_files, "No Java sources found for Swing client"
    classes_dir = tmp_path / "classes"
    classes_dir.mkdir()
    subprocess.run(["javac", "-d", str(classes_dir), *java_files], check=True)
    return classes_dir


def run_harness(classpath: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "java",
            "-Djava.awt.headless=true",
            "-cp",
            str(classpath),
            "calendarapp.swing.CalendarSwingClientTest",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def test_swing_client_harness_executes(tmp_path):
    classes_dir = compile_swing_sources(tmp_path)
    result = run_harness(classes_dir)
    assert "Swing client tests passed" in result.stdout
    assert result.stderr == ""


def test_backend_and_client_can_be_invoked_multiple_times(tmp_path):
    classes_dir = compile_swing_sources(tmp_path)
    # Run twice to ensure state is not cached improperly between invocations.
    first = run_harness(classes_dir)
    second = run_harness(classes_dir)
    assert first.stdout == second.stdout
