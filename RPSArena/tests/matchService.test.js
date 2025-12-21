import { strict as assert } from "node:assert";
import test from "node:test";
import { InMemoryStore } from "../src/data/inMemoryStore.js";
import { MatchService } from "../src/services/matchService.js";
import { UnlockableService } from "../src/services/unlockableService.js";
import { UserService } from "../src/services/userService.js";

async function setupPlayers() {
  const store = new InMemoryStore();
  const userService = new UserService(store);
  const unlockableService = new UnlockableService(store);
  const matchService = new MatchService(store, userService, unlockableService);

  const playerA = await userService.registerUser({
    username: "alpha",
    email: "alpha@example.com",
    password: "hunter2000",
    avatarColor: "123123",
  });
  const playerB = await userService.registerUser({
    username: "bravo",
    email: "bravo@example.com",
    password: "hunter2000",
    avatarColor: "321321",
  });
  return { store, userService, unlockableService, matchService, playerA, playerB };
}

test("matchmaking pairs players and resolves ranked classic", async () => {
  const { matchService, playerA, playerB, store } = await setupPlayers();
  matchService.enqueue(playerA.id, { mode: "classic", variant: "ranked", roundCount: 3 });
  const matched = matchService.enqueue(playerB.id, { mode: "classic", variant: "ranked", roundCount: 3 });
  assert.equal(matched.status, "matched");

  const waiting = await matchService.submitMoves(matched.match.id, playerA.id, { rounds: ["rock", "paper", "rock"] });
  assert.equal(waiting.status, "waiting");
  const completed = await matchService.submitMoves(matched.match.id, playerB.id, { rounds: ["scissors", "rock", "paper"] });
  assert.equal(completed.status, "completed");
  assert.equal(completed.result.winner, playerA.id);
  await assert.rejects(() => matchService.submitMoves(matched.match.id, playerA.id, { rounds: ["rock"] }));
  const history = await matchService.history(playerA.id, true);
  assert.equal(history.length, 1);
  const storedMatch = history[0];
  assert.ok(storedMatch.ratingChanges[playerA.id] !== undefined);

  const updatedWinner = await store.findUserById(playerA.id);
  assert.ok(updatedWinner.unlocks.rock.includes("basalt"));
});

test("extreme mode enforces equal lengths and can draw", async () => {
  const { matchService, playerA, playerB } = await setupPlayers();
  matchService.enqueue(playerA.id, { mode: "extreme", variant: "casual", roundCount: 2 });
  const matched = matchService.enqueue(playerB.id, { mode: "extreme", variant: "casual", roundCount: 2 });

  const waiting = await matchService.submitMoves(matched.match.id, playerA.id, { sequence: ["rock", "paper"] });
  assert.equal(waiting.status, "waiting");
  await assert.rejects(() => matchService.submitMoves(matched.match.id, playerB.id, { sequence: ["rock"] }));
  const completed = await matchService.submitMoves(matched.match.id, playerB.id, { sequence: ["rock", "paper"] });
  assert.equal(completed.result.winner, null);
});

test("enqueue prevents double-queuing", async () => {
  const { matchService, playerA } = await setupPlayers();
  matchService.enqueue(playerA.id, { mode: "classic", variant: "casual" });
  assert.throws(() => matchService.enqueue(playerA.id, { mode: "classic", variant: "casual" }), /already queued/);
});

test("player B flawless victory awards unlocks", async () => {
  const { matchService, playerA, playerB, store } = await setupPlayers();
  matchService.enqueue(playerA.id, { mode: "classic", variant: "casual" });
  const matched = matchService.enqueue(playerB.id, { mode: "classic", variant: "casual" });

  await matchService.submitMoves(matched.match.id, playerA.id, { rounds: ["rock", "rock"] });
  await matchService.submitMoves(matched.match.id, playerB.id, { rounds: ["paper", "paper"] });

  const updatedLoser = await store.findUserById(playerA.id);
  const updatedWinner = await store.findUserById(playerB.id);
  assert.equal(updatedLoser.achievements.streak, 0);
  assert.ok(updatedWinner.unlocks.paper.includes("satin") || updatedWinner.unlocks.rock.includes("basalt"));
});

test("classic submissions must align in length", async () => {
  const { matchService, playerA, playerB } = await setupPlayers();
  matchService.enqueue(playerA.id, { mode: "classic", variant: "casual" });
  const matched = matchService.enqueue(playerB.id, { mode: "classic", variant: "casual" });
  await matchService.submitMoves(matched.match.id, playerA.id, { rounds: ["rock"] });
  await assert.rejects(
    () => matchService.submitMoves(matched.match.id, playerB.id, { rounds: ["rock", "paper"] }),
    /same number/,
  );
});

test("resolveMatch verifies users exist", async () => {
  const { matchService, playerA, playerB, store } = await setupPlayers();
  matchService.enqueue(playerA.id, { mode: "classic", variant: "ranked" });
  const matched = matchService.enqueue(playerB.id, { mode: "classic", variant: "ranked" });
  await matchService.submitMoves(matched.match.id, playerA.id, { rounds: ["rock"] });
  store.users.delete(playerB.id);
  await assert.rejects(
    () => matchService.submitMoves(matched.match.id, playerB.id, { rounds: ["scissors"] }),
    /must exist/,
  );
});

test("normalizeSubmission rejects unsupported modes", async () => {
  const { matchService } = await setupPlayers();
  assert.throws(() => matchService.normalizeSubmission("arcade", {}), /Unsupported mode/);
  await assert.rejects(() => matchService.submitMoves("missing", "nobody", { rounds: ["rock"] }), /not found/);
});

test("submitMoves enforces round counts and membership", async () => {
  const { matchService, playerA, playerB } = await setupPlayers();
  assert.throws(() => matchService.enqueue(playerA.id, { mode: "classic", variant: "casual", roundCount: 0 }));
  matchService.enqueue(playerA.id, { mode: "classic", variant: "casual" });
  const matched = matchService.enqueue(playerB.id, { mode: "classic", variant: "casual" });
  const record = matchService.activeMatches.get(matched.match.id);
  record.match.state = "completed";
  await assert.rejects(() => matchService.submitMoves(matched.match.id, playerA.id, { rounds: ["rock"] }), /completed/);
  record.match.state = "awaiting-submissions";
  await assert.rejects(() => matchService.submitMoves(matched.match.id, "intruder", { rounds: ["rock"] }), /not part/);
});
