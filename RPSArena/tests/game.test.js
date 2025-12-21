import { strict as assert } from "node:assert";
import test from "node:test";
import { eloDelta, roundOutcome, scoreClassicMatch, scoreExtremeMatch } from "../src/game/rpsLogic.js";

test("roundOutcome determines winners", () => {
  assert.equal(roundOutcome("rock", "scissors"), 1);
  assert.equal(roundOutcome("scissors", "rock"), -1);
  assert.equal(roundOutcome("paper", "paper"), 0);
  assert.throws(() => roundOutcome("lizard", "rock"));
});

test("scoreClassicMatch aggregates rounds", () => {
  const result = scoreClassicMatch([
    { a: "rock", b: "scissors" },
    { a: "rock", b: "paper" },
    { a: "paper", b: "rock" },
  ]);
  assert.equal(result.winner, "playerA");
  assert.equal(result.roundResults.length, 3);
  assert.throws(() => scoreClassicMatch([]));
});

test("scoreExtremeMatch requires equal length", () => {
  const result = scoreExtremeMatch(["rock", "paper"], ["scissors", "rock"]);
  assert.equal(result.winner, "playerA");
  assert.throws(() => scoreExtremeMatch(["rock"], ["rock", "paper"]));
  assert.throws(() => scoreExtremeMatch("rock", ["rock"]));
  assert.throws(() => scoreExtremeMatch([], []));
});

test("eloDelta shifts ratings", () => {
  const delta = eloDelta(1200, 1200, 1);
  assert.equal(delta, 16);
  const deltaDraw = eloDelta(1200, 1200, 0.5);
  assert.equal(deltaDraw, 0);
});
