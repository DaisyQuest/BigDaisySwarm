import { CalendarModel, createSeedData } from './calendar_model.mjs';
import { createStorageFromConfig, resolveConfig } from './config.mjs';
import { renderAgenda, renderCalendarList, renderInsights, renderStatus } from './ui_templates.mjs';
import { OidcSession } from './auth.mjs';
import { BasicAuth } from './basic_auth.mjs';
import { isOidcConfigComplete, shouldUseBasicAuthFallback } from './auth_config.mjs';
import { createRemoteAdapter } from './remote_adapter.mjs';

const state = {
  calendarId: null,
  rangeStart: null,
  rangeEnd: null,
};

function createSyncedStorage(baseStorage, remoteAdapter, { onError } = {}) {
  return {
    load() {
      return baseStorage.load();
    },
    save(snapshot) {
      baseStorage.save(snapshot);
      Promise.resolve()
        .then(() => remoteAdapter.save(snapshot))
        .catch((error) => {
          if (onError) {
            onError(error);
          }
        });
    },
  };
}

function describeSyncMode(config, remoteActive) {
  if (remoteActive) {
    return `Sync: Remote (${config.apiBaseUrl || 'adapter'})`;
  }
  if (config.syncEnabled && !remoteActive) {
    return 'Sync: Local (remote unavailable)';
  }
  return 'Sync: Local only';
}

async function initializeClient(statusRegion, clientConfig = null) {
  const resolvedConfig = clientConfig || resolveConfig();
  const baseStorage = createStorageFromConfig(resolvedConfig);
  let remoteActive = false;
  let remoteAdapter = null;

  const syncLabel = () => describeSyncMode(resolvedConfig, remoteActive);
  const updateStatus = (message, tone = 'info') => {
    statusRegion.innerHTML = renderStatus(`${message} · ${syncLabel()}`, tone);
  };

  if (resolvedConfig.syncEnabled && !resolvedConfig.apiBaseUrl) {
    const error = new Error('Sync enabled but apiBaseUrl is not set');
    updateStatus(error.message, 'error');
    throw error;
  }

  if (resolvedConfig.syncEnabled && resolvedConfig.apiBaseUrl && isOidcConfigComplete(resolvedConfig.auth)) {
    let authSession;
    try {
      authSession = new OidcSession(resolvedConfig.auth);
    } catch (error) {
      updateStatus(`Auth configuration error: ${error.message}`, 'error');
      throw error;
    }

    try {
      await authSession.handleRedirectCallback(window.location.href);
    } catch (error) {
      updateStatus(`Authentication failed: ${error.message}`, 'error');
      throw error;
    }

    if (!authSession.hasValidAccessToken()) {
      const loginUrl = await authSession.buildAuthorizationUrl();
      updateStatus(`Sign in required. <a href="${loginUrl}">Continue with your identity provider</a>`, 'error');
      const authError = new Error('Authentication required');
      authError.loginUrl = loginUrl;
      throw authError;
    }

    const defaultJwks = resolvedConfig.auth?.issuer
      ? `${resolvedConfig.auth.issuer.replace(/\/$/, '')}/.well-known/jwks.json`
      : null;
    const jwksUri = resolvedConfig.auth?.jwksUri || defaultJwks;

    remoteAdapter = createRemoteAdapter({
      apiBaseUrl: resolvedConfig.apiBaseUrl,
      tokenProvider: () => authSession.requireAccessToken(),
      jwksUri,
      issuer: resolvedConfig.auth?.issuer,
      audience: resolvedConfig.auth?.audience || resolvedConfig.auth?.clientId,
      onWarn: (message) => updateStatus(message, 'error'),
    });

    try {
      const remoteSnapshot = await remoteAdapter.load();
      baseStorage.save(remoteSnapshot);
      remoteActive = true;
      updateStatus('Remote state loaded');
    } catch (error) {
      updateStatus(`Remote sync failed: ${error.message}`, 'error');
      throw error;
    }
  }

  const storage = remoteAdapter
    ? createSyncedStorage(baseStorage, remoteAdapter, {
        onError: (error) => updateStatus(`Remote save failed: ${error.message}`, 'error'),
      })
    : baseStorage;

  const model = new CalendarModel({ storage });
  if (!remoteActive && model.listCalendars().length === 0) {
    model.importSeed(createSeedData());
  }

  return { model, updateStatus };
}

function wireControls({ model, updateStatus }) {
  const calendarsRegion = document.querySelector('[data-region="calendars"]');
  const agendaRegion = document.querySelector('[data-region="agenda"]');
  const insightsRegion = document.querySelector('[data-region="insights"]');
  const calendarSelect = document.querySelector('#calendar-select');
  const rangeStart = document.querySelector('#range-start');
  const rangeEnd = document.querySelector('#range-end');
  const calendarForm = document.querySelector('#calendar-form');
  const eventForm = document.querySelector('#event-form');
  const refreshStatus = (message, tone = 'info') => updateStatus(message, tone);

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
  const toLocalInput = (date) =>
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  const startInput = document.querySelector('#event-start');
  const endInput = document.querySelector('#event-end');
  startInput.value = toLocalInput(start);
  endInput.value = toLocalInput(end);
}

function wireBasicAuth({ statusRegion, clientConfig }) {
  const authStatus = document.querySelector('[data-region="auth-status"]');
  const authPanel = document.querySelector('[data-region="auth"]');
  const layout = document.querySelector('.layout');
  const loginForm = document.querySelector('#login-form');
  const registerForm = document.querySelector('#registration-form');
  const auth = new BasicAuth();

  const showStatus = (message, tone = 'error') => {
    const content = renderStatus(message, tone);
    authStatus.innerHTML = content;
    statusRegion.innerHTML = content;
  };

  const startApp = async () => {
    authPanel.classList.add('hidden');
    layout.classList.remove('hidden');
    try {
      const { model, updateStatus } = await initializeClient(statusRegion, { ...clientConfig, syncEnabled: false });
      prefillEventForm();
      wireControls({ model, updateStatus });
      updateStatus('OIDC not configured; using local basic auth.');
    } catch (error) {
      showStatus(error?.message || 'Unable to start the client.');
    }
  };

  const hydrateFromSession = () => {
    const existing = auth.currentSession();
    if (existing) {
      showStatus(`Signed in as ${existing.username}`, 'info');
      startApp();
    } else {
      showStatus('OIDC not configured; sign up or log in with basic auth to continue.', 'error');
    }
  };

  loginForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const data = new FormData(event.target);
    try {
      const session = auth.authenticate(data.get('username'), data.get('password'));
      showStatus(`Signed in as ${session.username}`, 'info');
      startApp();
    } catch (error) {
      showStatus(error.message);
    }
  });

  registerForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const data = new FormData(event.target);
    try {
      const session = auth.register(data.get('username'), data.get('password'));
      showStatus(`Registered ${session.username}. You are now signed in.`, 'info');
      startApp();
    } catch (error) {
      showStatus(error.message);
    }
  });

  hydrateFromSession();
}

document.addEventListener('DOMContentLoaded', () => {
  const statusRegion = document.querySelector('[data-region="status"]');
  const authPanel = document.querySelector('[data-region="auth"]');
  const layout = document.querySelector('.layout');
  const clientConfig = resolveConfig();

  if (shouldUseBasicAuthFallback(clientConfig)) {
    authPanel.classList.remove('hidden');
    layout.classList.add('hidden');
    wireBasicAuth({ statusRegion, clientConfig });
    return;
  }

  authPanel.classList.add('hidden');
  layout.classList.remove('hidden');

  const boot = async () => {
    try {
      const { model, updateStatus } = await initializeClient(statusRegion, clientConfig);
      prefillEventForm();
      wireControls({ model, updateStatus });
      updateStatus('Ready to weave the next calendar story.');
    } catch (error) {
      const message = error?.loginUrl
        ? `Authentication required. <a href="${error.loginUrl}">Continue with your identity provider</a>`
        : error?.message || 'Unable to start the client.';
      statusRegion.innerHTML = renderStatus(message, 'error');
    }
  };
  boot();
});
