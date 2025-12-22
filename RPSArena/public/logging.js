const NOOP = () => {};

export function createLogger(logger = console) {
  const base = logger || {};
  const fallback = base.log ? base.log.bind(base) : NOOP;
  return {
    debug: base.debug ? base.debug.bind(base) : fallback,
    info: base.info ? base.info.bind(base) : fallback,
    warn: base.warn ? base.warn.bind(base) : fallback,
    error: base.error ? base.error.bind(base) : fallback,
  };
}

export function formatLog(message, details) {
  if (details === undefined) {
    return message;
  }
  try {
    return `${message} | ${JSON.stringify(details)}`;
  } catch {
    return message;
  }
}
