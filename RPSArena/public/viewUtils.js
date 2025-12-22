const escapeHtml = (value) => String(value ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

export function renderNews(items) {
  if (!Array.isArray(items) || items.length === 0) {
    return '<li class="empty">Nothing new yet. Queue a match to make headlines.</li>';
  }
  return items
    .map((item) => {
      const title = escapeHtml(item?.title || "Arena update");
      const body = escapeHtml(item?.body || "Stay tuned for more matches.");
      return `<li class="news-item"><div class="pill muted">Update</div><div class="news-copy"><strong>${title}</strong><p>${body}</p></div></li>`;
    })
    .join("");
}

export function renderLeaderboard(entries, offset = 0) {
  if (!Array.isArray(entries) || entries.length === 0) {
    return '<li class="empty">No ranked contenders yet. Be the first.</li>';
  }
  return entries
    .map((entry, idx) => {
      const rank = Number(offset) + idx + 1;
      const username = escapeHtml(entry?.username || "Unknown");
      const rating = escapeHtml(entry?.ratings?.ranked ?? "Unrated");
      const trend = entry?.trend === "up" ? "▲" : entry?.trend === "down" ? "▼" : "➖";
      return `<li><span class="rank">#${rank}</span><span class="name">${username}</span><span class="elo">${rating} ELO</span><span class="trend">${trend}</span></li>`;
    })
    .join("");
}

export function renderHighscores(entries, page = 1, pageSize = 10) {
  if (!Array.isArray(entries) || entries.length === 0) {
    return '<li class="empty">No highscores yet. Play a ranked set.</li>';
  }
  const baseIndex = (Number(page) - 1) * Number(pageSize);
  return entries
    .map((entry, idx) => {
      const placement = baseIndex + idx + 1;
      const username = escapeHtml(entry?.username || "Player");
      const rating = escapeHtml(entry?.ratings?.ranked ?? "Unrated");
      return `<li><span class="rank">#${placement}</span><span class="name">${username}</span><span class="elo">${rating}</span></li>`;
    })
    .join("");
}

export function renderMatchHistory(matches) {
  if (!Array.isArray(matches) || matches.length === 0) {
    return '<div class="match-card muted">No recent matches. Queue into ranked to build history.</div>';
  }
  return matches
    .map((match) => {
      const mode = escapeHtml(match?.mode || "classic");
      const variant = escapeHtml(match?.variant || "casual");
      const winner = match?.winner;
      const winnerLabel = winner === null || winner === undefined ? "Draw" : escapeHtml(winner);
      const rounds = Array.isArray(match?.rounds) ? match.rounds.length : 0;
      return `<div class="match-card"><div class="pill">${mode.toUpperCase()}</div><div class="meta"><strong>${variant} queue</strong><span>${rounds} rounds</span></div><p class="muted">Winner: ${winnerLabel}</p></div>`;
    })
    .join("");
}

export function statusMessage(message, tone = "success") {
  const safe = escapeHtml(message || "");
  const toneClass = tone === "error" ? "error" : "success";
  return `<span class="feedback ${toneClass}">${safe}</span>`;
}

export { escapeHtml };
