import { CalendarModel, createSeedData } from './calendar_model.mjs';
import { createStorageFromConfig, resolveConfig } from './config.mjs';
import { renderAgenda, renderCalendarList, renderInsights, renderStatus } from './ui_templates.mjs';

const state = {
  calendarId: null,
  rangeStart: null,
  rangeEnd: null,
};

const clientConfig = resolveConfig();
const storage = createStorageFromConfig(clientConfig);
const model = new CalendarModel({ storage });

function ensureSeeds() {
  if (model.listCalendars().length === 0) {
    model.importSeed(createSeedData());
  }
}

function wireControls() {
  const calendarsRegion = document.querySelector('[data-region="calendars"]');
  const agendaRegion = document.querySelector('[data-region="agenda"]');
  const insightsRegion = document.querySelector('[data-region="insights"]');
  const statusRegion = document.querySelector('[data-region="status"]');
  const calendarSelect = document.querySelector('#calendar-select');
  const rangeStart = document.querySelector('#range-start');
  const rangeEnd = document.querySelector('#range-end');
  const calendarForm = document.querySelector('#calendar-form');
  const eventForm = document.querySelector('#event-form');

  function describeSyncMode() {
    if (clientConfig.syncEnabled && clientConfig.remoteAdapter) {
      return `Sync: Remote (${clientConfig.apiBaseUrl || 'custom adapter'})`;
    }
    if (clientConfig.syncEnabled && !clientConfig.remoteAdapter) {
      return 'Sync: Local (remote adapter missing)';
    }
    return 'Sync: Local only';
  }

  function refreshStatus(message, tone = 'info') {
    statusRegion.innerHTML = renderStatus(`${message} · ${describeSyncMode()}`, tone);
  }

  function syncCalendarSelect(calendars) {
    calendarSelect.innerHTML = calendars
      .map(
        (calendar) => `
          <option value="${calendar.id}" ${calendar.id === state.calendarId ? 'selected' : ''}>${calendar.name}</option>`
      )
      .join('');
  }

  function refresh() {
    const calendars = model.listCalendars();
    if (!state.calendarId && calendars.length) {
      state.calendarId = calendars[0].id;
    }
    calendarsRegion.innerHTML = renderCalendarList(calendars, state.calendarId);
    syncCalendarSelect(calendars);

    const agenda = model.getAgenda(state.calendarId, {
      rangeStart: state.rangeStart,
      rangeEnd: state.rangeEnd,
    });
    agendaRegion.innerHTML = renderAgenda(agenda);

    insightsRegion.innerHTML = renderInsights(model.getInsights(state.calendarId));
    refreshStatus('Ready to weave the next calendar story.');
  }

  function handleCalendarClick(event) {
    const tile = event.target.closest('[data-calendar-id]');
    if (!tile) return;
    state.calendarId = tile.getAttribute('data-calendar-id');
    refresh();
  }

  function handleCalendarChange(event) {
    state.calendarId = event.target.value;
    refresh();
  }

  function handleCalendarForm(event) {
    event.preventDefault();
    const formData = new FormData(event.target);
    try {
      const owners = formData
        .get('owners')
        .split(',')
        .map((entry) => entry.trim())
        .filter(Boolean);
      const calendarId = model.createCalendar({
        name: formData.get('name'),
        owners,
        description: formData.get('description') ?? '',
      });
      state.calendarId = calendarId;
      event.target.reset();
      refresh();
      refreshStatus('Calendar created and spotlighted.');
    } catch (error) {
      refreshStatus(error.message, 'error');
    }
  }

  function handleEventForm(event) {
    event.preventDefault();
    const formData = new FormData(event.target);
    try {
      model.addEvent(state.calendarId, {
        title: formData.get('title'),
        start: formData.get('start'),
        end: formData.get('end'),
        timezone: formData.get('timezone') || 'UTC',
        description: formData.get('description') ?? '',
        location: formData.get('location') ?? '',
        tags: (formData.get('tags') ?? '')
          .split(',')
          .map((entry) => entry.trim())
          .filter(Boolean),
      });
      event.target.reset();
      refresh();
      refreshStatus('Event added to the schedule.');
    } catch (error) {
      refreshStatus(error.message, 'error');
    }
  }

  function handleRangeChange() {
    state.rangeStart = rangeStart.value || null;
    state.rangeEnd = rangeEnd.value || null;
    try {
      refresh();
    } catch (error) {
      refreshStatus(error.message, 'error');
    }
  }

  calendarsRegion.addEventListener('click', handleCalendarClick);
  calendarSelect.addEventListener('change', handleCalendarChange);
  calendarForm.addEventListener('submit', handleCalendarForm);
  eventForm.addEventListener('submit', handleEventForm);
  rangeStart.addEventListener('change', handleRangeChange);
  rangeEnd.addEventListener('change', handleRangeChange);

  refresh();
}

function prefillEventForm() {
  const now = new Date();
  const start = new Date(now.getTime() + 60 * 60 * 1000);
  const end = new Date(start.getTime() + 45 * 60 * 1000);
  const pad = (value) => `${value}`.padStart(2, '0');
  const toLocalInput = (date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  const startInput = document.querySelector('#event-start');
  const endInput = document.querySelector('#event-end');
  startInput.value = toLocalInput(start);
  endInput.value = toLocalInput(end);
}

document.addEventListener('DOMContentLoaded', () => {
  ensureSeeds();
  prefillEventForm();
  wireControls();
});
