// Collapsible key-glossary shown in the footer on every page.
// Curated to the terms the app actually surfaces (not all ~140 raw fields).

type Term = { abbr: string; name: string; desc: string };

const GROUPS: { title: string; terms: Term[] }[] = [
  {
    title: "Attacking",
    terms: [
      { abbr: "xG", name: "Expected Goals", desc: "Quality of chances — likelihood a shot becomes a goal." },
      { abbr: "xA", name: "Expected Assists", desc: "Likelihood a pass becomes an assist." },
      { abbr: "/90", name: "Per 90 minutes", desc: "A stat scaled to a full match, so subs and starters compare fairly." },
      { abbr: "SOT", name: "Shots on Target", desc: "Shots that would score without a save/block." },
      { abbr: "Big Ch.", name: "Big Chances Created", desc: "Passes that set up a clear scoring opportunity." },
    ],
  },
  {
    title: "Possession & defending",
    terms: [
      { abbr: "TCH", name: "Touches", desc: "Total times a player touched the ball." },
      { abbr: "Pass %", name: "Pass Completion", desc: "Share of attempted passes completed." },
      { abbr: "DUELW", name: "Duels Won", desc: "1v1 contests (ground/aerial) won." },
      { abbr: "DINT", name: "Defensive Interventions", desc: "Tackles, interceptions, clearances & blocks combined." },
      { abbr: "CLR", name: "Clearances", desc: "Defensive actions clearing the ball from danger." },
    ],
  },
  {
    title: "Team & match",
    terms: [
      { abbr: "xGA", name: "Expected Goals Against", desc: "Quality of chances a team conceded." },
      { abbr: "MINS", name: "Minutes", desc: "Total minutes played in the tournament." },
      { abbr: "DNP", name: "Did Not Play", desc: "Squad member who hasn't featured in a match yet." },
      { abbr: "Roles", name: "GK / DEF / MID / FWD", desc: "Goalkeeper, Defender, Midfielder, Forward." },
    ],
  },
  {
    title: "Predictor",
    terms: [
      { abbr: "Att/Def", name: "Attack / Defense rating", desc: "An XI's strength vs. the tournament average (1.0 = average)." },
      { abbr: "GK", name: "Goalkeeping rating", desc: "Shot-stopping above expectation (saves vs. xG faced)." },
      { abbr: "Poisson", name: "Goals model", desc: "Win/draw/loss from each side's expected goals (the football-analytics standard)." },
    ],
  },
];

export function GlossaryBar() {
  return (
    <details className="mx-auto max-w-7xl px-4">
      <summary className="cursor-pointer select-none rounded-lg px-3 py-2 text-xs font-semibold text-slate-400 transition-colors hover:bg-pitch-edge/40 hover:text-white">
        📖 Glossary — what the stats mean
      </summary>
      <div className="mt-2 grid gap-4 rounded-xl border border-pitch-edge bg-pitch-card/60 p-4 sm:grid-cols-2 lg:grid-cols-4">
        {GROUPS.map((g) => (
          <div key={g.title}>
            <div className="mb-2 text-[11px] font-bold uppercase tracking-wider stat-grad">
              {g.title}
            </div>
            <dl className="space-y-1.5">
              {g.terms.map((t) => (
                <div key={t.abbr}>
                  <dt className="text-xs font-semibold text-white">
                    {t.abbr} <span className="font-normal text-slate-500">· {t.name}</span>
                  </dt>
                  <dd className="text-[11px] leading-snug text-slate-400">{t.desc}</dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
    </details>
  );
}
