"use client";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, MatchDetail, MatchListItem } from "@/lib/api";
import { Flag } from "@/components/Flag";
import { Skeleton } from "@/components/ui";
import { MatchTimelineChart } from "@/components/MatchTimeline";

function fmtDate(d?: string) {
  if (!d) return "";
  try {
    return new Date(d).toLocaleDateString(undefined, {
      month: "short", day: "numeric",
    });
  } catch {
    return d;
  }
}

function MatchCard({
  m,
  active,
  onClick,
}: {
  m: MatchListItem;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      data-testid="match-card"
      className={`card flex min-w-[220px] items-center gap-2 px-3 py-2.5 text-left transition-colors ${
        active ? "border-pitch-accent" : "hover:bg-pitch-edge/30"
      }`}
    >
      <Flag src={m.home_flag} name={m.home_team} size={18} />
      <span className="flex-1 truncate text-xs font-semibold text-fg">{m.home_team}</span>
      <span className="rounded bg-pitch-edge px-1.5 py-0.5 text-xs font-black text-fg">
        {m.home_score}-{m.away_score}
        {m.home_shootout_score != null && m.away_shootout_score != null && (
          <span className="ml-1 font-semibold text-faint">
            ({m.home_shootout_score}-{m.away_shootout_score})
          </span>
        )}
      </span>
      <span className="flex-1 truncate text-right text-xs font-semibold text-fg">{m.away_team}</span>
      <Flag src={m.away_flag} name={m.away_team} size={18} />
    </button>
  );
}

function CompareRow({
  label,
  a,
  b,
  betterHigh,
}: {
  label: string;
  a: number;
  b: number;
  betterHigh: boolean;
}) {
  const total = a + b || 1;
  const aw = (a / total) * 100;
  const aBetter = betterHigh ? a > b : a < b;
  const bBetter = betterHigh ? b > a : b < a;
  return (
    <div className="py-2">
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className={aBetter ? "font-extrabold text-emerald-600 dark:text-emerald-400" : "font-semibold text-fg"}>{a}</span>
        <span className="text-xs uppercase tracking-wide text-muted">{label}</span>
        <span className={bBetter ? "font-extrabold text-amber-600 dark:text-amber-400" : "font-semibold text-fg"}>{b}</span>
      </div>
      <div className="flex h-2.5 overflow-hidden rounded-full bg-pitch-edge">
        {/* emerald vs amber — clearly distinguishable in both themes */}
        <div className="bg-emerald-500" style={{ width: `${aw}%` }} />
        <div className="bg-amber-500" style={{ width: `${100 - aw}%` }} />
      </div>
    </div>
  );
}

function Matches() {
  // Optional ?game=<id> deep link (e.g. clicking a finished match in the bracket).
  const requestedGame = useSearchParams().get("game");
  const [list, setList] = useState<MatchListItem[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<MatchDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.matches().then((r) => {
      setList(r.matches);
      setLoading(false);
      if (!r.matches.length) return;
      const deepLinked = requestedGame && r.matches.some((m) => m.game_id === requestedGame);
      setSelected(deepLinked ? requestedGame : r.matches[0].game_id);
    });
  }, [requestedGame]);

  useEffect(() => {
    if (!selected) return;
    setDetail(null);
    api.matchDetail(selected).then(setDetail);
  }, [selected]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black text-fg">Match Analysis</h1>
        <p className="text-sm text-muted">
          Pick a played match to compare both teams across the key indicators.
        </p>
      </div>

      {/* Match picker */}
      <div className="flex gap-3 overflow-x-auto pb-2">
        {loading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-12 min-w-[220px] shrink-0 rounded-2xl" />
          ))
        ) : (
          list.map((m) => (
            <MatchCard
              key={m.game_id}
              m={m}
              active={selected === m.game_id}
              onClick={() => setSelected(m.game_id)}
            />
          ))
        )}
      </div>

      {/* Comparison */}
      {!detail ? (
        <div className="space-y-5">
          <div className="card p-6">
            <Skeleton className="mx-auto h-10 w-48" />
          </div>
          <div className="card p-5">
            <Skeleton className="h-40 w-full rounded-xl" />
          </div>
          <div className="card space-y-3 p-5">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-8" />
            ))}
          </div>
        </div>
      ) : (
        <div data-testid="match-detail" className="space-y-5">
          {/* Scoreline header */}
          <div className="card flex items-center justify-center gap-2 p-4 sm:gap-6 sm:p-6">
            <div className="flex min-w-0 flex-1 items-center justify-end gap-2 sm:gap-3">
              <span className="hidden h-3 w-3 shrink-0 rounded-full bg-emerald-500 sm:block" title="left bars" />
              <span className="min-w-0 truncate text-right text-sm font-bold text-fg sm:text-lg">{detail.team_a.team_name}</span>
              <Flag src={detail.team_a.flag_url} name={detail.team_a.team_name} size={28} />
            </div>
            <div className="shrink-0 whitespace-nowrap text-2xl font-black stat-grad sm:text-4xl">
              {detail.team_a.score}–{detail.team_b.score}
              {detail.team_a.shootout_score != null && detail.team_b.shootout_score != null && (
                <span className="ml-1.5 text-base font-bold text-faint sm:text-xl">
                  ({detail.team_a.shootout_score}–{detail.team_b.shootout_score})
                </span>
              )}
            </div>
            <div className="flex min-w-0 flex-1 items-center gap-2 sm:gap-3">
              <Flag src={detail.team_b.flag_url} name={detail.team_b.team_name} size={28} />
              <span className="min-w-0 truncate text-sm font-bold text-fg sm:text-lg">{detail.team_b.team_name}</span>
              <span className="hidden h-3 w-3 shrink-0 rounded-full bg-amber-500 sm:block" title="right bars" />
            </div>
          </div>
          <div className="text-center text-xs text-faint">{fmtDate(detail.meta?.date)}</div>

          {/* Timeline & momentum */}
          {detail.timeline && (
            <MatchTimelineChart timeline={detail.timeline} aName={detail.team_a.team_name} />
          )}

          {/* Indicators */}
          <div className="card divide-y divide-pitch-edge/40 px-5 py-3">
            {detail.indicators.map((i) => (
              <CompareRow key={i.key} label={i.label} a={i.a} b={i.b} betterHigh={i.better_high} />
            ))}
          </div>
          <p className="text-center text-[11px] text-faint">
            Totals aggregated from every player's real match stats. Possession is share of total passes.
          </p>
        </div>
      )}
    </div>
  );
}

// useSearchParams() requires a Suspense boundary in the Next 14 App Router.
function MatchesSkeleton() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black text-fg">Match Analysis</h1>
        <p className="text-sm text-muted">
          Pick a played match to compare both teams across the key indicators.
        </p>
      </div>
      <div className="flex gap-3 overflow-x-auto pb-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-12 min-w-[220px] shrink-0 rounded-2xl" />
        ))}
      </div>
      <div className="card space-y-3 p-5">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-8" />
        ))}
      </div>
    </div>
  );
}

export default function MatchesPage() {
  return (
    <Suspense fallback={<MatchesSkeleton />}>
      <Matches />
    </Suspense>
  );
}
