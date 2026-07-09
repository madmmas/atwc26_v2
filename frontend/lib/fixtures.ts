import {
  BracketData,
  BracketMatch,
  BracketPrediction,
  BracketSlot,
  GroupStandings,
  MatchListItem,
} from "@/lib/api";
import { buildTeamGroupMap } from "./matchStages";

export type FixturePrediction = {
  home_win_prob: number;
  draw_prob?: number;
  away_win_prob: number;
  predicted_winner?: string | null;
};

/** Expected match length — matches ETL schedule_triggers default (105 min). */
export const MATCH_DURATION_MS = 105 * 60 * 1000;

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
  prediction?: FixturePrediction;
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

function upcomingTeams(m: BracketMatch): { home: string; away: string } | null {
  const home = slotTeam(m.slot_a) ?? m.prediction?.team_a_name ?? null;
  const away = slotTeam(m.slot_b) ?? m.prediction?.team_b_name ?? null;
  if (!home || !away) return null;
  return { home, away };
}

export function bracketPredictionToFixture(
  prediction: BracketPrediction,
  home: string,
  away: string
): FixturePrediction | undefined {
  if (!prediction.predicted_winner || prediction.win_probability == null) return undefined;
  const winProb = prediction.win_probability;
  if (prediction.predicted_winner === home) {
    return {
      home_win_prob: winProb,
      away_win_prob: 1 - winProb,
      predicted_winner: home,
    };
  }
  if (prediction.predicted_winner === away) {
    return {
      home_win_prob: 1 - winProb,
      away_win_prob: winProb,
      predicted_winner: away,
    };
  }
  return undefined;
}

export function upcomingFromBracket(bracket: BracketData): FixtureRow[] {
  const rows: FixtureRow[] = [];
  for (const round of bracket.rounds) {
    for (const m of round.matches) {
      if (m.completed) continue;
      const teams = upcomingTeams(m);
      if (!teams) continue;
      const { home, away } = teams;
      rows.push({
        game_id: m.game_id,
        date: m.kickoff_utc,
        home_team: home,
        away_team: away,
        home_flag: m.prediction?.team_a_flag ?? null,
        away_flag: m.prediction?.team_b_flag ?? null,
        home_score: null,
        away_score: null,
        status: "upcoming",
        kickoff_utc: m.kickoff_utc,
        completed: false,
        prediction: m.prediction
          ? bracketPredictionToFixture(m.prediction, home, away)
          : undefined,
      });
    }
  }
  return rows.sort((a, b) => (a.kickoff_utc ?? "").localeCompare(b.kickoff_utc ?? ""));
}

export function upcomingFromStandings(
  groups: Record<string, GroupStandings>
): FixtureRow[] {
  const rows: FixtureRow[] = [];
  for (const [letter, group] of Object.entries(groups)) {
    for (const m of group.remaining_matches) {
      rows.push({
        game_id: m.game_id,
        date: m.kickoff_utc,
        home_team: m.home_team,
        away_team: m.away_team,
        home_score: null,
        away_score: null,
        status: "upcoming",
        kickoff_utc: m.kickoff_utc,
        group: `Group ${letter}`,
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
  const playedIds = new Set(played.map((m) => m.game_id));
  const upcomingById = new Map<string, FixtureRow>();
  if (groups) {
    for (const row of upcomingFromStandings(groups)) {
      if (!playedIds.has(row.game_id)) upcomingById.set(row.game_id, row);
    }
  }
  if (bracket) {
    for (const row of upcomingFromBracket(bracket)) {
      if (!playedIds.has(row.game_id)) upcomingById.set(row.game_id, row);
    }
  }
  return applyLiveStatus([...played, ...upcomingById.values()]);
}

export function isLikelyLive(row: FixtureRow, reference = new Date()): boolean {
  if (row.completed || !row.kickoff_utc) return false;
  const kickoff = new Date(row.kickoff_utc).getTime();
  if (Number.isNaN(kickoff)) return false;
  const now = reference.getTime();
  return now >= kickoff && now < kickoff + MATCH_DURATION_MS;
}

export function applyLiveStatus(fixtures: FixtureRow[], reference = new Date()): FixtureRow[] {
  return fixtures.map((row) =>
    isLikelyLive(row, reference) ? { ...row, status: "LIVE" as const } : row
  );
}

export function liveFixtures(fixtures: FixtureRow[], reference = new Date()): FixtureRow[] {
  return applyLiveStatus(fixtures, reference).filter((r) => r.status === "LIVE");
}

export function formatElapsedMinute(kickoffUtc: string, reference = new Date()): string {
  const kickoff = new Date(kickoffUtc).getTime();
  if (Number.isNaN(kickoff)) return "—";
  const elapsed = Math.floor((reference.getTime() - kickoff) / 60_000);
  if (elapsed < 0) return "0′";
  if (elapsed > 120) return "120+′";
  return `${elapsed}′`;
}

export function fixtureDayKey(row: FixtureRow): string | null {
  const iso = row.kickoff_utc ?? row.date;
  if (!iso) return null;
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return null;
    return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
  } catch {
    return null;
  }
}

export function isSameCalendarDay(iso: string, reference = new Date()): boolean {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return false;
    return (
      d.getFullYear() === reference.getFullYear() &&
      d.getMonth() === reference.getMonth() &&
      d.getDate() === reference.getDate()
    );
  } catch {
    return false;
  }
}

export function fixturesForToday(
  fixtures: FixtureRow[],
  reference = new Date()
): FixtureRow[] {
  return fixtures
    .filter((row) => {
      const iso = row.kickoff_utc ?? row.date;
      return iso ? isSameCalendarDay(iso, reference) : false;
    })
    .sort((a, b) => {
      const ak = a.kickoff_utc ?? a.date;
      const bk = b.kickoff_utc ?? b.date;
      return ak.localeCompare(bk);
    });
}

export function formatTodayHeading(reference = new Date()): string {
  return reference.toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
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
