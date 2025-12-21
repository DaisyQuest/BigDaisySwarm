const WIN_REWARDS = [
  { threshold: 1, unlocks: { rock: ["basalt"] } },
  { threshold: 5, unlocks: { paper: ["carbon-fiber"] } },
  { threshold: 10, unlocks: { scissors: ["titanium"] } },
];

const FLAWLESS_REWARD = { rock: ["crystal"], paper: ["satin"], scissors: ["plasma"] };

export class UnlockableService {
  constructor(store) {
    this.store = store;
  }

  async recordResult(userId, { didWin, flawless }) {
    const user = await this.store.updateUser(userId, (current) => {
      const updated = { ...current };
      if (didWin) {
        updated.achievements.wins += 1;
        updated.achievements.streak += 1;
      } else {
        updated.achievements.streak = 0;
      }
      if (flawless) {
        updated.achievements.flawless += 1;
      }
      return updated;
    });

    const unlocks = {};
    if (user) {
      for (const reward of WIN_REWARDS) {
        if (user.achievements.wins === reward.threshold) {
          Object.assign(unlocks, reward.unlocks);
        }
      }
      if (flawless) {
        Object.assign(unlocks, FLAWLESS_REWARD);
      }
    }

    if (Object.keys(unlocks).length) {
      await this.store.addUnlockables(userId, unlocks);
    }

    return unlocks;
  }
}
