"use client";
import { useEffect, useMemo, useState } from "react";
import { api, Overview, Player, PlayerDetail } from "@/lib/api";
import { Flag } from "@/components/Flag";
import { RoleChip, Spinner } from "@/components/ui";

function fmtDate(d?: string) {
  if (!d) return "";
  try {
    return new Date(d).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return d;
  }
}

const RESULT_COLOR: Record<string, string> = {
  W: "bg-emerald-500/20 text-emerald-300",
  D: "bg-slate-500/20 text-fg-soft",
  L: "bg-rose-500/20 text-rose-300",
};

export default function Players() {
  const [teams, setTeams] = useState<{ name: string; flag?: string | null }[]>([]);
  const [team, setTeam] = useState("");
  const [roster, setRoster] = useState<Player[]>([]);
  const [playerId, setPlayerId] = useState<number | null>(null);
  const [detail, setDetail] = useState<PlayerDetail | null>(null);
  const [view, setView] = useState<string>("all"); // "all" or a game_id
  const [loadingRoster, setLoadingRoster] = useState(false);

  useEffect(() => {
    api.overview().then((o: Overview) =>
      setTeams(
        o.teams
          .map((t) => ({ name: t.team_name, flag: t.flag_url }))
          .sort((a, b) => a.name.localeCompare(b.name))
      )
    );
  }, []);

  useEffect(() => {
    if (!team) return;
    setLoadingRoster(true);
    setDetail(null);
    setPlayerId(null);
    api.teamPlayers(team).then((r) => {
      // alphabetical by player name, so they're easy to find
      const sorted = [...r.players].sort((a, b) =>
        a.player_name.localeCompare(b.player_name)
      );
      setRoster(sorted);
      setLoadingRoster(false);
    });
  }, [team]);

  useEffect(() => {
    if (!playerId) return;
    setDetail(null);
    setView("all");
    api.playerDetail(playerId).then(setDetail);
  }, [playerId]);

  const teamFlag = useMemo(() => teams.find((t) => t.name === team)?.flag, [teams, team]);

  // Value for an indicator under the current view (all vs single match).
  function valueFor(key: string, per90: boolean): string {
    if (!detail) return "—";
    if (view === "all") {
      const v = detail.totals[key];
      if (v == null) return "—";
      const extra = per90 && detail.per90[key] != null ? ` (${detail.per90[key]}/90)` : "";
      return `${v}${extra}`;
    }
    const m = detail.matches.find((x) => x.game_id === view);
    const v = m?.stats[key];
    return v == null ? "—" : `${v}`;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black text-fg">Player Analysis</h1>
        <p className="text-sm text-muted">
          Pick a country and player to see their key performance indicators — across
          the whole tournament or a single match.
        </p>
      </div>

      {/* Selectors */}
      <div className="card flex flex-wrap items-center gap-3 p-4">
        <select value={team} onChange={(e) => setTeam(e.target.value)} className="select" data-testid="pa-team">
          <option value="">Select country…</option>
          {teams.map((t) => (
            <option key={t.name} value={t.name}>{t.name}</option>
          ))}
        </select>
        {teamFlag && <Flag src={teamFlag} name={team} size={22} />}
        <select
          value={playerId ?? ""}
          onChange={(e) => setPlayerId(e.target.value ? Number(e.target.value) : null)}
          className="select min-w-[200px]"
          disabled={!roster.length}
          data-testid="pa-player"
        >
          <option value="">{loadingRoster ? "Loading…" : "Select player…"}</option>
          {roster.map((p) => (
            <option key={p.player_id} value={p.player_id}>
              {p.player_name} {p.minutes > 0 ? `· ${p.minutes}m` : "· DNP"}
            </option>
          ))}
        </select>
      </div>

      {!detail ? (
        playerId ? <Spinner /> : (
          <div className="card p-8 text-center text-faint">
            Select a country and player to begin.
          </div>
        )
      ) : detail.matches.length === 0 ? (
        <div className="card p-8 text-center text-muted" data-testid="pa-detail">
          <PlayerHeader detail={detail} />
          <p className="mt-4 text-sm">
            This player hasn’t featured in a match yet (DNP) — no performance data to show.
          </p>
        </div>
      ) : (
        <div className="space-y-5" data-testid="pa-detail">
          <PlayerHeader detail={detail} />

          {/* View toggle: all matches or a specific game */}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setView("all")}
              className={`rounded-lg px-3 py-1.5 text-xs font-bold ${
                view === "all" ? "bg-pitch-accent text-pitch-bg" : "bg-pitch-edge/60 text-fg-soft"
              }`}
            >
              All matches
            </button>
            {detail.matches.map((m) => (
              <button
                key={m.game_id}
                onClick={() => setView(m.game_id)}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold ${
                  view === m.game_id ? "bg-pitch-accent text-pitch-bg" : "bg-pitch-edge/60 text-fg-soft"
                }`}
              >
                <Flag src={m.opp_flag} name={m.opponent} size={14} />
                vs {m.opponent} {m.score}
              </button>
            ))}
          </div>

          {/* Indicator cards */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {detail.indicators.map((ind) => (
              <div key={ind.key} className="card p-3">
                <div className="text-[11px] uppercase tracking-wider text-faint">{ind.label}</div>
                <div className="mt-1 text-xl font-black stat-grad">{valueFor(ind.key, ind.per90)}</div>
              </div>
            ))}
          </div>

          {/* Per-match table */}
          <div>
            <div className="mb-2 text-sm font-bold text-fg">Match-by-match</div>
            <div className="card overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-pitch-edge/40 text-left text-xs uppercase tracking-wider text-muted">
                  <tr>
                    <th className="px-4 py-2.5">Opponent</th>
                    <th className="px-4 py-2.5">Res</th>
                    <th className="px-4 py-2.5 text-right">Min</th>
                    <th className="px-4 py-2.5 text-right">G</th>
                    <th className="px-4 py-2.5 text-right">A</th>
                    <th className="px-4 py-2.5 text-right">xG</th>
                    <th className="px-4 py-2.5 text-right">Shots</th>
                    <th className="px-4 py-2.5 text-right">Passes</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-pitch-edge/40">
                  {detail.matches.map((m) => (
                    <tr key={m.game_id} className="hover:bg-pitch-edge/20">
                      <td className="px-4 py-2.5">
                        <span className="inline-flex items-center gap-2 text-fg">
                          <Flag src={m.opp_flag} name={m.opponent} size={16} />
                          {m.opponent} <span className="text-faint">{m.score}</span>
                        </span>
                      </td>
                      <td className="px-4 py-2.5">
                        {m.result && (
                          <span className={`chip ${RESULT_COLOR[m.result]}`}>{m.result}</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-right text-muted">{m.minutes}</td>
                      <td className="px-4 py-2.5 text-right">{m.stats.totalGoals ?? "—"}</td>
                      <td className="px-4 py-2.5 text-right">{m.stats.goalAssists ?? "—"}</td>
                      <td className="px-4 py-2.5 text-right">{m.stats.expectedGoals ?? "—"}</td>
                      <td className="px-4 py-2.5 text-right">{m.stats.totalShots ?? "—"}</td>
                      <td className="px-4 py-2.5 text-right">{m.stats.totalPasses ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function PlayerHeader({ detail }: { detail: PlayerDetail }) {
  const p = detail.player;
  return (
    <div className="card flex flex-wrap items-center gap-4 p-5">
      <Flag src={p.flag_url} name={p.team_name} size={44} />
      <div className="flex-1">
        <div className="text-xl font-black text-fg">{p.player_name}</div>
        <div className="flex items-center gap-2 text-sm text-muted">
          {p.team_name} · {p.position} <RoleChip role={p.role} />
        </div>
      </div>
      <div className="flex gap-5 text-center">
        <div>
          <div className="text-2xl font-black stat-grad">{p.games}</div>
          <div className="text-[10px] uppercase tracking-wider text-faint">Matches</div>
        </div>
        <div>
          <div className="text-2xl font-black stat-grad">{p.minutes}</div>
          <div className="text-[10px] uppercase tracking-wider text-faint">Minutes</div>
        </div>
      </div>
    </div>
  );
}
