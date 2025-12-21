import { strict as assert } from "node:assert";
import test from "node:test";
import { DEFAULT_UNLOCKS } from "../src/constants.js";
import { InMemoryStore } from "../src/data/inMemoryStore.js";
import { createUser } from "../src/data/modelFactories.js";

test("InMemoryStore supports lookups, news, and unlock merges", async () => {
  const store = new InMemoryStore();
  const baseUser = createUser({
    id: "user-1",
    username: "storetest",
    email: "store@example.com",
    passwordHash: "hash",
    avatarColor: "#000000",
  });
  await store.createUser(baseUser);
  const foundByName = await store.findUserByUsername("storetest");
  assert.equal(foundByName.email, "store@example.com");
  await assert.rejects(() => store.createUser(baseUser));

  const newsItem = await store.addNews({ id: "breaking", title: "Test" });
  const allNews = await store.listNews();
  assert.ok(allNews.some((n) => n.id === newsItem.id));

  const unlocked = await store.addUnlockables("user-1", { rock: ["diamond"] });
  assert.ok(unlocked.unlocks.rock.includes("diamond"));
  assert.ok(unlocked.unlocks.paper.includes(DEFAULT_UNLOCKS.paper[0]));
  const unchanged = await store.addUnlockables("user-1", {});
  assert.deepEqual(unchanged.unlocks.rock.includes("diamond"), true);
  await store.updateUser("user-1", (user) => {
    delete user.unlocks;
    return user;
  });
  const rebuilt = await store.addUnlockables("user-1", { paper: ["foil"] });
  assert.ok(rebuilt.unlocks.paper.includes("foil"));
});
