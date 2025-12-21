const registrationForm = document.getElementById("registration-form");
const registrationFeedback = document.getElementById("registration-feedback");
const navRegister = document.getElementById("nav-register");
const navHome = document.getElementById("nav-home");
const homeSection = document.getElementById("home");
const registrationSection = document.getElementById("registration");
const newsFeed = document.getElementById("news-feed");
const queueForm = document.getElementById("queue-form");
const queueFeedback = document.getElementById("queue-feedback");
const leaderboardEl = document.getElementById("leaderboard");
const avatarForm = document.getElementById("avatar-form");
const avatarFeedback = document.getElementById("avatar-feedback");
const historyUserInput = document.getElementById("history-user");
const historyButton = document.getElementById("load-history");
const historyContainer = document.getElementById("match-history");
const viewAllButton = document.getElementById("view-all");
const highscorePage = document.getElementById("highscore-page");
const highscoreSize = document.getElementById("highscore-size");
const highscoresEl = document.getElementById("highscores");
const loadHighscoresButton = document.getElementById("load-highscores");

function showHome() {
  registrationSection.classList.add("hidden");
  homeSection.classList.remove("hidden");
}

function showRegistration() {
  registrationSection.classList.remove("hidden");
  homeSection.classList.add("hidden");
}

navRegister.addEventListener("click", showRegistration);
navHome.addEventListener("click", () => {
  showHome();
  refreshHomeData();
});

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Unexpected error");
  }
  return data;
}

function setFeedback(el, message, isError = false) {
  el.textContent = message;
  el.style.color = isError ? "#ff7b7b" : "#26e2b3";
}

registrationForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(registrationForm);
  const payload = Object.fromEntries(formData.entries());
  try {
    const user = await api("/api/register", { method: "POST", body: JSON.stringify(payload) });
    setFeedback(registrationFeedback, `Registered ${user.username}. Your player id: ${user.id}`);
    showHome();
    refreshHomeData();
  } catch (error) {
    setFeedback(registrationFeedback, error.message, true);
  }
});

queueForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(queueForm).entries());
  payload.roundCount = Number(payload.roundCount || 3);
  try {
    const status = await api("/api/matchmaking", { method: "POST", body: JSON.stringify(payload) });
    if (status.status === "matched") {
      setFeedback(queueFeedback, `Matched! Match id: ${status.match.id} vs ${status.match.players[1]}`);
    } else {
      setFeedback(queueFeedback, "Queued. Keep this tab open for pairing.");
    }
  } catch (error) {
    setFeedback(queueFeedback, error.message, true);
  }
});

avatarForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(avatarForm).entries());
  try {
    const user = await api("/api/avatar", { method: "PATCH", body: JSON.stringify(payload) });
    setFeedback(avatarFeedback, `Avatar updated to ${user.avatarColor}`);
  } catch (error) {
    setFeedback(avatarFeedback, error.message, true);
  }
});

async function loadNews() {
  try {
    const news = await api("/api/news");
    newsFeed.innerHTML = news
      .map((item) => `<li><strong>${item.title}</strong> — ${item.body}</li>`)
      .join("");
  } catch (error) {
    newsFeed.innerHTML = `<li class="error">${error.message}</li>`;
  }
}

async function loadLeaderboard(limit = 100, offset = 0) {
  try {
    const board = await api(`/api/leaderboard?limit=${limit}&offset=${offset}`);
    leaderboardEl.innerHTML = board
      .map((entry, idx) => `<li>#${offset + idx + 1} ${entry.username} — ${entry.ratings.ranked} ELO</li>`)
      .join("");
  } catch (error) {
    leaderboardEl.innerHTML = `<li>${error.message}</li>`;
  }
}

async function loadHighscores() {
  const page = Number(highscorePage.value || 1);
  const size = Number(highscoreSize.value || 10);
  try {
    const scores = await api(`/api/highscores?page=${page}&pageSize=${size}`);
    highscoresEl.innerHTML = scores
      .map((entry, idx) => `<li>#${(page - 1) * size + idx + 1} ${entry.username} — ${entry.ratings.ranked}</li>`)
      .join("");
  } catch (error) {
    highscoresEl.innerHTML = `<li>${error.message}</li>`;
  }
}

async function loadHistory() {
  const playerId = historyUserInput.value.trim();
  if (!playerId) return;
  try {
    const history = await api(`/api/history?playerId=${encodeURIComponent(playerId)}&rankedOnly=true`);
    historyContainer.innerHTML = history
      .map(
        (match) => `<div class="match-card">${match.mode.toUpperCase()} ${match.variant} — Winner: ${match.winner ?? "Draw"}<br />Rounds: ${match.rounds.length}</div>`,
      )
      .join("");
  } catch (error) {
    historyContainer.innerHTML = `<div class="match-card">${error.message}</div>`;
  }
}

async function refreshHomeData() {
  await Promise.all([loadNews(), loadLeaderboard(10, 0), loadHighscores()]);
}

viewAllButton.addEventListener("click", () => loadLeaderboard(100, 0));
historyButton.addEventListener("click", loadHistory);
loadHighscoresButton.addEventListener("click", loadHighscores);

refreshHomeData();
