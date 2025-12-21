from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from bigdaisyswarm import (
    CalendarError,
    CalendarService,
    DSLExecutor,
    EventService,
    InMemoryCalendarStorage,
    ParticipantService,
)

from .storage import dump_storage, load_storage, serialize_storage


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CLI client for the calendar DSL backed by Big Daisy Swarm services."
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Execute DSL commands from a file or stdin")
    run_parser.add_argument(
        "--commands",
        help="Path to a file containing DSL commands. When omitted, commands are read from stdin.",
    )
    run_parser.add_argument(
        "--print-state",
        action="store_true",
        help="Print the updated calendar state as JSON after executing commands.",
    )
    run_parser.add_argument(
        "--storage",
        help="Optional path to a JSON file for persisting calendars and events between runs.",
    )

    show_parser = subparsers.add_parser("show-state", help="Print the current stored calendars and events")
    show_parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print the JSON output with indentation.",
    )
    show_parser.add_argument(
        "--storage",
        help="Optional path to a JSON file for persisting calendars and events between runs.",
    )

    return parser


def _read_commands(path: Optional[str]) -> List[str]:
    if path:
        command_path = Path(path)
        if not command_path.is_file():
            raise CalendarError(f"Commands file not found: {path}")
        content = command_path.read_text(encoding="utf-8")
    else:
        content = sys.stdin.read()
    return content.splitlines()


def _initialize_executor(storage_path: Optional[Path]) -> tuple[DSLExecutor, Optional[Path], InMemoryCalendarStorage]:
    storage = load_storage(storage_path)
    calendar_service = CalendarService(storage)
    event_service = EventService(calendar_service, storage)
    participant_service = ParticipantService(event_service)
    executor = DSLExecutor(calendar_service, event_service, participant_service=participant_service)
    return executor, storage_path, storage


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    storage_path = Path(args.storage) if args.storage else None
    try:
        executor, storage_path, storage = _initialize_executor(storage_path)
    except CalendarError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.command == "run":
        try:
            commands = _read_commands(args.commands)
        except (CalendarError, OSError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

        try:
            results = executor.execute(commands)
        except CalendarError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

        for result in results:
            print(result)

        if storage_path:
            dump_storage(storage, storage_path)

        if args.print_state:
            print(json.dumps(serialize_storage(storage), indent=2))
        return 0

    if args.command == "show-state":
        state = serialize_storage(storage)
        if args.pretty:
            print(json.dumps(state, indent=2))
        else:
            print(json.dumps(state))
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
