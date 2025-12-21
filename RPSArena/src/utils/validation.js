import { MODES, VARIANTS, MOVES } from "../constants.js";

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateEmail(email) {
  return typeof email === "string" && EMAIL_REGEX.test(email.trim());
}

export function validateAvatarColor(color) {
  return typeof color === "string" && /^#?[0-9a-fA-F]{6}$/.test(color.trim());
}

export function normalizeColor(color) {
  if (!validateAvatarColor(color)) {
    throw new Error("Avatar color must be a 6-digit hex code");
  }
  return color.startsWith("#") ? color.toLowerCase() : `#${color.toLowerCase()}`;
}

export function validateMode(mode) {
  if (!Object.values(MODES).includes(mode)) {
    throw new Error("Unsupported mode");
  }
}

export function validateVariant(variant) {
  if (!Object.values(VARIANTS).includes(variant)) {
    throw new Error("Unsupported variant");
  }
}

export function validateMoveSequence(sequence) {
  if (!Array.isArray(sequence) || sequence.length === 0) {
    throw new Error("At least one move is required");
  }

  sequence.forEach((move) => {
    if (!MOVES.includes(move)) {
      throw new Error(`Invalid move: ${move}`);
    }
  });
}

export function requireFields(payload, fields) {
  fields.forEach((field) => {
    if (payload[field] === undefined || payload[field] === null || payload[field] === "") {
      throw new Error(`Missing field: ${field}`);
    }
  });
}
