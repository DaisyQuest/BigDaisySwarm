import { CalendarModel, createSeedData } from './calendar_model.mjs';
import { createStorageFromConfig, resolveConfig } from './config.mjs';
import { renderAgenda, renderCalendarList, renderInsights, renderStatus } from './ui_templates.mjs';
import { OidcSession } from './auth.mjs';
import { BasicAuth } from './basic_auth.mjs';
import { isOidcConfigComplete, shouldUseBasicAuthFallback } from './auth_config.mjs';
import { createRemoteAdapter } from './remote_adapter.mjs';
import { describeSyncState, scopedStorageKey } from './sync_status.mjs';

const state = {
  calendarId: null,
  rangeStart: null,
  rangeEnd: null,
};

function createSyncedStorage(baseStorage, remoteAdapter, { onError, onSuccess } = {}) {
  return {
    load() {
      return baseStorage.load();
    },
    save(snapshot) {
      baseStorage.save(snapshot);
      Promise.resolve()
        .then(() => remoteAdapter.save(snapshot))
        .then(() => {
          if (onSuccess) {
            onSuccess();
          }
        })
        .catch((error) => {
          if (onError) {
            onError(error);
          }
        });
    },
  };
}

function createSyncController({ config, baseStorage, remoteAdapter, syncState, updateStatus }) {
  let statusElement = null;

  const label = () =>
    describeSyncState({
      ...config,
      remoteActive: syncState.remoteActive,
      lastError: syncState.lastError,
    });
  const render = () => {
    if (statusElement) {
      statusElement.textContent = label();
    }
  };
  const mark = (active, errorMessage = '') => {
    syncState.remoteActive = Boolean(active);
    syncState.lastError = errorMessage;
    render();
  };

  const storage = remoteAdapter
    ? createSyncedStorage(baseStorage, remoteAdapter, {
        onError: (error) => {
          const message = error?.message || 'Remote sync failed';
          mark(false, message);
          updateStatus(`Remote save failed: ${message}`, 'error');
        },
        onSuccess: () => mark(true, ''),
      })
    : baseStorage;

  const syncNow = async (model) => {
    if (!remoteAdapter) {
      mark(false, 'Sync not configured');
      updateStatus('Sync not configured; working locally.', 'error');
      return;
    }
    try {
      updateStatus('Syncing with cloud...', 'info');
      const snapshot = await remoteAdapter.load();
      baseStorage.save(snapshot);
      model.replaceSnapshot(snapshot);
      mark(true, '');
      updateStatus('Cloud sync complete.', 'info');
    } catch (error) {
      const message = error?.message || 'Sync failed';
      mark(false, message);
      updateStatus(`Cloud sync failed: ${message}`, 'error');
    }
  };

  return {
    label,
    render,
    attach(element) {
      statusElement = element;
      render();
    },
    mark,
    syncNow,
    storage,
  };
}

async function initializeClient(statusRegion, clientConfig = null, authContext = {}) {
  const resolvedConfig = clientConfig || resolveConfig();
  const scopedKey = authContext.basicSession
    ? scopedStorageKey(resolvedConfig.storageKey, authContext.basicSession.username)
    : resolvedConfig.storageKey;
  const config = { ...resolvedConfig, storageKey: scopedKey };
  const syncState = { remoteActive: false, lastError: '' };
  const baseStorage = createStorageFromConfig({ ...config, syncEnabled: false });

  const syncLabel = () =>
    describeSyncState({
      ...config,
      remoteActive: syncState.remoteActive,
      lastError: syncState.lastError,
    });
  const updateStatus = (message, tone = 'info') => {
    statusRegion.innerHTML = renderStatus(`${message} · ${syncLabel()}`, tone);
  };

  let remoteAdapter = null;

  if (config.syncEnabled && !config.apiBaseUrl) {
    syncState.lastError = 'apiBaseUrl not set';
    updateStatus('Sync enabled but apiBaseUrl is not set', 'error');
  }

  if (config.syncEnabled && config.apiBaseUrl) {
    if (isOidcConfigComplete(config.auth)) {
      let authSession;
      try {
        authSession = new OidcSession(config.auth);
      } catch (error) {
        updateStatus(`Auth configuration error: ${error.message}`, 'error');
      }

      if (authSession) {
        try {
          await authSession.handleRedirectCallback(window.location.href);
        } catch (error) {
          updateStatus(`Authentication failed: ${error.message}`, 'error');
        }

        if (!authSession.hasValidAccessToken()) {
          const loginUrl = await authSession.buildAuthorizationUrl();
          updateStatus(
            `Sign in required. <a href="${loginUrl}">Continue with your identity provider</a>`,
            'error'
          );
          const authError = new Error('Authentication required');
          authError.loginUrl = loginUrl;
          throw authError;
        }

        const defaultJwks = config.auth?.issuer
          ? `${config.auth.issuer.replace(/\/$/, '')}/.well-known/jwks.json`
          : null;
        const jwksUri = config.auth?.jwksUri || defaultJwks;

        remoteAdapter = createRemoteAdapter({
          apiBaseUrl: config.apiBaseUrl,
          tokenProvider: () => authSession.requireAccessToken(),
          jwksUri,
          issuer: config.auth?.issuer,
          audience: config.auth?.audience || config.auth?.clientId,
          onWarn: (message) => updateStatus(message, 'error'),
        });
      }
    } else if (authContext.basicSession) {
      remoteAdapter = createRemoteAdapter({
        apiBaseUrl: config.apiBaseUrl,
        tokenProvider: () => authContext.basicSession.token,
        authScheme: 'Basic',
        validateAccessToken: false,
        onWarn: (message) => updateStatus(message, 'error'),
      });
    } else {
      syncState.lastError = 'Authentication required';
      updateStatus('Sync requires authentication; continuing locally.', 'error');
    }
  }

  const sync = createSyncController({ config, baseStorage, remoteAdapter, syncState, updateStatus });

  if (remoteAdapter) {
    try {
      const remoteSnapshot = await remoteAdapter.load();
      baseStorage.save(remoteSnapshot);
      sync.mark(true, '');
      updateStatus('Remote state loaded');
    } catch (error) {
      sync.mark(false, error?.message || 'Remote sync failed');
      updateStatus(`Remote sync unavailable: ${error.message}`, 'error');
    }
  }

  const model = new CalendarModel({ storage: sync.storage });
  if (!syncState.remoteActive && model.listCalendars().length === 0) {
    model.importSeed(createSeedData());
  }

  return { model, updateStatus, sync };
}

function wireControls({ model, updateStatus, sync }) {
  const calendarsRegion = document.querySelector('[data-region="calendars"]');
  const agendaRegion = document.querySelector('[data-region="agenda"]');
  const insightsRegion = document.querySelector('[data-region="insights"]');
  const calendarSelect = document.querySelector('#calendar-select');
  const rangeStart = document.querySelector('#range-start');
  const rangeEnd = document.querySelector('#range-end');
  const calendarForm = document.querySelector('#calendar-form');
  const eventForm = document.querySelector('#event-form');
  const syncButton = document.querySelector('#sync-button');
  const syncStatus = document.querySelector('[data-region="sync-status"]');
  const refreshStatus = (message, tone = 'info') => updateStatus(message, tone);

  if (syncStatus) {
    sync.attach(syncStatus);
  }
  if (syncButton) {
    syncButton.addEventListener('click', async () => {
      syncButton.disabled = true;
      await sync.syncNow(model);
      syncButton.disabled = false;
    });
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

  const startApp = async (session = null) => {
    authPanel.classList.add('hidden');
    layout.classList.remove('hidden');
    try {
      const scopedConfig = session
        ? { ...clientConfig, storageKey: scopedStorageKey(clientConfig.storageKey, session.username) }
        : clientConfig;
      const { model, updateStatus, sync } = await initializeClient(statusRegion, scopedConfig, {
        basicSession: session,
      });
      prefillEventForm();
      wireControls({ model, updateStatus, sync });
      updateStatus('OIDC not configured; using basic auth for sync + local access.');
    } catch (error) {
      showStatus(error?.message || 'Unable to start the client.');
    }
  };

  const hydrateFromSession = () => {
    const existing = auth.currentSession();
    if (existing) {
      showStatus(`Signed in as ${existing.username}`, 'info');
      startApp(existing);
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
      startApp(session);
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
      startApp(session);
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
      const { model, updateStatus, sync } = await initializeClient(statusRegion, clientConfig);
      prefillEventForm();
      wireControls({ model, updateStatus, sync });
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
