import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Surfaces & text are CSS-variable-driven so they adapt to light/dark.
        pitch: {
          bg: "rgb(var(--bg) / <alpha-value>)",
          card: "rgb(var(--card) / <alpha-value>)",
          edge: "rgb(var(--edge) / <alpha-value>)",
          accent: "#10b981", // emerald (works on both themes)
          accent2: "#f59e0b", // amber
          warn: "#f59e0b",
          danger: "#ef4444",
        },
        // Semantic text tokens.
        fg: "rgb(var(--fg) / <alpha-value>)",
        "fg-soft": "rgb(var(--fg-soft) / <alpha-value>)",
        muted: "rgb(var(--muted) / <alpha-value>)",
        faint: "rgb(var(--faint) / <alpha-value>)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      boxShadow: {
        glow: "0 0 40px -10px rgba(16,185,129,0.35)",
      },
    },
  },
  plugins: [],
};
export default config;
