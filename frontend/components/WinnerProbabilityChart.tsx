"use client";
import { useEffect, useState } from "react";
import { api, WinnerProbability } from "@/lib/api";
import { TeamLabel } from "@/components/Flag";
import { SectionTitle, Skeleton } from "@/components/ui";

const DEFAULT_SHOWN = 16;

export function WinnerProbabilityChart() {
  const [teams, setTeams] = useState<WinnerProbability[] | null>(null);
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    api.winnerProbabilities().then((r) => setTeams(r.teams));
  }, []);

  if (!teams) {
    return (
      <div className="card p-5">
        <SectionTitle
          title="World Cup Winner Probability"
          hint="Loading simulation…"
        />
        <div className="space-y-2">
          {Array.from({ length: 10 }).map((_, i) => (
            <Skeleton key={i} className="h-4" />
          ))}
        </div>
      </div>
    );
  }

  const top = Math.max(...teams.map((t) => t.probability), 0.001);
  const shown = showAll ? teams : teams.slice(0, DEFAULT_SHOWN);

  return (
    <div className="card p-5">
      <SectionTitle
        title="World Cup Winner Probability"
        hint="Monte Carlo simulation · updates after every finished match"
      />
      <div className="space-y-1.5">
        {shown.map((t) => (
          <div key={t.team_name} className="flex items-center gap-2 text-xs">
            <TeamLabel
              name={t.team_name}
              flag={t.flag_url}
              size={16}
              className={`w-36 shrink-0 truncate ${t.eliminated ? "text-faint" : "text-fg"}`}
            />
            <div className="h-3 flex-1 overflow-hidden rounded-full bg-pitch-edge">
              {!t.eliminated && (
                <div
                  className="h-full rounded-full bg-pitch-accent"
                  style={{ width: `${Math.max((t.probability / top) * 100, 2)}%` }}
                />
              )}
            </div>
            <span
              className={`w-14 shrink-0 text-right font-bold ${
                t.eliminated ? "text-faint" : "text-fg"
              }`}
            >
              {t.eliminated ? "Out" : `${(t.probability * 100).toFixed(1)}%`}
            </span>
          </div>
        ))}
      </div>
      {teams.length > DEFAULT_SHOWN && (
        <button
          onClick={() => setShowAll((v) => !v)}
          className="mt-3 text-[11px] font-semibold text-faint hover:text-fg"
        >
          {showAll ? "Show fewer" : `Show all ${teams.length} teams`}
        </button>
      )}
      <p className="mt-3 text-[11px] leading-relaxed text-faint">
        Estimated from 10,000 simulated tournaments using the same player-form model as the
        predictor below — remaining group matches and the full knockout bracket are simulated,
        and a team is shown as &quot;Out&quot; only once they&apos;re actually eliminated, not
        just unlikely to win. See docs/WINNER_PROBABILITY_MODEL.md for the full methodology.
      </p>
    </div>
  );
}
