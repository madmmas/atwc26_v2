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
import { StatLabel } from "@/components/StatTooltip";
import { RoleChip, SectionTitle, StatCard } from "@/components/ui";
import { Flag } from "@/components/Flag";

function LeaderList({ players, metric, fmt }: { players: Player[]; metric: string; fmt?: (n: number) => string }) {
  return (
    <div className="card divide-y divide-pitch-edge/60">
      {players.map((p, i) => (
        <div key={p.player_id} className="flex items-center gap-3 px-4 py-2.5">
          <span className="w-5 text-sm font-bold text-faint">{i + 1}</span>
          <div className="flex-1">
            <Link
              href={`/players?player=${p.player_id}`}
              className="text-sm font-semibold text-fg transition-colors hover:text-pitch-accent"
              data-testid={`leader-player-${p.player_id}`}
            >
              {p.player_name}
            </Link>
            <div className="flex items-center gap-1.5 text-xs text-faint">
              <Flag src={p.flag_url} name={p.team_name} size={14} />
              {p.team_name}
            </div>
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
  const isLoading = !data && !err;

  // All tournament teams in alphabetical order (easy to find a country);
  // teams that haven't played sit at zero.
  const chart = data
    ? [...data.teams]
        .sort((a, b) => a.team_name.localeCompare(b.team_name))
        .map((t) => ({ name: t.team_name, xG: t.xg_per_game, xGA: t.xga_per_game }))
    : [];
  const chartWidth = Math.max(chart.length * 46, 640); // horizontal scroll for 48 teams

  return (
    <div className="space-y-8">
      {/* Hero */}
      <section className="relative overflow-hidden rounded-3xl border border-pitch-edge bg-pitch-card/60 p-8">
        <div className="max-w-2xl">
          <div className="chip bg-pitch-accent/15 text-pitch-accent">World Cup 2026 · Live Analytics</div>
          <h1 className="mt-3 text-4xl font-black leading-tight text-fg sm:text-5xl">
            See the game in <span className="stat-grad">numbers</span>.
          </h1>
          <p className="mt-3 text-muted">
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

      {err && (
        <div className="card p-4 text-sm text-rose-300">
          Could not load dashboard data right now. <span className="text-faint">Showing static UI only.</span>
          <div className="mt-1 text-xs text-faint">{err}</div>
        </div>
      )}

      {/* KPIs */}
      <section className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {data ? (
          <>
            <StatCard label="Teams" value={data.league.teams} />
            <StatCard label="Players tracked" value={data.league.players} />
            <StatCard label="Games" value={data.league.games} />
            <StatCard label="Avg goals / team" value={data.league.avg_team_goals} />
          </>
        ) : (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="card p-4">
              <div className="h-3 w-24 animate-pulse rounded bg-pitch-edge/70" />
              <div className="mt-3 h-8 w-14 animate-pulse rounded bg-pitch-edge/70" />
            </div>
          ))
        )}
      </section>

      {/* Team xG chart */}
      <section>
        <SectionTitle
          title="Team attacking output"
          hint={
            data
              ? `all ${chart.length} teams · xG vs. conceded (xGA) per game · scroll →`
              : "Loading chart data…"
          }
        />
        {data ? (
          <div className="card overflow-x-auto p-4">
            <div style={{ width: chartWidth, height: 340 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chart} margin={{ top: 8, right: 8, bottom: 56, left: -10 }}>
                  <CartesianGrid stroke="#94a3b8" strokeOpacity={0.18} vertical={false} />
                  <XAxis dataKey="name" angle={-45} textAnchor="end" interval={0} height={70} tick={{ fill: "#94a3b8", fontSize: 11 }} />
                  <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} />
                  <Tooltip
                    cursor={{ fill: "#94a3b8", fillOpacity: 0.1 }}
                    contentStyle={{ background: "rgb(var(--card))", border: "1px solid rgb(var(--edge))", borderRadius: 12, color: "rgb(var(--fg))" }}
                    labelStyle={{ color: "rgb(var(--fg))" }}
                  />
                  <Bar dataKey="xG" fill="#10b981" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="xGA" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        ) : (
          <div className="card p-5">
            <div className="h-64 w-full animate-pulse rounded-xl bg-pitch-edge/70" />
          </div>
        )}
      </section>

      {/* Leaderboards */}
      <section className="grid gap-6 lg:grid-cols-3">
        <div>
          <SectionTitle title="Top scorers" hint={<StatLabel stat="Goals" />} />
          {data ? (
            <LeaderList players={data.top_scorers} metric="totalGoals_total" />
          ) : (
            <div className="card space-y-2 p-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="h-8 animate-pulse rounded bg-pitch-edge/70" />
              ))}
            </div>
          )}
        </div>
        <div>
          <SectionTitle title="Sharpest finishers" hint={<StatLabel stat="xG / 90" />} />
          {data ? (
            <LeaderList players={data.top_xg_per90} metric="expectedGoals_p90" fmt={(n) => n?.toFixed(2)} />
          ) : (
            <div className="card space-y-2 p-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="h-8 animate-pulse rounded bg-pitch-edge/70" />
              ))}
            </div>
          )}
        </div>
        <div>
          <SectionTitle title="Top creators" hint={<StatLabel stat="xA / 90" />} />
          {data ? (
            <LeaderList players={data.top_creators_per90} metric="expectedAssists_p90" fmt={(n) => n?.toFixed(2)} />
          ) : (
            <div className="card space-y-2 p-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="h-8 animate-pulse rounded bg-pitch-edge/70" />
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
