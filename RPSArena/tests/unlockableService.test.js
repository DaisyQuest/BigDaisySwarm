import { strict as assert } from "node:assert";
import test from "node:test";
import { InMemoryStore } from "../src/data/inMemoryStore.js";
import { createUser } from "../src/data/modelFactories.js";
import { UnlockableService } from "../src/services/unlockableService.js";

function setup() {
  const store = new InMemoryStore();
  const user = createUser({
    id: "winner",
    username: "Winner",
    email: "win@example.com",
    passwordHash: "hash",
    avatarColor: "#ffffff",
  });
  store.createUser(user);
  const service = new UnlockableService(store);
  return { store, service };
}

test("unlockable rewards trigger on thresholds", async () => {
  const { service, store } = setup();
  await service.recordResult("winner", { didWin: true, flawless: false });
  let updated = await store.findUserById("winner");
  assert.equal(updated.achievements.wins, 1);
  await service.recordResult("winner", { didWin: true, flawless: true });
  updated = await store.findUserById("winner");
  assert.ok(updated.unlocks.rock.includes("basalt"));
  assert.ok(updated.unlocks.rock.includes("crystal"));
});
