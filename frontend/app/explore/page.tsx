"use client";
import { useEffect, useMemo, useState } from "react";
import { api, Overview, Player } from "@/lib/api";
import { RoleChip, SectionTitle, Spinner } from "@/components/ui";

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

export default function Explore() {
  const [teams, setTeams] = useState<string[]>([]);
  const [players, setPlayers] = useState<Player[]>([]);
  const [team, setTeam] = useState("ALL");
  const [role, setRole] = useState("ALL");
  const [sort, setSort] = useState("minutes");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.overview().then((o: Overview) => setTeams(o.teams.map((t) => t.team_name)));
  }, []);

  useEffect(() => {
    setLoading(true);
    const q = new URLSearchParams({ sort, limit: "500" });
    if (team !== "ALL") q.set("team", team);
    if (role !== "ALL") q.set("role", role);
    api.players(q.toString()).then((r) => {
      setPlayers(r.players);
      setLoading(false);
    });
  }, [team, role, sort]);

  const metric = useMemo(() => METRICS.find((m) => m.key === sort)!, [sort]);

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
                role === r ? "bg-pitch-accent text-pitch-bg" : "bg-pitch-edge/60 text-slate-300"
              }`}
            >
              {r}
            </button>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-2 text-sm">
          <span className="text-slate-500">Sort by</span>
          <select value={sort} onChange={(e) => setSort(e.target.value)} className="select">
            {METRICS.map((m) => (
              <option key={m.key} value={m.key}>{m.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <Spinner />
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-pitch-edge/40 text-left text-xs uppercase tracking-wider text-slate-400">
              <tr>
                <th className="px-4 py-3">#</th>
                <th className="px-4 py-3">Player</th>
                <th className="px-4 py-3">Team</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3 text-right">Mins</th>
                <th className="px-4 py-3 text-right">{metric.label}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-pitch-edge/40">
              {players.slice(0, 200).map((p, i) => (
                <tr key={p.player_id} className="hover:bg-pitch-edge/20">
                  <td className="px-4 py-2.5 text-slate-500">{i + 1}</td>
                  <td className="px-4 py-2.5 font-semibold text-white">{p.player_name}</td>
                  <td className="px-4 py-2.5 text-slate-400">{p.team_name}</td>
                  <td className="px-4 py-2.5"><RoleChip role={p.role} /></td>
                  <td className="px-4 py-2.5 text-right text-slate-400">{p.minutes}</td>
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
