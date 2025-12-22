import { InMemoryStore } from "../data/inMemoryStore.js";
import { MongoStore } from "../data/mongoStore.js";
import { MatchService } from "./matchService.js";
import { UnlockableService } from "./unlockableService.js";
import { UserService } from "./userService.js";

export async function chooseStore({
  mongoUri = process.env.MONGODB_URI,
  dbName = process.env.MONGODB_DB || "rpsarena",
  connector = MongoStore.connect,
  fallbackFactory = () => new InMemoryStore(),
  logger = console,
  onExit = process.on,
} = {}) {
  if (!mongoUri) {
    return { store: fallbackFactory(), client: null, usedMongo: false };
  }

  try {
    const { store, client } = await connector(mongoUri, dbName);
    if (client && onExit) {
      onExit("exit", () => client.close());
    }
    return { store, client, usedMongo: true };
  } catch (error) {
    if (logger?.error) {
      logger.error("Failed to connect to MongoDB, falling back to in-memory store", error);
    }
    return { store: fallbackFactory(), client: null, usedMongo: false, error };
  }
}

export async function buildServices(options = {}) {
  const { store, client, usedMongo, error } = await chooseStore(options);
  const userService = new UserService(store);
  const unlockableService = new UnlockableService(store);
  const matchService = new MatchService(store, userService, unlockableService);
  return { store, client, usedMongo, error, userService, unlockableService, matchService };
}

export function createJsonResponder(res = { writeHead: () => {}, end: () => {} }) {
  return function json(status, payload) {
    res.writeHead(status, { "Content-Type": "application/json" });
    res.end(JSON.stringify(payload));
  };
}
