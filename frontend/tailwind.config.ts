import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        pitch: {
          bg: "#0a0e14",
          card: "#121821",
          edge: "#1e2733",
          accent: "#10b981", // emerald
          accent2: "#06b6d4", // cyan
          warn: "#f59e0b",
          danger: "#ef4444",
        },
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
