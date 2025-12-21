# Calendar CLI Client User Guide

This CLI executes the Big Daisy Swarm calendar DSL against the in-memory services provided by `bigdaisyswarm.calendar`. Use it to script calendar workflows, persist state to disk, and inspect the current calendars and events.

## Prerequisites

- Python 3.11+.
- The `bigdaisyswarm` library available on `PYTHONPATH` (for this repository, run commands from the repo root or prefix with `PYTHONPATH=src`).

## Running commands

Execute DSL statements with the `run` subcommand. Commands can be provided via a file or standard input.

```bash
PYTHONPATH=src python -m calendar_cli_client.cli run \
  --storage CalendarApp/calendar_state.json \
  --commands sample.dsl \
  --print-state
```

- `--storage`: Optional path to a JSON file for persisting calendars and events across runs. If omitted, the session is in-memory only.
- `--commands`: Path to a file containing one DSL command per line. When omitted, the CLI reads from stdin.
- `--print-state`: Emit the updated calendars and events as JSON after executing commands.

### Example DSL snippet

```
CREATE_CALENDAR name="Team Calendar" owners=alice@example.com,bob@example.com
CREATE_EVENT calendar=<calendar_id> title="Kickoff" start=2025-01-01T10:00Z end=2025-01-01T11:00Z timezone=UTC
LIST_EVENTS calendar=<calendar_id>
```

Replace `<calendar_id>` with the identifier returned by `CREATE_CALENDAR`.

## Inspecting stored state

Use `show-state` to print the stored calendars and events without running new commands:

```bash
PYTHONPATH=src python -m calendar_cli_client.cli show-state --storage CalendarApp/calendar_state.json --pretty
```

- Omitting `--storage` prints an empty in-memory state.
- `--pretty` formats JSON with 2-space indentation for readability.

## Error handling

- Errors in DSL parsing or validation are printed to stderr and return a non-zero exit code.
- When command execution fails, the CLI does **not** write changes to the storage file, preserving the previous state.
- Invalid or unreadable storage files also cause an error and prevent execution.

## Persistence format

The storage file is a JSON document with 2-space indentation and a trailing newline:

```json
{
  "calendars": [{ "id": "work", "name": "Work", "owners": ["alice@example.com"], "description": "" }],
  "events": [
    {
      "id": "evt-1",
      "calendar_id": "work",
      "title": "Planning",
      "start": "2025-01-01T10:00:00+00:00",
      "end": "2025-01-01T11:00:00+00:00",
      "timezone": "UTC",
      "participants": {},
      "metadata": {},
      "overrides": {},
      "canceled": false
    }
  ]
}
```

This format is produced automatically by the CLI; manual edits should follow the same structure.
