const clone = (value) => JSON.parse(JSON.stringify(value ?? {}));

const createEmptySnapshot = () => ({ calendars: [], events: [] });

const normalizeCalendar = (calendar) => ({
  id: calendar.id,
  name: (calendar.name ?? "").trim(),
  owners: Array.isArray(calendar.owners)
    ? calendar.owners.map((owner) => owner.trim()).filter(Boolean)
    : [],
  description: (calendar.description ?? "").trim(),
});

const normalizeEvent = (event) => ({
  id: event.id,
  calendarId: event.calendarId,
  title: (event.title ?? "").trim(),
  start: event.start,
  end: event.end,
  timezone: event.timezone ?? "UTC",
  description: (event.description ?? "").trim(),
  location: (event.location ?? "").trim(),
  color: event.color ?? "#2563eb",
  tags: Array.isArray(event.tags) ? event.tags : [],
});

const normalizeSnapshot = (snapshot) => {
  if (!snapshot) {
    return createEmptySnapshot();
  }
  const calendars = Array.isArray(snapshot.calendars)
    ? snapshot.calendars.map(normalizeCalendar)
    : [];
  const events = Array.isArray(snapshot.events)
    ? snapshot.events.map(normalizeEvent)
    : [];
  return { calendars, events };
};

export class MemoryStorage {
  constructor(snapshot = null) {
    this.snapshot = snapshot ? normalizeSnapshot(snapshot) : createEmptySnapshot();
  }

  load() {
    return clone(this.snapshot);
  }

  save(snapshot) {
    this.snapshot = normalizeSnapshot(snapshot);
  }
}

export function createBrowserStorage(key = "calendarapp-web-state") {
  try {
    if (typeof localStorage !== "undefined") {
      return {
        load() {
          try {
            const raw = localStorage.getItem(key);
            if (!raw) {
              return createEmptySnapshot();
            }
            return normalizeSnapshot(JSON.parse(raw));
          } catch (error) {
            console.warn("Unable to parse stored calendar state, resetting to empty snapshot", error);
            return createEmptySnapshot();
          }
        },
        save(snapshot) {
          try {
            localStorage.setItem(key, JSON.stringify(normalizeSnapshot(snapshot)));
          } catch (error) {
            console.warn("Unable to persist calendar state to localStorage", error);
          }
        },
      };
    }
  } catch (error) {
    console.warn("Falling back to in-memory storage", error);
  }
  return new MemoryStorage();
}

export function createSeedData() {
  return {
    calendars: [
      {
        id: "cal-team",
        name: "Team Rituals",
        owners: ["team@calendar.app"],
        description: "Daily and weekly touchpoints",
      },
      {
        id: "cal-product",
        name: "Product Studio",
        owners: ["product@calendar.app", "ops@calendar.app"],
        description: "Feature shaping and delivery",
      },
    ],
    events: [
      {
        id: "evt-standup",
        calendarId: "cal-team",
        title: "Daily Standup",
        start: "2025-01-10T14:00:00Z",
        end: "2025-01-10T14:15:00Z",
        timezone: "UTC",
        description: "Fifteen-minute alignment with rotating facilitation",
        location: "Huddle Room",
        color: "#a855f7",
        tags: ["ritual", "sync"],
      },
      {
        id: "evt-planning",
        calendarId: "cal-product",
        title: "Iteration Planning",
        start: "2025-01-10T16:00:00Z",
        end: "2025-01-10T17:00:00Z",
        timezone: "UTC",
        description: "Frame the work and retire stale bets",
        location: "Canvas",
        color: "#22c55e",
        tags: ["planning"],
      },
      {
        id: "evt-retro",
        calendarId: "cal-team",
        title: "Retro + Ritual Refresh",
        start: "2025-01-12T15:00:00Z",
        end: "2025-01-12T16:00:00Z",
        timezone: "UTC",
        description: "Celebrate wins, refactor rituals, and retire drag",
        location: "Studio",
        color: "#0ea5e9",
        tags: ["retro", "learning"],
      },
    ],
  };
}

export class CalendarModel {
  constructor({ storage = new MemoryStorage(), now = () => new Date() } = {}) {
    this.storage = storage;
    this.now = now;
    const snapshot = typeof storage.load === "function" ? storage.load() : createEmptySnapshot();
    this.data = normalizeSnapshot(snapshot);
    this.palette = ["#a855f7", "#0ea5e9", "#f97316", "#10b981", "#ec4899"];
  }

  importSeed(seed) {
    this.data = normalizeSnapshot(seed);
    this._persist();
  }

  listCalendars() {
    return clone(this.data.calendars);
  }

  createCalendar({ name, owners, description = "" }) {
    const trimmedName = (name ?? "").trim();
    const normalizedOwners = this._normalizeOwners(owners);
    if (!trimmedName) {
      throw new Error("Calendar name is required");
    }
    if (normalizedOwners.length === 0) {
      throw new Error("At least one owner is required");
    }
    const calendar = {
      id: this._makeId("cal"),
      name: trimmedName,
      owners: normalizedOwners,
      description: description.trim(),
    };
    this.data.calendars.push(calendar);
    this._persist();
    return calendar.id;
  }

  addEvent(calendarId, { title, start, end, timezone = "UTC", description = "", location = "", tags = [] }) {
    const calendar = this._getCalendar(calendarId);
    const trimmedTitle = (title ?? "").trim();
    if (!trimmedTitle) {
      throw new Error("Event title is required");
    }
    const startDate = this._parseDate(start, "start");
    const endDate = this._parseDate(end, "end");
    if (startDate >= endDate) {
      throw new Error("Event start must be before end");
    }
    const event = {
      id: this._makeId("evt"),
      calendarId: calendar.id,
      title: trimmedTitle,
      start: startDate.toISOString(),
      end: endDate.toISOString(),
      timezone: timezone || "UTC",
      description: description.trim(),
      location: location.trim(),
      color: this._colorForCalendar(calendarId),
      tags: this._normalizeTags(tags),
    };
    this.data.events.push(event);
    this._persist();
    return event.id;
  }

  listEvents(calendarId = null, { rangeStart = null, rangeEnd = null } = {}) {
    const startFilter = rangeStart ? this._parseDate(rangeStart, "rangeStart") : null;
    const endFilter = rangeEnd ? this._parseDate(rangeEnd, "rangeEnd") : null;
    if (startFilter && endFilter && startFilter > endFilter) {
      throw new Error("rangeStart must be before rangeEnd");
    }
    if (calendarId) {
      this._getCalendar(calendarId);
    }
    const filtered = this.data.events
      .filter((event) => !calendarId || event.calendarId === calendarId)
      .filter((event) => this._withinRange(event, startFilter, endFilter))
      .sort((left, right) => new Date(left.start) - new Date(right.start))
      .map((event) => this._decorateEvent(event));
    return filtered;
  }

  getAgenda(calendarId = null, { rangeStart = null, rangeEnd = null } = {}) {
    const events = this.listEvents(calendarId, { rangeStart, rangeEnd });
    const groups = new Map();
    events.forEach((event) => {
      const day = event.start.slice(0, 10);
      if (!groups.has(day)) {
        groups.set(day, []);
      }
      groups.get(day).push(event);
    });
    return Array.from(groups.entries()).map(([date, groupedEvents]) => ({ date, events: groupedEvents }));
  }

  getInsights(calendarId = null) {
    const calendars = calendarId ? [this._getCalendar(calendarId)] : this.listCalendars();
    const events = this.listEvents(calendarId);
    const durationMinutes = events.reduce((sum, event) => sum + event.durationMinutes, 0);
    const earliest = events[0]?.start ?? null;
    const latest = events.length ? events[events.length - 1].end : null;
    const spanDays = earliest && latest ? Math.round((new Date(latest) - new Date(earliest)) / 86_400_000) + 1 : 0;
    return {
      calendarCount: calendars.length,
      eventCount: events.length,
      totalDurationMinutes: durationMinutes,
      spanDays,
      highlight: events.find((event) => event.durationMinutes > 60)?.title ?? "",
    };
  }

  _persist() {
    if (typeof this.storage.save === "function") {
      this.storage.save(this.data);
    }
  }

  _normalizeOwners(owners) {
    if (!owners) return [];
    if (Array.isArray(owners)) {
      return owners.map((owner) => owner.trim()).filter(Boolean);
    }
    if (typeof owners === "string") {
      return owners
        .split(",")
        .map((owner) => owner.trim())
        .filter(Boolean);
    }
    return [];
  }

  _normalizeTags(tags) {
    if (!tags) return [];
    if (Array.isArray(tags)) {
      return tags.map((tag) => `${tag}`.trim()).filter(Boolean);
    }
    return [`${tags}`.trim()].filter(Boolean);
  }

  _colorForCalendar(calendarId) {
    const index = Math.abs([...calendarId].reduce((acc, char) => acc + char.charCodeAt(0), 0)) % this.palette.length;
    return this.palette[index];
  }

  _withinRange(event, start, end) {
    const eventStart = new Date(event.start);
    if (start && eventStart < start) {
      return false;
    }
    if (end && eventStart > end) {
      return false;
    }
    return true;
  }

  _decorateEvent(event) {
    const startDate = new Date(event.start);
    const endDate = new Date(event.end);
    const durationMinutes = Math.round((endDate - startDate) / 60000);
    return {
      ...event,
      durationMinutes,
      day: event.start.slice(0, 10),
      startLabel: this._formatTime(startDate),
      endLabel: this._formatTime(endDate),
    };
  }

  _formatTime(value) {
    return new Intl.DateTimeFormat("en", {
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "UTC",
    }).format(value);
  }

  _parseDate(value, label) {
    if (value instanceof Date) {
      if (Number.isNaN(value.getTime())) {
        throw new Error(`${label} must be a valid date`);
      }
      return value;
    }
    if (typeof value === "string") {
      const parsed = new Date(value);
      if (Number.isNaN(parsed.getTime())) {
        throw new Error(`${label} must be an ISO-8601 date string`);
      }
      return parsed;
    }
    throw new Error(`${label} must be a date or ISO string`);
  }

  _getCalendar(id) {
    const calendar = this.data.calendars.find((candidate) => candidate.id === id);
    if (!calendar) {
      throw new Error(`Unknown calendar: ${id}`);
    }
    return calendar;
  }

  _makeId(prefix) {
    return `${prefix}_${Math.random().toString(36).slice(2, 8)}`;
  }
}
