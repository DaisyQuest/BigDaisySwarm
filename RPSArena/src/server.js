import http from "http";
import { readFile, stat } from "fs/promises";
import path from "path";
import { fileURLToPath } from "url";

import { MODES, VARIANTS } from "./constants.js";
import { buildServices, createJsonResponder } from "./services/bootstrap.js";
import { resolveMongoClientOptions, resolvePort } from "./utils/env.js";
import { requireFields } from "./utils/validation.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const publicDir = path.join(__dirname, "../public");

async function parseBody(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  const raw = Buffer.concat(chunks).toString();
  if (!raw) return {};
  try {
    return JSON.parse(raw);
  } catch (error) {
    throw new Error("Invalid JSON payload");
  }
}

function notFound(res) {
  res.writeHead(404);
  res.end();
}

function methodNotAllowed(res) {
  res.writeHead(405);
  res.end();
}

async function serveStatic(req, res) {
  const url = new URL(req.url, `http://${req.headers.host}`);
  const requestedPath = url.pathname === "/" ? "/index.html" : url.pathname;
  const relativePath = requestedPath.startsWith("/public/")
    ? requestedPath.replace("/public", "")
    : requestedPath;
  const filePath = path.join(publicDir, relativePath);
  try {
    const stats = await stat(filePath);
    if (stats.isDirectory()) {
      return notFound(res);
    }
    const content = await readFile(filePath);
    const ext = path.extname(filePath);
    const contentType = ext === ".css" ? "text/css" : ext === ".js" ? "application/javascript" : "text/html";
    res.writeHead(200, { "Content-Type": contentType });
    res.end(content);
    return true;
  } catch (error) {
    return false;
  }
}

function parseBoolean(value) {
  return value === "true" || value === true;
}

const servicesPromise = buildServices({ mongoOptions: resolveMongoClientOptions() });
const port = resolvePort();

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  const json = createJsonResponder(res);
  if (url.pathname.startsWith("/api/")) {
    const { userService, matchService } = await servicesPromise;
    try {
      if (url.pathname === "/api/register" && req.method === "POST") {
        const payload = await parseBody(req);
        const user = await userService.registerUser(payload);
        return json(201, user);
      }

      if (url.pathname === "/api/login" && req.method === "POST") {
        const payload = await parseBody(req);
        const user = await userService.authenticate(payload.email, payload.password);
        return json(200, user);
      }

      if (url.pathname === "/api/avatar" && req.method === "PATCH") {
        const payload = await parseBody(req);
        requireFields(payload, ["userId", "avatarColor"]);
        const user = await userService.updateAvatar(payload.userId, payload.avatarColor);
        return json(200, user);
      }

      if (url.pathname === "/api/leaderboard" && req.method === "GET") {
        const limit = Number.parseInt(url.searchParams.get("limit") || "100", 10);
        const offset = Number.parseInt(url.searchParams.get("offset") || "0", 10);
        const variant = url.searchParams.get("variant") || VARIANTS.RANKED;
        const board = await userService.leaderboard(limit, offset, variant);
        return json(200, board);
      }

      if (url.pathname === "/api/highscores" && req.method === "GET") {
        const page = Number.parseInt(url.searchParams.get("page") || "1", 10);
        const pageSize = Number.parseInt(url.searchParams.get("pageSize") || "25", 10);
        const variant = url.searchParams.get("variant") || VARIANTS.RANKED;
        const scores = await userService.highScores(page, pageSize, variant);
        return json(200, scores);
      }

      if (url.pathname === "/api/history" && req.method === "GET") {
        const playerId = url.searchParams.get("playerId") || undefined;
        const rankedOnly = parseBoolean(url.searchParams.get("rankedOnly"));
        const history = await matchService.history(playerId, rankedOnly);
        return json(200, history);
      }

      if (url.pathname === "/api/matchmaking" && req.method === "POST") {
        const payload = await parseBody(req);
        requireFields(payload, ["userId", "mode", "variant"]);
        const response = matchService.enqueue(payload.userId, {
          mode: payload.mode,
          variant: payload.variant,
          roundCount: payload.roundCount || 3,
        });
        return json(200, response);
      }

      if (url.pathname === "/api/match/submit" && req.method === "POST") {
        const payload = await parseBody(req);
        requireFields(payload, ["matchId", "userId"]);
        const outcome = await matchService.submitMoves(payload.matchId, payload.userId, payload);
        return json(200, outcome);
      }

      if (url.pathname === "/api/news" && req.method === "GET") {
        const { store } = await servicesPromise;
        const news = await store.listNews();
        return json(200, news);
      }

      return notFound(res);
    } catch (error) {
      return json(400, { error: error.message });
    }
  }

  const served = await serveStatic(req, res);
  if (!served) {
    notFound(res);
  }
});

servicesPromise
  .then(({ usedMongo, error }) => {
    if (!usedMongo && error && console.warn) {
      console.warn("MongoDB unavailable; using in-memory store", error);
    }
  })
  .catch((error) => {
    console.error("Service bootstrap failed", error);
  });

server.listen(port, () => {
  servicesPromise
    .then((services) => (services.usedMongo ? "MongoDB" : "in-memory"))
    .then((backend) => {
      console.log(`RPS Arena server listening on port ${port} using ${backend} storage`);
    })
    .catch((error) => {
      console.error(`RPS Arena server listening on port ${port} (storage unavailable during bootstrap)`, error);
    });
});

export default server;
