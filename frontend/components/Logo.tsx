import Image from "next/image";

type Size = "sm" | "md" | "lg";

// Logo sizing: responsive widths for the SVG wordmark.
const SIZES: Record<Size, string> = {
  sm: "w-32 h-8",   // 128px wide, ~32px tall
  md: "w-40 h-10",  // 160px wide, ~40px tall
  lg: "w-56 h-14",  // 224px wide, ~56px tall
};

export function Logo({ size = "md" }: { size?: Size }) {
  return (
    <div className={`inline-block ${SIZES[size]}`} data-testid="logo">
      <Image
        src="/NewLogoAnalyseThis.png"
        alt="AnalyseThisWC26"
        width={1854}
        height={302}
        priority
        className="w-full h-auto"
      />
    </div>
  );
}

// Symbol icon (AT badge) for small spaces like favicon or compact display.
export function Symbol({ size = "sm" }: { size?: "xs" | "sm" | "md" } = {}) {
  const SYMBOL_SIZES: Record<"xs" | "sm" | "md", string> = {
    xs: "w-6 h-6",   // 24px
    sm: "w-8 h-8",   // 32px
    md: "w-12 h-12", // 48px
  };
  return (
    <Image
      src="/ATSymble.png"
      alt="AT"
      width={420}
      height={414}
      className={`${SYMBOL_SIZES[size]} rounded`}
    />
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
        className="font-semibold text-muted transition-colors hover:text-pitch-accent"
      >
        NeuNov
      </a>
    </span>
  );
}
