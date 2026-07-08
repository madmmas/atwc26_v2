"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { api, WinnerProbability } from "@/lib/api";
import { Flag } from "@/components/Flag";
import { Skeleton } from "@/components/ui";

function PodiumCard({
  team,
  place,
  leaderProb,
}: {
  team: WinnerProbability;
  place: 1 | 2 | 3;
  leaderProb: number;
}) {
  const pct = (team.probability * 100).toFixed(1);
  const barW = leaderProb > 0 ? (team.probability / leaderProb) * 100 : 0;
  const isLeader = place === 1;

  return (
    <div
      className={`relative flex flex-col items-center rounded-lg border bg-pitch-card/80 p-4 ${
        isLeader ? "min-h-[168px] border-[#c8f135] border-[1.5px] pt-6" : "min-h-[148px] border-pitch-edge"
      }`}
    >
      {isLeader && (
        <span className="absolute -top-3 text-xl" aria-hidden>
          👑
        </span>
      )}
      <Flag src={team.flag_url} name={team.team_name} size={28} />
      <div className="mt-2 text-center text-sm font-bold text-fg">{team.team_name}</div>
      <div
        className={`mt-1 text-xl font-bold ${isLeader ? "text-[#c8f135]" : "text-fg"}`}
        style={{ fontSize: 20, fontWeight: 700 }}
      >
        {pct}%
      </div>
      <div className="text-[10px] text-faint">win probability</div>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-pitch-edge">
        <div
          className={`h-full rounded-full ${isLeader ? "bg-[#c8f135]" : "bg-pitch-accent/60"}`}
          style={{ width: `${Math.max(barW, 4)}%` }}
        />
      </div>
    </div>
  );
}

export function WinnerProbabilityWidget() {
  const [teams, setTeams] = useState<WinnerProbability[] | null>(null);

  useEffect(() => {
    api.winnerProbabilities().then((r) => setTeams(r.teams));
  }, []);

  const active = useMemo(
    () => (teams ?? []).filter((t) => !t.eliminated).sort((a, b) => b.probability - a.probability),
    [teams]
  );

  const podium = active.slice(0, 3);
  const rest = active.slice(3);
  const leaderProb = podium[0]?.probability ?? 1;

  const insight = useMemo(() => {
    if (!teams || teams.length < 2) return null;
    const sorted = [...teams].filter((t) => !t.eliminated).sort((a, b) => b.probability - a.probability);
    const leader = sorted[0];
    const runner = sorted[1];
    if (!leader || !runner) return null;
    return `${leader.team_name}'s probability leads at ${(leader.probability * 100).toFixed(1)}% — ${runner.team_name} next at ${(runner.probability * 100).toFixed(1)}%.`;
  }, [teams]);

  if (!teams) {
    return (
      <section>
        <div className="mb-3 flex items-center gap-2">
          <h2 className="text-lg font-bold text-fg">Tournament winner probability</h2>
          <Skeleton className="h-3 w-24" />
        </div>
        <div className="card p-5">
          <Skeleton className="h-32 w-full" />
        </div>
      </section>
    );
  }

  const podiumOrder: (WinnerProbability | undefined)[] = [podium[1], podium[0], podium[2]];

  return (
    <section>
      <div className="mb-3 flex items-center gap-2">
        <h2 className="text-lg font-bold text-fg">Tournament winner probability</h2>
        <span className="inline-flex items-center gap-1.5 text-xs text-faint">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />
          live model
        </span>
      </div>

      <div className="card space-y-4 p-5">
        <div className="grid grid-cols-3 items-end gap-3">
          {podiumOrder.map((t, i) => {
            const place = (i === 1 ? 1 : i === 0 ? 2 : 3) as 1 | 2 | 3;
            if (!t) return <div key={i} />;
            return <PodiumCard key={t.team_name} team={t} place={place} leaderProb={leaderProb} />;
          })}
        </div>

        {rest.length > 0 && (
          <div>
            <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-faint">
              Rest of field
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-2">
              {rest.map((t) => (
                <div key={t.team_name} className="flex items-center gap-2 text-xs">
                  <Flag src={t.flag_url} name={t.team_name} size={14} />
                  <span className="min-w-0 flex-1 truncate text-fg-soft">{t.team_name}</span>
                  <div className="h-1.5 w-16 overflow-hidden rounded-full bg-pitch-edge">
                    <div
                      className="h-full rounded-full bg-pitch-accent/50"
                      style={{ width: `${Math.max((t.probability / leaderProb) * 100, 2)}%` }}
                    />
                  </div>
                  <span className="w-10 text-right font-bold text-fg">
                    {(t.probability * 100).toFixed(1)}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {insight && (
          <div className="rounded-lg border border-[#2a3800] bg-[#1a2800] px-3 py-2 text-xs text-fg-soft">
            {insight}
          </div>
        )}

        <div className="flex items-center justify-between">
          <p className="text-[10px] text-[#444]">
            Monte Carlo simulation · updates after every match
          </p>
          <Link href="/predict#winner-probability" className="text-xs font-semibold text-faint hover:text-pitch-accent">
            Full breakdown →
          </Link>
        </div>
      </div>
    </section>
  );
}
