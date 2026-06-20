"use client";
import { useState } from "react";
import { MatchTimeline as MatchTimelineData } from "@/lib/api";

const ICONS: Record<string, string> = {
  goal: "⚽",
  "goal---header": "⚽",
  "own-goal": "⚽",
  substitution: "↕",
};
const CARD_TYPES = new Set(["yellow-card", "red-card"]);

const SVG_W = 1000;
const SVG_H = 100;
const BASELINE = SVG_H / 2;
const LANE_GAP = 17; // px between staggered markers that land too close together

// Compresses real magnitude differences (sign/order preserved) so a goal
// spike doesn't visually flatten smaller real shot/corner fluctuations.
function compress(v: number) {
  return Math.sign(v) * Math.sqrt(Math.abs(v));
}

type Laned = MatchTimelineData["events"][number] & { lane: number };

// Greedily packs same-side events into lanes so two markers landing on (or
// very near) the same minute don't sit exactly on top of each other and
// become unhoverable.
function assignLanes(events: MatchTimelineData["events"], duration: number): Laned[] {
  const threshold = Math.max(1.5, duration * 0.02);
  const laneLast: number[] = [];
  return events
    .slice()
    .sort((a, b) => a.minute - b.minute)
    .map((e) => {
      let lane = laneLast.findIndex((last) => e.minute - last >= threshold);
      if (lane === -1) {
        if (laneLast.length < 3) {
          lane = laneLast.length;
          laneLast.push(e.minute);
        } else {
          lane = laneLast.indexOf(Math.min(...laneLast));
          laneLast[lane] = e.minute;
        }
      } else {
        laneLast[lane] = e.minute;
      }
      return { ...e, lane };
    });
}

type Tip = { text: string; left: string; top: number } | null;

function Marker({
  e,
  duration,
  top,
  onShow,
  onHide,
}: {
  e: Laned;
  duration: number;
  top: number;
  onShow: (tip: Tip) => void;
  onHide: () => void;
}) {
  const left = `${(e.minute / duration) * 100}%`;
  const tip = `${e.display} ${e.team ? `${e.team}: ` : ""}${e.label}`;
  const body = CARD_TYPES.has(e.type) ? (
    <span
      className={`block h-3 w-2.5 rounded-[1px] ${
        e.type === "yellow-card" ? "bg-amber-500" : "bg-rose-600"
      }`}
    />
  ) : (
    <span className="text-sm leading-none">{ICONS[e.type] ?? "•"}</span>
  );
  return (
    <span
      aria-label={tip}
      className="absolute -translate-x-1/2 flex h-5 w-5 cursor-help items-center justify-center"
      style={{ left, top }}
      onMouseEnter={() => onShow({ text: tip, left, top })}
      onMouseLeave={onHide}
      onFocus={() => onShow({ text: tip, left, top })}
      onBlur={onHide}
      tabIndex={0}
    >
      {body}
    </span>
  );
}

export function MatchTimelineChart({
  timeline,
  aName,
}: {
  timeline: MatchTimelineData;
  aName: string;
}) {
  const [tip, setTip] = useState<Tip>(null);
  const duration = Math.max(timeline.duration, 90);
  const aIsHome = timeline.home_team === aName;
  // keep the emerald (left/team A) vs amber (right/team B) pairing used in the overview charts
  const homeColor = aIsHome ? "#10b981" : "#f59e0b";
  const awayColor = aIsHome ? "#f59e0b" : "#10b981";

  const compressed = timeline.momentum.map((p) => compress(p.value));
  const maxAbs = Math.max(1, ...compressed.map(Math.abs));
  const points = timeline.momentum.map((p, i) => {
    const x = (p.minute / duration) * SVG_W;
    const y = BASELINE - (compressed[i] / maxAbs) * (BASELINE - 4);
    return [x, y] as const;
  });
  const areaPath =
    points.length > 1
      ? `M ${points[0][0]} ${BASELINE} ` +
        points.map(([x, y]) => `L ${x} ${y}`).join(" ") +
        ` L ${points[points.length - 1][0]} ${BASELINE} Z`
      : "";

  const boundaryEvents = timeline.events.filter((e) =>
    ["kickoff", "halftime", "end-regular-time"].includes(e.type)
  );
  const markerEvents = timeline.events.filter(
    (e) => !["kickoff", "halftime", "end-regular-time"].includes(e.type)
  );
  // home team's events sit above the chart (in its colored half), away team's below
  const topMarkers = assignLanes(markerEvents.filter((e) => e.team !== timeline.away_team), duration);
  const bottomMarkers = assignLanes(markerEvents.filter((e) => e.team === timeline.away_team), duration);
  const topLanes = Math.max(1, ...topMarkers.map((e) => e.lane + 1));
  const bottomLanes = Math.max(1, ...bottomMarkers.map((e) => e.lane + 1));

  return (
    <div className="card p-4">
      <div className="mb-1 flex flex-wrap items-center justify-between gap-1 text-xs text-faint">
        <span>Match timeline &amp; momentum</span>
        <span title="Goals/cards/subs are ESPN's own event log. The wave is our estimate of attacking momentum, derived from real shot/corner/offside events per minute — not ESPN's proprietary metric.">
          ⓘ estimated momentum
        </span>
      </div>

      <div className="relative w-full">
        {tip && (
          <div
            className="absolute z-20 -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-md bg-pitch-card px-2 py-1 text-[11px] font-medium text-fg shadow-lg ring-1 ring-pitch-edge"
            style={{ left: tip.left, top: tip.top - 4 }}
          >
            {tip.text}
          </div>
        )}

        {/* home-team markers, above the chart */}
        <div className="relative" style={{ height: topLanes * LANE_GAP + 20 }}>
          {topMarkers.map((e, i) => (
            <Marker
              key={i}
              e={e}
              duration={duration}
              top={(topLanes - 1 - e.lane) * LANE_GAP}
              onShow={setTip}
              onHide={() => setTip(null)}
            />
          ))}
        </div>

        {/* momentum area chart */}
        <div className="relative h-20">
          <svg viewBox={`0 0 ${SVG_W} ${SVG_H}`} preserveAspectRatio="none" className="h-full w-full">
            <clipPath id="momentum-top"><rect x="0" y="0" width={SVG_W} height={BASELINE} /></clipPath>
            <clipPath id="momentum-bottom"><rect x="0" y={BASELINE} width={SVG_W} height={BASELINE} /></clipPath>
            {areaPath && (
              <>
                <path d={areaPath} fill={homeColor} fillOpacity={0.55} clipPath="url(#momentum-top)" />
                <path d={areaPath} fill={awayColor} fillOpacity={0.55} clipPath="url(#momentum-bottom)" />
              </>
            )}
            <line x1={0} y1={BASELINE} x2={SVG_W} y2={BASELINE} stroke="#10b981" strokeOpacity={0.45} strokeWidth={1.5} />
          </svg>
        </div>

        {/* away-team markers, below the chart */}
        <div className="relative" style={{ height: bottomLanes * LANE_GAP + 20 }}>
          {bottomMarkers.map((e, i) => (
            <Marker
              key={i}
              e={e}
              duration={duration}
              top={e.lane * LANE_GAP}
              onShow={setTip}
              onHide={() => setTip(null)}
            />
          ))}
        </div>

        {/* KO / HT / FT markers */}
        <div className="relative h-5 text-[10px] text-faint">
          {boundaryEvents.map((e, i) => (
            <span
              key={i}
              className="absolute -translate-x-1/2 whitespace-nowrap"
              style={{ left: `${(e.minute / duration) * 100}%` }}
            >
              {e.display}
            </span>
          ))}
        </div>
      </div>

      <p className="mt-2 text-center text-[11px] text-faint">
        ⚽ goal · card · ↕ substitution — hover a marker for details
      </p>
    </div>
  );
}
