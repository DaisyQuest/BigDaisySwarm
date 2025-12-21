import { strict as assert } from "node:assert";
import test from "node:test";
import {
  normalizeColor,
  requireFields,
  validateMode,
  validateAvatarColor,
  validateEmail,
  validateMoveSequence,
  validateVariant,
} from "../src/utils/validation.js";

test("validateEmail", () => {
  assert.ok(validateEmail("user@example.com"));
  assert.ok(!validateEmail("invalid@com"));
});

test("normalizeColor ensures hash and lower", () => {
  assert.equal(normalizeColor("ABCDEF"), "#abcdef");
  assert.equal(normalizeColor("#a1b2c3"), "#a1b2c3");
  assert.throws(() => normalizeColor("oops"));
});

test("requireFields throws when missing", () => {
  assert.doesNotThrow(() => requireFields({ a: 1 }, ["a"]));
  assert.throws(() => requireFields({}, ["a"]));
});

test("validateMoveSequence guards moves", () => {
  assert.doesNotThrow(() => validateMoveSequence(["rock", "paper"]));
  assert.throws(() => validateMoveSequence([]));
  assert.throws(() => validateMoveSequence(["rock", "lizard"]));
});

test("validateMode and validateVariant guard inputs", () => {
  assert.doesNotThrow(() => validateMode("classic"));
  assert.throws(() => validateMode("arcade"));
  assert.doesNotThrow(() => validateVariant("ranked"));
  assert.throws(() => validateVariant("hardcore"));
});
