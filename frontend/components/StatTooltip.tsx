"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { STAT_DEFINITIONS } from "@/lib/statDefinitions";

type StatTooltipProps = {
  stat: string;
  /** When false, only the ⓘ icon is shown (e.g. column header already has the label). */
  showLabel?: boolean;
  className?: string;
};

export function StatTooltip({ stat, showLabel = true, className = "" }: StatTooltipProps) {
  const def = STAT_DEFINITIONS[stat];
  const [open, setOpen] = useState(false);
  const [flipBelow, setFlipBelow] = useState(false);
  const wrapRef = useRef<HTMLSpanElement>(null);
  const tooltipId = useId();

  const updatePlacement = useCallback(() => {
    const el = wrapRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    setFlipBelow(rect.top < 80);
  }, []);

  useEffect(() => {
    if (!open) return;
    updatePlacement();
    const onOutside = (e: MouseEvent | TouchEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onOutside);
    document.addEventListener("touchstart", onOutside);
    return () => {
      document.removeEventListener("mousedown", onOutside);
      document.removeEventListener("touchstart", onOutside);
    };
  }, [open, updatePlacement]);

  if (!def) {
    return showLabel ? <span className={className}>{stat}</span> : null;
  }

  return (
    <span ref={wrapRef} className={`relative inline-flex items-center gap-0.5 ${className}`}>
      {showLabel && <span>{stat}</span>}
      <button
        type="button"
        aria-label={`${def.label} definition`}
        aria-describedby={open ? tooltipId : undefined}
        className="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px] leading-none text-faint transition-colors hover:text-fg focus:outline-none focus-visible:ring-1 focus-visible:ring-pitch-accent"
        onMouseEnter={() => {
          updatePlacement();
          setOpen(true);
        }}
        onMouseLeave={() => setOpen(false)}
        onClick={(e) => {
          e.stopPropagation();
          updatePlacement();
          setOpen((v) => !v);
        }}
      >
        ⓘ
      </button>
      {open && (
        <span
          id={tooltipId}
          role="tooltip"
          className={`pointer-events-none absolute left-1/2 z-50 w-max max-w-[220px] -translate-x-1/2 rounded-md border border-[#2a2a2a] bg-[#1e1e1e] px-2.5 py-2 text-[12px] leading-snug text-fg shadow-lg ${
            flipBelow ? "top-full mt-1.5" : "bottom-full mb-1.5"
          }`}
        >
          <span className="block font-semibold text-fg">{def.label}</span>
          <span className="mt-0.5 block text-fg-soft">{def.definition}</span>
          {def.unit && (
            <span className="mt-1 block text-[11px] text-faint">Unit: {def.unit}</span>
          )}
        </span>
      )}
    </span>
  );
}

/** Column header / stat card label with inline tooltip. */
export function StatLabel({ stat, className = "" }: { stat: string; className?: string }) {
  return <StatTooltip stat={stat} className={className} />;
}
