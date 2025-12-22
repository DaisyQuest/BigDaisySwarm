import { randomUUID } from "crypto";
import { MODES, VARIANTS } from "../constants.js";
import { createUser } from "../data/modelFactories.js";
import { eloDelta, scoreClassicMatch, scoreExtremeMatch } from "../game/rpsLogic.js";
import { validateMode, validateMoveSequence, validateVariant } from "../utils/validation.js";
import { hashPassword } from "../utils/crypto.js";

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

export class MatchService {
  constructor(store, userService, unlockableService) {
    this.store = store;
    this.userService = userService;
    this.unlockableService = unlockableService;
    this.botId = "arena-bot";
    this.queues = {
      [MODES.CLASSIC]: { [VARIANTS.RANKED]: [], [VARIANTS.CASUAL]: [] },
      [MODES.EXTREME]: { [VARIANTS.RANKED]: [], [VARIANTS.CASUAL]: [] },
    };
    this.activeMatches = new Map();
  }

  findActiveMatchByPlayer(playerId) {
    for (const record of this.activeMatches.values()) {
      if (record.match.players.includes(playerId)) {
        return record;
      }
    }
    return null;
  }

  async loadMatchPlayers(playerIds) {
    const profiles = [];
    for (const id of playerIds) {
      const player = await this.store.findUserById(id);
      if (!player) {
        throw new Error("Players must exist before matchmaking");
      }
      profiles.push(this.userService.sanitize(player));
    }
    return profiles;
  }

  async ensureBotUser() {
    const existing = await this.store.findUserById(this.botId);
    if (existing) {
      return existing;
    }
    const bot = createUser({
      id: this.botId,
      username: "ArenaBot",
      email: "arena-bot@rps.arena",
      passwordHash: hashPassword("bot-credential"),
      avatarColor: "#444444",
    });
    await this.store.createUser(bot);
    return bot;
  }

  async enqueue(playerId, { mode, variant, roundCount = 3 }) {
    validateMode(mode);
    validateVariant(variant);
    if (roundCount < 1) {
      throw new Error("Round count must be at least 1");
    }

    const activeMatch = this.findActiveMatchByPlayer(playerId);
    if (activeMatch) {
      return { status: "matched", match: clone(activeMatch.match) };
    }

    if (this.isPlayerQueued(playerId)) {
      return { status: "queued" };
    }

    const queue = this.queues[mode][variant];
    const existing = queue[0];
    if (existing && existing.playerId !== playerId) {
      const opponent = queue.shift();
      try {
        const resolvedRoundCount = opponent.roundCount;
        return await this.createMatch(opponent.playerId, playerId, {
          mode,
          variant,
          roundCount: resolvedRoundCount,
        });
      } catch (error) {
        queue.unshift(opponent);
        throw error;
      }
    }

    queue.push({ playerId, roundCount, requestedAt: Date.now() });
    return { status: "queued" };
  }

  async playBot(playerId, { mode, variant, roundCount = 3 }) {
    validateMode(mode);
    validateVariant(variant);
    if (roundCount < 1) {
      throw new Error("Round count must be at least 1");
    }

    const activeMatch = this.findActiveMatchByPlayer(playerId);
    if (activeMatch) {
      return { status: "matched", match: clone(activeMatch.match) };
    }

    await this.ensureBotUser();
    return this.createMatch(playerId, this.botId, { mode, variant, roundCount });
  }

  isPlayerQueued(playerId) {
    return Object.values(this.queues).some((byVariant) =>
      Object.values(byVariant).some((entries) => entries.some((entry) => entry.playerId === playerId)),
    );
  }

  async createMatch(playerA, playerB, { mode, variant, roundCount = 3 }) {
    const playerProfiles = await this.loadMatchPlayers([playerA, playerB]);
    const match = {
      id: randomUUID(),
      mode,
      variant,
      roundCount,
      players: [playerA, playerB],
      playerProfiles,
      createdAt: new Date().toISOString(),
      state: "awaiting-submissions",
      rounds: [],
      winner: null,
    };
    this.activeMatches.set(match.id, { match, submissions: {} });
    return { status: "matched", match: clone(match) };
  }

  async submitMoves(matchId, userId, payload) {
    const record = this.activeMatches.get(matchId);
    if (!record) {
      throw new Error("Match not found or already completed");
    }

    const { match, submissions } = record;
    if (!match.players.includes(userId)) {
      throw new Error("Player is not part of this match");
    }

    if (match.state === "completed") {
      throw new Error("Match already completed");
    }

    const normalized = this.normalizeSubmission(match.mode, payload);
    submissions[userId] = normalized;

    if (Object.keys(submissions).length < 2) {
      return { status: "waiting" };
    }

    const result = await this.resolveMatch(record);
    this.activeMatches.delete(match.id);
    return { status: "completed", result };
  }

  normalizeSubmission(mode, payload) {
    if (mode === MODES.CLASSIC) {
      validateMoveSequence(payload.rounds);
      return { rounds: [...payload.rounds] };
    }
    if (mode === MODES.EXTREME) {
      validateMoveSequence(payload.sequence);
      return { sequence: [...payload.sequence] };
    }
    throw new Error("Unsupported mode");
  }

  determineFlawless(roundResults, winningPlayerIndex) {
    if (winningPlayerIndex === null) return false;
    return roundResults.every((round) => (winningPlayerIndex === 0 ? round.outcome >= 0 : round.outcome <= 0));
  }

  async resolveMatch(record) {
    const { match, submissions } = record;
    const [playerA, playerB] = match.players;
    const submissionA = submissions[playerA];
    const submissionB = submissions[playerB];

    let score;
    if (match.mode === MODES.CLASSIC) {
      if (submissionA.rounds.length !== submissionB.rounds.length) {
        throw new Error("Players must submit the same number of rounds");
      }
      const rounds = submissionA.rounds.map((move, idx) => ({ a: move, b: submissionB.rounds[idx] }));
      score = scoreClassicMatch(rounds);
    } else {
      score = scoreExtremeMatch(submissionA.sequence, submissionB.sequence);
    }

    match.rounds = score.roundResults;
    match.winner = score.winner ? (score.winner === "playerA" ? playerA : playerB) : null;
    match.state = "completed";
    match.completedAt = new Date().toISOString();

    const playerAData = await this.store.findUserById(playerA);
    const playerBData = await this.store.findUserById(playerB);
    if (!playerAData || !playerBData) {
      throw new Error("Players must exist before resolving matches");
    }

    const winnerScore = score.winner === "playerA" ? 1 : score.winner === "playerB" ? 0 : 0.5;
    const ratingDeltaA =
      match.variant === VARIANTS.RANKED
        ? eloDelta(playerAData.ratings[match.variant], playerBData.ratings[match.variant], winnerScore)
        : 0;
    const ratingDeltaB = match.variant === VARIANTS.RANKED ? -ratingDeltaA : 0;

    const ratingChanges = {};
    if (match.variant === VARIANTS.RANKED) {
      await this.userService.applyRatingChange(playerA, match.variant, ratingDeltaA);
      await this.userService.applyRatingChange(playerB, match.variant, ratingDeltaB);
      ratingChanges[playerA] = ratingDeltaA;
      ratingChanges[playerB] = ratingDeltaB;
    }

    const winningIndex = score.winner === "playerA" ? 0 : score.winner === "playerB" ? 1 : null;
    const flawless = this.determineFlawless(score.roundResults, winningIndex);

    const unlockPromises = [
      this.unlockableService.recordResult(playerA, { didWin: score.winner === "playerA", flawless }),
      this.unlockableService.recordResult(playerB, { didWin: score.winner === "playerB", flawless }),
    ];
    const unlocks = await Promise.all(unlockPromises);

    await Promise.all([
      this.userService.recordLastMatch(playerA, match.id),
      this.userService.recordLastMatch(playerB, match.id),
    ]);

    await this.store.recordMatch({ ...clone(match), ratingChanges });

    return {
      ...clone(match),
      ratingChanges,
      unlocks: { [playerA]: unlocks[0], [playerB]: unlocks[1] },
    };
  }

  async history(playerId, rankedOnly = false) {
    return this.store.listMatches({ playerId, rankedOnly });
  }
}
