"use client";

import { useEffect, useState } from "react";
import { api, BacktestSummary } from "@/lib/api";

function pct(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return `${(n * 100).toFixed(0)}%`;
}

function num(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toFixed(3);
}

export function TrackRecordPanel() {
  const [summary, setSummary] = useState<BacktestSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .backtest()
      .then((data) => {
        if (!cancelled) setSummary(data);
      })
      .catch(() => {
        if (!cancelled) setError("No backtest summary yet — run make etl-train.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <div className="rounded-xl border border-pitch-edge/60 bg-pitch-edge/20 px-4 py-3 text-xs text-faint">
        Track record: {error}
      </div>
    );
  }

  if (!summary?.models || Object.keys(summary.models).length === 0) {
    return null;
  }

  const rows = Object.entries(summary.models);

  return (
    <div
      className="rounded-xl border border-pitch-edge/60 bg-pitch-edge/20 p-4"
      data-testid="track-record-panel"
    >
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <div className="text-xs uppercase tracking-wider text-faint">
          Model track record (hold-out)
        </div>
        <div className="text-[11px] text-faint">
          n={summary.holdout_n ?? "—"}
          {summary.generated_at
            ? ` · updated ${new Date(summary.generated_at).toLocaleDateString()}`
            : ""}
        </div>
      </div>
      <div className="overflow-x-auto text-sm">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-pitch-edge/60 text-faint">
              <th className="pb-2 pr-4 font-medium">Model</th>
              <th className="pb-2 pr-4 font-medium">Accuracy</th>
              <th className="pb-2 pr-4 font-medium">Log-loss</th>
              <th className="pb-2 font-medium">Brier</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([name, m]) => (
              <tr key={name} className="border-b border-pitch-edge/30">
                <td className="py-2 pr-4 capitalize text-fg-soft">
                  {name.replace(/_/g, " ")}
                </td>
                <td className="py-2 pr-4 font-semibold text-fg">{pct(m.accuracy)}</td>
                <td className="py-2 pr-4 text-fg-soft">{num(m.log_loss)}</td>
                <td className="py-2 text-fg-soft">{num(m.brier)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
