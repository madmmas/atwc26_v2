"use client";

import { useEffect, useState } from "react";

const STEPS = [
  "Step 1: Pick two teams",
  "Step 2: Choose formation",
  "Step 3: Build your XI",
  "Step 4: Predict result",
];

export function PredictorHintBar({
  teamA,
  teamB,
  formationA,
  formationB,
  slotsAFull,
  slotsBFull,
}: {
  teamA: string;
  teamB: string;
  formationA: string;
  formationB: string;
  slotsAFull: boolean;
  slotsBFull: boolean;
}) {
  const [dismissed, setDismissed] = useState(true);

  useEffect(() => {
    setDismissed(sessionStorage.getItem("predictor_hint_dismissed") === "true");
  }, []);

  if (dismissed || (teamA && teamB)) return null;

  let active = 1;
  if (teamA || teamB) active = 2;
  if (formationA && formationB) active = 3;
  if (slotsAFull && slotsBFull) active = 4;

  function dismiss() {
    sessionStorage.setItem("predictor_hint_dismissed", "true");
    setDismissed(true);
  }

  return (
    <div className="relative rounded-lg border border-[#2a2a2a] bg-[#1a1a1a] px-4 py-2.5 pr-10 text-[12px] text-[#888]">
      <div className="flex flex-wrap items-center gap-1">
        {STEPS.map((s, i) => (
          <span key={s} className="inline-flex items-center gap-1">
            {i > 0 && <span className="text-faint">→</span>}
            <span className={active === i + 1 ? "font-semibold text-[#c8f135]" : ""}>{s}</span>
          </span>
        ))}
      </div>
      <button
        type="button"
        onClick={dismiss}
        aria-label="Dismiss hint"
        className="absolute right-2 top-2 text-faint hover:text-fg"
      >
        ×
      </button>
    </div>
  );
}
