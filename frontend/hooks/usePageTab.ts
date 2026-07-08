"use client";

import { useCallback } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

export function usePageTab(
  paramName: string,
  defaultTab: string,
  storageKey: string,
  validTabs: readonly string[]
) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const activeTab = (() => {
    const fromUrl = searchParams.get(paramName);
    if (fromUrl && validTabs.includes(fromUrl)) return fromUrl;
    if (typeof window !== "undefined") {
      const stored = sessionStorage.getItem(storageKey);
      if (stored && validTabs.includes(stored)) return stored;
    }
    return defaultTab;
  })();

  const setTab = useCallback(
    (tabId: string) => {
      if (!validTabs.includes(tabId)) return;
      const params = new URLSearchParams(searchParams.toString());
      params.set(paramName, tabId);
      const q = params.toString();
      router.replace(q ? `${pathname}?${q}` : pathname, { scroll: false });
      sessionStorage.setItem(storageKey, tabId);
      const reducedMotion =
        typeof window !== "undefined" &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      document.getElementById("predict-top")?.scrollIntoView({
        behavior: reducedMotion ? "auto" : "smooth",
      });
    },
    [router, pathname, searchParams, paramName, storageKey, validTabs]
  );

  return { activeTab, setTab };
}
