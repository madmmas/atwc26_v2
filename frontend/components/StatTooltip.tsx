"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { STAT_DEFINITIONS } from "@/lib/statDefinitions";

type StatTooltipProps = {
  stat: string;
  /** When false, only the ⓘ icon is shown (e.g. column header already has the label). */
  showLabel?: boolean;
  className?: string;
};

type TooltipPos = {
  top: number;
  left: number;
  placement: "above" | "below";
};

const TOOLTIP_MAX_WIDTH = 220;

export function StatTooltip({ stat, showLabel = true, className = "" }: StatTooltipProps) {
  const def = STAT_DEFINITIONS[stat];
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<TooltipPos | null>(null);
  const [mounted, setMounted] = useState(false);
  const btnRef = useRef<HTMLButtonElement>(null);
  const tooltipId = useId();

  useEffect(() => {
    setMounted(true);
  }, []);

  const updatePlacement = useCallback(() => {
    const el = btnRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const placement: TooltipPos["placement"] = rect.top < 100 ? "below" : "above";
    const half = TOOLTIP_MAX_WIDTH / 2;
    const left = Math.max(half + 8, Math.min(window.innerWidth - half - 8, rect.left + rect.width / 2));
    const top = placement === "below" ? rect.bottom + 6 : rect.top - 6;
    setPos({ top, left, placement });
  }, []);

  useEffect(() => {
    if (!open) return;
    updatePlacement();
    const onReposition = () => updatePlacement();
    window.addEventListener("scroll", onReposition, true);
    window.addEventListener("resize", onReposition);
    const onOutside = (e: MouseEvent | TouchEvent) => {
      if (btnRef.current && !btnRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onOutside);
    document.addEventListener("touchstart", onOutside);
    return () => {
      window.removeEventListener("scroll", onReposition, true);
      window.removeEventListener("resize", onReposition);
      document.removeEventListener("mousedown", onOutside);
      document.removeEventListener("touchstart", onOutside);
    };
  }, [open, updatePlacement]);

  if (!def) {
    return showLabel ? <span className={className}>{stat}</span> : null;
  }

  const tooltip =
    open && pos && mounted
      ? createPortal(
          <span
            id={tooltipId}
            role="tooltip"
            className="pointer-events-none fixed z-[9999] w-max max-w-[220px] rounded-md border border-[#2a2a2a] bg-[#1e1e1e] px-2.5 py-2 text-[12px] leading-snug text-fg shadow-lg"
            style={{
              top: pos.top,
              left: pos.left,
              transform:
                pos.placement === "below"
                  ? "translateX(-50%)"
                  : "translate(-50%, -100%)",
            }}
          >
            <span className="block font-semibold text-fg">{def.label}</span>
            <span className="mt-0.5 block text-fg-soft">{def.definition}</span>
            {def.unit && (
              <span className="mt-1 block text-[11px] text-faint">Unit: {def.unit}</span>
            )}
          </span>,
          document.body
        )
      : null;

  return (
    <>
      <span className={`inline-flex items-center gap-0.5 ${className}`}>
        {showLabel && <span>{stat}</span>}
        <button
          ref={btnRef}
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
      </span>
      {tooltip}
    </>
  );
}

/** Column header / stat card label with inline tooltip. */
export function StatLabel({ stat, className = "" }: { stat: string; className?: string }) {
  return <StatTooltip stat={stat} className={className} />;
}
