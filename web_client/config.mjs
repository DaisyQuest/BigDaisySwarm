import { createBrowserStorage, MemoryStorage } from "./calendar_model.mjs";

export const defaultConfig = {
  syncEnabled: false,
  apiBaseUrl: "",
  storageKey: "calendarapp-web-state",
  useLocalStorage: true,
  remoteAdapter: null,
};

export function mergeConfig(overrides = {}) {
  return { ...defaultConfig, ...(overrides || {}) };
}

export function resolveConfig(globalOverrides = null, localOverrides = null) {
  const globalConfig =
    typeof window !== "undefined" && window.__CALENDAR_APP_CONFIG__
      ? window.__CALENDAR_APP_CONFIG__
      : {};
  return mergeConfig({ ...globalConfig, ...(globalOverrides || {}), ...(localOverrides || {}) });
}

export function createStorageFromConfig(config, { logger = console } = {}) {
  const baseStorage = config.useLocalStorage ? createBrowserStorage(config.storageKey) : new MemoryStorage();

  if (config.syncEnabled) {
    const adapter = config.remoteAdapter;
    const hasRemote = adapter && typeof adapter.load === "function" && typeof adapter.save === "function";
    if (hasRemote) {
      return {
        load() {
          try {
            return adapter.load();
          } catch (error) {
            logger.warn("Remote load failed, falling back to local storage", error);
            return baseStorage.load();
          }
        },
        save(snapshot) {
          try {
            adapter.save(snapshot);
          } catch (error) {
            logger.warn("Remote save failed, using local storage", error);
            baseStorage.save(snapshot);
          }
        },
      };
    }
    logger.warn("Sync enabled but no remoteAdapter provided; using local storage.");
  }

  return baseStorage;
}
