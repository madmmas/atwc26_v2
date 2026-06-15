"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, Overview, Player } from "@/lib/api";
import { RoleChip, SectionTitle, Spinner, StatCard } from "@/components/ui";

function LeaderList({ players, metric, fmt }: { players: Player[]; metric: string; fmt?: (n: number) => string }) {
  return (
    <div className="card divide-y divide-pitch-edge/60">
      {players.map((p, i) => (
        <div key={p.player_id} className="flex items-center gap-3 px-4 py-2.5">
          <span className="w-5 text-sm font-bold text-slate-500">{i + 1}</span>
          <div className="flex-1">
            <div className="text-sm font-semibold text-white">{p.player_name}</div>
            <div className="text-xs text-slate-500">{p.team_name}</div>
          </div>
          <RoleChip role={p.role} />
          <span className="w-14 text-right text-sm font-bold stat-grad">
            {fmt ? fmt(p[metric]) : p[metric]}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function Home() {
  const [data, setData] = useState<Overview | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.overview().then(setData).catch((e) => setErr(String(e)));
  }, []);

  if (err)
    return (
      <div className="card mt-10 p-6 text-rose-300">
        Could not reach the API. Is the backend running? <br />
        <span className="text-xs text-slate-500">{err}</span>
      </div>
    );
  if (!data) return <Spinner label="Loading tournament data…" />;

  const chart = [...data.teams]
    .sort((a, b) => b.xg_per_game - a.xg_per_game)
    .slice(0, 12)
    .map((t) => ({ name: t.team_name, xG: t.xg_per_game, xGA: t.xga_per_game }));

  return (
    <div className="space-y-8">
      {/* Hero */}
      <section className="relative overflow-hidden rounded-3xl border border-pitch-edge bg-pitch-card/60 p-8">
        <div className="max-w-2xl">
          <div className="chip bg-pitch-accent/15 text-pitch-accent">World Cup 2026 · Live Analytics</div>
          <h1 className="mt-3 text-4xl font-black leading-tight text-white sm:text-5xl">
            See the game in <span className="stat-grad">numbers</span>.
          </h1>
          <p className="mt-3 text-slate-400">
            Explore every player and team of the tournament, then build two XIs and let
            the AI engine predict the result from real per-90 performance.
          </p>
          <div className="mt-5 flex gap-3">
            <Link href="/predict" className="btn-primary">
              Build a match →
            </Link>
            <Link href="/explore" className="btn-ghost">
              Explore players
            </Link>
          </div>
        </div>
      </section>

      {/* KPIs */}
      <section className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="Teams" value={data.league.teams} />
        <StatCard label="Players tracked" value={data.league.players} />
        <StatCard label="Games" value={data.league.games} />
        <StatCard label="Avg goals / team" value={data.league.avg_team_goals} />
      </section>

      {/* Team xG chart */}
      <section>
        <SectionTitle title="Team attacking output" hint="expected goals per game (xG) vs. conceded (xGA)" />
        <div className="card p-4" style={{ height: 320 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chart} margin={{ top: 8, right: 8, bottom: 40, left: -10 }}>
              <CartesianGrid stroke="#1e2733" vertical={false} />
              <XAxis dataKey="name" angle={-35} textAnchor="end" interval={0} tick={{ fill: "#94a3b8", fontSize: 11 }} />
              <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} />
              <Tooltip
                contentStyle={{ background: "#121821", border: "1px solid #1e2733", borderRadius: 12 }}
                labelStyle={{ color: "#fff" }}
              />
              <Bar dataKey="xG" fill="#10b981" radius={[4, 4, 0, 0]} />
              <Bar dataKey="xGA" fill="#f59e0b" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      {/* Leaderboards */}
      <section className="grid gap-6 lg:grid-cols-3">
        <div>
          <SectionTitle title="Top scorers" hint="goals" />
          <LeaderList players={data.top_scorers} metric="totalGoals_total" />
        </div>
        <div>
          <SectionTitle title="Sharpest finishers" hint="xG / 90" />
          <LeaderList players={data.top_xg_per90} metric="expectedGoals_p90" fmt={(n) => n?.toFixed(2)} />
        </div>
        <div>
          <SectionTitle title="Top creators" hint="xA / 90" />
          <LeaderList players={data.top_creators_per90} metric="expectedAssists_p90" fmt={(n) => n?.toFixed(2)} />
        </div>
      </section>
    </div>
  );
}
