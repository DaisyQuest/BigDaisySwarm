import { createLogger, formatLog } from "./logging.js";

export class MatchmakingPoller {
  constructor({
    request,
    intervalMs = 2000,
    onMatched,
    onQueued,
    onError,
    scheduler = setInterval,
    canceller = clearInterval,
    logger = console,
  } = {}) {
    if (typeof request !== "function") {
      throw new Error("A request function is required for matchmaking polling");
    }
    this.request = request;
    this.intervalMs = intervalMs;
    this.onMatched = onMatched;
    this.onQueued = onQueued;
    this.onError = onError;
    this.scheduler = scheduler;
    this.canceller = canceller;
    this.logger = createLogger(logger);
    this.timer = null;
    this.inFlight = false;
  }

  stop() {
    if (this.timer) {
      this.logger.debug(formatLog("Stopping matchmaking poller", { timer: this.timer }));
      this.canceller(this.timer);
      this.timer = null;
    }
  }

  async tick() {
    if (this.inFlight) {
      this.logger.debug("Skipping tick because a request is in flight");
      return null;
    }
    this.inFlight = true;
    try {
      const status = await this.request();
      if (status?.status === "matched") {
        this.stop();
        if (this.onMatched) {
          this.onMatched(status.match, status);
        }
        this.logger.info(formatLog("Match found", { matchId: status.match?.id }));
        this.inFlight = false;
        return status;
      }
      if (status?.status === "queued") {
        if (this.onQueued) {
          this.onQueued(status);
        }
        this.logger.debug("Still queued for matchmaking");
        this.inFlight = false;
        return status;
      }
      const error = new Error("Unexpected matchmaking response");
      this.stop();
      if (this.onError) {
        this.onError(error);
        this.logger.warn(formatLog("Unexpected matchmaking payload", status));
        this.inFlight = false;
        return status;
      }
      this.inFlight = false;
      throw error;
    } catch (error) {
      this.stop();
      if (this.onError) {
        this.onError(error);
        this.logger.error(formatLog("Matchmaking poll failed", { error: error.message }));
        this.inFlight = false;
        return null;
      }
      this.inFlight = false;
      throw error;
    }
  }

  start() {
    if (this.timer) {
      this.logger.debug("Matchmaking poller already running");
      return this.inFlight ? null : Promise.resolve();
    }
    const runner = () => this.tick();
    this.timer = this.scheduler(runner, this.intervalMs);
    this.logger.info(formatLog("Starting matchmaking poller", { intervalMs: this.intervalMs }));
    return this.tick();
  }
}
