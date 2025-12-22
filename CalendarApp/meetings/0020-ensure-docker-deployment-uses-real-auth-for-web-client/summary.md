# Meeting Summary

Meeting: 0020-ensure-docker-deployment-uses-real-auth-for-web-client
Task: ensure docker deployment uses real auth for web client

## Outcomes
- Web client now blocks startup when sync is enabled without a configured API/OIDC target, preventing silent fallback to seed data.
- Added runtime-config + Docker entrypoint wiring so container deployments inject `CALENDAR_API_BASE_URL` and `OIDC_*` settings with JWKS enforcement.
- Delivered OIDC/JWT helper modules and a remote adapter that verifies ES256/RS256 signatures before syncing calendar state.

## Decisions
- Require HTTPS (except localhost) and a JWKS URI for any remote sync path; seeds remain local-only.
- Persist remote state via the `/state` endpoint with bearer tokens, surfacing failures in the UI rather than falling back.

## Next steps
- Validate the web client against the live issuer/API combo and adjust the `/state` contract if the production API diverges.
- Add a deployment smoke check that confirms runtime-config generation, JWKS fetch, and the authorization redirect work end-to-end.
