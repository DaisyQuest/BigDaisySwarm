# Security, Cryptography, and Identity Specification

This specification defines the cryptography requirements and OpenID Connect (OIDC) workflows for the CalendarApp backend and its clients.

## Cryptography posture
- **Transport:**
  - TLS 1.3 required for all inbound and service-to-service traffic.
  - Preferred cipher suites: `TLS_AES_256_GCM_SHA384`, `TLS_CHACHA20_POLY1305_SHA256`.
  - Enforce HTTP Strict Transport Security (HSTS) on public ingress.
  - For Azure App Service, require HTTPS-only and enable minimum TLS 1.3 in configuration.
- **Data at rest:**
  - PostgreSQL with encryption at rest; client connections use TLS (`sslmode=require`).
  - Secrets and signing keys stored in a hardware-backed KMS (e.g., AWS KMS, GCP KMS, HashiCorp Vault with HSM).
  - Backups encrypted with AES-256-GCM; keys rotated at least every 90 days.
- **Application-layer encryption:**
  - Sensitive fields (e.g., invitee emails, metadata blobs) support optional envelope encryption:
    - Data keys: AES-256-GCM.
    - Key wrapping: RSA-OAEP-256 or AES-KW with keys from KMS.
- **Hashing and integrity:**
  - Passwords (for admin/ops users only) use Argon2id with memory-hard parameters.
  - Payload integrity for signed objects uses SHA-256 or SHA-384 depending on platform requirements.
- **Key management:**
  - Rotate signing keys with overlapping validity windows; publish old keys for at least 24 hours to avoid hard failures.
  - Maintain JWKS endpoints with `kid` and `alg` fields populated; reject keys without an expiration/rotation policy.

## OpenID Connect workflow
- **Grant type:** Authorization Code + PKCE for interactive clients; Client Credentials for server-to-server automation.
- **Token format:** JWT access tokens signed with asymmetric keys.
  - Algorithm: `ES256` preferred; `RS256` permitted when HSM-backed ECDSA is unavailable.
  - Claims to validate:
    - `iss` matches `OIDC_ISSUER`
    - `aud` includes `OIDC_AUDIENCE`
    - `exp` and `nbf` are current; reject tokens with more than 5 minutes of clock skew
    - `sub` present and stable across sessions
    - `jti` used for replay detection when revocation lists are enabled
  - Scope expectations: `calendar.read`, `calendar.write`, `calendar.admin` govern access to API routes.
- **Token validation steps (API):**
  1. Fetch JWKS from `OIDC_JWKS_URL` with caching and background refresh.
  2. Verify signature against the matching `kid`.
  3. Enforce claim validation (issuer, audience, expiry, scope).
  4. Map `sub` and scopes to internal identities/roles.
  5. Emit structured authentication metrics and trace attributes for success/failure.
- **Refresh tokens:**
  - Stored and issued by the IdP; never handled by the API service.
  - Use short-lived access tokens (≤15 minutes) with automatic refresh in clients.

## Threat modeling checkpoints
- **Replay attacks:** require nonce per authorization request (PKCE) and enforce `jti` uniqueness where supported.
- **Token substitution:** bind tokens to TLS by preferring DPoP or `cnf` confirmation when the IdP supports it.
- **CSRF:** state parameter on authorization requests; SameSite=Lax cookies for browser flows.
- **Brute force:** rate-limit token introspection and login attempts; enable IP- and user-based throttling.
- **Logging hygiene:** never log tokens or secrets; redact PII in structured logs.
  - For App Service, disable detailed error messages in responses; rely on structured logging and Application Insights for diagnostics.

## Client implementation guidance
- Web, mobile, CLI, and Rust clients should all rely on the same OIDC discovery document and JWKS.
- Clients must:
  - Use PKCE on interactive flows.
  - Store refresh tokens in secure storage (Keychain, Keystore) or avoid refresh tokens for CLI by using device code flow.
  - Retry with exponential backoff when JWKS retrieval fails, but cache previously valid keys to allow limited-time offline validation.
  - For low-cost Azure hosting, prefer short-lived access tokens and minimize refresh token lifetimes to reduce blast radius.
- Sample header for API calls:

```
Authorization: Bearer <access-token>
DPoP: <header-if-supported>
```

## Compliance and auditing
- Maintain an audit log for authentication decisions and calendar/event mutations, including `sub`, `scope`, and request id.
- Perform quarterly key-rotation drills and penetration tests on the OIDC integration.
- Include security test cases in automated pipelines (JWT validation, expired token handling, JWKS key rollover).
