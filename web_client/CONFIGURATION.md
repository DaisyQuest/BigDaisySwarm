# Calendar Web Client Configuration

The client ships with sensible defaults and runs entirely in-browser. You can configure synchronization and storage without a build step by setting a global config object before loading `app.js`.

## Runtime config
Set a global `window.__CALENDAR_APP_CONFIG__` **before** including `app.js`:

```html
<script>
  window.__CALENDAR_APP_CONFIG__ = {
    syncEnabled: true,
    apiBaseUrl: "https://api.example.com",
    storageKey: "calendarapp-web-state",
    useLocalStorage: true,
    // Optional: supply a remote adapter with synchronous load/save methods
    remoteAdapter: {
      load: () => ({ calendars: [], events: [] }),
      save: (snapshot) => console.log("persist", snapshot),
    },
  };
</script>
<script type="module" src="./app.js"></script>
```

Fields:
- `syncEnabled` (boolean): If `true`, the client attempts to use `remoteAdapter`; otherwise it stays local.
- `apiBaseUrl` (string): For documentation/status only; include your server base URL when syncing remotely.
- `storageKey` (string): Key used for `localStorage` persistence.
- `useLocalStorage` (boolean): If `false`, the client stays in-memory.
- `remoteAdapter` (object | null): Optional adapter with `load()` and `save(snapshot)` methods. Errors fall back to local storage with a warning.

## Fallback behavior
- If `syncEnabled` is `true` but `remoteAdapter` is missing or fails, the client logs a warning and uses local storage.
- Storage read/write errors also emit warnings and retain in-memory state, keeping the UI responsive.

## Deploying with configuration
When hosting statically (Azure Static Web Apps, Azure Storage, etc.), you can place a small inline script in `index.html` or add a separate configuration file that sets `window.__CALENDAR_APP_CONFIG__` before `app.js`. No build or bundling is required.
