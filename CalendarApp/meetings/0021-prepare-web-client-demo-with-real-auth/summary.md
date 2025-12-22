# Meeting Summary

Meeting: 0021-prepare-web-client-demo-with-real-auth
Task: prepare web client demo with real auth

## Outcomes
- Web client boot now demands configured API base + OIDC and verifies JWTs/JWKS before syncing, preventing seed-only demos in production.
- Runtime config is generated at container startup; Azure workflow enforces health checks and required secrets for public deployments.

## Decisions
- Fail fast when sync is enabled but config is incomplete; no silent fallback to seed data in public demos.
- Require HTTPS (except localhost) and JWKS validation before any remote state calls.

## Next steps
- Add live staging smoke to exercise auth redirect + JWKS fetch, and confirm `/state` contract with the production API.
- Monitor auth/JWKS errors to catch issuer drift early during demo validations.
