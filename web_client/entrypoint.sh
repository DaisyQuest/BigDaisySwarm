#!/bin/sh
set -eu

CONFIG_PATH="${CONFIG_PATH:-/usr/share/nginx/html/runtime-config.js}"

escape_json_string() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

normalize_bool() {
  raw="$1"
  default_value="$2"
  if [ -z "$raw" ]; then
    echo "$default_value"
    return
  fi
  case "$(echo "$raw" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on) echo "true" ;;
    0|false|no|off) echo "false" ;;
    *) echo "$default_value" ;;
  esac
}

normalize_scopes() {
  raw="$1"
  default_scopes='["openid","profile","email","calendar.read","calendar.write"]'
  if [ -z "$raw" ]; then
    echo "$default_scopes"
    return
  fi
  trimmed="$raw"
  if echo "$raw" | grep -Eq '^[[:space:]]*\[.*\][[:space:]]*$'; then
    trimmed=$(echo "$raw" | sed 's/^[[:space:]]*\\[//; s/\\][[:space:]]*$//')
  fi
  cleaned=$(echo "$trimmed" | tr ',' ' ' | tr -d '[]"')
  normalized=""
  for scope in $cleaned; do
    scope=$(echo "$scope" | sed 's/^"//; s/"$//; s/^'"'"'//; s/'"'"'$//; s/,$//')
    if [ -z "$scope" ]; then
      continue
    fi
    if [ -n "$normalized" ]; then
      normalized="$normalized,\"$scope\""
    else
      normalized="\"$scope\""
    fi
  done
  if [ -z "$normalized" ]; then
    echo "$default_scopes"
  else
    echo "[$normalized]"
  fi
}

SYNC_ENABLED_VALUE=$(normalize_bool "${SYNC_ENABLED:-}" true)
USE_LOCAL_STORAGE_VALUE=$(normalize_bool "${USE_LOCAL_STORAGE:-}" true)
SCOPES_VALUE=$(normalize_scopes "${OIDC_SCOPES:-}")

API_BASE_URL=$(escape_json_string "${CALENDAR_API_BASE_URL:-}")
STORAGE_KEY=$(escape_json_string "${STORAGE_KEY:-calendarapp-web-state}")
ISSUER=$(escape_json_string "${OIDC_ISSUER:-}")
AUDIENCE=$(escape_json_string "${OIDC_AUDIENCE:-}")
CLIENT_ID=$(escape_json_string "${OIDC_CLIENT_ID:-}")
AUTHORIZATION_ENDPOINT=$(escape_json_string "${OIDC_AUTHORIZATION_ENDPOINT:-}")
TOKEN_ENDPOINT=$(escape_json_string "${OIDC_TOKEN_ENDPOINT:-}")
JWKS_URI=$(escape_json_string "${OIDC_JWKS_URI:-}")
REDIRECT_URI=$(escape_json_string "${OIDC_REDIRECT_URI:-}")

cat > "$CONFIG_PATH" <<EOF
// Generated at container startup to wire remote sync + OIDC.
window.__CALENDAR_APP_CONFIG__ = {
  syncEnabled: ${SYNC_ENABLED_VALUE},
  apiBaseUrl: "${API_BASE_URL}",
  storageKey: "${STORAGE_KEY}",
  useLocalStorage: ${USE_LOCAL_STORAGE_VALUE},
  remoteAdapter: null,
  auth: {
    issuer: "${ISSUER}",
    audience: "${AUDIENCE}",
    clientId: "${CLIENT_ID}",
    authorizationEndpoint: "${AUTHORIZATION_ENDPOINT}",
    tokenEndpoint: "${TOKEN_ENDPOINT}",
    jwksUri: "${JWKS_URI}",
    redirectUri: "${REDIRECT_URI}",
    scopes: ${SCOPES_VALUE},
  },
};
EOF

if [ "${SKIP_NGINX:-}" = "1" ]; then
  exit 0
fi

exec nginx -g "daemon off;"
