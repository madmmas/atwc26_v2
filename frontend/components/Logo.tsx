// Colorful typographic wordmark for AnalyseThisWC26.
// Pure CSS/typography — no image asset — so it stays crisp at any size.

type Size = "sm" | "md" | "lg";

const TILE: Record<Size, string> = {
  sm: "h-8 w-8 text-base",
  md: "h-9 w-9 text-lg",
  lg: "h-12 w-12 text-2xl",
};
const WORD: Record<Size, string> = {
  sm: "text-sm",
  md: "text-base",
  lg: "text-3xl",
};

export function Logo({ size = "md" }: { size?: Size }) {
  return (
    <span className="inline-flex items-center gap-2" data-testid="logo">
      <span
        className={`grid ${TILE[size]} place-items-center rounded-xl bg-gradient-to-br from-emerald-400 via-cyan-400 to-violet-500 font-black text-pitch-bg shadow-glow`}
      >
        A
      </span>
      <span className={`flex items-baseline gap-1 font-black tracking-tight ${WORD[size]}`}>
        <span className="bg-gradient-to-r from-emerald-300 to-cyan-400 bg-clip-text text-transparent">
          Analyse
        </span>
        <span className="bg-gradient-to-r from-amber-300 to-rose-400 bg-clip-text text-transparent">
          This
        </span>
        <span className="rounded-md bg-gradient-to-br from-violet-500 to-fuchsia-500 px-1.5 py-0.5 text-[0.55em] font-black uppercase tracking-wider text-white">
          WC26
        </span>
      </span>
    </span>
  );
}

// "by NeuNov" with an external link to neunov.com. Kept separate from any
// Next <Link> so it never nests inside another anchor.
export function ByNeuNov({ className = "" }: { className?: string }) {
  return (
    <span className={className}>
      by{" "}
      <a
        href="https://neunov.com"
        target="_blank"
        rel="noopener noreferrer"
        className="font-semibold text-slate-400 transition-colors hover:text-pitch-accent"
      >
        NeuNov
      </a>
    </span>
  );
}
