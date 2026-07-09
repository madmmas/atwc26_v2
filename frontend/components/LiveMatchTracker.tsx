"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, BracketData, GroupStandings, MatchListItem } from "@/lib/api";
import { Flag } from "@/components/Flag";
import { SectionTitle, Skeleton } from "@/components/ui";
import {
  FixtureRow,
  buildFixtures,
  formatElapsedMinute,
  formatMatchScore,
  liveFixtures,
} from "@/lib/fixtures";

const POLL_MS = 45_000;
const CLOCK_TICK_MS = 30_000;

function LiveMatchRow({ row, now }: { row: FixtureRow; now: Date }) {
  const elapsed = row.kickoff_utc ? formatElapsedMinute(row.kickoff_utc, now) : null;

  return (
    <div className="border-b border-pitch-edge/40 px-4 py-3 last:border-0">
      <div className="flex items-center gap-3">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <Flag src={row.home_flag} name={row.home_team} size={18} />
          <span className="truncate text-sm font-semibold text-fg">{row.home_team}</span>
        </div>
        <div className="shrink-0 text-sm font-black text-fg">{formatMatchScore(row)}</div>
        <div className="flex min-w-0 flex-1 items-center justify-end gap-2">
          <span className="truncate text-sm font-semibold text-fg">{row.away_team}</span>
          <Flag src={row.away_flag} name={row.away_team} size={18} />
        </div>
        <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-bold bg-[#3a1a1a] text-[#e05555]">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#e05555]" />
          LIVE{elapsed ? ` · ${elapsed}` : ""}
        </span>
      </div>
      <p className="mt-1.5 pl-7 text-[11px] text-faint">
        Score updates after full time when match data is processed.
      </p>
    </div>
  );
}

export function LiveMatchTracker() {
  const [matches, setMatches] = useState<MatchListItem[] | null>(null);
  const [bracket, setBracket] = useState<BracketData | null>(null);
  const [groups, setGroups] = useState<Record<string, GroupStandings> | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [now, setNow] = useState(() => new Date());

  const fetchFixtures = useCallback(async () => {
    const [m, b, s] = await Promise.all([api.matches(), api.bracket(), api.standings()]);
    setMatches(m.matches);
    setBracket(b);
    setGroups(s.groups);
    setLoaded(true);
    setNow(new Date());
  }, []);

  useEffect(() => {
    fetchFixtures().catch(() => setLoaded(true));
    const id = setInterval(() => {
      fetchFixtures().catch(() => {});
    }, POLL_MS);
    return () => clearInterval(id);
  }, [fetchFixtures]);

  const liveRows = useMemo(() => {
    if (!matches) return [];
    return liveFixtures(buildFixtures(matches, bracket, groups), now);
  }, [matches, bracket, groups, now]);

  useEffect(() => {
    if (liveRows.length === 0) return;
    const id = setInterval(() => setNow(new Date()), CLOCK_TICK_MS);
    return () => clearInterval(id);
  }, [liveRows.length]);

  if (!loaded) {
    return (
      <section data-testid="live-match-tracker-loading">
        <SectionTitle title="Live now" hint="Loading…" />
        <div className="card space-y-2 p-4">
          <Skeleton className="h-12" />
        </div>
      </section>
    );
  }

  if (!matches || liveRows.length === 0) return null;

  return (
    <section data-testid="live-match-tracker">
      <SectionTitle title="Live now" hint={`${liveRows.length} in progress`} />
      <div className="card overflow-hidden border-[#3a1a1a]/40 p-0">
        {liveRows.map((row) => (
          <LiveMatchRow key={row.game_id} row={row} now={now} />
        ))}
        <div className="border-t border-pitch-edge/40 px-4 py-2 text-right">
          <Link href="/matches" className="text-xs font-semibold text-faint hover:text-pitch-accent">
            View all matches →
          </Link>
        </div>
      </div>
    </section>
  );
}
