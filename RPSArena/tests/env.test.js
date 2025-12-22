import { strict as assert } from "node:assert";
import test from "node:test";

import { __test__, resolveMongoClientOptions, resolvePort } from "../src/utils/env.js";

const { normalizeBoolean } = __test__;

test("normalizeBoolean handles booleans, numbers, and empty strings", () => {
  assert.equal(normalizeBoolean(true), true);
  assert.equal(normalizeBoolean("TRUE"), true);
  assert.equal(normalizeBoolean("1"), true);
  assert.equal(normalizeBoolean("no"), false);
  assert.equal(normalizeBoolean(0), false);
  assert.equal(normalizeBoolean(undefined), false);
  assert.equal(normalizeBoolean("", true), true);
});

test("resolvePort prefers PORT then WEBSITES_PORT before defaulting", () => {
  assert.equal(resolvePort({ PORT: "8080" }), 8080);
  assert.equal(resolvePort({ PORT: "invalid", WEBSITES_PORT: "9090" }), 9090);
  assert.equal(resolvePort({ WEBSITES_PORT: "0" }), 3000);
  assert.equal(resolvePort({}), 3000);
});

test("resolveMongoClientOptions maps TLS flags, CA file, and timeouts", () => {
  const options = resolveMongoClientOptions({
    MONGODB_TLS: "true",
    MONGODB_TLS_ALLOW_INVALID_CERTS: "1",
    MONGODB_TLS_CA_FILE: "/certs/ca.pem",
    MONGODB_SERVER_SELECTION_TIMEOUT_MS: "5000",
  });

  assert.deepEqual(options, {
    tls: true,
    tlsAllowInvalidCertificates: true,
    tlsCAFile: "/certs/ca.pem",
    serverSelectionTimeoutMS: 5000,
  });
});

test("resolveMongoClientOptions ignores invalid timeout and records explicit false", () => {
  const withInvalidTimeout = resolveMongoClientOptions({
    MONGODB_TLS: "",
    MONGODB_SERVER_SELECTION_TIMEOUT_MS: "abc",
  });

  assert.deepEqual(withInvalidTimeout, { tls: false });
});
