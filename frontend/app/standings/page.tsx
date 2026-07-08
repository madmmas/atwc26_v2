"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api, BracketData, GroupStandings, Overview, Team } from "@/lib/api";
import { Skeleton } from "@/components/ui";
import { GroupTable, Predictions, applyHypotheticalResults } from "@/components/GroupTable";
import { Bracket } from "@/components/Bracket";
import { GROUP_LETTERS } from "@/lib/matchStages";

function GroupTab({
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

function StandingsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const groupParam = searchParams.get("group");

  const [groups, setGroups] = useState<Record<string, GroupStandings> | null>(null);
  const [bracket, setBracket] = useState<BracketData | null>(null);
  const [teams, setTeams] = useState<Team[]>([]);
  const [predictions, setPredictions] = useState<Predictions>({});

  const activeGroup =
    groupParam === "all" || !groupParam
      ? "all"
      : GROUP_LETTERS.includes(groupParam)
        ? groupParam
        : "all";

  useEffect(() => {
    api.standings().then((r) => setGroups(r.groups));
    api.bracket().then(setBracket);
    api.overview().then((o: Overview) => setTeams(o.teams));
  }, []);

  const xgByTeam = useMemo(() => {
    const map = new Map<string, number>();
    for (const t of teams) {
      const balance = Math.round((t.xg_per_game - t.xga_per_game) * t.games * 10) / 10;
      map.set(t.team_name, balance);
    }
    return map;
  }, [teams]);

  const rankedGroups = useMemo(() => {
    if (!groups) return {};
    return Object.fromEntries(
      Object.entries(groups).map(([name, g]) => [name, applyHypotheticalResults(g, predictions)])
    );
  }, [groups, predictions]);

  function setScore(gameId: string, side: "home" | "away", v: number | "") {
    setPredictions((prev) => ({
      ...prev,
      [gameId]: { home: prev[gameId]?.home ?? "", away: prev[gameId]?.away ?? "", [side]: v },
    }));
  }

  function resetGroup(gameIds: string[]) {
    setPredictions((prev) => {
      const next = { ...prev };
      for (const gid of gameIds) delete next[gid];
      return next;
    });
  }

  function setGroupFilter(letter: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (letter === "all") params.delete("group");
    else params.set("group", letter);
    const q = params.toString();
    router.replace(q ? `/standings?${q}` : "/standings", { scroll: false });
  }

  const names = groups ? Object.keys(groups).sort() : [];
  const visibleNames =
    activeGroup === "all"
      ? names
      : names.filter((n) => n.replace(/^Group\s+/i, "") === activeGroup);

  return (
    <div className="space-y-6">
      {bracket ? (
        <Bracket bracket={bracket} rankedGroups={rankedGroups} />
      ) : (
        <div className="card p-5">
          <Skeleton className="h-48 w-full rounded-xl" />
        </div>
      )}

      <div>
        <h1 className="text-2xl font-black text-fg">Group Standings</h1>
        <p className="text-sm text-muted">
          Real group tables from every played match. Try a score for the remaining
          fixture(s) below any group to see how the table — and the knockout bracket
          above — would change. Predictions aren&apos;t saved, reload to reset.
        </p>
      </div>

      <div className="flex gap-2 overflow-x-auto pb-1">
        <GroupTab active={activeGroup === "all"} onClick={() => setGroupFilter("all")}>
          All
        </GroupTab>
        {GROUP_LETTERS.map((g) => (
          <GroupTab key={g} active={activeGroup === g} onClick={() => setGroupFilter(g)}>
            {g}
          </GroupTab>
        ))}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {groups ? (
          visibleNames.map((name) => (
            <GroupTable
              key={name}
              name={name}
              group={groups[name]}
              ranked={rankedGroups[name]}
              predictions={predictions}
              xgByTeam={xgByTeam}
              onSetScore={setScore}
              onReset={resetGroup}
            />
          ))
        ) : (
          Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="card space-y-2 p-4">
              <Skeleton className="h-5 w-8" />
              {Array.from({ length: 4 }).map((_, j) => (
                <Skeleton key={j} className="h-7" />
              ))}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default function Standings() {
  return (
    <Suspense fallback={<div className="card p-8 text-faint">Loading standings…</div>}>
      <StandingsContent />
    </Suspense>
  );
}
