import assert from "node:assert/strict";
import test from "node:test";
import { createLogger as createServerLogger, formatLog as formatServerLog } from "../src/utils/logging.js";
import { createLogger as createClientLogger, formatLog as formatClientLog } from "../public/logging.js";

test("createLogger provides fallbacks for missing methods", () => {
  const calls = [];
  const base = { log: (...args) => calls.push(["log", ...args]), info: (...args) => calls.push(["info", ...args]) };
  const logger = createServerLogger(base);

  logger.debug("debug-msg");
  logger.info("info-msg");
  logger.warn("warn-msg");
  logger.error("error-msg");

  assert.deepEqual(calls, [
    ["log", "debug-msg"],
    ["info", "info-msg"],
    ["log", "warn-msg"],
    ["log", "error-msg"],
  ]);
});

test("createLogger binds provided methods and falls back to noop when log is absent", () => {
  const customCalls = [];
  const custom = {
    debug: (...args) => customCalls.push(["debug", ...args]),
    info: (...args) => customCalls.push(["info", ...args]),
    warn: (...args) => customCalls.push(["warn", ...args]),
    error: (...args) => customCalls.push(["error", ...args]),
  };
  const withCustom = createServerLogger(custom);
  withCustom.debug("a");
  withCustom.error("b");
  assert.deepEqual(customCalls, [
    ["debug", "a"],
    ["error", "b"],
  ]);

  const noopLogger = createServerLogger({});
  assert.doesNotThrow(() => noopLogger.debug("noop"));
  assert.doesNotThrow(() => noopLogger.warn("noop"));
  const nullLogger = createServerLogger(null);
  assert.doesNotThrow(() => nullLogger.info("null-logger"));
});

test("formatLog stringifies details and handles failures", () => {
  const payload = { id: 1 };
  assert.equal(formatServerLog("Message", payload), 'Message | {"id":1}');
  assert.equal(formatServerLog("Message"), "Message");

  const circular = {};
  circular.self = circular;
  assert.equal(formatServerLog("Circular", circular), "Circular");
});

test("client logger mirrors server utilities", () => {
  const logger = createClientLogger({ log: () => {} });
  assert.equal(typeof logger.info, "function");
  assert.equal(typeof logger.error, "function");
  assert.equal(formatClientLog("Client", { ok: true }), 'Client | {"ok":true}');
  assert.equal(formatClientLog("Client"), "Client");
  const circular = {};
  circular.self = circular;
  assert.equal(formatClientLog("Circular", circular), "Circular");

  const noop = createClientLogger({});
  assert.doesNotThrow(() => noop.warn("noop-client"));
  const nullLogger = createClientLogger(null);
  assert.doesNotThrow(() => nullLogger.debug("null-client"));
});
