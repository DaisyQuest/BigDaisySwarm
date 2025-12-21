import { DEFAULT_RATING, DEFAULT_UNLOCKS } from "../constants.js";

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

export function createUser({ id, username, email, passwordHash, avatarColor }) {
  const now = new Date().toISOString();
  return {
    id,
    username,
    email,
    passwordHash,
    avatarColor,
    ratings: { ranked: DEFAULT_RATING, casual: DEFAULT_RATING },
    achievements: { wins: 0, flawless: 0, streak: 0 },
    unlocks: clone(DEFAULT_UNLOCKS),
    createdAt: now,
    updatedAt: now,
  };
}
