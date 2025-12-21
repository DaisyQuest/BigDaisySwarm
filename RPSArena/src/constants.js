export const MODES = {
  CLASSIC: "classic",
  EXTREME: "extreme",
};

export const VARIANTS = {
  RANKED: "ranked",
  CASUAL: "casual",
};

export const MOVES = ["rock", "paper", "scissors"];

export const DEFAULT_RATING = 1200;

export const DEFAULT_UNLOCKS = {
  rock: ["granite", "marble"],
  paper: ["linen", "glossy"],
  scissors: ["steel", "obsidian"],
};

export const NEWS_BULLETINS = [
  {
    id: "launch",
    title: "RPS Arena bootstrapped",
    body: "Get ready for lightning-fast classic and extreme matches with unlockable throws!",
    category: "announcement",
  },
  {
    id: "elo-tuning",
    title: "ELO tuned for competitive balance",
    body: "Ranked queues now keep your rating climbs steady and fair.",
    category: "balance",
  },
];
