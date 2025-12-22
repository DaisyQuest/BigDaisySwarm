#!/bin/sh
set -eu

CONFIG_PATH="/usr/share/nginx/html/runtime-config.js"

cat > "$CONFIG_PATH" <<EOF
// Generated at container startup to wire remote sync + OIDC.
window.__CALENDAR_APP_CONFIG__ = {
  syncEnabled: ${SYNC_ENABLED:-true},
  apiBaseUrl: "${CALENDAR_API_BASE_URL:-}",
  storageKey: "${STORAGE_KEY:-calendarapp-web-state}",
  useLocalStorage: ${USE_LOCAL_STORAGE:-true},
  remoteAdapter: null,
  auth: {
    issuer: "${OIDC_ISSUER:-}",
    audience: "${OIDC_AUDIENCE:-}",
    clientId: "${OIDC_CLIENT_ID:-}",
    authorizationEndpoint: "${OIDC_AUTHORIZATION_ENDPOINT:-}",
    tokenEndpoint: "${OIDC_TOKEN_ENDPOINT:-}",
    jwksUri: "${OIDC_JWKS_URI:-}",
    redirectUri: "${OIDC_REDIRECT_URI:-}",
    scopes: ${OIDC_SCOPES:-["openid","profile","email","calendar.read","calendar.write"]},
  },
};
EOF

exec nginx -g "daemon off;"
