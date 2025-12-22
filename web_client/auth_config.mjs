export function isOidcConfigComplete(auth = {}) {
  const required = ["authorizationEndpoint", "tokenEndpoint", "issuer", "clientId", "redirectUri"];
  return required.every((field) => Boolean(auth?.[field]));
}

export function shouldUseBasicAuthFallback(config = {}) {
  const syncRequested = Boolean(config.syncEnabled && config.apiBaseUrl);
  if (!syncRequested) {
    return false;
  }
  return !isOidcConfigComplete(config.auth);
}
