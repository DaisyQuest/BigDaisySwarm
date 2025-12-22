const encoder = new TextEncoder();
const decoder = new TextDecoder();

const toBase64 = (bytes) => {
  if (typeof Buffer !== "undefined") {
    return Buffer.from(bytes).toString("base64");
  }
  let binary = "";
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return btoa(binary);
};

const fromBase64 = (value) => {
  if (typeof Buffer !== "undefined") {
    return new Uint8Array(Buffer.from(value, "base64"));
  }
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
};

const base64UrlEncode = (input) => {
  const bytes = input instanceof Uint8Array ? input : encoder.encode(String(input));
  const base64 = toBase64(bytes);
  return base64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
};

const base64UrlDecode = (input) => {
  const normalized = input.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);
  return fromBase64(padded);
};

function assertHttps(url, { allowLocal = true } = {}) {
  const parsed = new URL(url);
  if (parsed.protocol === "https:") {
    return;
  }
  if (allowLocal && ["http:", "https:"].includes(parsed.protocol) && ["localhost", "127.0.0.1"].includes(parsed.hostname)) {
    return;
  }
  throw new Error(`Insecure URL blocked for auth: ${url}`);
}

export function decodeJwt(token) {
  const parts = token.split(".");
  if (parts.length !== 3) {
    throw new Error("Invalid JWT format");
  }
  const [encodedHeader, encodedPayload, signature] = parts;
  const header = JSON.parse(decoder.decode(fromBase64(encodedHeader)));
  const payload = JSON.parse(decoder.decode(fromBase64(encodedPayload)));
  return { header, payload, signature, signingInput: `${encodedHeader}.${encodedPayload}` };
}

const algorithms = {
  RS256: { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
  ES256: { name: "ECDSA", hash: "SHA-256", namedCurve: "P-256" },
};

async function importVerificationKey(jwk, alg) {
  if (!algorithms[alg]) {
    throw new Error(`Unsupported JWT alg: ${alg}`);
  }
  return crypto.subtle.importKey("jwk", jwk, algorithms[alg], false, ["verify"]);
}

export async function verifyJwt(token, jwks, { issuer, audience, clockSkewSeconds = 300, now = () => Date.now() } = {}) {
  if (!jwks || !Array.isArray(jwks.keys) || jwks.keys.length === 0) {
    throw new Error("JWKS is empty");
  }
  const { header, payload, signature, signingInput } = decodeJwt(token);
  const jwk = jwks.keys.find((candidate) => candidate.kid === header.kid) || jwks.keys.find((candidate) => candidate.alg === header.alg);
  if (!jwk) {
    throw new Error(`No JWKS key matches kid=${header.kid || "<missing>"}`);
  }
  const key = await importVerificationKey(jwk, header.alg);
  const verified = await crypto.subtle.verify(
    algorithms[header.alg],
    key,
    base64UrlDecode(signature),
    encoder.encode(signingInput),
  );
  if (!verified) {
    throw new Error("Invalid JWT signature");
  }

  const nowSeconds = Math.floor(now() / 1000);
  if (payload.exp && nowSeconds > payload.exp + clockSkewSeconds) {
    throw new Error("Token expired");
  }
  if (payload.nbf && nowSeconds + clockSkewSeconds < payload.nbf) {
    throw new Error("Token not yet valid");
  }
  if (issuer && payload.iss !== issuer) {
    throw new Error(`Issuer mismatch: expected ${issuer}, got ${payload.iss}`);
  }
  if (audience) {
    const audiences = Array.isArray(payload.aud) ? payload.aud : [payload.aud];
    if (!audiences.includes(audience)) {
      throw new Error(`Audience mismatch: expected ${audience}, got ${audiences.join(",")}`);
    }
  }

  return payload;
}

export function createPkceChallenge(codeVerifier) {
  if (!codeVerifier || codeVerifier.length < 43) {
    throw new Error("codeVerifier must be at least 43 characters");
  }
  const data = encoder.encode(codeVerifier);
  return crypto.subtle.digest("SHA-256", data).then((digest) => base64UrlEncode(new Uint8Array(digest)));
}

export function createRandomVerifier(length = 64) {
  const bytes = new Uint8Array(length);
  crypto.getRandomValues(bytes);
  return base64UrlEncode(bytes);
}

class MemoryStorage {
  constructor() {
    this.store = new Map();
  }

  getItem(key) {
    return this.store.has(key) ? this.store.get(key) : null;
  }

  setItem(key, value) {
    this.store.set(key, value);
  }

  removeItem(key) {
    this.store.delete(key);
  }
}

export class OidcSession {
  constructor(config = {}, { storage = null, fetchImpl = null, now = () => Date.now() } = {}) {
    this.config = {
      scopes: ["openid", "profile", "email", "calendar.read", "calendar.write"],
      requireHttps: true,
      ...config,
    };
    const { authorizationEndpoint, tokenEndpoint, jwksUri, issuer, clientId, redirectUri } = this.config;
    if (!authorizationEndpoint || !tokenEndpoint || !issuer || !clientId || !redirectUri) {
      throw new Error("OIDC configuration is incomplete");
    }
    assertHttps(authorizationEndpoint);
    assertHttps(tokenEndpoint);
    assertHttps(issuer);
    if (jwksUri) {
      assertHttps(jwksUri);
    }
    this.fetchImpl = fetchImpl || fetch;
    this.storage = storage || (typeof sessionStorage !== "undefined" ? sessionStorage : new MemoryStorage());
    this.now = now;
    this.jwksUri = jwksUri || `${issuer.replace(/\/$/, "")}/.well-known/jwks.json`;
  }

  get pkceStorageKey() {
    return "calendarapp:oidc:pkce";
  }

  get tokenStorageKey() {
    return "calendarapp:oidc:tokens";
  }

  _savePkce({ codeVerifier, state }) {
    this.storage.setItem(this.pkceStorageKey, JSON.stringify({ codeVerifier, state, createdAt: this.now() }));
  }

  _readPkce() {
    const raw = this.storage.getItem(this.pkceStorageKey);
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }

  _clearPkce() {
    this.storage.removeItem(this.pkceStorageKey);
  }

  _saveTokens(tokens) {
    this.storage.setItem(this.tokenStorageKey, JSON.stringify(tokens));
  }

  _readTokens() {
    const raw = this.storage.getItem(this.tokenStorageKey);
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }

  _effectiveScopes() {
    return Array.from(new Set([...(this.config.scopes || []), "openid"])).join(" ");
  }

  async buildAuthorizationUrl() {
    const codeVerifier = createRandomVerifier();
    const codeChallenge = await createPkceChallenge(codeVerifier);
    const state = base64UrlEncode(createRandomVerifier(32));
    this._savePkce({ codeVerifier, state });

    const url = new URL(this.config.authorizationEndpoint);
    url.searchParams.set("response_type", "code");
    url.searchParams.set("client_id", this.config.clientId);
    url.searchParams.set("redirect_uri", this.config.redirectUri);
    url.searchParams.set("scope", this._effectiveScopes());
    url.searchParams.set("code_challenge", codeChallenge);
    url.searchParams.set("code_challenge_method", "S256");
    url.searchParams.set("state", state);
    if (this.config.audience) {
      url.searchParams.set("audience", this.config.audience);
    }
    if (this.config.prompt) {
      url.searchParams.set("prompt", this.config.prompt);
    }
    return url.toString();
  }

  _tokenIsValid(tokens) {
    if (!tokens || !tokens.access_token || !tokens.expires_at) {
      return false;
    }
    return this.now() < tokens.expires_at;
  }

  hasValidAccessToken() {
    return this._tokenIsValid(this._readTokens());
  }

  requireAccessToken() {
    const tokens = this._readTokens();
    if (this._tokenIsValid(tokens)) {
      return tokens.access_token;
    }
    throw new Error("Access token missing or expired");
  }

  async _fetchJwks() {
    const response = await this.fetchImpl(this.jwksUri, { headers: { Accept: "application/json" } });
    if (!response.ok) {
      throw new Error(`Failed to fetch JWKS: ${response.status}`);
    }
    return response.json();
  }

  async _exchangeCode(code) {
    const pkce = this._readPkce();
    if (!pkce?.codeVerifier || !pkce?.state) {
      throw new Error("Missing PKCE verifier for token exchange");
    }
    const params = new URLSearchParams({
      grant_type: "authorization_code",
      client_id: this.config.clientId,
      redirect_uri: this.config.redirectUri,
      code_verifier: pkce.codeVerifier,
      code,
      scope: this._effectiveScopes(),
    });
    if (this.config.audience) {
      params.set("audience", this.config.audience);
    }
    const response = await this.fetchImpl(this.config.tokenEndpoint, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: params.toString(),
    });
    if (!response.ok) {
      throw new Error(`Token endpoint returned ${response.status}`);
    }
    const payload = await response.json();
    if (!payload.access_token) {
      throw new Error("Token response missing access_token");
    }
    const expiresIn = payload.expires_in ?? 900;
    const expires_at = this.now() + expiresIn * 1000;
    const jwks = await this._fetchJwks();
    await verifyJwt(payload.id_token || payload.access_token, jwks, {
      issuer: this.config.issuer,
      audience: this.config.audience || this.config.clientId,
      now: this.now,
    });
    this._clearPkce();
    const tokens = { ...payload, expires_at };
    this._saveTokens(tokens);
    return tokens;
  }

  async handleRedirectCallback(urlString) {
    const url = new URL(urlString);
    const code = url.searchParams.get("code");
    const state = url.searchParams.get("state");
    const error = url.searchParams.get("error");
    if (error) {
      throw new Error(`Authorization failed: ${url.searchParams.get("error_description") || error}`);
    }
    if (!code) {
      return { handled: false };
    }
    const pkce = this._readPkce();
    if (!pkce || pkce.state !== state) {
      throw new Error("State does not match stored PKCE verifier");
    }
    const tokens = await this._exchangeCode(code);
    return { handled: true, tokens };
  }
}

export const authUtils = {
  base64UrlEncode,
  base64UrlDecode,
  createPkceChallenge,
  createRandomVerifier,
  assertHttps,
};
