"use client";

import { useCallback, useEffect, useState } from "react";

const SECTION_HASH: Record<string, string> = {
  "standings-bracket": "#bracket",
  "standings-groups": "#groups",
};

function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function scrollBehavior(): ScrollBehavior {
  return prefersReducedMotion() ? "auto" : "smooth";
}

function syncHash(sectionId: string) {
  const hash = SECTION_HASH[sectionId];
  if (!hash) return;
  const path = `${window.location.pathname}${window.location.search}${hash}`;
  if (`${window.location.pathname}${window.location.search}${window.location.hash}` !== path) {
    window.history.replaceState(null, "", path);
  }
}

export function useActiveSection(sectionIds: readonly string[], defaultSection: string) {
  const [activeSection, setActiveSection] = useState(defaultSection);

  const scrollToSection = useCallback((sectionId: string) => {
    const el = document.getElementById(sectionId);
    if (!el) return;
    el.scrollIntoView({ behavior: scrollBehavior(), block: "start" });
    setActiveSection(sectionId);
    syncHash(sectionId);
  }, []);

  useEffect(() => {
    const hash = window.location.hash;
    if (hash === "#groups") {
      requestAnimationFrame(() => {
        document.getElementById("standings-groups")?.scrollIntoView({
          behavior: scrollBehavior(),
          block: "start",
        });
        setActiveSection("standings-groups");
      });
      return;
    }
    if (hash === "#bracket") {
      setActiveSection("standings-bracket");
    }
  }, []);

  useEffect(() => {
    const elements = sectionIds
      .map((id) => document.getElementById(id))
      .filter((el): el is HTMLElement => !!el);
    if (!elements.length) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (!visible.length) return;
        const id = visible[0].target.id;
        setActiveSection(id);
        syncHash(id);
      },
      { threshold: 0.3 }
    );

    elements.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [sectionIds]);

  return { activeSection, scrollToSection };
}
