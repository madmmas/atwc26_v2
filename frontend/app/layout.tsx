import type { Metadata } from "next";
import "./globals.css";
import { Nav } from "@/components/Nav";
import { GlossaryBar } from "@/components/GlossaryBar";

export const metadata: Metadata = {
  title: "AnalyseThisWC26 — World Cup 2026 Analytics",
  description:
    "Interactive FIFA World Cup 2026 player & team analytics with an AI match predictor. A NeuNov Technologies demo.",
  icons: {
    icon: "/ATSymble.png",
    apple: "/ATSymble.png",
  },
};

// Applies the saved/system theme before paint to avoid a flash of the wrong theme.
const themeScript = `(function(){try{var t=localStorage.getItem('theme');var d=t?t==='dark':window.matchMedia('(prefers-color-scheme: dark)').matches;document.documentElement.classList.toggle('dark',d);}catch(e){document.documentElement.classList.add('dark');}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <Nav />
        <main className="mx-auto max-w-7xl px-4 pb-12 pt-6">{children}</main>
        <div className="border-t border-pitch-edge/60 py-4">
          <GlossaryBar />
        </div>
        <footer className="border-t border-pitch-edge/60 py-8 text-center text-xs text-faint">
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
