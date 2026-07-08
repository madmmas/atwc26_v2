"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, Overview, Player } from "@/lib/api";
import { fetchAllPlayers, matchPlayerName } from "@/lib/playerSearch";
import { Flag } from "@/components/Flag";
import { StatLabel } from "@/components/StatTooltip";
import { SkeletonRow } from "@/components/SkeletonRow";
import { RoleChip, SectionTitle } from "@/components/ui";

const PAGE_SIZE = 50;

const METRICS: { key: string; label: string; stat: string; fmt?: (n: number) => string }[] = [
  { key: "minutes", label: "Min", stat: "Min" },
  { key: "totalGoals_total", label: "Goals", stat: "Goals" },
  { key: "expectedGoals_p90", label: "xG / 90", fmt: (n) => n?.toFixed(2), stat: "xG / 90" },
  { key: "expectedAssists_p90", label: "xA / 90", fmt: (n) => n?.toFixed(2), stat: "xA / 90" },
  { key: "totalShots_p90", label: "Shots / 90", fmt: (n) => n?.toFixed(2), stat: "Shots / 90" },
  { key: "duelsWon_p90", label: "Duels / 90", fmt: (n) => n?.toFixed(1), stat: "Duels won / 90" },
  {
    key: "defensiveInterventions_p90",
    label: "Def / 90",
    fmt: (n) => n?.toFixed(1),
    stat: "Def. actions / 90",
  },
  { key: "passPct", label: "Pass %", fmt: (n) => (n * 100)?.toFixed(0) + "%", stat: "Pass%" },
];

const SORT_URL_MAP: Record<string, string> = {
  minutes: "minutes",
  totalGoals_total: "goals",
  expectedGoals_p90: "xG90",
  expectedAssists_p90: "xA90",
  totalShots_p90: "shots90",
  duelsWon_p90: "duels90",
  defensiveInterventions_p90: "def90",
  passPct: "passPct",
};

const SORT_FROM_URL: Record<string, string> = Object.fromEntries(
  Object.entries(SORT_URL_MAP).map(([k, v]) => [v, k])
);

const ROLES = ["ALL", "GK", "DEF", "MID", "FWD"];

type SortDir = "asc" | "desc";

function buildQuery(p: {
  sort: string;
  dir: SortDir;
  role: string;
  team: string;
  cursor?: string | null;
}) {
  const q = new URLSearchParams({
    sort: p.sort,
    dir: p.dir,
    limit: String(PAGE_SIZE),
    fields: "slim",
  });
  if (p.role !== "ALL") q.set("role", p.role);
  if (p.team !== "ALL") q.set("team", p.team);
  if (p.cursor) q.set("cursor", p.cursor);
  return q.toString();
}

function SortableHeader({
  label,
  stat,
  columnKey,
  activeKey,
  dir,
  align = "left",
  onSort,
}: {
  label: string;
  stat?: string;
  columnKey: string;
  activeKey: string;
  dir: SortDir;
  align?: "left" | "right";
  onSort: (key: string) => void;
}) {
  const active = columnKey === activeKey;
  const ariaSort = active ? (dir === "asc" ? "ascending" : "descending") : "none";

  return (
    <th className={`px-4 py-3 font-medium ${align === "right" ? "text-right" : "text-left"}`}>
      <button
        type="button"
        role="columnheader"
        aria-sort={ariaSort}
        onClick={() => onSort(columnKey)}
        className={`inline-flex items-center gap-0.5 transition-colors ${
          active ? "text-pitch-accent" : "text-[#888] hover:text-fg-soft"
        } ${align === "right" ? "ml-auto" : ""}`}
      >
        {stat ? <StatLabel stat={stat} /> : label}
        {active && (
          <span className="text-pitch-accent" aria-hidden>
            {dir === "asc" ? "↑" : "↓"}
          </span>
        )}
      </button>
    </th>
  );
}

function ExploreContent() {
  const searchParams = useSearchParams();
  const [teamOptions, setTeamOptions] = useState<string[]>([]);
  const [players, setPlayers] = useState<Player[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [team, setTeam] = useState("ALL");
  const [role, setRole] = useState("ALL");
  const [sort, setSort] = useState("minutes");
  const [dir, setDir] = useState<SortDir>("desc");
  const [search, setSearch] = useState("");
  const [searchDebounced, setSearchDebounced] = useState("");
  const [searchPool, setSearchPool] = useState<Player[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const urlInit = useRef(false);

  useEffect(() => {
    if (urlInit.current) return;
    const urlSort = searchParams.get("sort");
    const urlOrder = searchParams.get("order");
    if (urlSort && SORT_FROM_URL[urlSort]) setSort(SORT_FROM_URL[urlSort]);
    if (urlOrder === "asc" || urlOrder === "desc") setDir(urlOrder);
    urlInit.current = true;
  }, [searchParams]);

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
      const data = await api.players(buildQuery({ sort, dir, role, team }));
      if (ctrl.signal.aborted) return;
      setPlayers(data.players);
      setTotalCount(data.count);
      setNextCursor(data.next_cursor ?? null);
    } finally {
      if (!ctrl.signal.aborted) setLoading(false);
    }
  }, [sort, dir, role, team]);

  useEffect(() => {
    fetchFirst();
  }, [fetchFirst]);

  const fetchMore = useCallback(async () => {
    if (!nextCursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const data = await api.players(buildQuery({ sort, dir, role, team, cursor: nextCursor }));
      setPlayers((prev) => [...prev, ...data.players]);
      setNextCursor(data.next_cursor ?? null);
    } finally {
      setLoadingMore(false);
    }
  }, [nextCursor, loadingMore, sort, dir, role, team]);

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

  useEffect(() => {
    const t = setTimeout(() => setSearchDebounced(search.trim()), 150);
    return () => clearTimeout(t);
  }, [search]);

  useEffect(() => {
    if (!searchDebounced) {
      setSearchPool(null);
      return;
    }
    let cancelled = false;
    fetchAllPlayers().then((all) => {
      if (!cancelled) setSearchPool(all);
    });
    return () => {
      cancelled = true;
    };
  }, [searchDebounced]);

  const displayed = useMemo(() => {
    if (!searchDebounced) return players;
    const pool = searchPool ?? players;
    return pool.filter((p) => matchPlayerName(p.player_name, searchDebounced));
  }, [players, searchPool, searchDebounced]);

  function handleSort(key: string) {
    if (key === sort) {
      setDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSort(key);
      setDir("desc");
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <SectionTitle
          title="Player explorer"
          hint={loading ? "Loading…" : `${totalCount} players`}
        />
        <p className="text-sm text-muted">
          Browse and rank all {totalCount || "1,251"} players by any stat
        </p>
      </div>

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

        <div className="relative min-w-[180px] flex-1">
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search player name…"
            className="h-[34px] w-full rounded-lg border border-[#2a2a2a] bg-[#1e1e1e] px-3 pr-8 text-sm text-[#ddd] outline-none focus:border-pitch-accent"
          />
          {search && (
            <button
              type="button"
              onClick={() => setSearch("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-faint hover:text-fg"
              aria-label="Clear search"
            >
              ×
            </button>
          )}
        </div>

        <div className="flex items-center gap-2 text-sm">
          <span className="text-faint">Sort by</span>
          <select
            value={sort}
            onChange={(e) => {
              setSort(e.target.value);
              setDir("desc");
            }}
            className="select"
          >
            {METRICS.map((m) => (
              <option key={m.key} value={m.key}>
                {m.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <div className="card overflow-hidden p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-pitch-edge text-left text-xs text-faint">
                <th className="px-4 py-3 font-medium">#</th>
                <th className="px-4 py-3 font-medium">Player</th>
                <th className="px-4 py-3 font-medium">Team</th>
                <th className="px-4 py-3 font-medium">Role</th>
                {METRICS.map((m) => (
                  <th key={m.key} className="px-4 py-3 text-right font-medium">
                    {m.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Array.from({ length: 12 }).map((_, i) => (
                <SkeletonRow key={i} />
              ))}
            </tbody>
          </table>
        </div>
      ) : displayed.length === 0 ? (
        <div className="card p-8 text-center text-sm text-muted">
          No players match &apos;{searchDebounced}&apos;. Try a different name or clear the filters.
        </div>
      ) : (
        <>
          <div className="card overflow-x-auto p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-pitch-edge text-xs">
                  <th className="px-4 py-3 font-medium text-[#888]">#</th>
                  <th className="px-4 py-3 font-medium text-[#888]">Player</th>
                  <th className="px-4 py-3 font-medium text-[#888]">Team</th>
                  <th className="px-4 py-3 font-medium text-[#888]">Role</th>
                  {METRICS.map((m) => (
                    <SortableHeader
                      key={m.key}
                      label={m.label}
                      stat={m.stat}
                      columnKey={m.key}
                      activeKey={sort}
                      dir={dir}
                      align="right"
                      onSort={handleSort}
                    />
                  ))}
                </tr>
              </thead>
              <tbody>
                {displayed.map((p, i) => (
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
                    {METRICS.map((m) => {
                      const val = (p as Record<string, number | undefined>)[m.key];
                      return (
                        <td
                          key={m.key}
                          className={`px-4 py-3 text-right font-mono ${
                            m.key === sort ? "font-medium text-fg" : "text-fg-soft"
                          }`}
                        >
                          {val == null ? "—" : m.fmt ? m.fmt(val) : val}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {!searchDebounced && (
            <>
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
        </>
      )}
    </div>
  );
}

export default function Explore() {
  return (
    <Suspense fallback={<div className="card p-8 text-faint">Loading explorer…</div>}>
      <ExploreContent />
    </Suspense>
  );
}
