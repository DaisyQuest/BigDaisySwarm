import assert from "node:assert/strict";
import test from "node:test";

import { buildServices, chooseStore, createJsonResponder } from "../src/services/bootstrap.js";

test("chooseStore returns in-memory when no Mongo URI provided", async () => {
  const { store, client, usedMongo, error } = await chooseStore({ mongoUri: "" });

  assert.equal(usedMongo, false);
  assert.equal(client, null);
  assert.equal(typeof store.listNews, "function");
  assert.equal(error, undefined);
});

test("chooseStore returns Mongo store and wires exit handler", async () => {
  let closeCalled = false;
  let exitCallback;
  const fakeClient = { close: () => (closeCalled = true) };
  const connector = async (uri, dbName, _factory, options) => {
    assert.equal(uri, "mongo://example");
    assert.equal(dbName, "customdb");
    assert.deepEqual(options, { tls: true });
    return { store: { kind: "mongo" }, client: fakeClient };
  };
  const onExit = (signal, cb) => {
    assert.equal(signal, "exit");
    exitCallback = cb;
  };

  const { store, client, usedMongo, error } = await chooseStore({
    mongoUri: "mongo://example",
    dbName: "customdb",
    mongoOptions: { tls: true },
    connector,
    onExit,
  });

  assert.equal(usedMongo, true);
  assert.equal(store.kind, "mongo");
  assert.equal(client, fakeClient);
  assert.equal(typeof exitCallback, "function");
  assert.equal(error, undefined);

  exitCallback();
  assert.equal(closeCalled, true, "client close should be invoked on process exit");
});

test("chooseStore logs and falls back on Mongo connection failure", async () => {
  const messages = [];
  const logger = { error: (...args) => messages.push(args.join(" ")) };
  const error = new Error("boom");
  const fallbackStore = { name: "memory" };
  const connector = async () => {
    throw error;
  };

  const result = await chooseStore({ mongoUri: "mongodb://bad", connector, fallbackFactory: () => fallbackStore, logger });

  assert.equal(result.usedMongo, false);
  assert.equal(result.client, null);
  assert.equal(result.store, fallbackStore);
  assert.equal(result.error, error);
  assert.ok(messages.some((msg) => msg.includes("Failed to connect")));
});

test("chooseStore forwards explicit Mongo client options", async () => {
  const mongoOptions = { tlsAllowInvalidCertificates: true, serverSelectionTimeoutMS: 5000 };
  let receivedOptions;
  const connector = async (uri, dbName, _factory, options) => {
    receivedOptions = options;
    return { store: { kind: "mongo" }, client: null };
  };

  const result = await chooseStore({ mongoUri: "mongodb://secure", connector, mongoOptions });

  assert.equal(result.usedMongo, true);
  assert.equal(result.error, undefined);
  assert.equal(result.client, null);
  assert.equal(result.store.kind, "mongo");
  assert.equal(receivedOptions, mongoOptions);
});

test("buildServices returns fully wired services", async () => {
  const store = { label: "store" };
  const connector = async () => ({ store, client: null });
  const services = await buildServices({ mongoUri: "mongodb://mock", connector });

  assert.equal(services.store, store);
  assert.ok(services.userService);
  assert.ok(services.unlockableService);
  assert.ok(services.matchService);
});

test("createJsonResponder writes headers and payload", () => {
  const calls = [];
  const res = {
    writeHead: (status, headers) => calls.push(["writeHead", status, headers]),
    end: (body) => calls.push(["end", body]),
  };
  const responder = createJsonResponder(res);

  responder(201, { ok: true });

  assert.deepEqual(calls[0], ["writeHead", 201, { "Content-Type": "application/json" }]);
  assert.deepEqual(JSON.parse(calls[1][1]), { ok: true });
});

test("createJsonResponder falls back to noop response when omitted", () => {
  const responder = createJsonResponder();
  assert.doesNotThrow(() => responder(204, { empty: true }));
});
