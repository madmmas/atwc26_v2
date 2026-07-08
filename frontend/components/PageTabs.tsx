"use client";

import { useCallback, useRef } from "react";
import styles from "./PageTabs.module.css";

export interface PageTab {
  id: string;
  label: string;
  labelShort?: string;
  icon?: string;
}

interface PageTabsProps {
  tabs: PageTab[];
  activeTab: string;
  onChange: (tabId: string) => void;
}

export function PageTabs({ tabs, activeTab, onChange }: PageTabsProps) {
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const focusTab = useCallback(
    (index: number) => {
      const el = tabRefs.current[index];
      el?.focus();
    },
    []
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (e.key === "ArrowRight") {
      e.preventDefault();
      const next = (index + 1) % tabs.length;
      onChange(tabs[next].id);
      focusTab(next);
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      const prev = (index - 1 + tabs.length) % tabs.length;
      onChange(tabs[prev].id);
      focusTab(prev);
    } else if (e.key === "Home") {
      e.preventDefault();
      onChange(tabs[0].id);
      focusTab(0);
    } else if (e.key === "End") {
      e.preventDefault();
      onChange(tabs[tabs.length - 1].id);
      focusTab(tabs.length - 1);
    }
  };

  return (
    <div className={styles["page-tab-bar"]} role="tablist">
      {tabs.map((tab, index) => {
        const isActive = activeTab === tab.id;
        const shortLabel = tab.labelShort ?? tab.label;
        return (
          <button
            key={tab.id}
            ref={(el) => {
              tabRefs.current[index] = el;
            }}
            type="button"
            role="tab"
            id={`tab-${tab.id}`}
            aria-selected={isActive}
            aria-controls={`tabpanel-${tab.id}`}
            tabIndex={isActive ? 0 : -1}
            className={`${styles["page-tab"]} ${isActive ? styles.active : ""}`}
            onClick={() => onChange(tab.id)}
            onKeyDown={(e) => handleKeyDown(e, index)}
          >
            {tab.icon && <span className={styles["tab-icon"]}>{tab.icon}</span>}
            <span className={styles["tab-label-full"]}>{tab.label}</span>
            <span className={styles["tab-label-short"]}>{shortLabel}</span>
          </button>
        );
      })}
    </div>
  );
}
