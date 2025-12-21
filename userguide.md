# Calendar Swing Client User Guide

This guide explains how to build and exercise the Java Swing calendar client that pairs with the Big Daisy Swarm backend models.

## Project layout
- `swing/src/`: Java sources for the Swing client, including an in-memory backend for demos and tests.
- `tests/test_swing_client.py`: Pytest wrapper that compiles and runs the Java harness.
- `CalendarApp/meetings/`: Agent meeting history for the CalendarApp project.

## Building the Swing client
Compile all Swing sources into a target directory (e.g., `out/`):

```bash
javac -d out $(find swing/src -name "*.java")
```

## Running the Swing demo
Launch the sample UI populated with in-memory events:

```bash
java -cp out calendarapp.swing.CalendarSwingApp
```

By default the UI opens in non-headless mode. The data comes from `InMemoryCalendarBackend.sampleData()`, which mirrors the API surface expected by richer backends.

## Connecting to the backend server
The Swing client can synchronize with the live backend by using the HTTP backend:

```java
CalendarBackend backend = new HttpCalendarBackend("http://localhost:8080");
CalendarSwingClient client = new CalendarSwingClient(backend);
client.loadAllEvents();
```

`HttpCalendarBackend` talks to the server using JSON endpoints for listing, canceling, rescheduling, and upserting events. It accepts query parameters for `calendarId`, `date`, and `includeCanceled`, matching the Python backend’s API surface.

## Running tests
The repository test suite includes the Swing harness. From the repo root:

```bash
PYTHONPATH=src pytest --maxfail=1
```

`tests/test_swing_client.py` compiles the Java sources and executes `calendarapp.swing.CalendarSwingClientTest` in headless mode, ensuring the backend filters, sorting, and UI table population remain correct across repeated runs.
