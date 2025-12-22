import { randomUUID } from "crypto";
import { createUser } from "../data/modelFactories.js";
import { hashPassword, verifyPassword } from "../utils/crypto.js";
import {
  normalizeColor,
  requireFields,
  validateAvatarColor,
  validateEmail,
  validateVariant,
} from "../utils/validation.js";

export class UserService {
  constructor(store, logger = console) {
    this.store = store;
    this.logger = logger;
  }

  sanitize(user) {
    if (!user) return null;
    const { passwordHash, ...safe } = user;
    return safe;
  }

  async registerUser(payload) {
    requireFields(payload, ["username", "email", "password", "avatarColor"]);
    const username = payload.username.trim();
    const email = payload.email.trim().toLowerCase();
    const avatarColor = normalizeColor(payload.avatarColor);

    if (!validateEmail(email)) {
      throw new Error("Invalid email");
    }
    if (username.length < 3) {
      throw new Error("Username must be at least 3 characters");
    }

    const existingEmail = await this.store.findUserByEmail(email);
    if (existingEmail) {
      throw new Error("Email already registered");
    }
    const existingUsername = await this.store.findUserByUsername(username);
    if (existingUsername) {
      throw new Error("Username already taken");
    }

    const passwordHash = hashPassword(payload.password);
    const user = createUser({
      id: randomUUID(),
      username,
      email,
      passwordHash,
      avatarColor,
    });

    const saved = await this.store.createUser(user);
    this.logger.info?.(`Registered user ${user.id}`);
    return this.sanitize(saved);
  }

  async authenticate(email, password) {
    const user = await this.store.findUserByEmail(email.trim().toLowerCase());
    if (!user) {
      throw new Error("Invalid credentials");
    }
    const valid = verifyPassword(password, user.passwordHash);
    if (!valid) {
      throw new Error("Invalid credentials");
    }
    return this.sanitize(user);
  }

  async updateAvatar(userId, color) {
    if (!validateAvatarColor(color)) {
      throw new Error("Avatar color must be a 6-digit hex code");
    }
    const normalized = normalizeColor(color);
    const updated = await this.store.updateUser(userId, (current) => ({
      ...current,
      avatarColor: normalized,
    }));
    if (!updated) {
      throw new Error("User not found");
    }
    this.logger.info?.(`Updated avatar for ${userId}`);
    return this.sanitize(updated);
  }

  async leaderboard(limit = 100, offset = 0, variant = "ranked") {
    validateVariant(variant);
    const results = await this.store.listLeaderboard(limit, offset, variant);
    return results.map((user) => this.sanitize(user));
  }

  async highScores(page = 1, pageSize = 25, variant = "ranked") {
    const offset = (page - 1) * pageSize;
    return this.leaderboard(pageSize, offset, variant);
  }

  async applyRatingChange(userId, variant, delta) {
    validateVariant(variant);
    const updated = await this.store.updateUser(userId, (user) => {
      const next = { ...user };
      next.ratings = {
        ...user.ratings,
        [variant]: Math.max(1, user.ratings[variant] + delta),
      };
      return next;
    });
    if (!updated) {
      throw new Error("User not found");
    }
    this.logger.debug?.(`Rating change for ${userId} on ${variant}: ${delta}`);
    return this.sanitize(updated);
  }

  async recordLastMatch(userId, matchId) {
    return this.store.updateUser(userId, (user) => ({ ...user, lastMatchId: matchId }));
  }
}
