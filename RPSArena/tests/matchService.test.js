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

test("matchmaking pairs players, loads profiles, and resolves ranked classic", async () => {
  const { matchService, playerA, playerB, store } = await setupPlayers();
  await matchService.enqueue(playerA.id, { mode: "classic", variant: "ranked", roundCount: 3 });
  const matched = await matchService.enqueue(playerB.id, { mode: "classic", variant: "ranked", roundCount: 3 });
  assert.equal(matched.status, "matched");
  assert.equal(matched.match.players[0], playerA.id);
  assert.ok(matched.match.playerProfiles.some((profile) => profile.id === playerA.id));
  assert.ok(matched.match.playerProfiles.every((profile) => profile.passwordHash === undefined));

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
  await matchService.enqueue(playerA.id, { mode: "extreme", variant: "casual", roundCount: 2 });
  const matched = await matchService.enqueue(playerB.id, { mode: "extreme", variant: "casual", roundCount: 2 });

  const waiting = await matchService.submitMoves(matched.match.id, playerA.id, { sequence: ["rock", "paper"] });
  assert.equal(waiting.status, "waiting");
  await assert.rejects(() => matchService.submitMoves(matched.match.id, playerB.id, { sequence: ["rock"] }));
  const completed = await matchService.submitMoves(matched.match.id, playerB.id, { sequence: ["rock", "paper"] });
  assert.equal(completed.result.winner, null);
});

test("enqueue reports queued status on repeat requests", async () => {
  const { matchService, playerA } = await setupPlayers();
  const first = await matchService.enqueue(playerA.id, { mode: "classic", variant: "casual" });
  assert.equal(first.status, "queued");
  const second = await matchService.enqueue(playerA.id, { mode: "classic", variant: "casual" });
  assert.equal(second.status, "queued");
});

test("player B flawless victory awards unlocks", async () => {
  const { matchService, playerA, playerB, store } = await setupPlayers();
  await matchService.enqueue(playerA.id, { mode: "classic", variant: "casual" });
  const matched = await matchService.enqueue(playerB.id, { mode: "classic", variant: "casual" });

  await matchService.submitMoves(matched.match.id, playerA.id, { rounds: ["rock", "rock"] });
  await matchService.submitMoves(matched.match.id, playerB.id, { rounds: ["paper", "paper"] });

  const updatedLoser = await store.findUserById(playerA.id);
  const updatedWinner = await store.findUserById(playerB.id);
  assert.equal(updatedLoser.achievements.streak, 0);
  assert.ok(updatedWinner.unlocks.paper.includes("satin") || updatedWinner.unlocks.rock.includes("basalt"));
});

test("classic submissions must align in length", async () => {
  const { matchService, playerA, playerB } = await setupPlayers();
  await matchService.enqueue(playerA.id, { mode: "classic", variant: "casual" });
  const matched = await matchService.enqueue(playerB.id, { mode: "classic", variant: "casual" });
  await matchService.submitMoves(matched.match.id, playerA.id, { rounds: ["rock"] });
  await assert.rejects(
    () => matchService.submitMoves(matched.match.id, playerB.id, { rounds: ["rock", "paper"] }),
    /same number/,
  );
});

test("resolveMatch verifies users exist", async () => {
  const { matchService, playerA, playerB, store } = await setupPlayers();
  await matchService.enqueue(playerA.id, { mode: "classic", variant: "ranked" });
  const matched = await matchService.enqueue(playerB.id, { mode: "classic", variant: "ranked" });
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
  await assert.rejects(() =>
    matchService.enqueue(playerA.id, { mode: "classic", variant: "casual", roundCount: 0 }),
  );
  await matchService.enqueue(playerA.id, { mode: "classic", variant: "casual" });
  const matched = await matchService.enqueue(playerB.id, { mode: "classic", variant: "casual" });
  const record = matchService.activeMatches.get(matched.match.id);
  record.match.state = "completed";
  await assert.rejects(() => matchService.submitMoves(matched.match.id, playerA.id, { rounds: ["rock"] }), /completed/);
  record.match.state = "awaiting-submissions";
  await assert.rejects(() => matchService.submitMoves(matched.match.id, "intruder", { rounds: ["rock"] }), /not part/);
});

test("players can poll matchmaking to receive their paired game", async () => {
  const { matchService, playerA, playerB } = await setupPlayers();
  const queued = await matchService.enqueue(playerA.id, { mode: "classic", variant: "casual", roundCount: 5 });
  assert.equal(queued.status, "queued");

  const matched = await matchService.enqueue(playerB.id, { mode: "classic", variant: "casual", roundCount: 3 });
  assert.equal(matched.match.roundCount, 5);

  const polled = await matchService.enqueue(playerA.id, { mode: "classic", variant: "casual" });
  assert.equal(polled.status, "matched");
  assert.equal(polled.match.id, matched.match.id);
  assert.equal(polled.match.players.includes(playerB.id), true);
  assert.equal(polled.match.playerProfiles.length, 2);
  assert.ok(polled.match.playerProfiles.some((profile) => profile.username === "bravo"));
});

test("enqueue restores queue when opponent is missing from the store", async () => {
  const { matchService, playerA } = await setupPlayers();
  await matchService.enqueue(playerA.id, { mode: "classic", variant: "ranked" });
  await assert.rejects(
    () => matchService.enqueue("ghost", { mode: "classic", variant: "ranked" }),
    /exist before matchmaking/,
  );
  const status = await matchService.enqueue(playerA.id, { mode: "classic", variant: "ranked" });
  assert.equal(status.status, "queued");
});

test("playBot creates a bot opponent and hydrates profiles", async () => {
  const { matchService, playerA, store } = await setupPlayers();
  const response = await matchService.playBot(playerA.id, { mode: "classic", variant: "casual", roundCount: 2 });
  assert.equal(response.status, "matched");
  assert.ok(response.match.players.includes(matchService.botId));
  assert.equal(response.match.roundCount, 2);
  assert.equal(response.match.playerProfiles.length, 2);
  assert.ok(response.match.playerProfiles.every((p) => p.passwordHash === undefined));

  const bot = await store.findUserById(matchService.botId);
  assert.ok(bot);
  assert.equal(bot.username, "ArenaBot");
});

test("playBot returns existing active match and reuses bot user", async () => {
  const { matchService, playerA, store } = await setupPlayers();
  const first = await matchService.playBot(playerA.id, { mode: "classic", variant: "casual" });
  const second = await matchService.playBot(playerA.id, { mode: "classic", variant: "casual" });
  assert.equal(second.match.id, first.match.id);

  const bot = await matchService.ensureBotUser();
  const existing = await matchService.ensureBotUser();
  assert.equal(bot.id, existing.id);
  const allUsers = [...store.users.values()].map((u) => u.id);
  assert.equal(allUsers.filter((id) => id === matchService.botId).length, 1);
});

test("playBot enforces minimum round count", async () => {
  const { matchService, playerA } = await setupPlayers();
  await assert.rejects(() => matchService.playBot(playerA.id, { mode: "classic", variant: "casual", roundCount: 0 }));
});
