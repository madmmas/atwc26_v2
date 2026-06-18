"use client";
import { useEffect, useState } from "react";
import { api, MatchDetail, MatchListItem } from "@/lib/api";
import { Flag } from "@/components/Flag";
import { SectionTitle, Spinner } from "@/components/ui";

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
        <span className={bBetter ? "font-extrabold text-indigo-600 dark:text-indigo-400" : "font-semibold text-fg"}>{b}</span>
      </div>
      <div className="flex h-2.5 overflow-hidden rounded-full bg-pitch-edge">
        {/* emerald vs indigo — clearly distinguishable in both themes */}
        <div className="bg-emerald-500" style={{ width: `${aw}%` }} />
        <div className="bg-indigo-500" style={{ width: `${100 - aw}%` }} />
      </div>
    </div>
  );
}

export default function Matches() {
  const [list, setList] = useState<MatchListItem[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<MatchDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.matches().then((r) => {
      setList(r.matches);
      setLoading(false);
      if (r.matches.length) setSelected(r.matches[0].game_id);
    });
  }, []);

  useEffect(() => {
    if (!selected) return;
    setDetail(null);
    api.matchDetail(selected).then(setDetail);
  }, [selected]);

  if (loading) return <Spinner label="Loading matches…" />;

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
        {list.map((m) => (
          <MatchCard
            key={m.game_id}
            m={m}
            active={selected === m.game_id}
            onClick={() => setSelected(m.game_id)}
          />
        ))}
      </div>

      {/* Comparison */}
      {!detail ? (
        <Spinner />
      ) : (
        <div data-testid="match-detail" className="space-y-5">
          {/* Scoreline header */}
          <div className="card flex items-center justify-center gap-6 p-6">
            <div className="flex flex-1 items-center justify-end gap-3">
              <span className="h-3 w-3 rounded-full bg-emerald-500" title="left bars" />
              <span className="text-right text-lg font-bold text-fg">{detail.team_a.team_name}</span>
              <Flag src={detail.team_a.flag_url} name={detail.team_a.team_name} size={34} />
            </div>
            <div className="text-4xl font-black stat-grad">
              {detail.team_a.score}–{detail.team_b.score}
            </div>
            <div className="flex flex-1 items-center gap-3">
              <Flag src={detail.team_b.flag_url} name={detail.team_b.team_name} size={34} />
              <span className="text-lg font-bold text-fg">{detail.team_b.team_name}</span>
              <span className="h-3 w-3 rounded-full bg-indigo-500" title="right bars" />
            </div>
          </div>
          <div className="text-center text-xs text-faint">{fmtDate(detail.meta?.date)}</div>

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
