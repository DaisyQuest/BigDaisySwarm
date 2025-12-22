function normalizeBoolean(value, defaultValue = false) {
  if (value === undefined) return defaultValue;
  if (typeof value === "boolean") return value;
  const normalized = String(value).trim().toLowerCase();
  if (!normalized) return defaultValue;
  return ["1", "true", "yes", "on"].includes(normalized);
}

export function resolvePort(env = process.env) {
  const candidates = [env.PORT, env.WEBSITES_PORT];
  for (const candidate of candidates) {
    const port = Number(candidate);
    if (Number.isFinite(port) && port > 0) {
      return port;
    }
  }
  return 3000;
}

export function resolveMongoClientOptions(env = process.env) {
  const options = {};

  if (env.MONGODB_TLS !== undefined) {
    options.tls = normalizeBoolean(env.MONGODB_TLS);
  }

  if (env.MONGODB_TLS_ALLOW_INVALID_CERTS !== undefined) {
    options.tlsAllowInvalidCertificates = normalizeBoolean(env.MONGODB_TLS_ALLOW_INVALID_CERTS);
  }

  if (env.MONGODB_TLS_CA_FILE) {
    options.tlsCAFile = env.MONGODB_TLS_CA_FILE;
  }

  if (env.MONGODB_SERVER_SELECTION_TIMEOUT_MS !== undefined) {
    const timeout = Number(env.MONGODB_SERVER_SELECTION_TIMEOUT_MS);
    if (Number.isFinite(timeout) && timeout > 0) {
      options.serverSelectionTimeoutMS = timeout;
    }
  }

  return options;
}

export const __test__ = { normalizeBoolean };
