export class MatchmakingPoller {
  constructor({
    request,
    intervalMs = 2000,
    onMatched,
    onQueued,
    onError,
    scheduler = setInterval,
    canceller = clearInterval,
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
    this.timer = null;
    this.inFlight = false;
  }

  stop() {
    if (this.timer) {
      this.canceller(this.timer);
      this.timer = null;
    }
  }

  async tick() {
    if (this.inFlight) {
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
      } else if (status?.status === "queued") {
        if (this.onQueued) {
          this.onQueued(status);
        }
      } else {
        const error = new Error("Unexpected matchmaking response");
        this.stop();
        if (this.onError) {
          this.onError(error);
        } else {
          throw error;
        }
      }
      return status;
    } catch (error) {
      this.stop();
      if (this.onError) {
        this.onError(error);
      } else {
        throw error;
      }
      return null;
    } finally {
      this.inFlight = false;
    }
  }

  start() {
    if (this.timer) {
      return this.inFlight ? null : Promise.resolve();
    }
    const runner = () => this.tick();
    this.timer = this.scheduler(runner, this.intervalMs);
    return this.tick();
  }
}

