"use client";
import { useEffect, useMemo, useState } from "react";
import { api, Overview, Player } from "@/lib/api";
import { RoleChip, SectionTitle, Skeleton } from "@/components/ui";
import { Flag } from "@/components/Flag";

const METRICS: { key: string; label: string; fmt?: (n: number) => string }[] = [
  { key: "minutes", label: "Minutes" },
  { key: "totalGoals_total", label: "Goals" },
  { key: "expectedGoals_p90", label: "xG / 90", fmt: (n) => n?.toFixed(2) },
  { key: "expectedAssists_p90", label: "xA / 90", fmt: (n) => n?.toFixed(2) },
  { key: "totalShots_p90", label: "Shots / 90", fmt: (n) => n?.toFixed(2) },
  { key: "duelsWon_p90", label: "Duels won / 90", fmt: (n) => n?.toFixed(1) },
  { key: "defensiveInterventions_p90", label: "Def. actions / 90", fmt: (n) => n?.toFixed(1) },
  { key: "passPct", label: "Pass %", fmt: (n) => (n * 100)?.toFixed(0) + "%" },
  { key: "rating", label: "Rating", fmt: (n) => n?.toFixed(2) },
];
const ROLES = ["ALL", "GK", "DEF", "MID", "FWD"];
const ROLE_ORDER: Record<string, number> = { GK: 0, DEF: 1, MID: 2, FWD: 3 };
type Dir = "asc" | "desc";

export default function Explore() {
  const [teams, setTeams] = useState<string[]>([]);
  const [players, setPlayers] = useState<Player[]>([]);
  const [team, setTeam] = useState("ALL");
  const [role, setRole] = useState("ALL");
  const [sort, setSort] = useState("minutes");          // which stat column to show
  const [sortKey, setSortKey] = useState("minutes");    // active sort column
  const [sortDir, setSortDir] = useState<Dir>("desc");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.overview().then((o: Overview) =>
      setTeams(o.teams.map((t) => t.team_name).sort((a, b) => a.localeCompare(b)))
    );
  }, []);

  useEffect(() => {
    setLoading(true);
    const q = new URLSearchParams({ sort, limit: "1500" });
    if (team !== "ALL") q.set("team", team);
    if (role !== "ALL") q.set("role", role);
    api.players(q.toString()).then((r) => {
      setPlayers(r.players);
      setLoading(false);
    });
  }, [team, role, sort]);

  // Changing the displayed metric also sorts by it (descending).
  useEffect(() => {
    setSortKey(sort);
    setSortDir("desc");
  }, [sort]);

  const metric = useMemo(() => METRICS.find((m) => m.key === sort)!, [sort]);

  function toggleSort(key: string) {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      // text columns default A→Z, numbers default high→low
      setSortDir(["player_name", "team_name", "role"].includes(key) ? "asc" : "desc");
    }
  }

  const sorted = useMemo(() => {
    const arr = [...players];
    arr.sort((a, b) => {
      let av: any, bv: any;
      if (sortKey === "role") {
        av = ROLE_ORDER[a.role] ?? 9;
        bv = ROLE_ORDER[b.role] ?? 9;
      } else {
        av = (a as any)[sortKey];
        bv = (b as any)[sortKey];
      }
      if (typeof av === "string" || typeof bv === "string") {
        const r = String(av ?? "").localeCompare(String(bv ?? ""));
        return sortDir === "asc" ? r : -r;
      }
      av = av ?? -Infinity;
      bv = bv ?? -Infinity;
      return sortDir === "asc" ? av - bv : bv - av;
    });
    return arr;
  }, [players, sortKey, sortDir]);

  const arrow = (key: string) =>
    sortKey === key ? (sortDir === "asc" ? " ▲" : " ▼") : "";

  return (
    <div className="space-y-5">
      <SectionTitle title="Player explorer" hint={`${players.length} players`} />

      {/* Filters */}
      <div className="card flex flex-wrap items-center gap-3 p-4">
        <select value={team} onChange={(e) => setTeam(e.target.value)} className="select">
          <option value="ALL">All teams</option>
          {teams.map((t) => (
            <option key={t} value={t}>{t}</option>
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
              <option key={m.key} value={m.key}>{m.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <div className="card space-y-2 p-4">
          <Skeleton className="h-10" />
          {Array.from({ length: 12 }).map((_, i) => (
            <Skeleton key={i} className="h-8" />
          ))}
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-pitch-edge/40 text-left text-xs uppercase tracking-wider text-muted">
              <tr>
                <th className="px-4 py-3">#</th>
                {[
                  { key: "player_name", label: "Player", align: "left" },
                  { key: "team_name", label: "Team", align: "left" },
                  { key: "role", label: "Role", align: "left" },
                  { key: "minutes", label: "Mins", align: "right" },
                  { key: metric.key, label: metric.label, align: "right" },
                ].map((c) => (
                  <th
                    key={c.key}
                    onClick={() => toggleSort(c.key)}
                    className={`cursor-pointer select-none px-4 py-3 transition-colors hover:text-fg ${
                      c.align === "right" ? "text-right" : ""
                    } ${sortKey === c.key ? "text-pitch-accent" : ""}`}
                    title="Click to sort"
                  >
                    {c.label}{arrow(c.key)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-pitch-edge/40">
              {sorted.slice(0, 300).map((p, i) => (
                <tr key={`${p.player_id}-${p.team_name}`} className="hover:bg-pitch-edge/20">
                  <td className="px-4 py-2.5 text-faint">{i + 1}</td>
                  <td className="px-4 py-2.5 font-semibold text-fg">{p.player_name}</td>
                  <td className="px-4 py-2.5 text-muted">
                    <span className="inline-flex items-center gap-1.5">
                      <Flag src={p.flag_url} name={p.team_name} size={14} />
                      {p.team_name}
                    </span>
                  </td>
                  <td className="px-4 py-2.5"><RoleChip role={p.role} /></td>
                  <td className="px-4 py-2.5 text-right text-muted">{p.minutes}</td>
                  <td className="px-4 py-2.5 text-right font-bold stat-grad">
                    {metric.fmt ? metric.fmt(p[metric.key]) : p[metric.key] ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
