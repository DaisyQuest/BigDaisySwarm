const escapeHtml = (value) => `${value ?? ""}`.replace(/[&<>"']/g, (char) => ({
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
}[char]));

const renderBadge = (text) => `<span class="badge">${escapeHtml(text)}</span>`;

export function renderCalendarList(calendars, selectedId = null) {
  if (!calendars.length) {
    return '<p class="empty">No calendars yet—start by introducing your first ritual.</p>';
  }
  const items = calendars
    .map((calendar) => {
      const active = calendar.id === selectedId ? " active" : "";
      const owners = calendar.owners.map(renderBadge).join(" ");
      return `
        <li class="calendar-tile${active}" data-calendar-id="${escapeHtml(calendar.id)}">
          <div class="calendar-title">${escapeHtml(calendar.name)}</div>
          <div class="calendar-owners">${owners}</div>
          <div class="calendar-description">${escapeHtml(calendar.description)}</div>
        </li>`;
    })
    .join("");
  return `<ul class="calendar-list">${items}</ul>`;
}

export function renderAgenda(agenda) {
  if (!agenda.length) {
    return '<div class="empty">No events in view. Open up the timeline with a new slice of time.</div>';
  }
  return agenda
    .map(
      (slot) => `
        <section class="day-group">
          <header class="day-header">
            <div class="day-label">${escapeHtml(slot.date)}</div>
            <div class="day-count">${slot.events.length} event${slot.events.length === 1 ? "" : "s"}</div>
          </header>
          <div class="event-grid">
            ${slot.events
              .map(
                (event) => `
                  <article class="event-card" style="--event-accent:${escapeHtml(event.color)}">
                    <div class="event-time">${escapeHtml(event.startLabel)} → ${escapeHtml(event.endLabel)}</div>
                    <div class="event-title">${escapeHtml(event.title)}</div>
                    <div class="event-meta">${escapeHtml(event.location || event.timezone)} · ${event.durationMinutes} min</div>
                    ${event.description ? `<p class="event-description">${escapeHtml(event.description)}</p>` : ""}
                    ${event.tags?.length ? `<div class="event-tags">${event.tags.map(renderBadge).join(" ")}</div>` : ""}
                  </article>`
              )
              .join("")}
          </div>
        </section>`
    )
    .join("");
}

export function renderInsights(insights) {
  const { calendarCount, eventCount, totalDurationMinutes, spanDays, highlight } = insights;
  const cards = [
    {
      title: "Calendars",
      value: calendarCount,
      detail: "threads of collaboration",
    },
    {
      title: "Events",
      value: eventCount,
      detail: "moments captured",
    },
    {
      title: "Time Invested",
      value: `${totalDurationMinutes} minutes`,
      detail: "curated focus",
    },
    {
      title: "Timeline",
      value: spanDays ? `${spanDays} day span` : "fresh start",
      detail: highlight || "compose your next highlight",
    },
  ];

  const cardMarkup = cards
    .map(
      (card) => `
        <div class="insight-card">
          <div class="insight-title">${escapeHtml(card.title)}</div>
          <div class="insight-value">${escapeHtml(card.value)}</div>
          <div class="insight-detail">${escapeHtml(card.detail)}</div>
        </div>`
    )
    .join("");

  return `<div class="insight-grid">${cardMarkup}</div>`;
}

export function renderStatus(message, tone = "info") {
  const toneClass = tone === "error" ? "status error" : "status info";
  return `<div class="${toneClass}" role="status">${escapeHtml(message)}</div>`;
}

export const templates = {
  renderCalendarList,
  renderAgenda,
  renderInsights,
  renderStatus,
};
