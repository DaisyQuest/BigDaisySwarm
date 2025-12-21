from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .project import kickoff_task


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Kick off a new meeting for a task so agents can leave opinions."
    )
    parser.add_argument(
        "--project-root",
        required=True,
        help="Path to the project root containing teamconfig.json and meetings/",
    )
    parser.add_argument(
        "--task",
        required=True,
        help='Task description (e.g., "continue developing the software")',
    )
    parser.add_argument(
        "--meeting-id",
        help="Optional meeting id override (defaults to next available numeric id with a slug)",
    )

    args = parser.parse_args(argv)

    try:
        project_root = Path(args.project_root)
        meeting_path = kickoff_task(project_root, task=args.task, meeting_id=args.meeting_id)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(meeting_path)


if __name__ == "__main__":
    main()
