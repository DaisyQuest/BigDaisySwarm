import { MatchmakingPoller } from "./matchPolling.js";
import { renderHighscores, renderLeaderboard, renderMatchHistory, renderNews, statusMessage } from "./viewUtils.js";

const registrationForm = document.getElementById("registration-form");
const registrationFeedback = document.getElementById("registration-feedback");
const loginForm = document.getElementById("login-form");
const loginFeedback = document.getElementById("login-feedback");
const navRegister = document.getElementById("nav-register");
const navLogin = document.getElementById("nav-login");
const navHome = document.getElementById("nav-home");
const homeSection = document.getElementById("home");
const registrationSection = document.getElementById("registration");
const loginSection = document.getElementById("login");
const newsFeed = document.getElementById("news-feed");
const queueForm = document.getElementById("queue-form");
const queueFeedback = document.getElementById("queue-feedback");
const queueBotButton = document.getElementById("queue-bot");
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
const userSummary = document.getElementById("user-summary");

let currentUser = null;
let matchmakingPoller = null;

function showHome() {
  registrationSection.classList.add("hidden");
  loginSection.classList.add("hidden");
  homeSection.classList.remove("hidden");
  navHome.classList.add("active");
  navRegister.classList.remove("active");
  navLogin.classList.remove("active");
}

function showRegistration() {
  registrationSection.classList.remove("hidden");
  loginSection.classList.add("hidden");
  homeSection.classList.add("hidden");
  navRegister.classList.add("active");
  navHome.classList.remove("active");
  navLogin.classList.remove("active");
}

function showLogin() {
  loginSection.classList.remove("hidden");
  registrationSection.classList.add("hidden");
  homeSection.classList.add("hidden");
  navLogin.classList.add("active");
  navRegister.classList.remove("active");
  navHome.classList.remove("active");
}

navRegister.addEventListener("click", showRegistration);
navLogin.addEventListener("click", showLogin);
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
  el.innerHTML = statusMessage(message, isError ? "error" : "success");
}

function updateUserSummary(user) {
  if (!user) {
    userSummary.textContent = "Not logged in";
    return;
  }
  userSummary.textContent = `${user.username} — ${user.id}`;
}

function setCurrentUser(user) {
  currentUser = user;
  updateUserSummary(user);
}

function stopMatchmakingPoller() {
  if (matchmakingPoller) {
    matchmakingPoller.stop();
    matchmakingPoller = null;
  }
}

function describeOpponent(match) {
  if (!match?.players || !currentUser) return "";
  const opponent = match.players.find((id) => id !== currentUser.id);
  return opponent ? ` vs ${opponent}` : "";
}

function announceMatch(match) {
  const matchId = match?.id || "pending";
  setFeedback(queueFeedback, `Matched! Match id: ${matchId}${describeOpponent(match)}`);
}

function createMatchmakingRequest(payload) {
  return () => api("/api/matchmaking", { method: "POST", body: JSON.stringify(payload) });
}

function startMatchmakingPolling(request) {
  stopMatchmakingPoller();
  setFeedback(queueFeedback, "Queued. Keep this tab open for pairing.");
  matchmakingPoller = new MatchmakingPoller({
    request,
    onQueued: () => setFeedback(queueFeedback, "Queued. Keep this tab open for pairing."),
    onMatched: (match) => announceMatch(match),
    onError: (error) => setFeedback(queueFeedback, error?.message || "Matchmaking failed", true),
  });
  matchmakingPoller.start();
}

async function submitMatchmaking(payload) {
  stopMatchmakingPoller();
  const request = createMatchmakingRequest(payload);
  const status = await request();
  if (status.status === "matched") {
    announceMatch(status.match);
    return;
  }
  startMatchmakingPolling(request);
}

registrationForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(registrationForm);
  const payload = Object.fromEntries(formData.entries());
  try {
    const user = await api("/api/register", { method: "POST", body: JSON.stringify(payload) });
    setCurrentUser(user);
    setFeedback(registrationFeedback, `Registered ${user.username}. Your player id: ${user.id}`);
    showHome();
    refreshHomeData();
  } catch (error) {
    setFeedback(registrationFeedback, error.message, true);
  }
});

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(loginForm).entries());
  try {
    const user = await api("/api/login", { method: "POST", body: JSON.stringify(payload) });
    setCurrentUser(user);
    setFeedback(loginFeedback, `Welcome back, ${user.username}`);
    showHome();
    refreshHomeData();
  } catch (error) {
    setFeedback(loginFeedback, error.message, true);
  }
});

function requireAuth(feedbackEl) {
  if (!currentUser) {
    setFeedback(feedbackEl, "Please login or register first.", true);
    throw new Error("Authentication required");
  }
}

queueForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    requireAuth(queueFeedback);
  } catch {
    return;
  }
  const payload = Object.fromEntries(new FormData(queueForm).entries());
  payload.userId = currentUser.id;
  payload.roundCount = Number(payload.roundCount || 3);
  try {
    await submitMatchmaking(payload);
  } catch (error) {
    setFeedback(queueFeedback, error.message, true);
  }
});

queueBotButton.addEventListener("click", async () => {
  try {
    requireAuth(queueFeedback);
  } catch {
    return;
  }
  const payload = Object.fromEntries(new FormData(queueForm).entries());
  payload.userId = currentUser.id;
  payload.roundCount = Number(payload.roundCount || 3);
  payload.playBot = true;
  try {
    await submitMatchmaking(payload);
  } catch (error) {
    setFeedback(queueFeedback, error.message, true);
  }
});

avatarForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    requireAuth(avatarFeedback);
  } catch {
    return;
  }
  const payload = Object.fromEntries(new FormData(avatarForm).entries());
  payload.userId = currentUser.id;
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
    newsFeed.innerHTML = renderNews(news);
  } catch (error) {
    newsFeed.innerHTML = statusMessage(error.message, "error");
  }
}

async function loadLeaderboard(limit = 100, offset = 0) {
  try {
    const board = await api(`/api/leaderboard?limit=${limit}&offset=${offset}`);
    leaderboardEl.innerHTML = renderLeaderboard(board, offset);
  } catch (error) {
    leaderboardEl.innerHTML = `<li>${error.message}</li>`;
  }
}

async function loadHighscores() {
  const page = Number(highscorePage.value || 1);
  const size = Number(highscoreSize.value || 10);
  try {
    const scores = await api(`/api/highscores?page=${page}&pageSize=${size}`);
    highscoresEl.innerHTML = renderHighscores(scores, page, size);
  } catch (error) {
    highscoresEl.innerHTML = `<li>${error.message}</li>`;
  }
}

async function loadHistory() {
  const playerId = historyUserInput.value.trim() || currentUser?.id;
  if (!playerId) {
    setFeedback(historyContainer, "Please login or enter a player id.", true);
    return;
  }
  try {
    const history = await api(`/api/history?playerId=${encodeURIComponent(playerId)}&rankedOnly=true`);
    historyContainer.innerHTML = renderMatchHistory(history);
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
