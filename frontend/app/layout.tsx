import type { Metadata } from "next";
import "./globals.css";
import { Nav } from "@/components/Nav";

export const metadata: Metadata = {
  title: "AnalyseThisWC26 — World Cup 2026 Analytics",
  description:
    "Interactive FIFA World Cup 2026 player & team analytics with an AI match predictor. A NeuNov Technologies demo.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Nav />
        <main className="mx-auto max-w-7xl px-4 pb-24 pt-6">{children}</main>
        <footer className="border-t border-pitch-edge/60 py-8 text-center text-xs text-slate-500">
          AnalyseThisWC26 · A demo by{" "}
          <a
            href="https://neunov.com"
            target="_blank"
            rel="noopener noreferrer"
            className="stat-grad font-semibold hover:underline"
          >
            NeuNov Technologies
          </a>{" "}
          · Data from public tournament sources, for demonstration only.
        </footer>
      </body>
    </html>
  );
}
