const toBase64 = (value) => {
  if (typeof Buffer !== "undefined") {
    return Buffer.from(value, "utf-8").toString("base64");
  }
  return btoa(value);
};

class MemoryStorage {
  constructor() {
    this.map = new Map();
  }

  getItem(key) {
    return this.map.has(key) ? this.map.get(key) : null;
  }

  setItem(key, value) {
    this.map.set(key, value);
  }

  removeItem(key) {
    this.map.delete(key);
  }
}

const USERS_KEY = "calendarapp:basic-auth:users";
const SESSION_KEY = "calendarapp:basic-auth:session";

function normalizeUsername(username) {
  const normalized = String(username || "").trim().toLowerCase();
  if (!normalized) {
    throw new Error("Username is required");
  }
  return normalized;
}

function requirePassword(password) {
  if (!password || String(password).length < 6) {
    throw new Error("Password must be at least 6 characters long");
  }
}

function readJson(storage, key) {
  const raw = storage.getItem(key);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    storage.removeItem(key);
    return null;
  }
}

function writeJson(storage, key, value) {
  storage.setItem(key, JSON.stringify(value));
}

function buildToken(username, password) {
  return `Basic ${toBase64(`${username}:${password}`)}`;
}

export class BasicAuth {
  constructor({ storage = null, now = () => Date.now() } = {}) {
    this.storage = storage || (typeof localStorage !== "undefined" ? localStorage : new MemoryStorage());
    this.now = now;
  }

  _loadUsers() {
    const users = readJson(this.storage, USERS_KEY);
    return Array.isArray(users) ? users : [];
  }

  _saveUsers(users) {
    writeJson(this.storage, USERS_KEY, users);
  }

  _saveSession(session) {
    writeJson(this.storage, SESSION_KEY, session);
  }

  _currentSession() {
    const session = readJson(this.storage, SESSION_KEY);
    if (!session || !session.username) {
      return null;
    }
    const users = this._loadUsers();
    if (!users.some((user) => user.username === session.username)) {
      this.logout();
      return null;
    }
    return session;
  }

  register(username, password) {
    const normalized = normalizeUsername(username);
    requirePassword(password);
    const users = this._loadUsers();
    if (users.some((user) => user.username === normalized)) {
      throw new Error("User already registered");
    }
    const user = { username: normalized, secret: toBase64(String(password)), createdAt: this.now() };
    users.push(user);
    this._saveUsers(users);
    const session = { username: user.username, token: buildToken(normalized, password), issuedAt: this.now() };
    this._saveSession(session);
    return session;
  }

  authenticate(username, password) {
    const normalized = normalizeUsername(username);
    requirePassword(password);
    const users = this._loadUsers();
    const user = users.find((candidate) => candidate.username === normalized);
    if (!user || user.secret !== toBase64(String(password))) {
      throw new Error("Invalid credentials");
    }
    const session = { username: user.username, token: buildToken(normalized, password), issuedAt: this.now() };
    this._saveSession(session);
    return session;
  }

  currentSession() {
    return this._currentSession();
  }

  logout() {
    this.storage.removeItem(SESSION_KEY);
  }
}

export { MemoryStorage };
