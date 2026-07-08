"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Logo, ByNeuNov } from "@/components/Logo";
import { ThemeToggle } from "@/components/ThemeToggle";

const links = [
  { href: "/", label: "Overview" },
  { href: "/standings", label: "Standings" },
  { href: "/explore", label: "Explore" },
  { href: "/matches", label: "Matches" },
  { href: "/players", label: "Players" },
  { href: "/predict", label: "Predictor" },
];

export function Nav() {
  const path = usePathname();
  const [open, setOpen] = useState(false);

  // Close the mobile menu whenever the route actually changes.
  useEffect(() => setOpen(false), [path]);

  return (
    <header className="sticky top-0 z-50 border-b border-pitch-edge/60 bg-pitch-bg/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
        <div className="flex items-center gap-2">
          <Link href="/" aria-label="AnalyseThisWC26 home">
            <Logo size="md" />
          </Link>
          <ByNeuNov className="hidden text-[10px] uppercase tracking-widest text-faint sm:inline" />
        </div>

        {/* Desktop nav */}
        <nav className="hidden items-center gap-1 md:flex" data-testid="nav">
          {links.map((l) => {
            const active =
              l.href === "/"
                ? path === "/"
                : l.href === "/players"
                  ? path.startsWith("/players")
                  : path === l.href || path.startsWith(l.href + "/");
            return (
              <Link
                key={l.href}
                href={l.href}
                data-testid={`nav-${l.href === "/" ? "overview" : l.href.slice(1)}`}
                className={`rounded-lg px-2.5 py-1.5 text-sm font-semibold transition-colors ${
                  active ? "bg-white text-[#111]" : "text-muted hover:text-fg"
                }`}
              >
                {l.label}
              </Link>
            );
          })}
          <ThemeToggle />
        </nav>

        {/* Mobile controls: theme toggle + hamburger */}
        <div className="flex items-center gap-2 md:hidden">
          <ThemeToggle />
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            data-testid="nav-menu-toggle"
            className="rounded-lg border border-pitch-edge p-2 text-fg transition-colors hover:bg-pitch-edge/60"
          >
            {open ? (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
              </svg>
            ) : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M3 6h18M3 12h18M3 18h18" strokeLinecap="round" />
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Mobile dropdown */}
      {open && (
        <nav
          data-testid="nav-mobile"
          className="border-t border-pitch-edge/60 px-4 py-2 md:hidden"
        >
          <div className="flex flex-col gap-1 py-1">
            {links.map((l) => {
              const active =
                l.href === "/"
                  ? path === "/"
                  : l.href === "/players"
                    ? path.startsWith("/players")
                    : path === l.href || path.startsWith(l.href + "/");
              return (
                <Link
                  key={l.href}
                  href={l.href}
                  data-testid={`nav-mobile-${l.href === "/" ? "overview" : l.href.slice(1)}`}
                  onClick={() => setOpen(false)}
                  className={`rounded-lg px-3 py-2 text-sm font-semibold transition-colors ${
                    active ? "bg-white text-[#111]" : "text-muted hover:text-fg"
                  }`}
                >
                  {l.label}
                </Link>
              );
            })}
          </div>
        </nav>
      )}
    </header>
  );
}
