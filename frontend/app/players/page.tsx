"use client";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, Overview, Player, PlayerDetail } from "@/lib/api";
import { Flag } from "@/components/Flag";
import { StatLabel } from "@/components/StatTooltip";
import { RoleChip, Skeleton } from "@/components/ui";

const RESULT_COLOR: Record<string, string> = {
  W: "bg-emerald-500/20 text-emerald-300",
  D: "bg-slate-500/20 text-fg-soft",
  L: "bg-rose-500/20 text-rose-300",
};

export default function Players() {
  return (
    <Suspense fallback={<PlayersSkeleton />}>
      <PlayersContent />
    </Suspense>
  );
}

function PlayersSkeleton() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black text-fg">Player Analysis</h1>
        <p className="text-sm text-muted">
          Pick a country and player to see their key performance indicators — across
          the whole tournament or a single match.
        </p>
      </div>
      <div className="card flex flex-wrap items-center gap-3 p-4">
        <Skeleton className="h-10 w-44" />
        <Skeleton className="h-10 w-52" />
      </div>
      <div className="card p-5">
        <Skeleton className="h-16 w-full" />
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="card p-3">
            <Skeleton className="h-3 w-16" />
            <Skeleton className="mt-2 h-7 w-12" />
          </div>
        ))}
      </div>
    </div>
  );
}

function PlayersContent() {
  const searchParams = useSearchParams();
  const deepLinkRef = useRef<number | null>(null);
  const processedDeepLink = useRef<string | null>(null);

  const [teams, setTeams] = useState<{ name: string; flag?: string | null }[]>([]);
  const [team, setTeam] = useState("");
  const [roster, setRoster] = useState<Player[]>([]);
  const [playerId, setPlayerId] = useState<number | null>(null);
  const [detail, setDetail] = useState<PlayerDetail | null>(null);
  const [view, setView] = useState<string>("all");
  const [loadingRoster, setLoadingRoster] = useState(false);
  const [deepLinkErr, setDeepLinkErr] = useState<string | null>(null);

  useEffect(() => {
    api.overview().then((o: Overview) =>
      setTeams(
        o.teams
          .map((t) => ({ name: t.team_name, flag: t.flag_url }))
          .sort((a, b) => a.name.localeCompare(b.name))
      )
    );
  }, []);

  // Deep link: /players?player={id}
  useEffect(() => {
    const raw = searchParams.get("player");
    if (!raw || raw === processedDeepLink.current) return;

    const id = Number(raw);
    if (!Number.isFinite(id) || id <= 0) {
      setDeepLinkErr("Invalid player id in URL.");
      return;
    }

    processedDeepLink.current = raw;
    deepLinkRef.current = id;
    setDeepLinkErr(null);

    api.playerDetail(id)
      .then((d) => setTeam(d.player.team_name))
      .catch(() => {
        deepLinkRef.current = null;
        processedDeepLink.current = null;
        setDeepLinkErr("Could not load player from link.");
      });
  }, [searchParams]);

  useEffect(() => {
    if (!team) return;

    const initPlayerId = deepLinkRef.current;
    setLoadingRoster(true);
    if (!initPlayerId) {
      setDetail(null);
      setPlayerId(null);
    }

    api.teamPlayers(team).then((r) => {
      const sorted = [...r.players].sort((a, b) =>
        a.player_name.localeCompare(b.player_name)
      );
      setRoster(sorted);
      setLoadingRoster(false);

      if (initPlayerId) {
        setPlayerId(initPlayerId);
        deepLinkRef.current = null;
      }
    });
  }, [team]);

  useEffect(() => {
    if (!playerId) return;
    setDetail(null);
    setView("all");
    api.playerDetail(playerId).then(setDetail);
  }, [playerId]);

  const teamFlag = useMemo(() => teams.find((t) => t.name === team)?.flag, [teams, team]);

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

      {deepLinkErr && (
        <div className="card p-4 text-sm text-rose-300">{deepLinkErr}</div>
      )}

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
        playerId ? (
          <div className="space-y-5">
            <div className="card p-5">
              <Skeleton className="h-16 w-full" />
            </div>
            <div className="flex flex-wrap gap-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-8 w-24 rounded-lg" />
              ))}
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="card p-3">
                  <Skeleton className="h-3 w-16" />
                  <Skeleton className="mt-2 h-7 w-12" />
                </div>
              ))}
            </div>
            <div className="card space-y-2 p-4">
              <Skeleton className="h-8" />
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-7" />
              ))}
            </div>
          </div>
        ) : (
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
                <div className="text-[11px] uppercase tracking-wider text-faint">
                  <StatLabel stat={ind.label} />
                </div>
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
                    <th className="px-4 py-2.5 text-right">
                      <StatLabel stat="Min" />
                    </th>
                    <th className="px-4 py-2.5 text-right">
                      <StatLabel stat="G" />
                    </th>
                    <th className="px-4 py-2.5 text-right">
                      <StatLabel stat="A" />
                    </th>
                    <th className="px-4 py-2.5 text-right">
                      <StatLabel stat="xG" />
                    </th>
                    <th className="px-4 py-2.5 text-right">
                      <StatLabel stat="Shots" />
                    </th>
                    <th className="px-4 py-2.5 text-right">
                      <StatLabel stat="Passes" />
                    </th>
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
