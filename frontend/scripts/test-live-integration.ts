/**
 * Integration check against local analytics API.
 * Run: npx tsx frontend/scripts/test-live-integration.ts
 */
import { buildFixtures, liveFixtures } from "../lib/fixtures";
import type { BracketData, GroupStandings, MatchListItem } from "../lib/api";

const ANALYTICS = process.env.ANALYTICS_URL ?? "http://localhost:8001";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${ANALYTICS}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

async function main() {
  const [matchesRes, bracket, standingsRes] = await Promise.all([
    get<{ matches: MatchListItem[] }>("/api/matches"),
    get<BracketData>("/api/bracket"),
    get<{ groups: Record<string, GroupStandings> }>("/api/standings"),
  ]);

  const fixtures = buildFixtures(matchesRes.matches, bracket, standingsRes.groups);
  const live = liveFixtures(fixtures);
  const now = new Date();

  console.log(`Fetched ${fixtures.length} fixtures at ${now.toISOString()}`);
  console.log(`Live matches now: ${live.length}`);
  for (const row of live) {
    console.log(`  LIVE: ${row.home_team} vs ${row.away_team} (${row.kickoff_utc})`);
  }

  const france = fixtures.find((f) => f.game_id === "760510");
  if (france) {
    console.log(`France vs Morocco status=${france.status} completed=${france.completed}`);
  } else {
    console.log("France vs Morocco (760510) not in fixture list");
  }

  console.log("Integration check OK");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
