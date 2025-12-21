import { DEFAULT_UNLOCKS, NEWS_BULLETINS } from "../constants.js";

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

export class InMemoryStore {
  constructor() {
    this.users = new Map();
    this.matches = new Map();
    this.news = [...NEWS_BULLETINS];
  }

  async createUser(user) {
    if (this.users.has(user.id)) {
      throw new Error("User already exists");
    }
    this.users.set(user.id, clone(user));
    return clone(user);
  }

  async findUserByEmail(email) {
    for (const user of this.users.values()) {
      if (user.email === email) {
        return clone(user);
      }
    }
    return null;
  }

  async findUserByUsername(username) {
    for (const user of this.users.values()) {
      if (user.username === username) {
        return clone(user);
      }
    }
    return null;
  }

  async findUserById(userId) {
    const user = this.users.get(userId);
    return user ? clone(user) : null;
  }

  async updateUser(userId, updater) {
    const existing = this.users.get(userId);
    if (!existing) return null;
    const updated = updater(clone(existing));
    updated.updatedAt = new Date().toISOString();
    this.users.set(userId, clone(updated));
    return clone(updated);
  }

  async listLeaderboard(limit = 100, offset = 0, variant = "ranked") {
    const sorted = [...this.users.values()].sort((a, b) => b.ratings[variant] - a.ratings[variant]);
    return clone(sorted.slice(offset, offset + limit));
  }

  async recordMatch(match) {
    this.matches.set(match.id, clone(match));
    return clone(match);
  }

  async listMatches({ playerId, rankedOnly = false } = {}) {
    const matches = [...this.matches.values()].filter((match) => {
      const isParticipant = !playerId || match.players.includes(playerId);
      const variantOk = !rankedOnly || match.variant === "ranked";
      return isParticipant && variantOk;
    });
    return clone(matches);
  }

  async addNews(item) {
    this.news.push(clone(item));
    return clone(item);
  }

  async listNews() {
    return clone(this.news);
  }

  async addUnlockables(userId, unlocks) {
    return this.updateUser(userId, (user) => {
      const merged = { ...DEFAULT_UNLOCKS };
      for (const key of Object.keys(merged)) {
        const existing = user.unlocks?.[key] || [];
        const incoming = unlocks[key] || [];
        merged[key] = Array.from(new Set([...existing, ...incoming]));
      }
      user.unlocks = merged;
      return user;
    });
  }
}
