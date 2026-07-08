"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api, BracketData, GroupStandings, MatchDetail } from "@/lib/api";
import { buildSimplePredictUrl } from "@/lib/predictUrl";
import { Flag } from "@/components/Flag";
import { Skeleton } from "@/components/ui";
import { MatchTimelineChart } from "@/components/MatchTimeline";
import {
  FixtureRow,
  buildFixtures,
  formatMatchScore,
  hasShootout,
  resolveWinner,
} from "@/lib/fixtures";
import {
  GROUP_LETTERS,
  STAGE_TABS,
  StageKey,
  buildGameStageMap,
  buildTeamGroupMap,
  filterMatches,
  stageCounts,
} from "@/lib/matchStages";

function fmtDate(d?: string) {
  if (!d) return "";
  try {
    return new Date(d).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    });
  } catch {
    return d;
  }
}

function FilterPill({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`shrink-0 rounded-lg px-3 py-1.5 text-xs font-bold transition-colors ${
        active ? "bg-white text-[#111]" : "bg-pitch-edge/60 text-fg-soft hover:text-fg"
      }`}
    >
      {children}
    </button>
  );
}

function MatchCard({
  row,
  active,
  onClick,
}: {
  row: FixtureRow;
  active: boolean;
  onClick: () => void;
}) {
  const winner = row.completed ? resolveWinner(row) : null;
  const pens = row.completed && hasShootout(row);
  return (
    <div
      className={`card flex min-w-[240px] items-center gap-2 px-3 py-2.5 transition-colors ${
        active ? "border-pitch-accent" : "hover:bg-pitch-edge/30"
      }`}
    >
      <button onClick={onClick} data-testid="match-card" className="flex min-w-0 flex-1 items-center gap-2 text-left">
        <Flag src={row.home_flag} name={row.home_team} size={18} />
        <span
          className={`flex-1 truncate text-xs font-semibold ${
            winner === "home" ? "text-emerald-400" : winner === "away" ? "text-faint" : "text-fg"
          }`}
        >
          {row.home_team}
        </span>
        <span
          className="rounded bg-pitch-edge px-1.5 py-0.5 text-xs font-black text-fg"
          title={pens ? "Decided on penalties" : undefined}
        >
          {formatMatchScore(row)}
        </span>
        <span
          className={`flex-1 truncate text-right text-xs font-semibold ${
            winner === "away" ? "text-emerald-400" : winner === "home" ? "text-faint" : "text-fg"
          }`}
        >
          {row.away_team}
        </span>
        <Flag src={row.away_flag} name={row.away_team} size={18} />
      </button>
      {row.completed ? (
        <button
          type="button"
          onClick={onClick}
          className="shrink-0 text-[12px] text-[#888] hover:text-pitch-accent"
        >
          Match stats →
        </button>
      ) : (
        <Link
          href={buildSimplePredictUrl(row.home_team, row.away_team)}
          className="shrink-0 rounded border border-[#2a2a2a] px-2 py-1 text-[12px] text-[#888] hover:text-pitch-accent"
        >
          Predict →
        </Link>
      )}
    </div>
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
        <span className={aBetter ? "font-extrabold text-emerald-600 dark:text-emerald-400" : "font-semibold text-fg"}>
          {a}
        </span>
        <span className="text-xs uppercase tracking-wide text-muted">{label}</span>
        <span className={bBetter ? "font-extrabold text-amber-600 dark:text-amber-400" : "font-semibold text-fg"}>
          {b}
        </span>
      </div>
      <div className="flex h-2.5 overflow-hidden rounded-full bg-pitch-edge">
        <div className="bg-emerald-500" style={{ width: `${aw}%` }} />
        <div className="bg-amber-500" style={{ width: `${100 - aw}%` }} />
      </div>
    </div>
  );
}

function MatchesContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedGame = searchParams.get("game");
  const stageParam = (searchParams.get("stage") as StageKey | null) ?? "all";
  const groupParam = searchParams.get("group");

  const [list, setList] = useState<FixtureRow[]>([]);
  const [groups, setGroups] = useState<Record<string, GroupStandings> | null>(null);
  const [bracket, setBracket] = useState<BracketData | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<MatchDetail | null>(null);
  const [loading, setLoading] = useState(true);

  const stage: StageKey = STAGE_TABS.some((t) => t.key === stageParam) ? stageParam : "all";
  const groupFilter = groupParam && GROUP_LETTERS.includes(groupParam) ? groupParam : "all";

  useEffect(() => {
    Promise.all([api.matches(), api.standings(), api.bracket()]).then(([m, s, b]) => {
      const fixtures = buildFixtures(m.matches, b, s.groups);
      setList(fixtures);
      setGroups(s.groups);
      setBracket(b);
      setLoading(false);
      const played = fixtures.filter((x) => x.completed);
      if (!played.length) return;
      const deepLinked = requestedGame && played.some((x) => x.game_id === requestedGame);
      setSelected(deepLinked ? requestedGame : played[0].game_id);
    });
  }, [requestedGame]);

  const teamGroups = useMemo(() => (groups ? buildTeamGroupMap(groups) : new Map()), [groups]);
  const gameStages = useMemo(() => (bracket ? buildGameStageMap(bracket) : new Map()), [bracket]);

  const playedList = useMemo(() => list.filter((m) => m.completed), [list]);

  const filtered = useMemo(
    () => filterMatches(playedList, stage, groupFilter, teamGroups, gameStages),
    [playedList, stage, groupFilter, teamGroups, gameStages]
  );

  const displayList: FixtureRow[] = useMemo(() => {
    if (stage === "all") {
      const upcoming = list.filter((m) => !m.completed);
      return [...filtered.map((m) => list.find((x) => x.game_id === m.game_id)!), ...upcoming];
    }
    return filtered.map((m) => list.find((x) => x.game_id === m.game_id)!).filter(Boolean);
  }, [list, filtered, stage]);

  const counts = useMemo(
    () => stageCounts(playedList, teamGroups, gameStages),
    [playedList, teamGroups, gameStages]
  );

  useEffect(() => {
    if (!filtered.length) {
      setSelected(null);
      return;
    }
    if (!selected || !filtered.some((m) => m.game_id === selected)) {
      setSelected(filtered[0].game_id);
    }
  }, [filtered, selected]);

  useEffect(() => {
    if (!selected) return;
    const row = list.find((m) => m.game_id === selected);
    if (!row?.completed) {
      setDetail(null);
      return;
    }
    setDetail(null);
    api.matchDetail(selected).then(setDetail);
  }, [selected, list]);

  function setStageFilter(nextStage: StageKey, nextGroup?: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (nextStage === "all") {
      params.delete("stage");
      params.delete("group");
    } else {
      params.set("stage", nextStage);
      if (nextStage === "group" && nextGroup && nextGroup !== "all") {
        params.set("group", nextGroup);
      } else {
        params.delete("group");
      }
    }
    const q = params.toString();
    router.replace(q ? `/matches?${q}` : "/matches", { scroll: false });
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black text-fg">Match Analysis</h1>
        <p className="text-sm text-muted">
          Pick a played match to compare both teams across the key indicators.
        </p>
      </div>

      <div className="space-y-2">
        <div className="flex gap-2 overflow-x-auto pb-1">
          {STAGE_TABS.map((tab) => (
            <FilterPill
              key={tab.key}
              active={stage === tab.key}
              onClick={() => setStageFilter(tab.key)}
            >
              {tab.label}
              {tab.key !== "all" && counts[tab.key] > 0 && ` (${counts[tab.key]})`}
              {tab.key === "all" && ` (${counts.all})`}
            </FilterPill>
          ))}
        </div>

        {stage === "group" && (
          <div className="flex gap-2 overflow-x-auto pb-1">
            <FilterPill active={groupFilter === "all"} onClick={() => setStageFilter("group", "all")}>
              All Groups
            </FilterPill>
            {GROUP_LETTERS.map((g) => (
              <FilterPill key={g} active={groupFilter === g} onClick={() => setStageFilter("group", g)}>
                {g}
              </FilterPill>
            ))}
          </div>
        )}
      </div>

      <div className="flex gap-3 overflow-x-auto pb-2">
        {loading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-12 min-w-[220px] shrink-0 rounded-2xl" />
          ))
        ) : displayList.length === 0 ? (
          <p className="py-4 text-sm text-faint">No matches in this filter.</p>
        ) : (
          displayList.map((m) => (
            <MatchCard
              key={m.game_id}
              row={m}
              active={selected === m.game_id}
              onClick={() => m.completed && setSelected(m.game_id)}
            />
          ))
        )}
      </div>

      {!selected || !list.find((m) => m.game_id === selected)?.completed ? (
        <div className="card p-8 text-center text-sm text-muted">
          Select a completed match to compare team stats, or use Predict → on an upcoming fixture.
        </div>
      ) : !detail ? (
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
          <div className="card flex items-center justify-center gap-2 p-4 sm:gap-6 sm:p-6">
            <div className="flex min-w-0 flex-1 items-center justify-end gap-2 sm:gap-3">
              <span className="hidden h-3 w-3 shrink-0 rounded-full bg-emerald-500 sm:block" title="left bars" />
              <span className="min-w-0 truncate text-right text-sm font-bold text-fg sm:text-lg">
                {detail.team_a.team_name}
              </span>
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
              <span className="min-w-0 truncate text-sm font-bold text-fg sm:text-lg">
                {detail.team_b.team_name}
              </span>
              <span className="hidden h-3 w-3 shrink-0 rounded-full bg-amber-500 sm:block" title="right bars" />
            </div>
          </div>
          <div className="text-center text-xs text-faint">{fmtDate(detail.meta?.date)}</div>

          {detail.timeline && (
            <MatchTimelineChart timeline={detail.timeline} aName={detail.team_a.team_name} />
          )}

          <div className="card divide-y divide-pitch-edge/40 px-5 py-3">
            {detail.indicators.map((i) => (
              <CompareRow key={i.key} label={i.label} a={i.a} b={i.b} betterHigh={i.better_high} />
            ))}
          </div>
          <p className="text-center text-[11px] text-faint">
            Totals aggregated from every player&apos;s real match stats. Possession is share of total passes.
          </p>
        </div>
      )}
    </div>
  );
}

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
      <MatchesContent />
    </Suspense>
  );
}
