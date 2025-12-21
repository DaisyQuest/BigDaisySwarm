import { MOVES } from "../constants.js";

export function validateMove(move) {
  if (!MOVES.includes(move)) {
    throw new Error(`Invalid move: ${move}`);
  }
}

export function roundOutcome(moveA, moveB) {
  validateMove(moveA);
  validateMove(moveB);

  if (moveA === moveB) return 0;
  const wins = {
    rock: "scissors",
    paper: "rock",
    scissors: "paper",
  };
  return wins[moveA] === moveB ? 1 : -1;
}

export function scoreClassicMatch(rounds) {
  if (!Array.isArray(rounds) || rounds.length === 0) {
    throw new Error("At least one round is required");
  }

  let score = 0;
  const roundResults = rounds.map(({ a, b }, idx) => {
    const outcome = roundOutcome(a, b);
    score += outcome;
    return { round: idx + 1, moveA: a, moveB: b, outcome };
  });

  const winner = score === 0 ? null : score > 0 ? "playerA" : "playerB";
  return { winner, roundResults, score };
}

export function scoreExtremeMatch(sequenceA, sequenceB) {
  if (!Array.isArray(sequenceA) || !Array.isArray(sequenceB)) {
    throw new Error("Move sequences are required");
  }
  if (sequenceA.length !== sequenceB.length) {
    throw new Error("Extreme mode requires equal sequence lengths");
  }
  if (sequenceA.length === 0) {
    throw new Error("At least one move is required");
  }

  const rounds = sequenceA.map((moveA, idx) => ({ a: moveA, b: sequenceB[idx] }));
  return scoreClassicMatch(rounds);
}

export function eloDelta(playerRating, opponentRating, result, kFactor = 32) {
  const expected = 1 / (1 + 10 ** ((opponentRating - playerRating) / 400));
  return Math.round(kFactor * (result - expected));
}
