export function describeSyncState({ syncEnabled, apiBaseUrl, remoteActive, lastError = "" } = {}) {
  if (!syncEnabled) {
    return "Sync: Local only";
  }
  if (remoteActive) {
    return `Sync: Remote (${apiBaseUrl || "adapter"})`;
  }
  const errorSuffix = lastError ? `: ${lastError}` : "";
  return `Sync: Local (remote unavailable${errorSuffix})`;
}

export function scopedStorageKey(baseKey = "calendarapp-web-state", username = "") {
  const sanitizedBase = `${baseKey || "calendarapp-web-state"}`.trim() || "calendarapp-web-state";
  const scopedUser = `${username ?? ""}`.trim().toLowerCase();
  return scopedUser ? `${sanitizedBase}:${scopedUser}` : sanitizedBase;
}

export const syncStatus = {
  describeSyncState,
  scopedStorageKey,
};
