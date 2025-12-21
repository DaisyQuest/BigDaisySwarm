import crypto from "crypto";

const ITERATIONS = 120000;
const KEYLEN = 64;
const DIGEST = "sha512";

export function hashPassword(password) {
  if (typeof password !== "string" || password.length < 8) {
    throw new Error("Password must be at least 8 characters long");
  }

  const salt = crypto.randomBytes(16).toString("hex");
  const hash = crypto.pbkdf2Sync(password, salt, ITERATIONS, KEYLEN, DIGEST).toString("hex");
  return `${ITERATIONS}:${DIGEST}:${salt}:${hash}`;
}

export function verifyPassword(password, storedHash) {
  if (!storedHash || typeof storedHash !== "string") {
    return false;
  }

  const [iterationStr, digest, salt, originalHash] = storedHash.split(":");
  const iterations = Number.parseInt(iterationStr, 10);
  if (!iterations || !digest || !salt || !originalHash) {
    return false;
  }

  const comparisonHash = crypto
    .pbkdf2Sync(password, salt, iterations, Buffer.from(originalHash, "hex").length, digest)
    .toString("hex");

  return crypto.timingSafeEqual(Buffer.from(originalHash, "hex"), Buffer.from(comparisonHash, "hex"));
}
