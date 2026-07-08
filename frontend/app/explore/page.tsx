"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, Overview, Player } from "@/lib/api";
import { Flag } from "@/components/Flag";
import { StatLabel } from "@/components/StatTooltip";
import { RoleChip, SectionTitle, Skeleton } from "@/components/ui";

const PAGE_SIZE = 50;

const METRICS: { key: string; label: string; fmt?: (n: number) => string }[] = [
  { key: "minutes", label: "Minutes" },
  { key: "totalGoals_total", label: "Goals" },
  { key: "expectedGoals_p90", label: "xG / 90", fmt: (n) => n?.toFixed(2) },
  { key: "expectedAssists_p90", label: "xA / 90", fmt: (n) => n?.toFixed(2) },
  { key: "totalShots_p90", label: "Shots / 90", fmt: (n) => n?.toFixed(2) },
  { key: "duelsWon_p90", label: "Duels won / 90", fmt: (n) => n?.toFixed(1) },
  { key: "defensiveInterventions_p90", label: "Def. actions / 90", fmt: (n) => n?.toFixed(1) },
  { key: "passPct", label: "Pass %", fmt: (n) => (n * 100)?.toFixed(0) + "%" },
];

const ROLES = ["ALL", "GK", "DEF", "MID", "FWD"];

function buildQuery(p: { sort: string; role: string; team: string; cursor?: string | null }) {
  const q = new URLSearchParams({
    sort: "minutes",
    dir: "desc",
    limit: String(PAGE_SIZE),
    fields: "slim",
  });
  q.set("sort", p.sort);
  if (p.role !== "ALL") q.set("role", p.role);
  if (p.team !== "ALL") q.set("team", p.team);
  if (p.cursor) q.set("cursor", p.cursor);
  return q.toString();
}

export default function Explore() {
  const [teamOptions, setTeamOptions] = useState<string[]>([]);
  const [players, setPlayers] = useState<Player[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [team, setTeam] = useState("ALL");
  const [role, setRole] = useState("ALL");
  const [sort, setSort] = useState("minutes");
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    api.overview().then((o: Overview) =>
      setTeamOptions(o.teams.map((t) => t.team_name).sort((a, b) => a.localeCompare(b)))
    );
  }, []);

  const fetchFirst = useCallback(async () => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setLoading(true);
    setPlayers([]);
    setNextCursor(null);
    try {
      const data = await api.players(buildQuery({ sort, role, team }));
      if (ctrl.signal.aborted) return;
      setPlayers(data.players);
      setTotalCount(data.count);
      setNextCursor(data.next_cursor ?? null);
    } finally {
      if (!ctrl.signal.aborted) setLoading(false);
    }
  }, [sort, role, team]);

  useEffect(() => {
    fetchFirst();
  }, [fetchFirst]);

  const fetchMore = useCallback(async () => {
    if (!nextCursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const data = await api.players(buildQuery({ sort, role, team, cursor: nextCursor }));
      setPlayers((prev) => [...prev, ...data.players]);
      setNextCursor(data.next_cursor ?? null);
    } finally {
      setLoadingMore(false);
    }
  }, [nextCursor, loadingMore, sort, role, team]);

  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) fetchMore();
      },
      { rootMargin: "200px" }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [fetchMore]);

  const metric = useMemo(() => METRICS.find((m) => m.key === sort) ?? METRICS[0], [sort]);

  return (
    <div className="space-y-5">
      <SectionTitle
        title="Player explorer"
        hint={loading ? "Loading…" : `${totalCount} players`}
      />

      <div className="card flex flex-wrap items-center gap-3 p-4">
        <select value={team} onChange={(e) => setTeam(e.target.value)} className="select">
          <option value="ALL">All teams</option>
          {teamOptions.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>

        <div className="flex gap-1">
          {ROLES.map((r) => (
            <button
              key={r}
              onClick={() => setRole(r)}
              className={`rounded-lg px-3 py-1.5 text-xs font-bold ${
                role === r ? "bg-pitch-accent text-pitch-bg" : "bg-pitch-edge/60 text-fg-soft"
              }`}
            >
              {r}
            </button>
          ))}
        </div>

        <div className="ml-auto flex items-center gap-2 text-sm">
          <span className="text-faint">Sort by</span>
          <select value={sort} onChange={(e) => setSort(e.target.value)} className="select">
            {METRICS.map((m) => (
              <option key={m.key} value={m.key}>
                {m.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <div className="card space-y-3 p-4">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="flex gap-4">
              <Skeleton className="h-4 w-6" />
              <Skeleton className="h-4 flex-1" />
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-16" />
              <Skeleton className="h-4 w-16" />
              <Skeleton className="h-4 w-16" />
            </div>
          ))}
        </div>
      ) : (
        <>
          <div className="card overflow-hidden p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-pitch-edge text-left text-xs text-faint">
                  <th className="px-4 py-3 font-medium">#</th>
                  <th className="px-4 py-3 font-medium">Player</th>
                  <th className="px-4 py-3 font-medium">Team</th>
                  <th className="px-4 py-3 font-medium">Role</th>
                  <th className="px-4 py-3 font-medium">
                    <StatLabel stat="Min" />
                  </th>
                  <th className="px-4 py-3 font-medium text-right">
                    <StatLabel stat={metric.label} />
                  </th>
                </tr>
              </thead>
              <tbody>
                {players.map((p, i) => {
                  const val = (p as Record<string, number | undefined>)[sort];
                  return (
                    <tr
                      key={p.player_id}
                      className="border-b border-pitch-edge/40 transition-colors hover:bg-pitch-edge/20"
                    >
                      <td className="px-4 py-3 text-faint">{i + 1}</td>
                      <td className="px-4 py-3 font-medium text-fg">{p.player_name}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <Flag src={p.flag_url} name={p.team_name} size={16} />
                          <span className="text-fg-soft">{p.team_name}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <RoleChip role={p.role} />
                      </td>
                      <td className="px-4 py-3 text-fg-soft">{p.minutes}</td>
                      <td className="px-4 py-3 text-right font-mono font-medium text-fg">
                        {val == null ? "—" : metric.fmt ? metric.fmt(val) : val}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div ref={sentinelRef} className="h-4" />
          {loadingMore && (
            <div className="flex justify-center py-4">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-pitch-accent border-t-transparent" />
            </div>
          )}
          {!nextCursor && players.length > 0 && (
            <p className="py-4 text-center text-xs text-faint">All {totalCount} players loaded</p>
          )}
        </>
      )}
    </div>
  );
}
