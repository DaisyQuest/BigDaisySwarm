import { strict as assert } from "node:assert";
import test from "node:test";
import { InMemoryStore } from "../src/data/inMemoryStore.js";
import { createUser } from "../src/data/modelFactories.js";
import { UserService } from "../src/services/userService.js";

function buildService() {
  const store = new InMemoryStore();
  const userService = new UserService(store);
  return { store, userService };
}

test("sanitize returns null when user missing", () => {
  const { userService } = buildService();
  assert.equal(userService.sanitize(null), null);
});

test("registerUser creates sanitized profiles and enforces uniqueness", async () => {
  const { userService, store } = buildService();
  const user = await userService.registerUser({
    username: "arenaMaster",
    email: "master@example.com",
    password: "hunter2000",
    avatarColor: "abcdef",
  });
  assert.ok(user.id);
  assert.equal(user.avatarColor, "#abcdef");
  const stored = await store.findUserByEmail("master@example.com");
  assert.ok(stored.passwordHash);
  await assert.rejects(
    () =>
      userService.registerUser({
        username: "arenaMaster",
        email: "master@example.com",
        password: "anotherpass",
        avatarColor: "aaaaaa",
      }),
    /Email already registered/,
  );
});

test("registerUser enforces username rules", async () => {
  const { userService } = buildService();
  await assert.rejects(() =>
    userService.registerUser({
      username: "ab",
      email: "short@example.com",
      password: "hunter2000",
      avatarColor: "111111",
    }),
  );
  await assert.rejects(() =>
    userService.registerUser({
      username: "validname",
      email: "invalid-email",
      password: "hunter2000",
      avatarColor: "111111",
    }),
  );
  await userService.registerUser({
    username: "unique",
    email: "unique@example.com",
    password: "hunter2000",
    avatarColor: "123123",
  });
  await assert.rejects(() =>
    userService.registerUser({
      username: "unique",
      email: "different@example.com",
      password: "hunter2000",
      avatarColor: "123123",
    }),
  );
});

test("registerUser rejects malformed email addresses", async () => {
  const { userService } = buildService();
  await assert.rejects(() =>
    userService.registerUser({
      username: "emailer",
      email: "not-an-email",
      password: "hunter2000",
      avatarColor: "123123",
    }),
  );
});

test("authentication fails on wrong password", async () => {
  const { userService } = buildService();
  await userService.registerUser({
    username: "player1",
    email: "player1@example.com",
    password: "hunter2000",
    avatarColor: "123456",
  });
  await assert.rejects(() => userService.authenticate("player1@example.com", "nope"));
  await assert.rejects(() => userService.authenticate("ghost@example.com", "pass"));
});

test("authentication succeeds with correct credentials", async () => {
  const { userService } = buildService();
  await userService.registerUser({
    username: "login",
    email: "login@example.com",
    password: "hunter2000",
    avatarColor: "123456",
  });
  const authenticated = await userService.authenticate("login@example.com", "hunter2000");
  assert.equal(authenticated.username, "login");
});

test("updateAvatar validates color", async () => {
  const { userService } = buildService();
  const user = await userService.registerUser({
    username: "styler",
    email: "styler@example.com",
    password: "hunter2000",
    avatarColor: "123123",
  });
  const updated = await userService.updateAvatar(user.id, "ff00ff");
  assert.equal(updated.avatarColor, "#ff00ff");
  await assert.rejects(() => userService.updateAvatar(user.id, "pink"));
  await assert.rejects(() => userService.updateAvatar("missing", "ffffff"));
});

test("leaderboard and ratings changes", async () => {
  const { userService, store } = buildService();
  const userA = createUser({
    id: "a",
    username: "A",
    email: "a@example.com",
    passwordHash: "hash",
    avatarColor: "#111111",
  });
  const userB = createUser({
    id: "b",
    username: "B",
    email: "b@example.com",
    passwordHash: "hash",
    avatarColor: "#222222",
  });
  userA.ratings.ranked = 1250;
  await store.createUser(userA);
  await store.createUser(userB);

  const board = await userService.leaderboard();
  assert.equal(board[0].username, "A");
  const bumped = await userService.applyRatingChange("b", "ranked", 30);
  assert.equal(bumped.ratings.ranked, userB.ratings.ranked + 30);
  const highScores = await userService.highScores(1, 1);
  assert.equal(highScores.length, 1);
  await assert.rejects(() => userService.applyRatingChange("missing", "ranked", 5));
});
