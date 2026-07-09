/**
 * Quick local checks for live fixture helpers.
 * Run: npx tsx frontend/scripts/test-live-fixtures.ts
 */
import {
  FixtureRow,
  applyLiveStatus,
  formatElapsedMinute,
  isLikelyLive,
  liveFixtures,
  MATCH_DURATION_MS,
} from "../lib/fixtures";

function assert(cond: boolean, msg: string) {
  if (!cond) throw new Error(msg);
}

const baseUpcoming: FixtureRow = {
  game_id: "760510",
  date: "2026-07-09T20:00Z",
  home_team: "France",
  away_team: "Morocco",
  home_score: null,
  away_score: null,
  status: "upcoming",
  kickoff_utc: "2026-07-09T20:00Z",
  completed: false,
};

// 30 min into match
const duringMatch = new Date("2026-07-09T20:30:00Z");
assert(isLikelyLive(baseUpcoming, duringMatch), "should be live 30 min after kickoff");
assert(
  applyLiveStatus([baseUpcoming], duringMatch)[0].status === "LIVE",
  "applyLiveStatus marks LIVE"
);
assert(liveFixtures([baseUpcoming], duringMatch).length === 1, "liveFixtures returns one row");
assert(
  formatElapsedMinute("2026-07-09T20:00Z", duringMatch) === "30′",
  "elapsed minute formatting"
);

// Before kickoff
const beforeKickoff = new Date("2026-07-09T19:30:00Z");
assert(!isLikelyLive(baseUpcoming, beforeKickoff), "not live before kickoff");

// After match window (kickoff + 105 min)
const afterWindow = new Date("2026-07-09T21:46:00Z");
assert(!isLikelyLive(baseUpcoming, afterWindow), "not live after 105 min window");

// Completed row never live
const completed: FixtureRow = { ...baseUpcoming, completed: true, status: "FT", home_score: 2, away_score: 1 };
assert(!isLikelyLive(completed, duringMatch), "completed match is never live");

console.log("All live fixture helper checks passed.");
console.log(`MATCH_DURATION_MS = ${MATCH_DURATION_MS} (${MATCH_DURATION_MS / 60_000} min)`);
