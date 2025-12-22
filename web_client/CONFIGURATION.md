# Calendar Web Client Configuration

The client ships with sensible defaults and runs entirely in-browser. You can configure synchronization and storage without a build step by setting a global config object before loading `app.js`.

## Runtime config
Set a global `window.__CALENDAR_APP_CONFIG__` **before** including `app.js`:

```html
<script>
  window.__CALENDAR_APP_CONFIG__ = {
    syncEnabled: true,
    apiBaseUrl: "https://calendar-demo-server.azurewebsites.net",
    storageKey: "calendarapp-web-state",
    useLocalStorage: true,
    // Optional: supply a remote adapter with synchronous load/save methods
    remoteAdapter: {
      load: () => ({ calendars: [], events: [] }),
      save: (snapshot) => console.log("persist", snapshot),
    },
    auth: {
      issuer: "https://issuer.example.com",
      audience: "calendar-api",
      clientId: "calendar-web",
      authorizationEndpoint: "https://issuer.example.com/authorize",
      tokenEndpoint: "https://issuer.example.com/oauth/token",
      jwksUri: "https://issuer.example.com/.well-known/jwks.json",
      redirectUri: "https://client.example.com",
      scopes: ["openid", "profile", "email", "calendar.read", "calendar.write"],
    },
  };
</script>
<script type="module" src="./app.js"></script>
```

Fields:
- `syncEnabled` (boolean): If `true`, the client attempts to use `remoteAdapter`; otherwise it stays local.
- `apiBaseUrl` (string): Server base URL used for remote sync. Defaults to `https://calendar-demo-server.azurewebsites.net` when unset.
- `storageKey` (string): Key used for `localStorage` persistence.
- `useLocalStorage` (boolean): If `false`, the client stays in-memory.
- `remoteAdapter` (object | null): Optional adapter with `load()` and `save(snapshot)` methods. Errors fall back to local storage with a warning.
- `auth` (object): OIDC wiring for remote sync.
  - `issuer`, `audience`, `clientId`, `authorizationEndpoint`, `tokenEndpoint`, `redirectUri` are required when `syncEnabled` is `true`.
  - `jwksUri` (string): Override JWKS discovery; defaults to `${issuer}/.well-known/jwks.json`.
  - `scopes` (array): Requested scopes; `openid` is added automatically.

## Fallback behavior
- If `syncEnabled` is `true` but `remoteAdapter` is missing or fails, the client logs a warning and uses local storage.
- Storage read/write errors also emit warnings and retain in-memory state, keeping the UI responsive.
- When `syncEnabled=true` without a configured `apiBaseUrl` or OIDC endpoints, the UI will halt with an error instead of silently using seed data.

## Deploying with configuration
When hosting statically (Azure Static Web Apps, Azure Storage, etc.), you can place a small inline script in `index.html` or add a separate configuration file that sets `window.__CALENDAR_APP_CONFIG__` before `app.js`. No build or bundling is required.

`runtime-config.js` is loaded ahead of `app.js`; container deployments rewrite it from environment variables:

- `CALENDAR_API_BASE_URL` → `apiBaseUrl` (defaults to `https://calendar-demo-server.azurewebsites.net` if unset)
- `SYNC_ENABLED`, `USE_LOCAL_STORAGE`, `STORAGE_KEY`
- `OIDC_ISSUER`, `OIDC_AUDIENCE`, `OIDC_CLIENT_ID`, `OIDC_AUTHORIZATION_ENDPOINT`, `OIDC_TOKEN_ENDPOINT`, `OIDC_JWKS_URI`, `OIDC_REDIRECT_URI`, `OIDC_SCOPES`
