"use client";

import styles from "./SectionNavBar.module.css";

export interface StandingsAnchor {
  id: string;
  label: string;
  labelShort?: string;
  icon?: string;
}

interface StandingsAnchorBarProps {
  anchors: StandingsAnchor[];
  activeSection: string;
  onNavigate: (sectionId: string) => void;
}

export function StandingsAnchorBar({ anchors, activeSection, onNavigate }: StandingsAnchorBarProps) {
  return (
    <nav
      className={`${styles.bar} ${styles.barSticky}`}
      role="navigation"
      aria-label="Page sections"
    >
      {anchors.map((anchor) => {
        const isActive = activeSection === anchor.id;
        const shortLabel = anchor.labelShort ?? anchor.label;
        return (
          <button
            key={anchor.id}
            id={`anchor-${anchor.id}`}
            type="button"
            aria-current={isActive ? "true" : undefined}
            className={`${styles.btn} ${isActive ? styles.btnActive : ""}`}
            onClick={() => onNavigate(anchor.id)}
          >
            {anchor.icon && <span className={styles.icon}>{anchor.icon}</span>}
            <span className={styles.labelFull}>{anchor.label}</span>
            <span className={styles.labelShort}>{shortLabel}</span>
          </button>
        );
      })}
    </nav>
  );
}
