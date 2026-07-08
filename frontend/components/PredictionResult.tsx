"use client";
import { useState } from "react";
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
      <div className="mt-1 flex justify-between text-xs text-muted">
        <span>{p.team_a.team_name} win</span>
        <span>Draw</span>
        <span>{p.team_b.team_name} win</span>
      </div>
    </div>
  );
}

function modelLabel(p: Prediction): string {
  return p.model.name || p.model.type || "Model";
}

function modelDescription(p: Prediction): string {
  return p.model.description || p.model.assumptions || "";
}

export function PredictionResult({ p, shareUrl }: { p: Prediction; shareUrl?: string }) {
  const [copied, setCopied] = useState(false);

  async function copyLink() {
    if (!shareUrl) return;
    await navigator.clipboard.writeText(shareUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const dims = p.radar?.dimensions ?? [];
  const radarData = dims.map((d) => ({
    dim: d,
    [p.team_a.team_name]: p.radar?.[p.team_a.team_name]?.[d],
    [p.team_b.team_name]: p.radar?.[p.team_b.team_name]?.[d],
  }));

  const hasRatings =
    p.team_a.attack_rating != null ||
    p.team_a.defense_rating != null ||
    p.team_a.expected_goals != null ||
    p.team_a.elo_rating != null;

  return (
    <div className="space-y-6" data-testid="prediction-result">
      {p.most_likely_score && (
        <div className="card p-6 text-center">
          <div className="text-xs uppercase tracking-widest text-faint">
            Most likely scoreline
          </div>
          <div className="mt-2 flex items-center justify-center gap-6">
            <span className="max-w-[40%] truncate text-right text-lg font-bold text-fg">
              {p.team_a.team_name}
            </span>
            <span className="text-5xl font-black stat-grad">
              {p.most_likely_score.a}–{p.most_likely_score.b}
            </span>
            <span className="max-w-[40%] truncate text-left text-lg font-bold text-fg">
              {p.team_b.team_name}
            </span>
          </div>
          <div className="mt-1 text-xs text-faint">
            {(p.most_likely_score.prob * 100).toFixed(1)}% likely
            {p.team_a.expected_goals != null && p.team_b.expected_goals != null && (
              <> · xG {p.team_a.expected_goals} – {p.team_b.expected_goals}</>
            )}
          </div>
        </div>
      )}

      <div className="card p-5">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div className="text-xs uppercase tracking-widest text-faint">
            Win probability · {modelLabel(p)}
          </div>
          {shareUrl && (
            <button type="button" onClick={copyLink} className="btn-ghost shrink-0 text-xs">
              {copied ? "Copied! ✓" : "Copy link"}
            </button>
          )}
        </div>
        <ProbBar p={p} />
        {p.narrative && (
          <p className="mt-4 text-sm leading-relaxed text-fg-soft">{p.narrative}</p>
        )}
        {modelDescription(p) && !p.narrative && (
          <p className="mt-4 text-sm leading-relaxed text-fg-soft">{modelDescription(p)}</p>
        )}
      </div>

      {(dims.length > 0 || hasRatings) && (
        <div className="grid gap-6 lg:grid-cols-2">
          {dims.length > 0 && (
            <div className="card p-4" style={{ height: 320 }}>
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radarData} outerRadius="72%">
                  <PolarGrid stroke="#94a3b8" strokeOpacity={0.22} />
                  <PolarAngleAxis dataKey="dim" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                  <Radar name={p.team_a.team_name} dataKey={p.team_a.team_name} stroke="#10b981" fill="#10b981" fillOpacity={0.35} />
                  <Radar name={p.team_b.team_name} dataKey={p.team_b.team_name} stroke="#f59e0b" fill="#f59e0b" fillOpacity={0.3} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          )}

          {hasRatings && (
            <div className={`grid grid-cols-2 gap-4 ${dims.length === 0 ? "lg:col-span-2" : ""}`}>
              {[p.team_a, p.team_b].map((t, i) => (
                <div key={t.team_name} className="card p-4">
                  <div className={`text-sm font-bold ${i === 0 ? "text-pitch-accent" : "text-pitch-accent2"}`}>
                    {t.team_name}
                  </div>
                  <dl className="mt-3 space-y-2 text-sm">
                    {t.elo_rating != null && (
                      <div className="flex justify-between">
                        <dt className="text-faint">Elo rating</dt>
                        <dd className="font-bold text-fg">{t.elo_rating}</dd>
                      </div>
                    )}
                    {[
                      ["Attack", t.attack_rating],
                      ["Defense", t.defense_rating],
                      ["Goalkeeping", t.gk_rating],
                      ["Expected goals", t.expected_goals],
                    ]
                      .filter(([, v]) => v != null)
                      .map(([k, v]) => (
                        <div key={k as string} className="flex justify-between">
                          <dt className="text-faint">{k}</dt>
                          <dd className="font-bold text-fg">{v}</dd>
                        </div>
                      ))}
                  </dl>
                  {t.key_players && t.key_players.length > 0 && (
                    <div className="mt-3 border-t border-pitch-edge/60 pt-2">
                      <div className="text-[10px] uppercase tracking-wider text-faint">Key players</div>
                      {t.key_players.slice(0, 3).map((kp) => (
                        <div key={kp.player_id} className="mt-1 flex justify-between text-xs">
                          <span className="text-fg-soft">{kp.player_name}</span>
                          <span className="text-faint">
                            A {kp.attack} · D {kp.defense}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {p.top_scorelines && p.top_scorelines.length > 0 && (
        <div className="card p-4">
          <div className="mb-2 text-xs uppercase tracking-wider text-faint">
            Most likely scorelines
          </div>
          <div className="flex flex-wrap gap-2">
            {p.top_scorelines.map((s, i) => (
              <span key={i} className="chip bg-pitch-edge/60 text-fg">
                {s.a}–{s.b}
                <span className="ml-1.5 text-faint">{(s.prob * 100).toFixed(1)}%</span>
              </span>
            ))}
          </div>
          <p className="mt-3 text-[11px] leading-relaxed text-faint">
            Model: {modelLabel(p)}
            {modelDescription(p) ? `. ${modelDescription(p)}` : ""}
          </p>
        </div>
      )}

      {p.comparison && Object.keys(p.comparison).length > 1 && (
        <div className="card p-4">
          <div className="mb-3 text-xs uppercase tracking-wider text-faint">
            Model comparison
          </div>
          <div className="overflow-x-auto text-sm">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-pitch-edge/60 text-faint">
                  <th className="pb-2 pr-4 font-medium">Model</th>
                  <th className="pb-2 pr-4 font-medium">P(home win)</th>
                  <th className="pb-2 pr-4 font-medium">P(draw)</th>
                  <th className="pb-2 font-medium">P(away win)</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(p.comparison).map(([key, row]) => (
                  <tr key={key} className="border-b border-pitch-edge/30">
                    <td className="py-2 pr-4 capitalize text-fg-soft">
                      {row.model_name || key.replace(/_/g, " ")}
                    </td>
                    <td className="py-2 pr-4">{(row.win_probability_a * 100).toFixed(0)}%</td>
                    <td className="py-2 pr-4">{(row.draw_probability * 100).toFixed(0)}%</td>
                    <td className="py-2">{(row.win_probability_b * 100).toFixed(0)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
