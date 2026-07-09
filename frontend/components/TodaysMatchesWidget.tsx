"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, BracketData, GroupStandings, MatchListItem } from "@/lib/api";
import { Flag } from "@/components/Flag";
import { SectionTitle, Skeleton } from "@/components/ui";
import {
  FixturePrediction,
  FixtureRow,
  buildFixtures,
  fixturesForToday,
  formatKickoff,
  formatMatchScore,
  formatTodayHeading,
  hasShootout,
  resolveWinner,
} from "@/lib/fixtures";
import { buildPredictorMatchUrl } from "@/lib/predictUrl";
import { quickPredict } from "@/lib/quickPredict";

function formatProb(n: number): string {
  return `${Math.round(n * 100)}%`;
}

function ProbabilityLine({ prediction, home, away }: { prediction: FixturePrediction; home: string; away: string }) {
  const favored =
    prediction.predicted_winner ??
    (prediction.home_win_prob >= prediction.away_win_prob ? home : away);
  const favoredProb =
    favored === home ? prediction.home_win_prob : prediction.away_win_prob;
  return (
    <div className="text-[11px] text-faint">
      <span className="font-semibold text-pitch-accent">{favored}</span>{" "}
      <span>{formatProb(favoredProb)}</span>
      {prediction.draw_prob != null && prediction.draw_prob > 0.01 && (
        <span className="text-faint"> · Draw {formatProb(prediction.draw_prob)}</span>
      )}
    </div>
  );
}

function StatusBadge({ row }: { row: FixtureRow }) {
  if (row.completed) {
    const pens = hasShootout(row);
    return (
      <span
        className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
          pens ? "bg-[#2a2a1a] text-[#d4a843]" : "bg-[#1a3a2a] text-[#4caf85]"
        }`}
        title={pens ? "Decided on penalties" : undefined}
      >
        {pens ? "PENS" : "FT"}
      </span>
    );
  }
  return (
    <span className="rounded px-1.5 py-0.5 text-[10px] font-bold bg-[#1a2a3a] text-[#5599dd]">
      {row.kickoff_utc ? formatKickoff(row.kickoff_utc) : "Soon"}
    </span>
  );
}

function MatchRow({
  row,
  prediction,
  loadingPrediction,
}: {
  row: FixtureRow;
  prediction?: FixturePrediction;
  loadingPrediction?: boolean;
}) {
  const winner = row.completed ? resolveWinner(row) : null;
  const detailHref = `/matches?game=${row.game_id}`;

  return (
    <div className="border-b border-pitch-edge/40 px-4 py-3 last:border-0">
      <div className="flex items-center gap-3">
        <Link
          href={detailHref}
          className="flex min-w-0 flex-1 items-center gap-2 transition-colors hover:text-pitch-accent"
        >
          <Flag src={row.home_flag} name={row.home_team} size={18} />
          <span
            className={`truncate text-sm font-semibold ${
              winner === "home" ? "text-emerald-400" : winner === "away" ? "text-faint" : "text-fg"
            }`}
          >
            {row.home_team}
          </span>
        </Link>
        <div className="shrink-0 text-sm font-black text-fg">{formatMatchScore(row)}</div>
        <Link
          href={detailHref}
          className="flex min-w-0 flex-1 items-center justify-end gap-2 transition-colors hover:text-pitch-accent"
        >
          <span
            className={`truncate text-sm font-semibold ${
              winner === "away" ? "text-emerald-400" : winner === "home" ? "text-faint" : "text-fg"
            }`}
          >
            {row.away_team}
          </span>
          <Flag src={row.away_flag} name={row.away_team} size={18} />
        </Link>
        <StatusBadge row={row} />
      </div>

      {!row.completed && (
        <div className="mt-2 flex items-center justify-between gap-3 pl-7 pr-1">
          <div className="min-w-0 flex-1">
            {loadingPrediction ? (
              <Skeleton className="h-3 w-28" />
            ) : prediction ? (
              <ProbabilityLine prediction={prediction} home={row.home_team} away={row.away_team} />
            ) : (
              <span className="text-[11px] text-faint">Prediction loading…</span>
            )}
          </div>
          <Link
            href={buildPredictorMatchUrl(row.home_team, row.away_team)}
            className="shrink-0 rounded border border-pitch-edge px-2 py-1 text-[11px] font-semibold text-faint transition-colors hover:border-pitch-accent hover:text-pitch-accent"
          >
            Predict →
          </Link>
        </div>
      )}

      {row.completed && (
        <div className="mt-1.5 text-right">
          <Link href={detailHref} className="text-[11px] font-semibold text-faint hover:text-pitch-accent">
            Match stats →
          </Link>
        </div>
      )}
    </div>
  );
}

export function TodaysMatchesWidget() {
  const [matches, setMatches] = useState<MatchListItem[] | null>(null);
  const [bracket, setBracket] = useState<BracketData | null>(null);
  const [groups, setGroups] = useState<Record<string, GroupStandings> | null>(null);
  const [predictions, setPredictions] = useState<Record<string, FixturePrediction>>({});
  const [loadingPredictions, setLoadingPredictions] = useState<Record<string, boolean>>({});
  const requestedPredictions = useRef(new Set<string>());

  useEffect(() => {
    Promise.all([api.matches(), api.bracket(), api.standings()]).then(([m, b, s]) => {
      setMatches(m.matches);
      setBracket(b);
      setGroups(s.groups);
    });
  }, []);

  const rows = useMemo(() => {
    if (!matches) return [];
    return fixturesForToday(buildFixtures(matches, bracket, groups));
  }, [matches, bracket, groups]);

  useEffect(() => {
    const upcoming = rows.filter((row) => !row.completed && !row.prediction);
    if (!upcoming.length) return;

    let cancelled = false;
    for (const row of upcoming) {
      setLoadingPredictions((prev) => {
        if (prev[row.game_id]) return prev;
        return { ...prev, [row.game_id]: true };
      });
      quickPredict(row.home_team, row.away_team)
        .then((prediction) => {
          if (cancelled) return;
          setPredictions((prev) => ({ ...prev, [row.game_id]: prediction }));
        })
        .catch(() => {
          /* leave row without probability */
        })
        .finally(() => {
          if (cancelled) return;
          setLoadingPredictions((prev) => {
            const next = { ...prev };
            delete next[row.game_id];
            return next;
          });
        });
    }

    return () => {
      cancelled = true;
    };
  }, [rows]);

  if (!matches) {
    return (
      <section>
        <SectionTitle title="Today's matches" hint="Loading…" />
        <div className="card space-y-2 p-4">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-14" />
          ))}
        </div>
      </section>
    );
  }

  const heading = formatTodayHeading();

  return (
    <section>
      <SectionTitle title="Today's matches" hint={heading} />
      <div className="card overflow-hidden p-0">
        {rows.length === 0 ? (
          <p className="p-4 text-sm text-faint">No matches scheduled for today.</p>
        ) : (
          rows.map((row) => (
            <MatchRow
              key={row.game_id}
              row={row}
              prediction={predictions[row.game_id] ?? row.prediction}
              loadingPrediction={!!loadingPredictions[row.game_id]}
            />
          ))
        )}
        <div className="border-t border-pitch-edge/40 px-4 py-2 text-right">
          <Link href="/matches" className="text-xs font-semibold text-faint hover:text-pitch-accent">
            View all matches →
          </Link>
        </div>
      </div>
    </section>
  );
}
