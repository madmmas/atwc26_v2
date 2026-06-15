"use client";
import {
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from "recharts";
import { Prediction } from "@/lib/api";

function ProbBar({ p }: { p: Prediction }) {
  const a = p.team_a.win_probability * 100;
  const d = p.draw_prob * 100;
  const b = p.team_b.win_probability * 100;
  return (
    <div>
      <div className="flex h-10 w-full overflow-hidden rounded-xl border border-pitch-edge text-xs font-bold">
        <div className="flex items-center justify-start bg-pitch-accent/80 pl-3 text-pitch-bg" style={{ width: `${a}%` }}>
          {a >= 8 && `${a.toFixed(0)}%`}
        </div>
        <div className="flex items-center justify-center bg-slate-600/70" style={{ width: `${d}%` }}>
          {d >= 8 && `${d.toFixed(0)}%`}
        </div>
        <div className="flex items-center justify-end bg-pitch-accent2/80 pr-3 text-pitch-bg" style={{ width: `${b}%` }}>
          {b >= 8 && `${b.toFixed(0)}%`}
        </div>
      </div>
      <div className="mt-1 flex justify-between text-xs text-slate-400">
        <span>{p.team_a.team_name} win</span>
        <span>Draw</span>
        <span>{p.team_b.team_name} win</span>
      </div>
    </div>
  );
}

export function PredictionResult({ p }: { p: Prediction }) {
  const dims = p.radar.dimensions;
  const radarData = dims.map((d) => ({
    dim: d,
    [p.team_a.team_name]: p.radar[p.team_a.team_name][d],
    [p.team_b.team_name]: p.radar[p.team_b.team_name][d],
  }));

  return (
    <div className="space-y-6" data-testid="prediction-result">
      {/* Scoreline headline */}
      <div className="card p-6 text-center">
        <div className="text-xs uppercase tracking-widest text-slate-500">
          Most likely scoreline
        </div>
        <div className="mt-2 flex items-center justify-center gap-6">
          <span className="max-w-[40%] truncate text-right text-lg font-bold text-white">
            {p.team_a.team_name}
          </span>
          <span className="text-5xl font-black stat-grad">
            {p.most_likely_score.a}–{p.most_likely_score.b}
          </span>
          <span className="max-w-[40%] truncate text-left text-lg font-bold text-white">
            {p.team_b.team_name}
          </span>
        </div>
        <div className="mt-1 text-xs text-slate-500">
          {(p.most_likely_score.prob * 100).toFixed(1)}% likely · xG {p.team_a.expected_goals} – {p.team_b.expected_goals}
        </div>
      </div>

      {/* Win probability bar */}
      <div className="card p-5">
        <ProbBar p={p} />
        <p className="mt-4 text-sm leading-relaxed text-slate-300">{p.narrative}</p>
      </div>

      {/* Radar + ratings */}
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card p-4" style={{ height: 320 }}>
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarData} outerRadius="72%">
              <PolarGrid stroke="#1e2733" />
              <PolarAngleAxis dataKey="dim" tick={{ fill: "#94a3b8", fontSize: 11 }} />
              <Radar name={p.team_a.team_name} dataKey={p.team_a.team_name} stroke="#10b981" fill="#10b981" fillOpacity={0.35} />
              <Radar name={p.team_b.team_name} dataKey={p.team_b.team_name} stroke="#06b6d4" fill="#06b6d4" fillOpacity={0.3} />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        <div className="grid grid-cols-2 gap-4">
          {[p.team_a, p.team_b].map((t, i) => (
            <div key={t.team_name} className="card p-4">
              <div className={`text-sm font-bold ${i === 0 ? "text-pitch-accent" : "text-pitch-accent2"}`}>
                {t.team_name}
              </div>
              <dl className="mt-3 space-y-2 text-sm">
                {[
                  ["Attack", t.attack_rating],
                  ["Defense", t.defense_rating],
                  ["Goalkeeping", t.gk_rating],
                  ["Expected goals", t.expected_goals],
                ].map(([k, v]) => (
                  <div key={k as string} className="flex justify-between">
                    <dt className="text-slate-500">{k}</dt>
                    <dd className="font-bold text-white">{v}</dd>
                  </div>
                ))}
              </dl>
              <div className="mt-3 border-t border-pitch-edge/60 pt-2">
                <div className="text-[10px] uppercase tracking-wider text-slate-500">Key players</div>
                {t.key_players.slice(0, 3).map((kp) => (
                  <div key={kp.player_id} className="mt-1 flex justify-between text-xs">
                    <span className="text-slate-300">{kp.player_name}</span>
                    <span className="text-slate-500">
                      A {kp.attack} · D {kp.defense}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Top scorelines */}
      <div className="card p-4">
        <div className="mb-2 text-xs uppercase tracking-wider text-slate-500">
          Most likely scorelines
        </div>
        <div className="flex flex-wrap gap-2">
          {p.top_scorelines.map((s, i) => (
            <span key={i} className="chip bg-pitch-edge/60 text-slate-200">
              {s.a}–{s.b}
              <span className="ml-1.5 text-slate-500">{(s.prob * 100).toFixed(1)}%</span>
            </span>
          ))}
        </div>
        <p className="mt-3 text-[11px] leading-relaxed text-slate-500">
          Model: {p.model.type}. {p.model.assumptions}
        </p>
      </div>
    </div>
  );
}
