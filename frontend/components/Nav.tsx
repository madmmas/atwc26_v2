"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Logo, ByNeuNov } from "@/components/Logo";

const links = [
  { href: "/", label: "Overview" },
  { href: "/explore", label: "Explore" },
  { href: "/predict", label: "Match Predictor" },
];

export function Nav() {
  const path = usePathname();
  return (
    <header className="sticky top-0 z-50 border-b border-pitch-edge/60 bg-pitch-bg/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
        <div className="flex items-center gap-2">
          <Link href="/" aria-label="AnalyseThisWC26 home">
            <Logo size="md" />
          </Link>
          <ByNeuNov className="hidden text-[10px] uppercase tracking-widest text-slate-500 sm:inline" />
        </div>
        <nav className="flex items-center gap-1" data-testid="nav">
          {links.map((l) => {
            const active = path === l.href;
            return (
              <Link
                key={l.href}
                href={l.href}
                data-testid={`nav-${l.href === "/" ? "overview" : l.href.slice(1)}`}
                className={`rounded-lg px-3 py-1.5 text-sm font-semibold transition-colors ${
                  active
                    ? "bg-pitch-edge text-white"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
