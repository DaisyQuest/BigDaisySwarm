import { MongoClient } from "mongodb";
import { DEFAULT_UNLOCKS, NEWS_BULLETINS } from "../constants.js";

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

export class MongoStore {
  constructor(db) {
    this.db = db;
    this.usersCollection = db.collection("users");
    this.matchesCollection = db.collection("matches");
    this.newsCollection = db.collection("news");
  }

  static async connect(uri, dbName = "rpsarena", clientFactory, clientOptions = {}) {
    const factory = clientFactory ?? ((url, options) => new MongoClient(url, options));
    const client = factory(uri, clientOptions);
    await client.connect();
    const db = client.db(dbName);
    const store = new MongoStore(db);
    await store.ensureIndexes();
    await store.seedNews();
    return { store, client };
  }

  async ensureIndexes() {
    await this.usersCollection.createIndex({ email: 1 }, { unique: true });
    await this.usersCollection.createIndex({ username: 1 }, { unique: true });
    await this.matchesCollection.createIndex({ players: 1 });
    await this.newsCollection.createIndex({ id: 1 }, { unique: true });
  }

  async seedNews() {
    for (const item of NEWS_BULLETINS) {
      await this.newsCollection.updateOne({ id: item.id }, { $setOnInsert: item }, { upsert: true });
    }
  }

  async createUser(user) {
    await this.usersCollection.insertOne(user);
    return clone(user);
  }

  async findUserByEmail(email) {
    const user = await this.usersCollection.findOne({ email });
    return user ? clone(user) : null;
  }

  async findUserByUsername(username) {
    const user = await this.usersCollection.findOne({ username });
    return user ? clone(user) : null;
  }

  async findUserById(userId) {
    const user = await this.usersCollection.findOne({ id: userId });
    return user ? clone(user) : null;
  }

  async updateUser(userId, updater) {
    const existing = await this.findUserById(userId);
    if (!existing) return null;
    const updated = updater(existing);
    updated.updatedAt = new Date().toISOString();
    await this.usersCollection.replaceOne({ id: userId }, updated);
    return clone(updated);
  }

  async listLeaderboard(limit = 100, offset = 0, variant = "ranked") {
    const cursor = this.usersCollection
      .find()
      .sort({ [`ratings.${variant}`]: -1 })
      .skip(offset)
      .limit(limit);
    const users = await cursor.toArray();
    return clone(users);
  }

  async recordMatch(match) {
    await this.matchesCollection.insertOne(match);
    return clone(match);
  }

  async listMatches({ playerId, rankedOnly = false } = {}) {
    const query = {};
    if (playerId) query.players = playerId;
    if (rankedOnly) query.variant = "ranked";
    const matches = await this.matchesCollection.find(query).toArray();
    return clone(matches);
  }

  async addNews(item) {
    await this.newsCollection.updateOne({ id: item.id }, { $set: item }, { upsert: true });
    return clone(item);
  }

  async listNews() {
    const news = await this.newsCollection.find().sort({ category: 1 }).toArray();
    return clone(news);
  }

  async addUnlockables(userId, unlocks) {
    return this.updateUser(userId, (user) => {
      const merged = { ...DEFAULT_UNLOCKS };
      for (const key of Object.keys(merged)) {
        const existing = user.unlocks?.[key] || [];
        const incoming = unlocks[key] || [];
        merged[key] = Array.from(new Set([...existing, ...incoming]));
      }
      user.unlocks = merged;
      return user;
    });
  }
}
