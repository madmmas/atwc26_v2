"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { api, BracketData, GroupStandings, MatchListItem } from "@/lib/api";
import { Flag } from "@/components/Flag";
import { SectionTitle, Skeleton } from "@/components/ui";
import {
  FixtureRow,
  buildFixtures,
  formatKickoff,
  isWithin24h,
} from "@/lib/fixtures";

function StatusBadge({ row }: { row: FixtureRow }) {
  if (row.status === "FT") {
    return (
      <span className="rounded px-1.5 py-0.5 text-[10px] font-bold bg-[#1a3a2a] text-[#4caf85]">
        FT
      </span>
    );
  }
  if (row.status === "LIVE") {
    return (
      <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-bold bg-[#3a1a1a] text-[#e05555]">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#e05555]" />
        LIVE
      </span>
    );
  }
  return (
    <span className="rounded px-1.5 py-0.5 text-[10px] font-bold bg-[#1a2a3a] text-[#5599dd]">
      {row.kickoff_utc ? formatKickoff(row.kickoff_utc) : "Soon"}
    </span>
  );
}

function MatchRow({ row }: { row: FixtureRow }) {
  const href = row.completed ? `/matches?game=${row.game_id}` : `/matches`;
  return (
    <Link
      href={href}
      className="flex items-center gap-3 border-b border-pitch-edge/40 px-4 py-3 transition-colors last:border-0 hover:bg-pitch-edge/20"
    >
      <div className="flex min-w-0 flex-1 items-center gap-2">
        <Flag src={row.home_flag} name={row.home_team} size={18} />
        <span className="truncate text-sm font-semibold text-fg">{row.home_team}</span>
      </div>
      <div className="shrink-0 text-sm font-black text-fg">
        {row.completed ? `${row.home_score}–${row.away_score}` : "vs"}
      </div>
      <div className="flex min-w-0 flex-1 items-center justify-end gap-2">
        <span className="truncate text-sm font-semibold text-fg">{row.away_team}</span>
        <Flag src={row.away_flag} name={row.away_team} size={18} />
      </div>
      <StatusBadge row={row} />
      {row.group && <span className="hidden text-[10px] text-faint sm:inline">{row.group}</span>}
    </Link>
  );
}

export function LatestMatchesWidget() {
  const [matches, setMatches] = useState<MatchListItem[] | null>(null);
  const [bracket, setBracket] = useState<BracketData | null>(null);
  const [groups, setGroups] = useState<Record<string, GroupStandings> | null>(null);

  useEffect(() => {
    Promise.all([api.matches(), api.bracket(), api.standings()]).then(([m, b, s]) => {
      setMatches(m.matches);
      setBracket(b);
      setGroups(s.groups);
    });
  }, []);

  const rows = useMemo(() => {
    if (!matches) return [];
    const all = buildFixtures(matches, bracket, groups);
    const completed = all.filter((r) => r.completed).slice(0, 3);
    const soon = all
      .filter((r) => !r.completed && r.kickoff_utc && isWithin24h(r.kickoff_utc))
      .slice(0, 1);
    return [...completed, ...soon];
  }, [matches, bracket, groups]);

  if (!matches) {
    return (
      <section>
        <SectionTitle title="Latest matches" hint="Loading…" />
        <div className="card space-y-2 p-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-10" />
          ))}
        </div>
      </section>
    );
  }

  return (
    <section>
      <SectionTitle title="Latest matches" />
      <div className="card overflow-hidden p-0">
        {rows.length === 0 ? (
          <p className="p-4 text-sm text-faint">No recent matches yet.</p>
        ) : (
          rows.map((r) => <MatchRow key={r.game_id} row={r} />)
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
