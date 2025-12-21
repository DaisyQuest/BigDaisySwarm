import json
import subprocess
from pathlib import Path

WEB_ROOT = Path(__file__).resolve().parents[1] / "web_client"
CALENDAR_MODEL = WEB_ROOT / "calendar_model.mjs"
UI_TEMPLATES = WEB_ROOT / "ui_templates.mjs"
INDEX_HTML = WEB_ROOT / "index.html"
DOCKERFILE = WEB_ROOT / "Dockerfile"
NGINX_CONF = WEB_ROOT / "nginx.conf"


def run_node_json(script: str) -> dict:
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_calendar_model_adds_and_filters_events():
    script = f"""
import {{ CalendarModel, MemoryStorage, createSeedData }} from 'file://{CALENDAR_MODEL.as_posix()}';
const model = new CalendarModel({{ storage: new MemoryStorage() }});
model.importSeed(createSeedData());
const focus = model.listCalendars()[0].id;
const extraId = model.addEvent(focus, {{
  title: 'Deep Work Session',
  start: '2025-02-01T09:00:00Z',
  end: '2025-02-01T10:45:00Z',
  location: 'Studio',
  tags: ['focus', 'flow']
}});
const fullAgenda = model.getAgenda(focus);
const windowAgenda = model.getAgenda(focus, {{
  rangeStart: '2025-02-01T00:00:00Z',
  rangeEnd: '2025-02-02T00:00:00Z'
}});
const decorated = model.listEvents(focus).find((event) => event.id === extraId);
console.log(JSON.stringify({{
  total: fullAgenda.reduce((sum, slot) => sum + slot.events.length, 0),
  range: windowAgenda.reduce((sum, slot) => sum + slot.events.length, 0),
  duration: decorated.durationMinutes,
  firstTag: decorated.tags[0],
  startLabel: decorated.startLabel,
}}));
"""
    result = run_node_json(script)
    assert result["total"] >= result["range"] >= 1
    assert result["duration"] == 105
    assert result["firstTag"] == "focus"
    assert ":" in result["startLabel"]


def test_calendar_model_validation_and_storage_fallback():
    script = f"""
import {{ CalendarModel, createBrowserStorage }} from 'file://{CALENDAR_MODEL.as_posix()}';
const errors = [];
const model = new CalendarModel({{ storage: createBrowserStorage('non-existent') }});
try {{
  model.createCalendar({{ name: '', owners: [''] }});
}} catch (error) {{
  errors.push(error.message);
}}
try {{
  model.listEvents('missing');
}} catch (error) {{
  errors.push(error.message);
}}
const stubStorage = {{
  saves: 0,
  save(snapshot) {{ this.saves += 1; this.snapshot = snapshot; }}
}};
const custom = new CalendarModel({{ storage: stubStorage }});
const calendarId = custom.createCalendar({{ name: 'Board', owners: 'ops@example.com' }});
custom.addEvent(calendarId, {{
  title: 'Curated Review',
  start: '2025-03-10T10:00:00Z',
  end: '2025-03-10T11:00:00Z',
}});
let rangeError = '';
try {{
  custom.listEvents(calendarId, {{ rangeStart: '2025-03-11T00:00:00Z', rangeEnd: '2025-03-10T00:00:00Z' }});
}} catch (error) {{
  rangeError = error.message;
}}
console.log(JSON.stringify({{
  errors,
  saves: stubStorage.saves,
  insights: custom.getInsights(calendarId),
  rangeError,
}}));
"""
    result = run_node_json(script)
    assert "Calendar name is required" in result["errors"][0]
    assert "Unknown calendar" in result["errors"][1]
    assert result["saves"] >= 2  # calendar + event
    assert result["insights"]["eventCount"] == 1
    assert "rangeStart must be before rangeEnd" in result["rangeError"]


def test_calendar_model_normalization_and_colors():
    script = f"""
import {{ CalendarModel, MemoryStorage }} from 'file://{CALENDAR_MODEL.as_posix()}';
const model = new CalendarModel({{ storage: new MemoryStorage() }});
const calendarId = model.createCalendar({{ name: 'Studio', owners: 'ops@example.com, design@example.com', description: '  Space ' }});
const firstId = model.addEvent(calendarId, {{
  title: 'Jam',
  start: '2025-04-01T10:00:00Z',
  end: '2025-04-01T11:30:00Z',
  tags: 'focus'
}});
const secondId = model.addEvent(calendarId, {{
  title: 'Retro',
  start: '2025-04-02T10:00:00Z',
  end: '2025-04-02T11:00:00Z',
  tags: ['team', 'learning']
}});
let error = '';
try {{
  model.addEvent(calendarId, {{ title: 'Broken', start: 123, end: '2025-04-03T11:00:00Z' }});
}} catch (err) {{
  error = err.message;
}}
const calendars = model.listCalendars();
const events = model.listEvents(calendarId);
const firstEvent = events.find((evt) => evt.id === firstId);
const secondEvent = events.find((evt) => evt.id === secondId);
console.log(JSON.stringify({{
  owners: calendars[0].owners,
  description: calendars[0].description,
  firstTags: firstEvent.tags,
  colorsMatch: firstEvent.color === secondEvent.color,
  duration: firstEvent.durationMinutes,
  error,
}}));
"""
    result = run_node_json(script)
    assert result["owners"] == ["ops@example.com", "design@example.com"]
    assert result["description"] == "Space"
    assert result["firstTags"] == ["focus"]
    assert result["colorsMatch"] is True
    assert result["duration"] == 90
    assert "start must be a date or ISO string" in result["error"]


def test_calendar_model_insights_span_and_highlight():
    script = f"""
import {{ CalendarModel, MemoryStorage }} from 'file://{CALENDAR_MODEL.as_posix()}';
const model = new CalendarModel({{ storage: new MemoryStorage() }});
const calendarId = model.createCalendar({{ name: 'Flow', owners: ['flow@example.com'] }});
model.addEvent(calendarId, {{
  title: 'Deep Focus',
  start: '2025-05-01T09:00:00Z',
  end: '2025-05-01T11:30:00Z'
}});
model.addEvent(calendarId, {{
  title: 'Check-in',
  start: '2025-05-03T10:00:00Z',
  end: '2025-05-03T10:30:00Z'
}});
const insights = model.getInsights(calendarId);
const emptyInsights = new CalendarModel({{ storage: new MemoryStorage() }}).getInsights();
console.log(JSON.stringify({{
  spanDays: insights.spanDays,
  highlight: insights.highlight,
  total: insights.totalDurationMinutes,
  emptyHighlight: emptyInsights.highlight,
  emptySpan: emptyInsights.spanDays,
}}));
"""
    result = run_node_json(script)
    assert result["spanDays"] == 3
    assert result["highlight"] == "Deep Focus"
    assert result["total"] == 180
    assert result["emptyHighlight"] == ""
    assert result["emptySpan"] == 0


def test_create_browser_storage_uses_local_storage():
    script = f"""
import {{ createBrowserStorage, createSeedData }} from 'file://{CALENDAR_MODEL.as_posix()}';
globalThis.localStorage = {{
  store: new Map(),
  getItem(key) {{ return this.store.has(key) ? this.store.get(key) : null; }},
  setItem(key, value) {{ this.store.set(key, value); }},
}};
const storage = createBrowserStorage('demo-key');
storage.save(createSeedData());
const loaded = storage.load();
console.log(JSON.stringify({{
  calendarCount: loaded.calendars.length,
  stored: globalThis.localStorage.getItem('demo-key') !== null
}}));
"""
    result = run_node_json(script)
    assert result["calendarCount"] == 2
    assert result["stored"] is True


def test_create_browser_storage_handles_invalid_payload():
    script = f"""
import {{ createBrowserStorage }} from 'file://{CALENDAR_MODEL.as_posix()}';
let warned = false;
globalThis.localStorage = {{
  store: new Map([['demo-key', 'not-json']]),
  getItem(key) {{ return this.store.has(key) ? this.store.get(key) : null; }},
  setItem(key, value) {{ this.store.set(key, value); }},
}};
const originalWarn = console.warn;
console.warn = () => {{ warned = true; }};
const storage = createBrowserStorage('demo-key');
const loaded = storage.load();
console.warn = originalWarn;
console.log(JSON.stringify({{
  warned,
  calendars: loaded.calendars.length,
  events: loaded.events.length
}}));
"""
    result = run_node_json(script)
    assert result["warned"] is True
    assert result["calendars"] == 0
    assert result["events"] == 0


def test_create_browser_storage_handles_exceptions():
    script = f"""
import {{ createBrowserStorage }} from 'file://{CALENDAR_MODEL.as_posix()}';
let warnings = [];
globalThis.localStorage = {{
  getItem(key) {{ throw new Error('boom'); }},
  setItem(key, value) {{ throw new Error('persist'); }},
}};
const originalWarn = console.warn;
console.warn = (...args) => {{ warnings.push(args[0]); }};
const storage = createBrowserStorage('demo-key');
const loaded = storage.load();
storage.save({{ calendars: [], events: [] }});
console.warn = originalWarn;
console.log(JSON.stringify({{
  warnings,
  calendars: loaded.calendars.length,
  events: loaded.events.length
}}));
"""
    result = run_node_json(script)
    assert result["calendars"] == 0
    assert result["events"] == 0
    assert any("Unable to parse stored calendar state" in warning for warning in result["warnings"])
    assert any("Unable to persist calendar state" in warning for warning in result["warnings"])


def test_calendar_model_range_filters_and_errors():
    script = f"""
import {{ CalendarModel, MemoryStorage }} from 'file://{CALENDAR_MODEL.as_posix()}';
const model = new CalendarModel({{ storage: new MemoryStorage() }});
const calendarId = model.createCalendar({{ name: 'Range', owners: ['ops@example.com'] }});
model.addEvent(calendarId, {{
  title: 'Inside',
  start: '2025-06-01T10:00:00Z',
  end: '2025-06-01T11:00:00Z'
}});
model.addEvent(calendarId, {{
  title: 'Outside',
  start: '2025-07-01T10:00:00Z',
  end: '2025-07-01T11:00:00Z'
}});
let error = '';
try {{
  model.listEvents(calendarId, {{ rangeStart: 42 }});
}} catch (err) {{
  error = err.message;
}}
const ranged = model.listEvents(calendarId, {{
  rangeStart: '2025-06-01T00:00:00Z',
  rangeEnd: '2025-06-15T00:00:00Z'
}});
console.log(JSON.stringify({{
  count: ranged.length,
  title: ranged[0].title,
  error,
}}));
"""
    result = run_node_json(script)
    assert result["count"] == 1
    assert result["title"] == "Inside"
    assert "rangeStart must be a date or ISO string" in result["error"]


def test_configurable_storage_supports_remote_adapter_and_fallback():
    script = f"""
import {{ mergeConfig, createStorageFromConfig, resolveConfig }} from 'file://{WEB_ROOT.joinpath("config.mjs").as_posix()}';
let remoteLoadOk = true;
const snapshots = {{
  remote: {{ calendars: [{{ id: 'remote', name: 'Remote' }}], events: [] }},
  local: {{ calendars: [{{ id: 'local', name: 'Local' }}], events: [] }},
}};
const remoteAdapter = {{
  load() {{
    if (!remoteLoadOk) throw new Error('remote down');
    return snapshots.remote;
  }},
  save() {{
    throw new Error('save failed');
  }},
}};
const logger = {{ warnings: [], warn(msg) {{ this.warnings.push(msg); }} }};
const storage = createStorageFromConfig(mergeConfig({{ syncEnabled: true, remoteAdapter, useLocalStorage: false }}), {{ logger }});
storage.save(snapshots.local);
remoteLoadOk = false;
const loaded = storage.load();
console.log(JSON.stringify({{
  loaded,
  warnings: logger.warnings,
  resolvedSync: resolveConfig({{ syncEnabled: true }}).syncEnabled
}}));
"""
    result = run_node_json(script)
    assert result["loaded"]["calendars"][0]["id"] == "local"
    assert any("Remote save failed" in warning for warning in result["warnings"])
    assert any("Remote load failed" in warning for warning in result["warnings"])
    assert result["resolvedSync"] is True


def test_ui_templates_and_shell():
    script = f"""
import {{ renderAgenda, renderCalendarList, renderInsights, renderStatus }} from 'file://{UI_TEMPLATES.as_posix()}';
const agendaEmpty = renderAgenda([]);
const agendaFilled = renderAgenda([{{ date: '2025-02-01', events: [{{ title: 'Design Clinic', startLabel: '09:00', endLabel: '10:00', durationMinutes: 60, color: '#0ea5e9', location: 'Loft', description: 'Crisp briefs', tags: ['design'] }}] }}]);
const calendars = renderCalendarList([{{ id: 'cal-A', name: 'Studio', owners: ['ops@example.com'], description: 'Delivery' }}], 'cal-A');
const insights = renderInsights({{ calendarCount: 2, eventCount: 4, totalDurationMinutes: 90, spanDays: 3, highlight: 'Pitch' }});
const status = renderStatus('Oops', 'error');
const statusInfo = renderStatus('Ready', 'info');
console.log(JSON.stringify({{
  emptyLine: agendaEmpty.includes('No events in view'),
  emptyCalendars: renderCalendarList([]).includes('No calendars yet'),
  badgePresent: calendars.includes('badge'),
  highlightPresent: insights.includes('Pitch'),
  agendaCard: agendaFilled.includes('Design Clinic') && agendaFilled.includes('Loft'),
  statusTone: status.includes('error'),
  statusInfo: statusInfo.includes('status info'),
}}));
"""
    result = run_node_json(script)
    assert result["emptyLine"] is True
    assert result["emptyCalendars"] is True
    assert result["badgePresent"] is True
    assert result["highlightPresent"] is True
    assert result["agendaCard"] is True
    assert result["statusTone"] is True
    assert result["statusInfo"] is True


def test_index_shell_contains_regions():
    html = INDEX_HTML.read_text(encoding="utf-8")
    for marker in [
        'data-region="calendars"',
        'data-region="agenda"',
        'data-region="insights"',
        'data-region="status"',
        'id="calendar-form"',
        'id="event-form"',
    ]:
        assert marker in html
    assert '<script type="module" src="./app.js"></script>' in html


def test_web_client_dockerfile_and_nginx_conf():
    dockerfile_text = DOCKERFILE.read_text(encoding="utf-8")
    assert "nginx:1.27-alpine" in dockerfile_text
    assert "COPY web_client/nginx.conf" in dockerfile_text

    nginx_text = NGINX_CONF.read_text(encoding="utf-8")
    assert "healthz" in nginx_text
    assert "application/javascript mjs" in nginx_text
    assert "try_files $uri $uri/ /index.html;" in nginx_text
