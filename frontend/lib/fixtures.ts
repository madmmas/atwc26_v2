import { BracketData, BracketSlot, GroupStandings, MatchListItem } from "@/lib/api";
import { buildTeamGroupMap } from "./matchStages";

export type FixtureRow = {
  game_id: string;
  date: string;
  home_team: string;
  away_team: string;
  home_flag?: string | null;
  away_flag?: string | null;
  home_score: number | null;
  away_score: number | null;
  home_shootout_score?: number | null;
  away_shootout_score?: number | null;
  status: "FT" | "LIVE" | "upcoming";
  kickoff_utc?: string;
  group?: string;
  completed: boolean;
};

type ScoreFields = Pick<
  FixtureRow,
  "home_score" | "away_score" | "home_shootout_score" | "away_shootout_score"
>;

export function hasShootout(row: ScoreFields): boolean {
  return row.home_shootout_score != null && row.away_shootout_score != null;
}

export function resolveWinner(row: ScoreFields): "home" | "away" | null {
  const hs = row.home_score ?? 0;
  const as = row.away_score ?? 0;
  if (hs > as) return "home";
  if (as > hs) return "away";
  if (hasShootout(row)) {
    if (row.home_shootout_score! > row.away_shootout_score!) return "home";
    if (row.away_shootout_score! > row.home_shootout_score!) return "away";
  }
  return null;
}

export function formatMatchScore(
  row: ScoreFields & Pick<FixtureRow, "completed">
): string {
  if (!row.completed) return "vs";
  const base = `${row.home_score ?? 0}–${row.away_score ?? 0}`;
  if (hasShootout(row)) {
    return `${base} (${row.home_shootout_score}–${row.away_shootout_score})`;
  }
  return base;
}

function slotTeam(slot: BracketSlot): string | null {
  if (slot.type === "team") return slot.team_name;
  return null;
}

export function upcomingFromBracket(bracket: BracketData): FixtureRow[] {
  const rows: FixtureRow[] = [];
  for (const round of bracket.rounds) {
    for (const m of round.matches) {
      if (m.completed) continue;
      const home = slotTeam(m.slot_a);
      const away = slotTeam(m.slot_b);
      if (!home || !away) continue;
      rows.push({
        game_id: m.game_id,
        date: m.kickoff_utc,
        home_team: home,
        away_team: away,
        home_score: null,
        away_score: null,
        status: "upcoming",
        kickoff_utc: m.kickoff_utc,
        completed: false,
      });
    }
  }
  return rows.sort((a, b) => (a.kickoff_utc ?? "").localeCompare(b.kickoff_utc ?? ""));
}

export function playedToFixture(m: MatchListItem, group?: string): FixtureRow {
  return {
    game_id: m.game_id,
    date: m.date,
    home_team: m.home_team,
    away_team: m.away_team,
    home_flag: m.home_flag,
    away_flag: m.away_flag,
    home_score: m.home_score,
    away_score: m.away_score,
    home_shootout_score: m.home_shootout_score,
    away_shootout_score: m.away_shootout_score,
    status: "FT",
    group,
    completed: true,
  };
}

export function groupForMatch(
  home: string,
  away: string,
  teamGroups: Map<string, string>
): string | undefined {
  const hg = teamGroups.get(home);
  const ag = teamGroups.get(away);
  return hg && ag && hg === ag ? `Group ${hg}` : undefined;
}

export function buildFixtures(
  matches: MatchListItem[],
  bracket: BracketData | null,
  groups: Record<string, GroupStandings> | null
): FixtureRow[] {
  const teamGroups = groups ? buildTeamGroupMap(groups) : new Map();
  const played = matches.map((m) =>
    playedToFixture(m, groupForMatch(m.home_team, m.away_team, teamGroups))
  );
  const upcoming = bracket ? upcomingFromBracket(bracket) : [];
  return [...played, ...upcoming];
}

export function isWithin24h(kickoffUtc: string): boolean {
  const kickoff = new Date(kickoffUtc).getTime();
  const now = Date.now();
  const diff = kickoff - now;
  return diff > 0 && diff <= 24 * 60 * 60 * 1000;
}

export function formatKickoff(kickoffUtc: string): string {
  try {
    return new Date(kickoffUtc).toLocaleTimeString(undefined, {
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return kickoffUtc;
  }
}
