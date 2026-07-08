"use client";

import { useEffect, useState } from "react";

export function formatRelativeTime(from: Date, now = new Date()): string {
  const diffMs = now.getTime() - from.getTime();
  const mins = Math.floor(diffMs / 60_000);
  if (mins < 60) return `${Math.max(mins, 0)} mins ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} hrs ago`;
  return from.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function DataFreshnessLabel({ fetchedAt }: { fetchedAt: Date | null }) {
  const [label, setLabel] = useState("");

  useEffect(() => {
    if (!fetchedAt) return;
    const tick = () => setLabel(formatRelativeTime(fetchedAt));
    tick();
    const id = setInterval(tick, 60_000);
    return () => clearInterval(id);
  }, [fetchedAt]);

  if (!fetchedAt || !label) return null;

  return (
    <p className="mt-1 text-[11px] text-[#555]">Last updated {label}</p>
  );
}
