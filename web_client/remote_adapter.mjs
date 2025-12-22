import { verifyJwt, authUtils } from "./auth.mjs";

const normalizeUrl = (url) => url.replace(/\/+$/, "");

function assertSecureUrl(url) {
  authUtils.assertHttps(url);
}

const asObject = (value) => {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return value;
};

function normalizeCalendarFromServer(calendar) {
  return {
    id: `${calendar.id ?? ""}`,
    name: `${calendar.name ?? ""}`.trim(),
    owners: Array.isArray(calendar.owners) ? calendar.owners : [],
    description: `${calendar.description ?? ""}`.trim(),
  };
}

function normalizeEventFromServer(event) {
  const calendarId = event.calendar_id ?? event.calendarId ?? event.calendar;
  if (!calendarId) {
    throw new Error("Remote event missing required field 'calendar_id'");
  }
  for (const field of ["id", "title", "start", "end"]) {
    if (event[field] === undefined || event[field] === null || event[field] === "") {
      throw new Error(`Remote event missing required field '${field}'`);
    }
  }
  return {
    id: `${event.id}`,
    calendarId: `${calendarId}`,
    title: `${event.title}`,
    start: event.start,
    end: event.end,
    timezone: event.timezone ?? "UTC",
    recurrence: event.recurrence ?? null,
    participants: asObject(event.participants),
    metadata: asObject(event.metadata),
    overrides: asObject(event.overrides),
    canceled: Boolean(event.canceled),
  };
}

function normalizeSnapshotFromServer(payload) {
  if (!payload || typeof payload !== "object") {
    throw new Error("Remote state must be an object with calendars and events");
  }
  if (!Array.isArray(payload.calendars) || !Array.isArray(payload.events)) {
    throw new Error("Remote state missing calendars/events");
  }
  const calendars = payload.calendars.map(normalizeCalendarFromServer);
  const events = payload.events.map(normalizeEventFromServer);
  return { calendars, events };
}

function normalizeEventForServer(event) {
  const calendarId = event.calendarId ?? event.calendar_id;
  if (!calendarId) {
    throw new Error("Event missing calendarId for remote sync");
  }
  const required = ["id", "title", "start", "end"];
  const missing = required.filter((field) => !event[field]);
  if (missing.length) {
    throw new Error(`Event ${event.id ?? "<unknown>"} missing required fields: ${missing.join(", ")}`);
  }
  return {
    id: `${event.id}`,
    calendar_id: `${calendarId}`,
    title: `${event.title}`,
    start: event.start,
    end: event.end,
    timezone: event.timezone || "UTC",
    recurrence: event.recurrence ?? null,
    participants: asObject(event.participants),
    metadata: asObject(event.metadata),
    overrides: asObject(event.overrides),
    canceled: Boolean(event.canceled),
  };
}

function normalizeSnapshotForServer(snapshot) {
  if (!snapshot || typeof snapshot !== "object") {
    throw new Error("Snapshot must be an object with calendars and events");
  }
  if (!Array.isArray(snapshot.calendars) || !Array.isArray(snapshot.events)) {
    throw new Error("Snapshot must include calendar and event arrays");
  }
  const calendars = snapshot.calendars;
  const events = snapshot.events;
  return {
    calendars,
    events: events.map(normalizeEventForServer),
  };
}

export function createRemoteAdapter({
  apiBaseUrl,
  tokenProvider,
  jwksUri,
  issuer,
  audience,
  authScheme = "Bearer",
  validateAccessToken = true,
  fetchImpl = null,
  now = () => Date.now(),
  onWarn = null,
} = {}) {
  if (!apiBaseUrl) {
    throw new Error("apiBaseUrl is required for remote sync");
  }
  if (typeof tokenProvider !== "function") {
    throw new Error("tokenProvider is required for remote sync");
  }
  const shouldValidate = validateAccessToken && authScheme !== "Basic";
  if (shouldValidate && !jwksUri) {
    throw new Error("jwksUri is required to validate remote sync tokens");
  }
  assertSecureUrl(apiBaseUrl);
  if (jwksUri) {
    assertSecureUrl(jwksUri);
  }

  const fetcher = fetchImpl || fetch;
  let jwksCache = null;
  const warn = onWarn || ((message) => console.warn(message));

  function buildAuthorizationHeader(token) {
    const raw = `${token ?? ""}`.trim();
    if (!raw) {
      throw new Error("Missing access token");
    }
    if (/^\w+\s+\S+/.test(raw)) {
      return raw;
    }
    const scheme = authScheme || "Bearer";
    return `${scheme} ${raw}`.trim();
  }

  async function fetchJwks() {
    if (jwksCache) return jwksCache;
    const response = await fetcher(jwksUri, { headers: { Accept: "application/json" } });
    if (!response.ok) {
      throw new Error(`Failed to fetch JWKS (${response.status})`);
    }
    jwksCache = await response.json();
    return jwksCache;
  }

  async function validatedToken() {
    const token = await tokenProvider();
    if (shouldValidate && jwksUri) {
      const jwks = await fetchJwks();
      await verifyJwt(token, jwks, { issuer, audience, now });
    }
    return buildAuthorizationHeader(token);
  }

  async function authorizedFetch(path, init = {}) {
    const authorization = await validatedToken();
    const headers = { ...(init.headers || {}), Authorization: authorization };
    const url = `${normalizeUrl(apiBaseUrl)}/${path.replace(/^\/+/, "")}`;
    return fetcher(url, { ...init, headers });
  }

  async function load() {
    const response = await authorizedFetch("/state", { method: "GET" });
    if (!response.ok) {
      throw new Error(`Remote load failed with status ${response.status}`);
    }
    const payload = await response.json();
    return normalizeSnapshotFromServer(payload);
  }

  async function save(snapshot) {
    let prepared = null;
    try {
      prepared = normalizeSnapshotForServer(snapshot);
    } catch (error) {
      warn(`Failed to persist remote state: ${error.message}`);
      throw error;
    }

    try {
      const response = await authorizedFetch("/state", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(prepared),
      });
      if (!response.ok) {
        throw new Error(`Remote save failed with status ${response.status}`);
      }
    } catch (error) {
      warn(`Failed to persist remote state: ${error.message}`);
      throw error;
    }
  }

  return { load, save };
}
