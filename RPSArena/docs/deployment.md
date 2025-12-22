# RPS Arena Deployment Playbook
_This file is generated from src/utils/deploymentDocs.js. Update the source, not the outputs._

Deploy the ultra-fast competitive RPS Arena server with confidence. This guide covers configuration, local validation, and production rollout steps. Both the Markdown and HTML outputs are generated from this shared source so the guidance stays consistent.

## Architecture snapshot
The Node.js HTTP server (src/server.js) serves the API and static assets from /public.
Data persistence is optional. If MONGODB_URI is unset, the server falls back to an in-memory store. Production deployments should always provide a MongoDB connection string.
Matchmaking, unlockables, and leaderboards depend on the same backing store, so storage outages affect the full experience.

- API base: /api/* endpoints for registration, login, matchmaking, leaderboards, highscores, news, and match history.
- Static content: served from /public with index.html, styles.css, and client scripts.
- Process model: single Node.js process bound to PORT (defaults to 3000).

## Prerequisites
Node.js 22+ installed on the host or base image.
Network access to MongoDB if you want persistent storage.
A deployment environment capable of setting environment variables for secrets.

- `PORT` (optional): HTTP port; defaults to 3000.
- `MONGODB_URI` (recommended): MongoDB connection string. If omitted, the server runs in-memory and loses data on restart.
- `MONGODB_DB` (optional): Database name; defaults to `rpsarena`.
- `NODE_ENV` (optional): Set to `production` to align with hardened hosting defaults.

## Local validation
Validate the build and APIs locally before promoting to shared environments.
Use a local MongoDB instance if you want persistence; otherwise the in-memory store works for smoke tests.

### Install dependencies
Install npm dependencies from the project root.

```bash
    npm install
```
**Outcome:** Dependencies installed with lockfile alignment.

### Run automated tests
Enforce 100% coverage for the Node suite and run the Python tests that back shared tooling.

```bash
    npm test
    pytest --maxfail=1
```
**Outcome:** All suites green before deployment.

### Launch the server
Start the server with or without Mongo. When MONGODB_URI is set, indexes and news seeds are created automatically.

```bash
    MONGODB_URI="mongodb://localhost:27017" npm start
    # or run in-memory
npm start
```
**Outcome:** HTTP server listening on the configured port.

### Smoke check APIs
Ensure core endpoints respond before packaging.

```bash
    curl -i http://localhost:3000/api/news
    curl -i "http://localhost:3000/api/leaderboard?limit=5"
```
**Outcome:** 200 responses with JSON payloads confirm the server is reachable.

## Production deployment
Provide MongoDB credentials and a stable PORT binding. The server is single-process and stateless aside from its storage connection.
Rotate credentials safely. Avoid hardcoding secrets in images; inject them through your platform's configuration layer.

### Build or package the app
Package the server into a container or artifact that runs `npm start`. Keep the working directory at the repository root so static assets resolve correctly.

```bash
    # Example Dockerfile snippet
    FROM node:22-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ENV NODE_ENV=production
CMD ["npm", "start"]
```
**Outcome:** Runnable artifact that starts the Node.js server.

### Configure environment
Bind PORT, supply MONGODB_URI and MONGODB_DB, and set NODE_ENV=production. Ensure outbound connectivity to MongoDB.

```bash
    PORT=3000
    MONGODB_URI=mongodb+srv://<user>:<password>@<cluster>/rpsarena?retryWrites=true&w=majority
    MONGODB_DB=rpsarena
```
**Outcome:** Runtime configured with durable storage and predictable port binding.

### Smoke test after deploy
Hit the same endpoints used locally. Expect seeded news to appear and empty collections for players/matches until traffic arrives.

```bash
    curl -sS https://<host>/api/news
    curl -sS "https://<host>/api/highscores?variant=ranked&page=1&pageSize=10"
```
**Outcome:** Healthy JSON responses indicate the deployment is ready for traffic.

## Operational checklist
Track the following items each time you roll out to keep environments consistent.

- Backups: ensure MongoDB backups or snapshots are enabled.
- Scaling: run at least two replicas if your platform supports it; the server is stateless aside from MongoDB.
- Logging: ship stdout/stderr to your logging pipeline for API call traces and errors.
- TLS: terminate TLS at the platform or a reverse proxy in front of the Node process.
- Static assets: confirm /public is being served; a blank homepage often means the working directory is wrong.

## Production readiness checklist
- Environment variables set: PORT, MONGODB_URI, MONGODB_DB, NODE_ENV=production.
- MongoDB reachable from the app host and credentials validated.
- npm test and pytest --maxfail=1 have both been executed successfully.
- Smoke checks on /api/news and /api/leaderboard succeed post-deploy.
- Backups, logging, and TLS termination documented for the environment.

## References
- **Server entrypoint:** src/server.js
- **Mongo persistence:** src/data/mongoStore.js
- **Static assets:** public/index.html and supporting files
