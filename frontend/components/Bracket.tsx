"use client";
import { useLayoutEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { toPng } from "html-to-image";
import { BracketData, BracketMatch, BracketSlot, GroupTeam } from "@/lib/api";
import { Flag } from "@/components/Flag";

// ─────────────────────────────────────────────────────────────────────────── //
// Fixed WC2026 knockout geometry.
//
// We deliberately DON'T trace the bracket from ESPN's slot references: as each
// Round-of-32 match finishes, ESPN rewrites the Round-of-16 slot from a
// "Round of 32 #N winner" placeholder into a concrete team, which erases the
// feeder link. Tracing then collapses the tree wherever games have been played.
// The bracket structure is fixed for the whole tournament, so we pin it here and
// look each match up by (round, position) regardless of resolution state.
//
// Positions verified against the pre-resolution bracket:
//   R16#1←R32 1,3   R16#2←R32 2,5   R16#3←R32 4,6   R16#4←R32 7,8
//   R16#5←R32 11,12 R16#6←R32 9,10  R16#7←R32 14,16 R16#8←R32 13,15
//   QF#1←R16 1,2  QF#2←R16 5,6  QF#3←R16 3,4  QF#4←R16 7,8
//   SF#1←QF 1,2   SF#2←QF 3,4   Final←SF 1,2
// ─────────────────────────────────────────────────────────────────────────── //
type Col = { round: string; pos: number[] };

const LEFT_COLS: Col[] = [
  { round: "Round of 32", pos: [1, 3, 2, 5, 11, 12, 9, 10] },
  { round: "Round of 16", pos: [1, 2, 5, 6] },
  { round: "Quarterfinals", pos: [1, 2] },
  { round: "Semifinals", pos: [1] },
];
const RIGHT_COLS: Col[] = [
  { round: "Round of 32", pos: [4, 6, 7, 8, 14, 16, 13, 15] },
  { round: "Round of 16", pos: [3, 4, 7, 8] },
  { round: "Quarterfinals", pos: [3, 4] },
  { round: "Semifinals", pos: [2] },
];

const ROUND_ABBR: Record<string, string> = {
  "Round of 32": "R32", "Round of 16": "R16",
  Quarterfinals: "QF", Semifinals: "SF", Final: "F",
};

// FIFA 3-letter codes for the 48 finalists (fallback: first 3 letters).
const CODE: Record<string, string> = {
  Algeria: "ALG", Argentina: "ARG", Australia: "AUS", Austria: "AUT",
  Belgium: "BEL", "Bosnia-Herzegovina": "BIH", Brazil: "BRA", Canada: "CAN",
  "Cape Verde": "CPV", Colombia: "COL", "Congo DR": "COD", Croatia: "CRO",
  "Curaçao": "CUW", Czechia: "CZE", Ecuador: "ECU", Egypt: "EGY",
  England: "ENG", France: "FRA", Germany: "GER", Ghana: "GHA", Haiti: "HAI",
  Iran: "IRN", Iraq: "IRQ", "Ivory Coast": "CIV", Japan: "JPN", Jordan: "JOR",
  Mexico: "MEX", Morocco: "MAR", Netherlands: "NED", "New Zealand": "NZL",
  Norway: "NOR", Panama: "PAN", Paraguay: "PAR", Portugal: "POR", Qatar: "QAT",
  "Saudi Arabia": "KSA", Scotland: "SCO", Senegal: "SEN", "South Africa": "RSA",
  "South Korea": "KOR", Spain: "ESP", Sweden: "SWE", Switzerland: "SUI",
  Tunisia: "TUN", "Türkiye": "TUR", "United States": "USA", Uruguay: "URU",
  Uzbekistan: "UZB",
};
const abbr = (name?: string | null) =>
  !name ? "" : CODE[name] ?? name.replace(/[^A-Za-zÀ-ÿ]/g, "").slice(0, 3).toUpperCase();

// Layout — sized to fill the width and read comfortably.
const H = 660;         // total bracket height (px) — 8 R32 slots per side
const CONNECTOR_W = 22;
const CARD_W = 112;

function formatKickoff(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  });
}

// ── Per-slot display for a still-unresolved placeholder ───────────────────── //
type SlotView = { code: string; name: string; flag?: string | null; resolved: boolean };

function placeholderView(slot: BracketSlot): SlotView {
  if (slot.type === "team")
    return { code: abbr(slot.team_name), name: slot.team_name, flag: slot.flag_url, resolved: true };
  if (slot.type === "group_rank")
    return { code: `${slot.group}${slot.rank}`, name: `Group ${slot.group} #${slot.rank}`, resolved: false };
  if (slot.type === "third_place")
    return { code: "3rd", name: `3rd (${slot.candidate_groups.join("/")})`, resolved: false };
  const r = ROUND_ABBR[slot.round] ?? slot.round;
  const tag = slot.type === "match_winner" ? "W" : "L";
  return { code: `${tag}·${r}${slot.position}`, name: `${slot.round} #${slot.position}`, resolved: false };
}

// ── Full match description (completed / predicted / placeholder) ──────────── //
type Side = SlotView & { score?: string | number | null; shootout?: number | null; win: boolean };
type MatchView = { status: string; predicted: boolean; winProb?: number | null; a: Side; b: Side } | null;

function describe(m: BracketMatch | undefined, flagOf: (n?: string | null) => string | null): MatchView {
  if (!m) return null;

  if (m.completed) {
    const sa = parseInt(m.score_a ?? "0"), sb = parseInt(m.score_b ?? "0");
    let aw = sa > sb, bw = sb > sa;
    if (sa === sb && m.shootout_a != null && m.shootout_b != null) {
      aw = m.shootout_a > m.shootout_b;
      bw = m.shootout_b > m.shootout_a;
    }
    const side = (slot: BracketSlot, score: string | null, so: number | null | undefined, win: boolean): Side => {
      const v = placeholderView(slot);
      return { ...v, flag: v.flag ?? flagOf(v.name), score, shootout: so, win };
    };
    return {
      status: "FT", predicted: false,
      a: side(m.slot_a, m.score_a, m.shootout_a, aw),
      b: side(m.slot_b, m.score_b, m.shootout_b, bw),
    };
  }

  const p = m.prediction;
  if (p && p.predicted_winner) {
    return {
      status: formatKickoff(m.kickoff_utc), predicted: true, winProb: p.win_probability,
      a: { code: abbr(p.team_a_name), name: p.team_a_name ?? "", flag: p.team_a_flag ?? flagOf(p.team_a_name),
           resolved: true, score: p.predicted_score_a, win: p.predicted_winner === p.team_a_name },
      b: { code: abbr(p.team_b_name), name: p.team_b_name ?? "", flag: p.team_b_flag ?? flagOf(p.team_b_name),
           resolved: true, score: p.predicted_score_b, win: p.predicted_winner === p.team_b_name },
    };
  }

  const av = placeholderView(m.slot_a), bv = placeholderView(m.slot_b);
  return {
    status: formatKickoff(m.kickoff_utc), predicted: false,
    a: { ...av, flag: av.flag ?? flagOf(av.name), win: false },
    b: { ...bv, flag: bv.flag ?? flagOf(bv.name), win: false },
  };
}

const championOf = (v: MatchView): string | null =>
  !v ? null : v.a.win ? v.a.name : v.b.win ? v.b.name : null;

// A finished match links to its full Analysis; upcoming ones aren't clickable.
const hrefOf = (m?: BracketMatch): string | undefined =>
  m && m.completed ? `/matches?game=${m.game_id}` : undefined;

// ── World Cup trophy ──────────────────────────────────────────────────────── //
// Trophy image from /public. Plain <img> (not next/image) so the bracket image
// export inlines it cleanly — it's same-origin, so no CORS taint.
function WorldCupTrophy({ height = 92 }: { height?: number }) {
  return (
    <img
      src="/world_cup_trophy_transparent.png"
      alt="World Cup trophy"
      style={{ height }}
      className="w-auto max-w-full object-contain"
    />
  );
}

// ── Match card ────────────────────────────────────────────────────────────── //
function SideRow({ s, predicted }: { s: Side; predicted: boolean }) {
  const scoreColor = s.win ? "text-emerald-500" : predicted ? "text-muted" : "text-fg";
  return (
    <div className={`flex items-center gap-1.5 py-0.5 text-[13px] ${s.resolved ? "text-fg" : "text-faint italic"}`}>
      <Flag src={s.flag} name={s.name} size={22} />
      {/* Full country name on hover */}
      <span
        title={s.name}
        className={`flex-1 cursor-default font-semibold ${s.win ? "text-emerald-600 dark:text-emerald-400" : ""}`}
      >
        {s.code}
      </span>
      {s.score != null && (
        <span className={`shrink-0 font-bold ${scoreColor}`}>
          {s.score}
          {s.shootout != null && <span className="ml-0.5 text-[9px] text-faint">({s.shootout})</span>}
        </span>
      )}
    </div>
  );
}

function MatchCard({ v, href }: { v: MatchView; href?: string }) {
  if (!v) {
    return <div style={{ width: CARD_W }} className="rounded-md border border-dashed border-pitch-edge/40 px-2 py-4" />;
  }
  const pct = v.winProb != null ? Math.round(v.winProb * 100) : null;
  const card = (
    <div
      style={{ width: CARD_W }}
      className={`rounded-md border bg-pitch-card px-2 py-1.5 shadow-sm ${
        href ? "border-pitch-edge/60 transition-colors hover:border-pitch-accent hover:bg-pitch-edge/30" : "border-pitch-edge/60"
      }`}
    >
      <div className="mb-0.5 text-center text-[9px] font-semibold uppercase tracking-wide text-faint">{v.status}</div>
      <SideRow s={v.a} predicted={v.predicted} />
      <SideRow s={v.b} predicted={v.predicted} />
      {v.predicted && pct != null && (
        <div className="mt-1">
          <div className="flex items-center justify-between text-[8px] font-bold uppercase tracking-wide">
            <span className="text-sky-500">predicted</span>
            <span className="text-muted" title="Model's confidence in the predicted winner advancing">{pct}%</span>
          </div>
          {/* confidence bar — how likely the predicted winner is to advance */}
          <div className="mt-0.5 h-1 overflow-hidden rounded-full bg-pitch-edge">
            <div className="h-full bg-sky-500" style={{ width: `${pct}%` }} />
          </div>
        </div>
      )}
      {v.predicted && pct == null && (
        <div className="text-center text-[8px] font-bold uppercase tracking-wide text-sky-500">predicted</div>
      )}
    </div>
  );
  if (href) {
    return (
      <Link href={href} title="View match analysis" className="block">
        {card}
      </Link>
    );
  }
  return card;
}

// ── Bracket connector lines ───────────────────────────────────────────────── //
function Connector({ outerN, facing }: { outerN: number; facing: "right" | "left" }) {
  const items = outerN / 2;
  const itemH = H / outerN;
  const side = facing === "right" ? "border-r-[1.5px]" : "border-l-[1.5px]";
  return (
    <div style={{ width: CONNECTOR_W, height: H }} className="flex shrink-0 flex-col justify-around">
      {Array.from({ length: items }, (_, j) => (
        <div key={j} style={{ height: itemH }} className={`${side} border-t-[1.5px] border-b-[1.5px] border-pitch-edge/45`} />
      ))}
    </div>
  );
}

// ── A half (R32→SF for the left, or SF→R32 mirrored for the right) ─────────── //
function Half({
  cols, matchOf, flagOf, mirror,
}: {
  cols: Col[];
  matchOf: (round: string, pos: number) => BracketMatch | undefined;
  flagOf: (n?: string | null) => string | null;
  mirror: boolean;
}) {
  const ordered = mirror ? [...cols].reverse() : cols;
  const Column = (col: Col) => (
    <div style={{ height: H }} className="flex flex-col justify-around">
      {col.pos.map((p) => {
        const m = matchOf(col.round, p);
        return (
          <MatchCard key={`${col.round}-${p}`} v={describe(m, flagOf)} href={hrefOf(m)} />
        );
      })}
    </div>
  );
  return (
    <div className="flex items-start">
      {ordered.map((col, idx) => {
        const outerN = col.pos.length;
        return (
          <div key={col.round} className="flex items-start">
            {mirror && idx > 0 && outerN >= 2 && <Connector outerN={outerN} facing="left" />}
            {Column(col)}
            {!mirror && idx < ordered.length - 1 && outerN >= 2 && <Connector outerN={outerN} facing="right" />}
          </div>
        );
      })}
    </div>
  );
}

// ── Image export ──────────────────────────────────────────────────────────── //
async function exportBracket(node: HTMLElement, action: "download" | "share") {
  // ESPN flag CDN sends `access-control-allow-origin: *`, so html-to-image can
  // inline the flags without tainting the canvas.
  const bg = getComputedStyle(document.body).backgroundColor || "#0b1220";
  // The bracket is CSS-scaled to fit the screen; offsetWidth/Height are the
  // pre-transform (natural) size. Capture at natural size with the scale reset
  // so the exported image is full-resolution, never the shrunk on-screen size.
  const dataUrl = await toPng(node, {
    cacheBust: true,
    pixelRatio: 2,
    backgroundColor: bg,
    width: node.offsetWidth,
    height: node.offsetHeight,
    style: { transform: "none", transformOrigin: "top left" },
  });

  if (action === "share") {
    try {
      const blob = await (await fetch(dataUrl)).blob();
      const file = new File([blob], "wc26-bracket.png", { type: "image/png" });
      // `canShare({ files })` is the real capability check — many desktop
      // browsers expose navigator.share but can't share files.
      if (navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], title: "2026 FIFA World Cup Bracket" });
        return;
      }
    } catch (err) {
      // User dismissed the share sheet — not an error, just stop.
      if (err instanceof DOMException && err.name === "AbortError") return;
      // Anything else (platform rejected the file share): fall back to download.
    }
  }
  const a = document.createElement("a");
  a.href = dataUrl;
  a.download = "wc26-bracket.png";
  a.click();
}

// ── Main bracket ─────────────────────────────────────────────────────────── //
export function Bracket({ bracket, rankedGroups }: { bracket: BracketData; rankedGroups: Record<string, GroupTeam[]> }) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const captureRef = useRef<HTMLDivElement>(null);
  const [busy, setBusy] = useState<null | "download" | "share">(null);
  const canShare = typeof navigator !== "undefined" && !!navigator.canShare;

  // Scale the whole bracket down so it always fits the card width — no horizontal
  // scroll. offsetWidth/Height are the pre-transform natural size, so remeasuring
  // is stable even while the node is already scaled.
  const [scale, setScale] = useState(1);
  const [naturalH, setNaturalH] = useState(0);
  useLayoutEffect(() => {
    const measure = () => {
      const wrap = wrapRef.current, node = captureRef.current;
      if (!wrap || !node) return;
      const avail = wrap.clientWidth;
      const natural = node.offsetWidth;
      if (natural > 0) setScale(Math.min(1, avail / natural));
      setNaturalH(node.offsetHeight);
    };
    measure();
    const ro = new ResizeObserver(measure);
    if (wrapRef.current) ro.observe(wrapRef.current);
    return () => ro.disconnect();
  }, [bracket]);

  const matchOf = useMemo(() => {
    const map = new Map<string, BracketMatch>();
    for (const r of bracket.rounds) for (const m of r.matches) map.set(`${r.name}#${m.position}`, m);
    return (round: string, pos: number) => map.get(`${round}#${pos}`);
  }, [bracket]);

  const flagByName = useMemo(() => {
    const map = new Map<string, string>();
    Object.values(rankedGroups).forEach((teams) =>
      teams.forEach((t) => { if (t.flag_url) map.set(t.team_name, t.flag_url); }));
    return map;
  }, [rankedGroups]);
  const flagOf = (n?: string | null) => (n ? flagByName.get(n) ?? null : null);

  const finalMatch = matchOf("Final", 1);
  const thirdMatch = matchOf("Third Place Match", 1);
  const finalView = describe(finalMatch, flagOf);
  const champion = championOf(finalView);
  const championIsPredicted = finalView?.predicted ?? true;

  async function handleExport(action: "download" | "share") {
    if (!captureRef.current) return;
    setBusy(action);
    try {
      await exportBracket(captureRef.current, action);
    } catch (e) {
      console.error("Bracket export failed", e);
      alert("Sorry — couldn't generate the image. Please try again.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="card p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-sm font-bold text-fg">Knockout Bracket</h2>
        <div className="flex gap-2">
          <button
            onClick={() => handleExport("download")}
            disabled={!!busy}
            className="rounded-md border border-pitch-edge px-2.5 py-1 text-xs font-semibold text-fg transition-colors hover:bg-pitch-edge/40 disabled:opacity-50"
          >
            {busy === "download" ? "Saving…" : "⬇ Download"}
          </button>
          {canShare && (
            <button
              onClick={() => handleExport("share")}
              disabled={!!busy}
              className="rounded-md border border-pitch-edge px-2.5 py-1 text-xs font-semibold text-fg transition-colors hover:bg-pitch-edge/40 disabled:opacity-50"
            >
              {busy === "share" ? "Sharing…" : "⤴ Share"}
            </button>
          )}
        </div>
      </div>

      {/* Fit-to-width: the inner node keeps its natural size (the capture target,
          so exports are never clipped) and is CSS-scaled down to fit the card.
          The outer div reserves the scaled height so nothing below overlaps. */}
      <div ref={wrapRef} className="overflow-hidden">
        <div style={{ height: naturalH ? naturalH * scale : undefined }}>
        <div
          ref={captureRef}
          style={{ transform: `scale(${scale})`, transformOrigin: "top left" }}
          className="inline-block bg-pitch-bg p-3"
        >
        <div className="flex items-start" style={{ minHeight: H }}>
          {/* Left half: R32 → SF */}
          <Half cols={LEFT_COLS} matchOf={matchOf} flagOf={flagOf} mirror={false} />

          {/* Trophy + champion + Final, centred */}
          <div className="flex shrink-0 items-center" style={{ height: H }}>
            <div className="border-t-[1.5px] border-pitch-edge/45" style={{ width: CONNECTOR_W }} />
            <div className="flex w-[180px] flex-col items-center gap-2 px-2 text-center">
              <WorldCupTrophy height={96} />
              <div className="whitespace-nowrap text-[11px] font-bold uppercase tracking-[0.18em] text-amber-500">
                2026 FIFA World Cup
              </div>
              <div className="w-full truncate text-lg font-black leading-tight text-fg" title={champion ?? undefined}>
                {champion ?? "Champion TBD"}
              </div>
              {champion && (
                <div className="text-[9px] font-semibold uppercase tracking-wide text-faint">
                  {championIsPredicted ? "predicted champion" : "champion"}
                </div>
              )}
              <div className="mt-2 text-[9px] font-bold uppercase tracking-wider text-faint">Final</div>
              <MatchCard v={finalView} href={hrefOf(finalMatch)} />
            </div>
            <div className="border-t-[1.5px] border-pitch-edge/45" style={{ width: CONNECTOR_W }} />
          </div>

          {/* Right half: SF → R32 (mirrored) */}
          <Half cols={RIGHT_COLS} matchOf={matchOf} flagOf={flagOf} mirror={true} />
        </div>

        {/* Third place */}
        {thirdMatch && (
          <div className="mt-5 flex flex-col items-center gap-1">
            <div className="text-[9px] font-bold uppercase tracking-wider text-faint">3rd Place</div>
            <MatchCard v={describe(thirdMatch, flagOf)} href={hrefOf(thirdMatch)} />
          </div>
        )}
        </div>
        </div>
      </div>

      <p className="mt-4 text-[10px] leading-relaxed text-faint">
        <span className="font-semibold text-fg">FT</span> = final result (ESPN).
        Upcoming matches show model predictions (same data as Winner Probability
        &amp; Match Predictor): predicted scores, winner highlighted in{" "}
        <span className="font-semibold text-emerald-500">green</span>, and a{" "}
        <span className="font-semibold text-sky-500">predicted</span> tag.
        Predictions cascade — each later round uses the predicted winners of the
        round before it, all the way to the predicted champion. The{" "}
        <span className="font-semibold text-sky-500">confidence bar</span> shows
        how likely the model thinks the predicted winner is to advance. Hover a
        team code to see the full country name, and click any{" "}
        <span className="font-semibold text-fg">finished match</span> to open its
        full analysis.
      </p>
    </div>
  );
}
