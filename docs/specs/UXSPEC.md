# ATWC26 — UX Improvement Spec
**For:** Cursor AI-assisted implementation  
**Product:** AnalyseThisWC26 (atwc26.com)  
**Audit base:** Live site at d3brosganz3u2u.cloudfront.net  
**Date:** July 2026  
**Priority order:** P0 = ship now · P1 = next sprint · P2 = backlog

---

## Context & Constraints

- React SPA, fully client-rendered (no SSR/SSG)
- Dark theme: near-black background (`#111`/`#161616`), green accent (`#c8f135` / teal `#1D9E75`), amber (`#F5A623`) for chart bars
- All data fetched client-side from AWS (DynamoDB via Lambda/ECS)
- Do **not** change the visual design language — all changes must stay within the existing token system
- Do **not** refactor page architecture — implement changes at the component level
- Shared components to edit: `Navbar`, `Glossary`, `StatTooltip` (new), `SkeletonRow` (new)

---

## SPEC 1 — Global: Active Nav State
**Priority:** P0  
**Files:** `Navbar.tsx` (or equivalent nav component)

### Problem
The nav pill highlight only appears on the Overview page. Navigating to `/explore`, `/matches`, `/players`, `/standings`, or `/predict` shows no active state — the user cannot tell where they are.

### Acceptance Criteria
- [ ] The nav item matching the current route renders with the active pill style (same as the "Overview" pill: white background, dark text, rounded)
- [ ] Active state is driven by `useLocation()` or equivalent router hook — not hardcoded
- [ ] On routes that don't match any nav item, no pill is highlighted
- [ ] Active state updates instantly on navigation (no flash)

### Implementation Notes
```tsx
// Pattern
const { pathname } = useLocation();
const isActive = (path: string) => pathname === path || pathname.startsWith(path);

// Apply to each nav item
<NavItem active={isActive('/explore')} href="/explore">Explore</NavItem>
```

---

## SPEC 2 — Global: Skeleton Loaders
**Priority:** P0  
**Files:** New `SkeletonRow.tsx`, `SkeletonCard.tsx` — import into `ExplorePage`, `PlayersPage`, `OverviewPage`

### Problem
Every page that fetches data shows a blank white-on-dark "Loading…" or "0 players" state before data arrives. This reads as broken, not loading.

### Acceptance Criteria
- [ ] **Explore page:** While players are loading, show 12 skeleton rows matching the real table row structure (rank number, player name, team flag, role badge, stat columns). Skeleton rows use a pulsing grey animation.
- [ ] **Players page:** While no country/player is selected, show a prompt card (not blank space). After selection, while data loads, show 3–5 skeleton stat cards.
- [ ] **Overview page:** If stat strip data hasn't loaded yet, show 4 skeleton number blocks (grey rectangle placeholders, same dimensions as the real numbers).
- [ ] Skeleton animation: `opacity` pulse between `0.4` and `0.7` on a `1.2s` ease-in-out loop — no shimmer (too distracting on dark bg).
- [ ] Skeleton rows must match the exact column widths of the real table so there is zero layout shift when real data arrives.

### Skeleton Row Structure
```
[  ##  ] [  Player name ████████  ] [ 🏳 Team ███  ] [ ROLE ] [ ███ ] [ ███ ] [ ███ ]
```

### Implementation Notes
```tsx
// SkeletonRow.tsx
const SkeletonRow = () => (
  <tr className="skeleton-row animate-pulse">
    <td><div className="skel-block w-6 h-4" /></td>
    <td><div className="skel-block w-40 h-4" /></td>
    <td><div className="skel-block w-24 h-4" /></td>
    <td><div className="skel-block w-12 h-5 rounded-full" /></td>
    <td><div className="skel-block w-10 h-4" /></td>
    <td><div className="skel-block w-10 h-4" /></td>
    <td><div className="skel-block w-10 h-4" /></td>
  </tr>
);

// In ExplorePage — replace empty/loading state:
{isLoading ? Array.from({length: 12}).map((_, i) => <SkeletonRow key={i} />) : <PlayerRows />}
```

---

## SPEC 3 — Global: Inline Stat Tooltips
**Priority:** P0  
**Files:** New `StatTooltip.tsx` — use in `ExplorePage` table headers, `PlayersPage` stat cards, `OverviewPage` leaderboard column labels

### Problem
Stat abbreviations — xG, xA, xGA, xGI, DINT, TCH, SOT, Big Ch., Pass%, DUELW, CLR, MINS — are used throughout with no inline explanation. The glossary is collapsed at the bottom of every page and requires deliberate navigation to find.

### Acceptance Criteria
- [ ] Every stat abbreviation in a column header, stat card label, or leaderboard metric label renders with a small `ⓘ` icon immediately after the text
- [ ] Hovering/tapping the `ⓘ` shows a tooltip with: **stat name**, one-sentence definition, and unit (e.g. "per 90 mins")
- [ ] Tooltip appears above the trigger by default; flips below if within 80px of the top of the viewport
- [ ] Tooltip disappears on mouse-leave or tap-outside; does not interfere with table row click handlers
- [ ] On mobile, tooltip triggers on tap and dismisses on tap-outside
- [ ] Tooltip background: `#1e1e1e`, border: `1px solid #2a2a2a`, text: `12px`, max-width: `220px`, border-radius: `6px`, padding: `8px 10px`
- [ ] Glossary section at the bottom of pages remains but is collapsed by default (see Spec 4)

### Stat Definitions Dictionary
```ts
// statDefinitions.ts
export const STAT_DEFINITIONS: Record<string, { label: string; definition: string; unit?: string }> = {
  xG:      { label: 'Expected Goals',             definition: 'Quality of chances — likelihood a shot becomes a goal.',          unit: 'per 90 mins' },
  xA:      { label: 'Expected Assists',            definition: 'Likelihood a pass leads to an assist.',                           unit: 'per 90 mins' },
  xGA:     { label: 'Expected Goals Against',      definition: 'Quality of chances a team conceded.',                             unit: 'per game' },
  SOT:     { label: 'Shots on Target',             definition: 'Shots that would score without a save or block.',                 unit: 'total' },
  'Big Ch.':{ label: 'Big Chances Created',        definition: 'Passes that set up a clear scoring opportunity.',                 unit: 'total' },
  TCH:     { label: 'Touches',                     definition: 'Total times a player touched the ball.',                          unit: 'total' },
  'Pass%': { label: 'Pass Completion',             definition: 'Share of attempted passes that were completed.',                  unit: '%' },
  DUELW:   { label: 'Duels Won',                   definition: '1v1 ground and aerial contests won.',                             unit: 'total' },
  DINT:    { label: 'Defensive Interventions',     definition: 'Tackles, interceptions, clearances and blocks combined.',         unit: 'total' },
  CLR:     { label: 'Clearances',                  definition: 'Defensive actions clearing the ball from danger.',                unit: 'total' },
  MINS:    { label: 'Minutes Played',              definition: 'Total minutes played in the tournament.',                         unit: 'mins' },
};
```

### Component API
```tsx
<StatTooltip stat="xG" /> 
// renders: xG ⓘ  — hover shows tooltip card
```

---

## SPEC 4 — Global: Collapse Glossary Footer
**Priority:** P0  
**Files:** `Glossary.tsx` (or wherever the glossary renders)

### Problem
The glossary expands into a large block at the bottom of every page, taking up significant vertical space even though users rarely need it (inline tooltips from Spec 3 handle the common case).

### Acceptance Criteria
- [ ] Glossary renders as a single collapsed row by default: `📖 Glossary — what the stats mean ▾`
- [ ] Clicking/tapping the row toggles expansion; chevron rotates 180° when open
- [ ] Expanded state is the same full content as today
- [ ] Collapse state persists per-session (sessionStorage key: `glossary_open`)
- [ ] Animation: max-height transition `0.2s ease` — no abrupt jump

```tsx
const [open, setOpen] = useState(
  () => sessionStorage.getItem('glossary_open') === 'true'
);
```

---

## SPEC 5 — Global: Data Freshness Timestamp
**Priority:** P1  
**Files:** `OverviewPage.tsx` (stat strip area), optionally `Navbar.tsx`

### Problem
There is no indication of when the displayed data was last updated. Users cannot tell if stats are from today or last week.

### Acceptance Criteria
- [ ] A "Last updated X mins ago" label appears directly below or alongside the stat strip on the Overview page
- [ ] Timestamp is sourced from the most recent data fetch response (use response timestamp or `Date.now()` at fetch completion)
- [ ] Format: `"Last updated 14 mins ago"` for < 60 mins, `"Last updated 2 hrs ago"` for < 24 hrs, `"Last updated Jul 6"` for older
- [ ] Text style: `11px`, colour: `#555` (muted, not competing with stat numbers)
- [ ] Updates in real-time if user leaves the tab open (use `setInterval` every 60s to re-render the relative time string)

---

## SPEC 6 — Overview Page: Latest Matches Widget
**Priority:** P1  
**Files:** New `LatestMatchesWidget.tsx`, import into `OverviewPage.tsx`

### Problem
The homepage has no recent match results. A returning user has no way to see what happened in the most recent games without navigating to `/matches`. This reduces daily return visits.

### Placement
Insert between the **stat strip** and the **Team attacking output chart**.

### Acceptance Criteria
- [ ] Shows the 3 most recently completed matches, ordered newest first
- [ ] If there is an upcoming match within 24 hours, show it as a 4th row with a "kick-off time" badge instead of a score
- [ ] Each match row displays: home team flag + name · score · away team flag + name · status badge (FT / LIVE / kick-off time) · group label
- [ ] "FT" badge: green background `#1a3a2a`, green text `#4caf85`
- [ ] "LIVE" badge: red background `#3a1a1a`, red text `#e05555`, with a pulsing dot
- [ ] Upcoming badge: blue background `#1a2a3a`, blue text `#5599dd`
- [ ] "View all matches →" link at bottom right of widget, routes to `/matches`
- [ ] Section title: `"Latest matches"` — same heading style as `"Team attacking output"`
- [ ] Clicking a match row navigates to `/matches` with that match pre-selected (if match detail view exists)
- [ ] Widget uses same card background as other homepage sections (`#1e1e1e`, `border-radius: 8px`)

### Data
Reuse the same matches data already fetched for `/matches`. No new API call needed — lift state or use existing context/store.

---

## SPEC 7 — Overview Page: Winner Probability Section
**Priority:** P1  
**Files:** New `WinnerProbabilityWidget.tsx`, import into `OverviewPage.tsx`

### Problem
The "World Cup Winner Probability" table exists on `/predict` but is invisible to users who never visit that page. The most universally engaging question during a tournament ("who will win?") has no answer on the homepage.

### Placement
Insert between **Latest Matches widget** (Spec 6) and the **Team attacking output chart**.

### Acceptance Criteria
- [ ] Shows top 3 teams in a podium layout: 2nd place left · 1st place centre (slightly taller card, green accent border) · 3rd place right
- [ ] Crown emoji `👑` floats above the 1st place card (position: absolute, top: -10px)
- [ ] Each podium card shows: country flag emoji · team name · probability % (large, `20px`, `font-weight: 700`) · "win probability" label · mini horizontal bar (width proportional to probability vs. leader)
- [ ] Leader card: border `1.5px solid #c8f135`, probability text colour `#c8f135`
- [ ] Below podium: "Rest of field" — 2-column grid of remaining qualified teams with flag, name, mini bar, percentage. Teams marked "Out" are not shown.
- [ ] Model insight strip: single sentence below the grid explaining the biggest model movement since last update. Background `#1a2800`, border `1px solid #2a3800`. Source this text from a `modelInsight` field in the existing winner probability data, or hardcode a template: `"[Team]'s probability moved from X% → Y% after [result]."` 
- [ ] "Full breakdown →" link routes to `/predict` (scrolls to the winner probability table)
- [ ] Footer label: `"Monte Carlo simulation · updates after every match"` — `10px`, `#444`
- [ ] Section title: `"Tournament winner probability"` with a live model indicator dot (green, pulsing, `6px`)
- [ ] Data source: same data already powering the `/predict` winner probability table — no new API call

---

## SPEC 8 — Overview Page: Leaderboard "See All" Links
**Priority:** P0  
**Files:** `OverviewPage.tsx` — Top scorers, Sharpest finishers, Top creators sections

### Problem
Each leaderboard shows 8 rows and then stops with no path forward. Users who want rank 9+ are stranded.

### Acceptance Criteria
- [ ] Each of the three leaderboard sections (Top scorers, Sharpest finishers, Top creators) has a `"View full leaderboard →"` link in the section header row (right-aligned, same style as other `see-all` links on the site)
- [ ] Top scorers → routes to `/explore` with sort set to `goals desc`
- [ ] Sharpest finishers → routes to `/explore` with sort set to `xG/90 desc`
- [ ] Top creators → routes to `/explore` with sort set to `xA/90 desc`
- [ ] Route params: use query strings e.g. `/explore?sort=xG90&order=desc` and read them in `ExplorePage` to pre-set the sort on mount

---

## SPEC 9 — Overview Page: Chart Legend
**Priority:** P0  
**Files:** `TeamAttackingChart.tsx` (or equivalent)

### Problem
The bar chart uses amber and teal bars with no in-chart legend. The caption "xG vs. conceded (xGA) per game" is `11px` and right-aligned — easy to miss, especially on mobile.

### Acceptance Criteria
- [ ] Add an inline legend inside the chart container, top-right corner: two colour swatches with labels
  - `■` amber `#F5A623` → `"xG (attacking)"`
  - `■` teal `#1D9E75` → `"xGA (defensive)"`
- [ ] Legend font: `11px`, colour: `#888`
- [ ] Remove or demote the right-aligned caption text below the chart — legend replaces it
- [ ] Y-axis label: add a rotated `"per game"` label on the Y axis, `10px`, `#555`
- [ ] No other changes to chart behaviour or data

---

## SPEC 10 — Explore Page: Sort Direction Indicators
**Priority:** P0  
**Files:** `ExplorePage.tsx`, table header component

### Problem
The table appears sortable (Sort by dropdown exists) but column headers show no visual indicator of which column is sorted or in which direction.

### Acceptance Criteria
- [ ] The currently sorted column header renders with an up `↑` or down `↓` arrow immediately after the label text
- [ ] Arrow colour: `#c8f135` (green accent, matches active state elsewhere)
- [ ] Unsorted column headers: no arrow, colour `#888`
- [ ] Clicking a column header that is already the sort key toggles asc/desc
- [ ] Clicking a different column header sorts by that column descending by default
- [ ] Keyboard accessible: column headers are `<button>` or have `role="columnheader"` + `aria-sort="ascending|descending|none"`

---

## SPEC 11 — Explore Page: Player Name Search
**Priority:** P0  
**Files:** `ExplorePage.tsx`

### Problem
With 1,251 players there is no way to find a specific player by name. The only navigation is via team dropdown and position filter.

### Acceptance Criteria
- [ ] A text search input appears in the filter bar, between the position pills and the Sort by dropdown
- [ ] Placeholder: `"Search player name…"`
- [ ] Filters the displayed rows in real-time (on each keystroke, debounced 150ms) — no submit needed
- [ ] Search is case-insensitive, matches on any part of the player name (e.g. "aal" matches "Haaland")
- [ ] Search works in combination with team and position filters (all three filter simultaneously with AND logic)
- [ ] Clear button (×) appears inside the input when text is present; clicking clears the search
- [ ] If no results match, show: `"No players match '[query]'. Try a different name or clear the filters."` — not a blank table
- [ ] Input style: matches existing dropdown style — dark background `#1e1e1e`, border `1px solid #2a2a2a`, text `#ddd`, `border-radius: 6px`, height same as position pills

---

## SPEC 12 — Predictor Page: Progressive Disclosure of XI Builder
**Priority:** P0  
**Files:** `PredictorPage.tsx`, team builder component

### Problem
On page load, 22 empty "— empty —" dropdowns (11 per team) are visible before any team is selected. This is visually overwhelming and gives no sense of what to do first.

### Acceptance Criteria
- [ ] On page load, each team column shows **only** the team selector dropdown. Player position slots are hidden (`display: none` or not mounted).
- [ ] Once a team is selected: the formation selector for that team becomes visible. Position slots remain hidden.
- [ ] Once a formation is selected: the 11 position-specific player dropdowns appear, pre-labelled by position (GK, DEF, DEF, DEF, DEF, MID, MID, MID, FWD, FWD, FWD for 4-3-3 etc.)
- [ ] Auto-pick XI button becomes visible after formation is selected
- [ ] Each step activates independently per team column — Team A can be at step 3 while Team B is still at step 1
- [ ] If user clears team selection: collapse back to step 1 for that column only
- [ ] Transition: `200ms` fade-in when new controls appear (opacity 0 → 1)

### Step States
```
Step 1 (no team):      [Select team... ▾]
Step 2 (team chosen):  [Argentina ▾] [Formation: 4-3-3 ▾]
Step 3 (formation):    [Argentina ▾] [Formation: 4-3-3 ▾] [Auto-pick XI]
                       GK  [— select —]
                       DEF [— select —]
                       ... 10 more position rows
```

---

## SPEC 13 — Predictor Page: Onboarding Hint Bar
**Priority:** P0  
**Files:** `PredictorPage.tsx`

### Problem
First-time visitors see two blank columns with no guidance. There is no indication of the expected workflow.

### Acceptance Criteria
- [ ] A 4-step hint bar appears at the top of the Match Predictor section (above the two team columns), and disappears once both teams have been selected
- [ ] Content: `Step 1: Pick two teams  →  Step 2: Choose formation  →  Step 3: Build your XI  →  Step 4: Predict result`
- [ ] Style: `background: #1a1a1a`, `border: 1px solid #2a2a2a`, `border-radius: 8px`, `padding: 10px 16px`, font `12px`, text colour `#888`, active step accent `#c8f135`
- [ ] Active step highlights when that step is in progress: Step 1 highlighted on load; Step 2 highlights when first team chosen; Step 3 highlights when formation chosen; Step 4 highlights when all 11 players selected for both teams
- [ ] Dismiss button (×) top-right of bar; dismissal stored in `sessionStorage` key `predictor_hint_dismissed`
- [ ] Does not re-appear after dismissal within the same session

---

## SPEC 14 — Predictor Page: Shareable Result URL
**Priority:** P1  
**Files:** `PredictorPage.tsx`, result display component

### Problem
After running a prediction, there is no way to share or bookmark the result. Each prediction is ephemeral.

### Acceptance Criteria
- [ ] After "Predict result →" is clicked and result renders, a `"Copy link"` button appears in the result panel
- [ ] Clicking encodes the current prediction state into the URL as query params and copies the full URL to clipboard
- [ ] URL params to encode: `teamA`, `teamB`, `formationA`, `formationB`, `playersA` (comma-separated IDs), `playersB` (comma-separated IDs), `homeAdvantage`
- [ ] Example: `/predict?teamA=ARG&teamB=FRA&formationA=4-3-3&formationB=4-2-3-1&playersA=123,456,...&homeAdvantage=A`
- [ ] On page load, if these params exist in the URL, auto-populate the builder and auto-run the prediction
- [ ] Copy success: button text changes to `"Copied! ✓"` for 2 seconds then reverts
- [ ] Button style: matches `btn-ghost` pattern on the site — outlined, not filled

---

## SPEC 15 — Predictor Page: Mobile Layout
**Priority:** P1  
**Files:** `PredictorPage.tsx`, team builder CSS

### Problem
The dual side-by-side XI builder requires significant horizontal space. On screens under 768px the layout will overflow or compress to an unusable width.

### Acceptance Criteria
- [ ] At viewport `< 768px`: team columns switch from `flex-row` to a **tabbed layout**
  - Two tabs: `"Team A"` and `"Team B"` rendered as pill tabs above the builder
  - Only one team column visible at a time
  - Tab labels update to show the selected team name once chosen (e.g. `"Argentina"` / `"France"`)
- [ ] At viewport `>= 768px`: existing side-by-side layout unchanged
- [ ] Home advantage bar and Predict result button remain full-width below the tabs on mobile
- [ ] Formation dropdown moves inside each team's tab panel on mobile
- [ ] Tab switching preserves state — selecting Team A players, switching to Team B, then back to Team A retains all Team A selections

---

## SPEC 16 — Matches Page: Stage/Group Filter
**Priority:** P1  
**Files:** `MatchesPage.tsx`

### Problem
All matches are shown in a single list with no way to filter by stage or group, making it slow to find a specific match in a 48-team tournament.

### Acceptance Criteria
- [ ] A filter tab strip appears above the match list: `All  |  Group Stage  |  Round of 16  |  Quarter-finals  |  Semi-finals  |  Final`
- [ ] Selecting a stage shows only matches from that stage
- [ ] Within Group Stage, a secondary filter appears: `All Groups  |  A  |  B  |  C  |  D  |  E  |  F  |  G  |  H  |  I  |  J  |  K  |  L`
- [ ] Active tab: same pill style as Overview nav (white bg, dark text)
- [ ] Default: `All` selected
- [ ] Filter state lives in URL query params (`?stage=r16`, `?stage=group&group=A`) so links are shareable
- [ ] Match count shown next to each tab label: `Group Stage (40)`

---

## SPEC 17 — Matches Page: Predict This Match CTA
**Priority:** P2  
**Files:** `MatchesPage.tsx`, match card component

### Problem
There is no bridge from the Matches page to the Predictor. Users thinking about an upcoming game have no prompt to run a prediction.

### Acceptance Criteria
- [ ] Upcoming matches (not yet played) show a `"Predict →"` button in the right side of the match card
- [ ] Clicking routes to `/predict?teamA=[homeTeam]&teamB=[awayTeam]` with both teams pre-selected
- [ ] Completed matches show a `"Match stats →"` link instead, which scrolls to or expands the stats for that match
- [ ] Button style: `12px`, outlined (`border: 1px solid #2a2a2a`), colour `#888`, hover colour `#c8f135`

---

## SPEC 18 — Standings Page: Qualification Zone Colouring
**Priority:** P0  
**Files:** `StandingsPage.tsx` or group table component

### Problem
The standings table has no visual indication of which teams are qualified or eliminated. Users must count manually.

### Acceptance Criteria
- [ ] Teams in qualifying positions (top 2 in each group for knockout stage) have a left border accent: `3px solid #1D9E75` (teal/green = through)
- [ ] Teams in elimination positions (bottom of group, mathematically out) have a left border accent: `3px solid #e05555` (red = out)
- [ ] Teams still with a chance (middle positions, not yet decided): no accent border
- [ ] A legend appears below the group table: `■ Qualified  ■ Eliminated  □ TBD` with matching colours
- [ ] Row background: qualified rows get a very subtle `rgba(29, 158, 117, 0.06)` background; eliminated rows get `rgba(224, 85, 85, 0.06)` — not distracting, just enough to reinforce colour coding

---

## SPEC 19 — Standings Page: Group Tabs
**Priority:** P0  
**Files:** `StandingsPage.tsx`

### Problem
All groups are shown in a single long scroll. With 12 groups in a 48-team tournament this creates excessive vertical scrolling.

### Acceptance Criteria
- [ ] A tab strip at the top of the Standings page: `All  |  A  |  B  |  C  |  D  |  E  |  F  |  G  |  H  |  I  |  J  |  K  |  L`
- [ ] Selecting a group letter shows only that group's table (hides all others)
- [ ] `All` shows all groups stacked (current behaviour)
- [ ] Active tab: pill highlight, same pattern as nav
- [ ] Active tab stored in URL param: `?group=B` — so links to a specific group are shareable
- [ ] On mobile, tab strip scrolls horizontally if needed (no wrapping)

---

## SPEC 20 — Standings Page: xG Balance Column
**Priority:** P2  
**Files:** `StandingsPage.tsx`, group table component

### Problem
The standings table shows standard W/D/L/GF/GA/GD/Pts columns — identical to every other football site. Adding xG balance would be a genuine differentiator.

### Acceptance Criteria
- [ ] Add one new column: `xG±` (xG balance = xGF − xGA, rounded to 1 decimal)
- [ ] Positive values rendered in teal `#1D9E75` with `+` prefix (e.g. `+2.3`)
- [ ] Negative values rendered in red `#e05555` (e.g. `-1.1`)
- [ ] Zero rendered in `#888`
- [ ] Column header has a `StatTooltip` (Spec 3): `"xG Balance: expected goals scored minus expected goals conceded. Positive = creating more than conceding."`
- [ ] Column is sortable — clicking sorts the group by xG± desc
- [ ] Data already available in the existing dataset — no new API call needed

---

## SPEC 21 — Players Page: Differentiate from Explore
**Priority:** P1  
**Files:** `PlayersPage.tsx`

### Problem
`/players` and `/explore` both show player tables with similar filters. The distinction is unclear to users.

### Acceptance Criteria
- [ ] **`/explore`** becomes the **team-level** view: filter by team + position, see the full player list, sort by any stat column. Purpose: browse and rank all players.
- [ ] **`/players`** becomes the **individual deep-dive** view: select country → select player → see full stat breakdown for that player across the tournament or per match. Purpose: analyse one player in depth.
- [ ] Update the page subtitle on each page to make the distinction explicit:
  - Explore: `"Browse and rank all 1,251 players by any stat"`
  - Players: `"Pick a player to see their full tournament performance"`
- [ ] Players page: after selecting a country and player, show:
  - Summary stat cards (xG/90, xA/90, DUELW, DINT, Pass%, MINS)
  - Per-match breakdown table (match vs. [opponent], date, stats for that match)
  - Position badge and role description

---

## SPEC 22 — Players Page: Player Name Search
**Priority:** P0  
**Files:** `PlayersPage.tsx`  
*(Note: Spec 11 covers search on Explore. This spec covers the Players page.)*

### Problem
The Players page requires selecting a country first, then a player from that country's dropdown. Finding "Haaland" requires knowing he plays for Norway. There is no cross-team name search.

### Acceptance Criteria
- [ ] Add a `"Search any player…"` text input above the country dropdown
- [ ] Typing in the search input shows a dropdown autocomplete list of matching players across all teams, formatted as `"Erling Haaland — Norway · FWD"`
- [ ] Selecting from autocomplete auto-sets the country dropdown and player dropdown, then loads that player's stats
- [ ] Search is case-insensitive, matches on partial name
- [ ] Country + player dropdowns still work independently for users who prefer to browse by team
- [ ] Debounce search input: `200ms`

---

## Implementation Order

| Sprint | Specs | Rationale |
|--------|-------|-----------|
| **1 (Now)** | 1, 2, 3, 4, 8, 9 | Global fixes + homepage leaderboard links — all visible immediately, mostly single-component changes |
| **2** | 10, 11, 12, 13, 18, 19 | Explore sort UX + search, Predictor onboarding, Standings visual treatment — medium complexity |
| **3** | 5, 6, 7, 14, 16 | New components (Latest Matches, Winner Probability on homepage), shareable URLs, Matches filter |
| **4** | 15, 17, 20, 21, 22 | Mobile layout, differentiate Players/Explore, xG± column, player search |

---

## Non-Goals (explicitly out of scope)

- No changes to the visual design language, colour palette, or typography
- No SSR/SSG migration
- No new data sources or API endpoints — all changes use data already fetched
- No authentication or user accounts
- No changes to the model logic (Poisson/Monte Carlo) — UI surface only
- No third-party analytics or tracking

---

## Testing Checklist (per spec)

For each spec, before marking done:
- [ ] Renders correctly at 1440px (desktop)
- [ ] Renders correctly at 768px (tablet)
- [ ] Renders correctly at 390px (mobile, iPhone 14 equivalent)
- [ ] Dark mode only — no light mode regressions (site is dark-only)
- [ ] No layout shift on data load (skeleton → real content swap)
- [ ] Keyboard navigable (tab order logical, focus rings visible)
- [ ] No console errors in production build
- [ ] No new network requests introduced (reuse existing data)