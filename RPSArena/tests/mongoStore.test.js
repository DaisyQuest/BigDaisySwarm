import { strict as assert } from "node:assert";
import test from "node:test";
import { MongoClient } from "mongodb";
import { MongoStore } from "../src/data/mongoStore.js";
import { createUser } from "../src/data/modelFactories.js";

function getValue(obj, key) {
  return key.split(".").reduce((acc, part) => (acc ? acc[part] : undefined), obj);
}

class FakeCollection {
  constructor() {
    this.items = [];
  }

  async insertOne(doc) {
    this.items.push(structuredClone(doc));
  }

  async findOne(query) {
    return (
      this.items.find((item) =>
        Object.entries(query).every(([key, value]) => {
          const itemValue = getValue(item, key);
          if (Array.isArray(itemValue)) {
            return itemValue.includes(value);
          }
          return itemValue === value;
        }),
      ) || null
    );
  }

  async replaceOne(filter, doc) {
    const idx = this.items.findIndex((item) => item.id === filter.id);
    if (idx !== -1) {
      this.items[idx] = structuredClone(doc);
    }
  }

  find(query = {}) {
    const self = this;
    let results = this.items.filter((item) =>
      Object.entries(query).every(([key, value]) => {
        const itemValue = getValue(item, key);
        if (Array.isArray(itemValue)) {
          return itemValue.includes(value);
        }
        return itemValue === value || value === undefined;
      }),
    );
    const chain = {
      sort(sortBy) {
        const [[key, dir]] = Object.entries(sortBy);
        results = results.sort((a, b) => (getValue(b, key) - getValue(a, key)) * (dir || 1));
        return chain;
      },
      skip(count) {
        results = results.slice(count);
        return chain;
      },
      limit(count) {
        results = results.slice(0, count);
        return chain;
      },
      async toArray() {
        return results.map((item) => structuredClone(item));
      },
    };
    return chain;
  }

  async toArray() {
    return this.items.map((item) => structuredClone(item));
  }

  async createIndex() {
    return true;
  }

  async updateOne(filter, update, { upsert } = {}) {
    const existing = await this.findOne(filter);
    if (existing) {
      const idx = this.items.indexOf(existing);
      const mutated = structuredClone(existing);
      if (update.$set) Object.assign(mutated, update.$set);
      if (update.$setOnInsert) Object.assign(mutated, update.$setOnInsert);
      this.items[idx] = mutated;
    } else if (upsert) {
      this.items.push(structuredClone(update.$set || update.$setOnInsert || filter));
    }
  }
}

class FakeDb {
  constructor() {
    this.collections = {
      users: new FakeCollection(),
      matches: new FakeCollection(),
      news: new FakeCollection(),
    };
  }

  collection(name) {
    return this.collections[name];
  }
}

class FakeClient {
  constructor(db) {
    this.dbInstance = db;
    this.closed = false;
  }

  async connect() {
    this.connected = true;
  }

  db() {
    return this.dbInstance;
  }

  close() {
    this.closed = true;
  }
}

test("MongoStore performs CRUD operations via driver shape", async () => {
  const db = new FakeDb();
  const store = new MongoStore(db);
  await store.ensureIndexes();
  await store.seedNews();

  const user = createUser({
    id: "mongo-user",
    username: "mongo",
    email: "mongo@example.com",
    passwordHash: "hash",
    avatarColor: "#123456",
  });
  await store.createUser(user);
  const found = await store.findUserByEmail("mongo@example.com");
  assert.equal(found.username, "mongo");
  const byUsername = await store.findUserByUsername("mongo");
  assert.equal(byUsername.email, "mongo@example.com");
  const missing = await store.findUserByEmail("none@example.com");
  assert.equal(missing, null);
  const missingByUsername = await store.findUserByUsername("ghost");
  assert.equal(missingByUsername, null);
  const missingUser = await store.updateUser("missing", (current) => current);
  assert.equal(missingUser, null);

  const updated = await store.updateUser("mongo-user", (current) => ({ ...current, avatarColor: "#654321" }));
  assert.equal(updated.avatarColor, "#654321");

  const leaderboard = await store.listLeaderboard(1, 0, "ranked");
  assert.equal(leaderboard.length, 1);

  const unlocked = await store.addUnlockables("mongo-user", { scissors: ["laser"] });
  assert.ok(unlocked.unlocks.scissors.includes("laser"));
  await store.updateUser("mongo-user", (user) => {
    delete user.unlocks;
    return user;
  });
  const rebuilt = await store.addUnlockables("mongo-user", { rock: ["slate"] });
  assert.ok(rebuilt.unlocks.rock.includes("slate"));
  const unlockedMissing = await store.addUnlockables("missing-user", { rock: ["granite"] });
  assert.equal(unlockedMissing, null);

  await store.recordMatch({ id: "m1", players: ["mongo-user"], variant: "ranked" });
  const matches = await store.listMatches({ playerId: "mongo-user", rankedOnly: true });
  assert.equal(matches.length, 1);

  await store.addNews({ id: "custom", title: "Hello" });
  const news = await store.listNews();
  assert.ok(news.some((n) => n.id === "custom"));
});

test("MongoStore.connect wires a client factory", async () => {
  const db = new FakeDb();
  const fakeClient = new FakeClient(db);
  const { store, client } = await MongoStore.connect("memory://test", "rpsarena", () => fakeClient);
  assert.ok(store instanceof MongoStore);
  assert.ok(fakeClient.connected);
  await client.close();
  assert.ok(fakeClient.closed);
});

test("MongoStore.connect forwards client options to the factory", async () => {
  const db = new FakeDb();
  const fakeClient = new FakeClient(db);
  let capturedOptions = null;

  const factory = (uri, options) => {
    assert.equal(uri, "mongodb://secure");
    capturedOptions = options;
    return fakeClient;
  };

  await MongoStore.connect("mongodb://secure", "securedb", factory, { tls: true, tlsAllowInvalidCertificates: true });

  assert.deepEqual(capturedOptions, { tls: true, tlsAllowInvalidCertificates: true });
});

test("MongoStore.connect can use default MongoClient factory", async () => {
  const db = new FakeDb();
  const originalConnect = MongoClient.prototype.connect;
  const originalDb = MongoClient.prototype.db;
  const originalClose = MongoClient.prototype.close;
  MongoClient.prototype.connect = async function () {
    this.connected = true;
    return this;
  };
  MongoClient.prototype.db = () => db;
  MongoClient.prototype.close = async function () {
    this.closed = true;
  };

  const { client } = await MongoStore.connect("mongodb://localhost:27017/default");
  assert.ok(client.connected);
  await client.close();
  assert.ok(client.closed);

  MongoClient.prototype.connect = originalConnect;
  MongoClient.prototype.db = originalDb;
  MongoClient.prototype.close = originalClose;
});
