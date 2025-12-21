from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .project import (
    kickoff_task,
    latest_meeting_path,
    list_meetings,
    plan_next_meeting,
    validate_project_teamconfig,
)


def _kickoff_args(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument(
        "--project-root",
        required=True,
        help="Path to the project root containing teamconfig.json and meetings/",
    )
    subparser.add_argument(
        "--task",
        help='Task description (e.g., "continue developing the software")',
    )
    subparser.add_argument(
        "--meeting-id",
        help="Optional meeting id override (must start with a numeric prefix like 0003-custom-slug)",
    )
    subparser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute the next meeting path without creating files",
    )
    subparser.add_argument(
        "--validate-config",
        action="store_true",
        help="Validate teamconfig.json against the agent definitions without creating a meeting",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Meeting coordination CLI for agent task workflows.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    kickoff = subparsers.add_parser("kickoff", help="Create a new meeting for a task")
    _kickoff_args(kickoff)

    list_parser = subparsers.add_parser("list", help="List existing meetings")
    list_parser.add_argument(
        "--project-root",
        required=True,
        help="Path to the project root containing meetings/",
    )

    latest = subparsers.add_parser("latest", help="Show the latest meeting path")
    latest.add_argument(
        "--project-root",
        required=True,
        help="Path to the project root containing meetings/",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    argv = list(argv) if argv is not None else sys.argv[1:]
    # Backwards compatibility: treat option-only invocation as kickoff.
    known_subcommands = {"kickoff", "list", "latest"}
    if argv and argv[0] not in known_subcommands and argv[0].startswith("-"):
        argv = ["kickoff", *argv]

    parser = _build_parser()
    args = parser.parse_args(argv)

    # Only kickoff requires --task; list/latest do not.
    if args.command == "kickoff" and not args.validate_config and not args.task:
        parser.error("--task is required unless --validate-config is provided")

    try:
        if args.command == "list":
            project_root = Path(args.project_root)
            for meeting in list_meetings(project_root):
                print(meeting)
            return

        if args.command == "latest":
            project_root = Path(args.project_root)
            print(latest_meeting_path(project_root))
            return

        # kickoff
        project_root = Path(args.project_root)

        if args.validate_config:
            validate_project_teamconfig(project_root)
            print("Team configuration is valid.")
            return

        if args.dry_run:
            meeting_path = plan_next_meeting(
                project_root,
                task=args.task,
                meeting_id=args.meeting_id,
            )
        else:
            meeting_path = kickoff_task(
                project_root,
                task=args.task,
                meeting_id=args.meeting_id,
            )

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(meeting_path)


if __name__ == "__main__":
    main()
