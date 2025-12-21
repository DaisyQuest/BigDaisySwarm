import { strict as assert } from "node:assert";
import test from "node:test";
import { hashPassword, verifyPassword } from "../src/utils/crypto.js";

test("hashPassword rejects short passwords", () => {
  assert.throws(() => hashPassword("short"));
});

test("hashPassword and verifyPassword round-trip", () => {
  const hash = hashPassword("strongPassword");
  assert.ok(verifyPassword("strongPassword", hash));
  assert.ok(!verifyPassword("wrong", hash));
  assert.ok(!verifyPassword("whatever", "malformed-hash"));
  assert.ok(!verifyPassword("whatever"));
});
