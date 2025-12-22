import { verifyJwt, authUtils } from "./auth.mjs";

const normalizeUrl = (url) => url.replace(/\/+$/, "");

function assertSecureUrl(url) {
  authUtils.assertHttps(url);
}

export function createRemoteAdapter({
  apiBaseUrl,
  tokenProvider,
  jwksUri,
  issuer,
  audience,
  fetchImpl = null,
  now = () => Date.now(),
  onWarn = null,
} = {}) {
  if (!apiBaseUrl) {
    throw new Error("apiBaseUrl is required for remote sync");
  }
  if (typeof tokenProvider !== "function") {
    throw new Error("tokenProvider is required for remote sync");
  }
  if (!jwksUri) {
    throw new Error("jwksUri is required for remote sync");
  }
  assertSecureUrl(apiBaseUrl);
  if (jwksUri) {
    assertSecureUrl(jwksUri);
  }

  const fetcher = fetchImpl || fetch;
  let jwksCache = null;
  const warn = onWarn || ((message) => console.warn(message));

  async function fetchJwks() {
    if (jwksCache) return jwksCache;
    const response = await fetcher(jwksUri, { headers: { Accept: "application/json" } });
    if (!response.ok) {
      throw new Error(`Failed to fetch JWKS (${response.status})`);
    }
    jwksCache = await response.json();
    return jwksCache;
  }

  async function validatedToken() {
    const token = await tokenProvider();
    if (!token) {
      throw new Error("Missing access token");
    }
    if (jwksUri) {
      const jwks = await fetchJwks();
      await verifyJwt(token, jwks, { issuer, audience, now });
    }
    return token;
  }

  async function authorizedFetch(path, init = {}) {
    const token = await validatedToken();
    const headers = { ...(init.headers || {}), Authorization: `Bearer ${token}` };
    const url = `${normalizeUrl(apiBaseUrl)}/${path.replace(/^\/+/, "")}`;
    return fetcher(url, { ...init, headers });
  }

  async function load() {
    const response = await authorizedFetch("/state", { method: "GET" });
    if (!response.ok) {
      throw new Error(`Remote load failed with status ${response.status}`);
    }
    const payload = await response.json();
    if (!Array.isArray(payload.calendars) || !Array.isArray(payload.events)) {
      throw new Error("Remote state missing calendars/events");
    }
    return payload;
  }

  async function save(snapshot) {
    try {
      const response = await authorizedFetch("/state", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(snapshot),
      });
      if (!response.ok) {
        throw new Error(`Remote save failed with status ${response.status}`);
      }
    } catch (error) {
      warn(`Failed to persist remote state: ${error.message}`);
      throw error;
    }
  }

  return { load, save };
}
