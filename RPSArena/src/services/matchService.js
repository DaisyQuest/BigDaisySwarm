import { randomUUID } from "crypto";
import { MODES, VARIANTS } from "../constants.js";
import { eloDelta, scoreClassicMatch, scoreExtremeMatch } from "../game/rpsLogic.js";
import { validateMode, validateMoveSequence, validateVariant } from "../utils/validation.js";

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

export class MatchService {
  constructor(store, userService, unlockableService) {
    this.store = store;
    this.userService = userService;
    this.unlockableService = unlockableService;
    this.queues = {
      [MODES.CLASSIC]: { [VARIANTS.RANKED]: [], [VARIANTS.CASUAL]: [] },
      [MODES.EXTREME]: { [VARIANTS.RANKED]: [], [VARIANTS.CASUAL]: [] },
    };
    this.activeMatches = new Map();
  }

  enqueue(playerId, { mode, variant, roundCount = 3 }) {
    validateMode(mode);
    validateVariant(variant);
    if (roundCount < 1) {
      throw new Error("Round count must be at least 1");
    }

    if (this.isPlayerQueued(playerId)) {
      throw new Error("Player already queued");
    }

    const queue = this.queues[mode][variant];
    const existing = queue.shift();
    if (existing && existing.playerId !== playerId) {
      return this.createMatch(existing.playerId, playerId, { mode, variant, roundCount });
    }

    queue.push({ playerId, roundCount, requestedAt: Date.now() });
    return { status: "queued" };
  }

  isPlayerQueued(playerId) {
    return Object.values(this.queues).some((byVariant) =>
      Object.values(byVariant).some((entries) => entries.some((entry) => entry.playerId === playerId)),
    );
  }

  createMatch(playerA, playerB, { mode, variant, roundCount }) {
    const match = {
      id: randomUUID(),
      mode,
      variant,
      roundCount,
      players: [playerA, playerB],
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
