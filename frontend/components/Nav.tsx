"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Logo, ByNeuNov } from "@/components/Logo";
import { ThemeToggle } from "@/components/ThemeToggle";

const links = [
  { href: "/", label: "Overview" },
  { href: "/explore", label: "Explore" },
  { href: "/matches", label: "Matches" },
  { href: "/players", label: "Players" },
  { href: "/predict", label: "Predictor" },
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
          <ByNeuNov className="hidden text-[10px] uppercase tracking-widest text-faint sm:inline" />
        </div>
        <nav className="flex items-center gap-1" data-testid="nav">
          {links.map((l) => {
            const active = l.href === "/players" ? path.startsWith("/players") : path === l.href;
            return (
              <Link
                key={l.href}
                href={l.href}
                data-testid={`nav-${l.href === "/" ? "overview" : l.href.slice(1)}`}
                className={`rounded-lg px-2.5 py-1.5 text-sm font-semibold transition-colors ${
                  active
                    ? "bg-pitch-edge text-fg"
                    : "text-muted hover:text-fg"
                }`}
              >
                {l.label}
              </Link>
            );
          })}
          <ThemeToggle />
        </nav>
      </div>
    </header>
  );
}
