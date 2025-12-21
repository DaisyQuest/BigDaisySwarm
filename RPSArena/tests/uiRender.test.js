import { strict as assert } from "node:assert";
import test from "node:test";
import { escapeHtml, renderHighscores, renderLeaderboard, renderMatchHistory, renderNews, statusMessage } from "../public/viewUtils.js";

test("escapeHtml prevents HTML injection", () => {
  assert.equal(escapeHtml('<script>alert("x")</script>'), "&lt;script&gt;alert(\"x\")&lt;/script&gt;");
  assert.equal(escapeHtml(undefined), "");
});

test("renderNews handles content and empty state", () => {
  const rendered = renderNews([{ title: "Patch", body: "Balance changes" }, { body: "System maintenance" }, {}]);
  assert.match(rendered, /Patch/);
  assert.match(rendered, /Balance changes/);
  assert.match(rendered, /pill muted/);
  assert.match(rendered, /Arena update/);
  assert.match(rendered, /Stay tuned/);

  const empty = renderNews([]);
  assert.match(empty, /Nothing new yet/);
});

test("renderLeaderboard displays ranking, fallbacks, and trends", () => {
  const leaderboard = renderLeaderboard(
    [
      { username: "Champ", ratings: { ranked: 1500 }, trend: "up" },
      { username: "Rival", ratings: { ranked: 1400 }, trend: "down" },
      { trend: "flat" },
    ],
    5,
  );

  assert.match(leaderboard, /#6/);
  assert.match(leaderboard, /#7/);
  assert.match(leaderboard, /#8/);
  assert.match(leaderboard, /Champ/);
  assert.match(leaderboard, /▲/);
  assert.match(leaderboard, /▼/);
  assert.match(leaderboard, /➖/);
  assert.match(leaderboard, /Unrated/);

  const empty = renderLeaderboard([], 0);
  assert.match(empty, /No ranked contenders/);
});

test("renderHighscores honors paging and fallbacks", () => {
  const highscores = renderHighscores(
    [{ username: "Peak", ratings: { ranked: 1800 } }, { username: "Mystery" }, {}],
    2,
    25,
  );
  assert.match(highscores, /#26/);
  assert.match(highscores, /Peak/);
  assert.match(highscores, /#27/);
  assert.match(highscores, /#28/);
  assert.match(highscores, /Player/);
  assert.match(highscores, /Unrated/);

  const fallback = renderHighscores(null, 1, 10);
  assert.match(fallback, /No highscores yet/);
});

test("renderMatchHistory includes mode, variant, and draw handling", () => {
  const history = renderMatchHistory([
    { mode: "extreme", variant: "ranked", rounds: [{}, {}], winner: "alice" },
    { mode: "classic", variant: "casual", rounds: [], winner: null },
    { rounds: "not-an-array" },
  ]);

  assert.match(history, /EXTREME/);
  assert.match(history, /ranked queue/);
  assert.match(history, /2 rounds/);
  assert.match(history, /Winner: alice/);
  assert.match(history, /Winner: Draw/);
  assert.match(history, /CLASSIC/);
  assert.match(history, /0 rounds/);

  const none = renderMatchHistory([]);
  assert.match(none, /No recent matches/);
});

test("statusMessage emits tone-aware markup", () => {
  assert.match(statusMessage("Saved", "success"), /feedback success/);
  assert.match(statusMessage("Oops", "error"), /feedback error/);
  assert.match(statusMessage("Default"), /feedback success/);
  assert.match(statusMessage(""), /feedback success/);
});
