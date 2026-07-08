import { BracketData, GroupStandings, MatchListItem } from "@/lib/api";

export type StageKey = "all" | "group" | "r16" | "qf" | "sf" | "final";

export const STAGE_TABS: { key: StageKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "group", label: "Group Stage" },
  { key: "r16", label: "Round of 16" },
  { key: "qf", label: "Quarter-finals" },
  { key: "sf", label: "Semi-finals" },
  { key: "final", label: "Final" },
];

const ROUND_TO_STAGE: Record<string, StageKey> = {
  "Round of 16": "r16",
  Quarterfinals: "qf",
  Semifinals: "sf",
  Final: "final",
  "Third Place Match": "sf",
};

export function buildTeamGroupMap(groups: Record<string, GroupStandings>): Map<string, string> {
  const map = new Map<string, string>();
  for (const [gname, g] of Object.entries(groups)) {
    const letter = gname.replace(/^Group\s+/i, "");
    for (const t of g.teams) {
      map.set(t.team_name, letter);
    }
  }
  return map;
}

export function buildGameStageMap(bracket: BracketData): Map<string, StageKey> {
  const map = new Map<string, StageKey>();
  for (const round of bracket.rounds) {
    const stage = ROUND_TO_STAGE[round.name];
    if (!stage) continue;
    for (const m of round.matches) {
      map.set(m.game_id, stage);
    }
  }
  return map;
}

export function classifyMatch(
  m: MatchListItem,
  teamGroups: Map<string, string>,
  gameStages: Map<string, StageKey>
): { stage: StageKey; group?: string } {
  const knockout = gameStages.get(m.game_id);
  if (knockout) return { stage: knockout };

  const homeGroup = teamGroups.get(m.home_team);
  const awayGroup = teamGroups.get(m.away_team);
  if (homeGroup && awayGroup && homeGroup === awayGroup) {
    return { stage: "group", group: homeGroup };
  }

  return { stage: "all" };
}

export function filterMatches(
  matches: MatchListItem[],
  stage: StageKey,
  group: string | null,
  teamGroups: Map<string, string>,
  gameStages: Map<string, StageKey>
): MatchListItem[] {
  return matches.filter((m) => {
    const info = classifyMatch(m, teamGroups, gameStages);
    if (stage === "all") return true;
    if (info.stage !== stage) return false;
    if (stage === "group" && group && group !== "all") {
      return info.group === group;
    }
    return true;
  });
}

export function stageCounts(
  matches: MatchListItem[],
  teamGroups: Map<string, string>,
  gameStages: Map<string, StageKey>
): Record<StageKey, number> {
  const counts: Record<StageKey, number> = {
    all: matches.length,
    group: 0,
    r16: 0,
    qf: 0,
    sf: 0,
    final: 0,
  };
  for (const m of matches) {
    const { stage } = classifyMatch(m, teamGroups, gameStages);
    if (stage !== "all") counts[stage] += 1;
  }
  return counts;
}

export const GROUP_LETTERS = "ABCDEFGHIJKL".split("");
