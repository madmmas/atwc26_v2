"use client";
import { useMemo, useState } from "react";
import { GroupStandings, GroupTeam } from "@/lib/api";
import { TeamLabel } from "@/components/Flag";
import { StatLabel } from "@/components/StatTooltip";

export type ScoreInput = { home: number | ""; away: number | "" };
export type Predictions = Record<string, ScoreInput>;

// Real GP/W/D/L/F/A + any filled-in hypothetical remaining-match scores ->
// a freshly ranked table. Pure function, shared with Bracket.tsx so the
// knockout slots resolve against the exact same "what would the group look
// like" computation as the table itself.
export function applyHypotheticalResults(
  group: GroupStandings,
  predictions: Predictions
): GroupTeam[] {
  const byId = new Map(group.teams.map((t) => [t.team_id, { ...t }]));

  for (const m of group.remaining_matches) {
    const pred = predictions[m.game_id];
    if (!pred || pred.home === "" || pred.away === "") continue;
    const home = byId.get(m.home_team_id);
    const away = byId.get(m.away_team_id);
    if (!home || !away) continue;

    const hs = Number(pred.home);
    const as = Number(pred.away);
    home.GP += 1;
    away.GP += 1;
    home.F += hs;
    home.A += as;
    away.F += as;
    away.A += hs;
    if (hs > as) {
      home.W += 1;
      away.L += 1;
    } else if (hs < as) {
      away.W += 1;
      home.L += 1;
    } else {
      home.D += 1;
      away.D += 1;
    }
  }

  const ranked = [...byId.values()].map((t) => ({
    ...t,
    GD: t.F - t.A,
    P: t.W * 3 + t.D,
  }));
  ranked.sort((a, b) =>
    b.P - a.P || b.GD - a.GD || b.F - a.F || a.team_name.localeCompare(b.team_name)
  );
  return ranked.map((t, i) => ({ ...t, rank: i + 1 }));
}

function ScoreCell({
  value,
  onChange,
}: {
  value: number | "";
  onChange: (v: number | "") => void;
}) {
  return (
    <input
      type="number"
      min={0}
      max={20}
      inputMode="numeric"
      value={value}
      placeholder="-"
      onChange={(e) => {
        const v = e.target.value;
        onChange(v === "" ? "" : Math.max(0, Math.min(20, Number(v))));
      }}
      className="h-8 w-12 rounded-md border border-pitch-edge bg-pitch-card text-center text-sm
                 font-bold text-fg outline-none focus:border-pitch-accent"
    />
  );
}

function formatXgBalance(n: number | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  if (n > 0) return `+${n.toFixed(1)}`;
  return n.toFixed(1);
}

function xgBalanceColor(n: number | undefined): string {
  if (n == null || n === 0) return "text-[#888]";
  return n > 0 ? "text-[#1D9E75]" : "text-[#e05555]";
}

export function GroupTable({
  name,
  group,
  ranked,
  predictions,
  xgByTeam,
  onSetScore,
  onReset,
}: {
  name: string;
  group: GroupStandings;
  ranked: GroupTeam[];
  predictions: Predictions;
  xgByTeam?: Map<string, number>;
  onSetScore: (gameId: string, side: "home" | "away", v: number | "") => void;
  onReset: (gameIds: string[]) => void;
}) {
  const [sortByXg, setSortByXg] = useState(false);
  const groupGameIds = group.remaining_matches.map((m) => m.game_id);
  const hasPredictions = groupGameIds.some((gid) => {
    const p = predictions[gid];
    return p && (p.home !== "" || p.away !== "");
  });

  const displayRows = useMemo(() => {
    if (!sortByXg || !xgByTeam) return ranked;
    return [...ranked].sort((a, b) => {
      const xa = xgByTeam.get(a.team_name) ?? -Infinity;
      const xb = xgByTeam.get(b.team_name) ?? -Infinity;
      return xb - xa || a.rank - b.rank;
    });
  }, [ranked, sortByXg, xgByTeam]);

  return (
    <div className="card p-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-bold text-fg">{name}</h3>
        {hasPredictions && (
          <button
            onClick={() => onReset(groupGameIds)}
            className="text-[11px] font-semibold text-faint hover:text-fg"
          >
            Reset
          </button>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-faint">
              <th className="py-1 text-left font-semibold">Team</th>
              {["GP", "W", "D", "L", "F", "A", "GD", "P"].map((h) => (
                <th key={h} className="px-1.5 py-1 text-right font-semibold">
                  {h}
                </th>
              ))}
              <th className="px-1.5 py-1 text-right font-semibold">
                <button
                  type="button"
                  onClick={() => setSortByXg((v) => !v)}
                  className={`inline-flex items-center gap-0.5 transition-colors ${
                    sortByXg ? "text-pitch-accent" : "hover:text-fg"
                  }`}
                  aria-sort={sortByXg ? "descending" : "none"}
                >
                  <StatLabel stat="xG±" />
                  {sortByXg && <span className="text-pitch-accent">↓</span>}
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            {displayRows.map((t) => {
              const xgb = xgByTeam?.get(t.team_name);
              return (
              <tr
                key={t.team_id}
                className={`border-t border-pitch-edge/40 ${
                  t.rank <= 2 ? "bg-pitch-accent/5" : ""
                }`}
              >
                <td className="py-1.5">
                  <TeamLabel name={t.team_name} flag={t.flag_url} size={16} />
                </td>
                <td className="px-1.5 text-right text-fg">{t.GP}</td>
                <td className="px-1.5 text-right text-fg">{t.W}</td>
                <td className="px-1.5 text-right text-fg">{t.D}</td>
                <td className="px-1.5 text-right text-fg">{t.L}</td>
                <td className="px-1.5 text-right text-fg">{t.F}</td>
                <td className="px-1.5 text-right text-fg">{t.A}</td>
                <td className="px-1.5 text-right text-fg">{t.GD > 0 ? `+${t.GD}` : t.GD}</td>
                <td className="px-1.5 text-right font-bold text-fg">{t.P}</td>
                <td className={`px-1.5 text-right font-medium ${xgBalanceColor(xgb)}`}>
                  {formatXgBalance(xgb)}
                </td>
              </tr>
            );
            })}
          </tbody>
        </table>
      </div>

      {group.remaining_matches.length > 0 && (
        <div className="mt-3 border-t border-pitch-edge/40 pt-3">
          <div className="mb-1.5 text-[10px] uppercase tracking-wider text-faint">
            Predict the remaining match{group.remaining_matches.length > 1 ? "es" : ""}
          </div>
          <div className="space-y-1.5">
            {group.remaining_matches.map((m) => (
              <div key={m.game_id} className="flex items-center justify-between gap-2 text-xs">
                <span className="min-w-0 flex-1 truncate text-right text-fg-soft">
                  {m.home_team}
                </span>
                <ScoreCell
                  value={predictions[m.game_id]?.home ?? ""}
                  onChange={(v) => onSetScore(m.game_id, "home", v)}
                />
                <span className="text-faint">–</span>
                <ScoreCell
                  value={predictions[m.game_id]?.away ?? ""}
                  onChange={(v) => onSetScore(m.game_id, "away", v)}
                />
                <span className="min-w-0 flex-1 truncate text-fg-soft">{m.away_team}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
