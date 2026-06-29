"use client";
import { useMemo } from "react";
import { BracketData, BracketSlot, GroupTeam } from "@/lib/api";
import { TeamLabel } from "@/components/Flag";

const THIRD_PLACE_POOL_SIZE = 8;

// Best-8-of-12 third-placed teams, by the same Points -> GD -> Goals tiebreak
// used within a group (this project's deliberate simplification of FIFA's
// full official tiebreaker chain — see GroupTable.tsx).
function qualifyingThirdPlaceTeams(rankedGroups: Record<string, GroupTeam[]>): Set<string> {
  const thirds = Object.values(rankedGroups)
    .map((teams) => teams.find((t) => t.rank === 3))
    .filter((t): t is GroupTeam => !!t);
  thirds.sort((a, b) => b.P - a.P || b.GD - a.GD || b.F - a.F || a.team_name.localeCompare(b.team_name));
  return new Set(thirds.slice(0, THIRD_PLACE_POOL_SIZE).map((t) => t.team_id));
}

function resolveSlot(
  slot: BracketSlot,
  rankedGroups: Record<string, GroupTeam[]>,
  qualifyingThirds: Set<string>
): { name: string; flag_url?: string | null; resolved: boolean } {
  if (slot.type === "team") {
    return { name: slot.team_name, flag_url: slot.flag_url, resolved: true };
  }
  if (slot.type === "group_rank") {
    const team = rankedGroups[`Group ${slot.group}`]?.find((t) => t.rank === slot.rank);
    return team
      ? { name: team.team_name, flag_url: team.flag_url, resolved: true }
      : { name: `Group ${slot.group} ${slot.rank === 1 ? "Winner" : "Runner-up"}`, resolved: false };
  }
  if (slot.type === "third_place") {
    // which of this slot's candidate groups has a qualifying 3rd-placed team?
    for (const g of slot.candidate_groups) {
      const team = rankedGroups[`Group ${g}`]?.find((t) => t.rank === 3);
      if (team && qualifyingThirds.has(team.team_id)) {
        return { name: team.team_name, flag_url: team.flag_url, resolved: true };
      }
    }
    return { name: `3rd Place (${slot.candidate_groups.join("/")})`, resolved: false };
  }
  // match_winner/match_loser: a Round of 16+ slot that depends on an
  // earlier knockout match we haven't actually played yet. The bracket
  // display only resolves group-stage-derived slots (above) — it doesn't
  // simulate knockout rounds itself (tournament.py's Monte Carlo simulator
  // does that, for the winner-probability chart) — so this always shows
  // ESPN's own "Round of X N Winner/Loser" reference as readable text.
  const suffix = slot.type === "match_winner" ? "Winner" : "Loser";
  return { name: `${slot.round} ${slot.position} ${suffix}`, resolved: false };
}

// Browser-local date/time — no explicit timeZone, so Intl picks up the
// viewer's own locale/timezone automatically rather than a fixed one.
function formatKickoff(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short", month: "short", day: "numeric",
    hour: "numeric", minute: "2-digit",
  });
}

export function Bracket({
  bracket,
  rankedGroups,
}: {
  bracket: BracketData;
  rankedGroups: Record<string, GroupTeam[]>;
}) {
  const qualifyingThirds = useMemo(
    () => qualifyingThirdPlaceTeams(rankedGroups),
    [rankedGroups]
  );

  return (
    <div className="card overflow-x-auto p-4">
      <h2 className="mb-3 text-sm font-bold text-fg">Knockout Bracket</h2>
      <div className="flex gap-4">
        {bracket.rounds.map((round) => (
          <div key={round.name} className="flex min-w-[180px] flex-col justify-around gap-3">
            <div className="text-center text-[10px] font-semibold uppercase tracking-wider text-faint">
              {round.name}
            </div>
            {round.matches.map((m) => {
              const a = resolveSlot(m.slot_a, rankedGroups, qualifyingThirds);
              const b = resolveSlot(m.slot_b, rankedGroups, qualifyingThirds);
              return (
                <div key={m.game_id} className="rounded-lg border border-pitch-edge/60 bg-pitch-card p-2">
                  <div className="mb-1 text-center text-[10px] text-faint">
                    {m.completed ? "Final" : formatKickoff(m.kickoff_utc)}
                  </div>
                  {[a, b].map((slot, i) => (
                    <div
                      key={i}
                      className={`flex items-center justify-between gap-1 py-0.5 text-xs ${
                        slot.resolved ? "text-fg" : "text-faint italic"
                      }`}
                    >
                      <TeamLabel name={slot.name} flag={slot.flag_url} size={14} />
                      {m.completed && (
                        <span className="font-bold">{i === 0 ? m.score_a : m.score_b}</span>
                      )}
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        ))}
      </div>
      <p className="mt-3 text-[11px] text-faint">
        Group-rank and 3rd-place wildcard slots reflect your what-if predictions above;
        later rounds show ESPN&apos;s own placeholder until those matches are actually played.
      </p>
    </div>
  );
}
