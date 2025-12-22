import { strict as assert } from "node:assert";
import test from "node:test";
import { MatchmakingPoller } from "../public/matchPolling.js";

function createStubLogger() {
  const calls = [];
  const record = (level) => (...args) => calls.push([level, ...args]);
  const logger = {
    debug: record("debug"),
    info: record("info"),
    warn: record("warn"),
    error: record("error"),
  };
  logger.calls = calls;
  return logger;
}

test("MatchmakingPoller polls queued responses until a match is found", async () => {
  const scheduled = [];
  const cancelled = [];
  const events = [];
  const logger = createStubLogger();
  const scheduler = (fn) => {
    scheduled.push(fn);
    return "timer-1";
  };
  const canceller = (id) => cancelled.push(id);
  const responses = [{ status: "queued" }, { status: "matched", match: { id: "m-1" } }];

  const poller = new MatchmakingPoller({
    request: async () => responses.shift(),
    scheduler,
    canceller,
    intervalMs: 5,
    onQueued: () => events.push("queued"),
    onMatched: (match) => events.push(`matched:${match.id}`),
    logger,
  });

  await poller.start();
  assert.deepEqual(events, ["queued"]);

  await scheduled[0]();
  assert.deepEqual(events, ["queued", "matched:m-1"]);
  assert.deepEqual(cancelled, ["timer-1"]);
  assert.ok(logger.calls.some((call) => call[0] === "info" && call[1].includes("Starting matchmaking poller")));
  assert.ok(logger.calls.some((call) => call[0] === "info" && call[1].includes("Match found")));
});

test("MatchmakingPoller reports errors and stops polling", async () => {
  const scheduled = [];
  const errors = [];
  const cancelled = [];
  const logger = createStubLogger();
  const poller = new MatchmakingPoller({
    request: async () => {
      throw new Error("offline");
    },
    scheduler: (fn) => {
      scheduled.push(fn);
      return "timer-err";
    },
    canceller: (id) => cancelled.push(id),
    onError: (error) => errors.push(error.message),
    logger,
  });

  await poller.start();
  assert.equal(errors[0], "offline");
  assert.deepEqual(cancelled, ["timer-err"]);
  assert.equal(typeof scheduled[0], "function");
  assert.ok(logger.calls.some((call) => call[0] === "error" && call[1].includes("Matchmaking poll failed")));
});

test("MatchmakingPoller surfaces unexpected responses when no error handler is provided", async () => {
  const cancelled = [];
  const poller = new MatchmakingPoller({
    request: async () => ({ status: "waiting" }),
    scheduler: (fn) => {
      fn.__scheduled = true; // marker for coverage
      return "timer-weird";
    },
    canceller: (id) => cancelled.push(id),
  });

  await assert.rejects(() => poller.start(), /Unexpected matchmaking response/);
  assert.deepEqual(cancelled, ["timer-weird"]);
});

test("MatchmakingPoller warns on unexpected responses when an error handler is provided", async () => {
  const cancelled = [];
  const errors = [];
  const logger = createStubLogger();
  const poller = new MatchmakingPoller({
    request: async () => ({ status: "waiting" }),
    scheduler: (fn) => {
      fn.__scheduled = true;
      return "timer-weird-handler";
    },
    canceller: (id) => cancelled.push(id),
    onError: (error) => errors.push(error.message),
    logger,
  });

  const status = await poller.start();
  assert.equal(status.status, "waiting");
  assert.deepEqual(cancelled, ["timer-weird-handler"]);
  assert.ok(errors.some((msg) => msg.includes("Unexpected matchmaking response")));
  assert.ok(logger.calls.some((call) => call[0] === "warn"));
});

test("MatchmakingPoller treats missing payloads as errors", async () => {
  const errors = [];
  const cancelled = [];
  const logger = createStubLogger();
  const poller = new MatchmakingPoller({
    request: async () => undefined,
    scheduler: (fn) => {
      fn.__scheduled = true;
      return "timer-missing";
    },
    canceller: (id) => cancelled.push(id),
    onError: (error) => errors.push(error.message),
    logger,
  });

  const status = await poller.start();
  assert.equal(status, undefined);
  assert.ok(errors.some((msg) => msg.includes("Unexpected matchmaking response")));
  assert.deepEqual(cancelled, ["timer-missing"]);
});

test("MatchmakingPoller prevents overlapping ticks and ignores duplicate starts", async () => {
  let resolveFirst;
  const firstResponse = new Promise((resolve) => {
    resolveFirst = resolve;
  });
  const scheduled = [];
  let requests = 0;

  const poller = new MatchmakingPoller({
    request: () => {
      requests += 1;
      if (requests === 1) {
        return firstResponse;
      }
      return Promise.resolve({ status: "matched", match: { id: "later" } });
    },
    scheduler: (fn) => {
      scheduled.push(fn);
      return "timer-overlap";
    },
    canceller: () => {},
    onQueued: () => {},
    logger: createStubLogger(),
  });

  const initial = poller.start();
  const duplicateStart = poller.start();
  assert.equal(duplicateStart, null);

  resolveFirst({ status: "queued" });
  await initial;

  const redundantStart = await poller.start();
  assert.equal(redundantStart, undefined);
  assert.equal(requests, 1);

  await scheduled[0]();
  assert.equal(requests, 2);
});

test("MatchmakingPoller rethrows request errors when no handler is supplied", async () => {
  const cancelled = [];
  const logger = createStubLogger();
  const poller = new MatchmakingPoller({
    request: async () => {
      throw new Error("boom");
    },
    scheduler: (fn) => {
      fn.__scheduled = true;
      return "timer-throw";
    },
    canceller: (id) => cancelled.push(id),
    logger,
  });

  await assert.rejects(() => poller.start(), /boom/);
  assert.deepEqual(cancelled, ["timer-throw"]);
  assert.ok(logger.calls.some((call) => call[0] === "info" && call[1].includes("Starting matchmaking poller")));
});

test("MatchmakingPoller requires a request function", () => {
  assert.throws(() => new MatchmakingPoller(), /request function/i);
});

test("MatchmakingPoller skips ticks when already in flight and logs stoppage", async () => {
  const logger = createStubLogger();
  const poller = new MatchmakingPoller({
    request: async () => ({ status: "queued" }),
    scheduler: (fn) => {
      fn();
      return "timer-skip";
    },
    canceller: () => {},
    logger,
  });

  poller.stop();
  poller.inFlight = true;
  const skipped = await poller.tick();
  assert.equal(skipped, null);
  poller.inFlight = false;
  await poller.start();
  poller.stop();
  assert.ok(logger.calls.some((call) => call[1] === "Skipping tick because a request is in flight"));
  assert.ok(logger.calls.some((call) => call[1].includes("Stopping matchmaking poller")));
});
