# ATWC26 — Page Section Navigation Spec

**For:** Cursor AI-assisted implementation
**Pages:** `/predict` (tabs) · `/standings` (sticky anchor bar)
**Date:** July 2026
**Replaces:** atwc26-tab-spec.md

> **STATUS: SHIPPED.** `PredictTabs` + `StandingsAnchorBar` are live. Treat this
> file as the design record; for the current page map see
> [WEBAPP_README.md](../WEBAPP_README.md). Acceptance checkboxes below are
> historical — do not re-implement from the “What exists today” sections.

---

## Design decision rationale

The two pages have different section relationships, so they get different
navigation patterns:


| Page         | Pattern                      | Why                                                                                                                                                                   |
| ------------ | ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/predict`   | **Tab switcher**             | Two sections serve independent intents. No data relationship between them. User is in one mode or the other — never both.                                             |
| `/standings` | **Sticky scroll-anchor bar** | The two sections are data-linked: editing a group score updates the bracket. Both sections must stay mounted simultaneously. Tabs would break the what-if simulation. |


---



## PART 1 — `/predict` — Tab Switcher



### What exists today

Two sections stacked vertically with a hard scroll between them:

```
┌─────────────────────────────────────────────┐
│  World Cup Winner Probability               │  ← Section 1 (~600px tall)
│  Bar chart · all 48 teams · Monte Carlo     │
│  "Show all 48 teams" toggle                 │
│  Methodology footnote                       │
└─────────────────────────────────────────────┘
            ↓ continuous scroll ↓
┌─────────────────────────────────────────────┐
│  Match Predictor                            │  ← Section 2
│  4-step hint bar                            │
│  Dual team builder (22 dropdowns)           │
│  Home advantage · Model selector            │
│  Predict result →                           │
└─────────────────────────────────────────────┘
```



### Target layout

```
┌─────────────────────────────────────────────────────────┐
│  NAV                                                    │
├─────────────────────────────────────────────────────────┤
│  Predictor                                              │
│  Explore win probabilities or build a match prediction. │
├─────────────────────────────────────────────────────────┤
│  [ 🏆 Winner Probability ]  [ ⚽ Match Predictor ]      │  ← tab bar
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Active tab content only                               │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---



### P1-1 — Tab Definitions


| Tab ID        | Label                | Icon | Default |
| ------------- | -------------------- | ---- | ------- |
| `probability` | `Winner Probability` | 🏆   | **Yes** |
| `predictor`   | `Match Predictor`    | ⚽    | No      |


**Default is** `probability` — it loads instantly, requires no interaction,
and answers the most universal tournament question. The predictor is active
and multi-step; it earns its place after the user has seen the data.

---



### P1-2 — Behaviour

- [ ] Only the active tab's content is **mounted**. The inactive tab is
  ```
  fully unmounted — not `display:none`. This means the Predictor's
  22 dropdowns do not initialise until the user explicitly opens
  that tab.
  ```
- [ ] Switching tabs scrolls the viewport to `#predict-top`
  ```
  (the page header anchor — see P1-4).
  ```
- [ ] Active tab is reflected in the URL:
  ```
  - `?tab=probability` → Winner Probability (default)
  - `?tab=predictor` → Match Predictor
  - No param → defaults to `probability`
  ```
- [ ] Direct navigation to `/predict?tab=predictor` opens the Match
  ```
  Predictor immediately — used by the homepage "Build a match →" CTA.
  ```
- [ ] Tab selection persists within session:
  ```
  `sessionStorage.setItem('predict_active_tab', tabId)`
  ```
- [ ] Switching tabs does **not** reset Match Predictor form state.
  ```
  If teams/formation/players are selected, switching to Probability
  and back must restore them exactly. Use a state-lifting pattern
  or context — do not re-initialise the predictor component on
  re-mount.

  ```tsx
  // Pattern: lift predictor state to PredictPage level
  // so it survives the tab's unmount/remount cycle

  const [predictorState, setPredictorState] = useState(initialPredictorState);

  {activeTab === 'predictor' && (
    <MatchPredictorSection
      state={predictorState}
      onChange={setPredictorState}
    />
  )}
  ```
  ```

---



### P1-3 — Tab Bar Visual Spec

```
Active tab:
  color: #ffffff
  font-weight: 600
  border-bottom: 2px solid #c8f135    ← green accent
  background: transparent

Inactive tab:
  color: #888888
  font-weight: 400
  border-bottom: 2px solid transparent
  background: transparent

Hover (inactive):
  color: #cccccc
  transition: color 0.15s ease

Tab bar container:
  display: flex
  border-bottom: 1px solid #2a2a2a
  margin-bottom: 28px
  gap: 0

Each tab <button>:
  padding: 12px 24px
  font-size: 14px
  border: none
  cursor: pointer
  display: inline-flex
  align-items: center
  gap: 6px
  margin-bottom: -1px        ← overlaps container border cleanly

Tab icon:
  font-size: 15px
```

No border-radius on tabs — flat underline style consistent with the
existing site nav pattern.

---



### P1-4 — Page Header

Remove the separate `<h2>` headings inside each section ("World Cup Winner
Probability" and "Match Predictor") since the tab labels serve that function.

Replace with a single page header **above the tab bar**:

```
id="predict-top"

h1:  Predictor
p:   Explore tournament win probabilities or build your own match prediction.
```

- `h1` size: same as "Player explorer" / "Match Analysis" on other pages
- Subtitle: `14px`, `#888888`, single line

---



### P1-5 — Winner Probability Tab — Content (unchanged)

Render the existing "World Cup Winner Probability" section exactly as today:

- Country flag · team name · probability % · horizontal progress bar
- Eliminated teams labelled "Out" with grey bar
- "Show all 48 teams" toggle
- Methodology footnote: *"Estimated from 10,000 simulated tournaments…"*
- Top-right label: *"Monte Carlo simulation · updates after every finished match"*

No changes to data, layout, or internal logic.

---



### P1-6 — Match Predictor Tab — Content (unchanged)

Render the existing "Match Predictor" section exactly as today:

- 4-step hint bar with dismiss ×
- Dual team columns (Team A left, Team B right)
- Per team: team selector → formation → XI position dropdowns
- Auto-pick XI button
- Home advantage toggle (Neutral / Team A / Team B)
- Model selector dropdown ("Compare all models")
- "Predict result →" button
- Result panel below builder after submission

No changes to data, layout, or internal logic.

---



### P1-7 — Homepage CTA Update

At the same time as implementing this spec, update the homepage
"Build a match →" button `href` from `/predict` to `/predict?tab=predictor`.

File: wherever the homepage hero CTAs are defined (likely `OverviewPage.tsx`
or `HeroSection.tsx`).

```tsx
// Before
<a href="/predict">Build a match →</a>

// After
<a href="/predict?tab=predictor">Build a match →</a>
```

---



### P1-8 — Mobile (< 768px)

Tab labels shorten on narrow viewports — CSS-only, no JS:


| Viewport | Tab 1 label        | Tab 2 label     |
| -------- | ------------------ | --------------- |
| ≥ 768px  | Winner Probability | Match Predictor |
| < 768px  | Probability        | Predictor       |


```tsx
<button className="predict-tab" ...>
  <span className="tab-icon">🏆</span>
  <span className="label-full">Winner Probability</span>
  <span className="label-short">Probability</span>
</button>
```

```css
.label-short { display: none; }
.label-full  { display: inline; }

@media (max-width: 767px) {
  .label-short { display: inline; }
  .label-full  { display: none; }
}
```

---



### P1-9 — Accessibility

- [ ] Tab bar container: `role="tablist"`
- [ ] Each tab `<button>`: `role="tab"`, `aria-selected="true|false"`,
  ```
  `aria-controls="tabpanel-{id}"`
  ```
- [ ] Each panel `<div>`: `role="tabpanel"`, `id="tabpanel-{id}"`,
  ```
  `aria-labelledby="tab-{id}"`
  ```
- [ ] Arrow keys `←` `→` move focus between tab buttons when focus is
  ```
  inside the tablist
  ```
- [ ] `Enter` / `Space` activates the focused tab
- [ ] Focus ring must not be suppressed (`outline` visible on keyboard nav)

---



### P1-10 — Files to Touch


| Action     | File                                                                         |
| ---------- | ---------------------------------------------------------------------------- |
| **Modify** | `PredictPage.tsx` — add tab bar, split into two panels, lift predictor state |
| **Create** | `components/PredictTabs.tsx` — tab bar component (local to this page)        |
| **Modify** | `OverviewPage.tsx` or `HeroSection.tsx` — update "Build a match →" href      |


> The tab component for `/predict` does **not** need to be the same shared
> component as any future tabs on other pages — keep it local to avoid
> over-engineering. `/standings` uses a completely different pattern (below).

---



### P1-11 — Acceptance Criteria

- [ ] Page loads with Winner Probability active, Match Predictor unmounted
- [ ] Clicking "Match Predictor" mounts predictor, scrolls to `#predict-top`
- [ ] Clicking "Winner Probability" unmounts predictor, shows probability
- [ ] Predictor form state (teams, formation, XI) survives tab switch and return
- [ ] URL updates to `?tab=predictor` / `?tab=probability` on switch
- [ ] `/predict?tab=predictor` opens predictor on direct load
- [ ] Homepage "Build a match →" links to `/predict?tab=predictor`
- [ ] Works at 1440px, 768px, 390px
- [ ] Arrow key navigation works between the two tabs
- [ ] No console errors on mount/unmount of either panel

---

---



## PART 2 — `/standings` — Sticky Scroll-Anchor Bar



### Why NOT tabs here

The Group Standings section has a live what-if feature: the user can type a
predicted score into a future fixture row and the Knockout Bracket **updates
in real time** to reflect the changed outcomes. This is the most interactive
and distinctive feature of the Standings page.

If the two sections are in separate tabs, the bracket is unmounted while the
user edits group scores — the live update stops working. The two sections
**must both be mounted simultaneously** for this to function.

A **sticky scroll-anchor bar** solves the scroll problem without breaking the
data relationship: both sections stay in the DOM, both stay reactive, and the
user can jump between them instantly with a single click.

---



### What exists today

```
┌─────────────────────────────────────────────┐
│  Knockout Bracket                           │  ← Section 1
│  (full bracket, R16→QF→SF→Final+3rd,        │
│   FT scores in green, predicted scores,     │
│   confidence bars, Download + Share)        │
│                                             │
│  Legend / footnote text                     │
└─────────────────────────────────────────────┘
            ↓ continuous scroll (~800px) ↓
┌─────────────────────────────────────────────┐
│  Group Standings                            │  ← Section 2
│  (subtitle + what-if instruction,           │
│   All/A–L group filter tabs,                │
│   3-column group card grid,                 │
│   GP/W/D/L/F/A/GD/P/xG± columns,           │
│   score input fields per fixture)           │
└─────────────────────────────────────────────┘
```



### Target layout

```
┌─────────────────────────────────────────────────────────┐
│  NAV                                                    │
├─────────────────────────────────────────────────────────┤  ← sticks here
│  [ 🗂 Knockout Bracket ↑ ]  [ 📊 Group Standings ↓ ]   │  ← STICKY BAR
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ── Knockout Bracket section ──────────────────────     │
│  id="standings-bracket"                                 │
│  (full bracket, Download, Share, legend)                │
│                                                         │
│  ── Group Standings section ───────────────────────     │
│  id="standings-groups"                                  │
│  (subtitle, All/A–L filter, group cards, score inputs)  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

Both sections are **always mounted**. The sticky bar is purely navigational —
clicking a button smoothly scrolls to the target section.

---



### P2-1 — Sticky Bar Definitions


| Button   | Label              | Icon | Scrolls to           |
| -------- | ------------------ | ---- | -------------------- |
| Button 1 | `Knockout Bracket` | 🗂   | `#standings-bracket` |
| Button 2 | `Group Standings`  | 📊   | `#standings-groups`  |


---



### P2-2 — Sticky Behaviour

- [ ] The bar sticks to the top of the viewport once the user scrolls past
  ```
  the page header — `position: sticky; top: 0` (or `top: nav-height`
  if the main nav is also sticky — measure the nav height and set
  `top` accordingly, e.g. `top: 56px`).
  ```
- [ ] The bar sits **below the main nav** and **above the bracket section**.
- [ ] Clicking "Knockout Bracket" → smooth scrolls to `#standings-bracket`.
- [ ] Clicking "Group Standings" → smooth scrolls to `#standings-groups`.
- [ ] Both sections are always in the DOM — neither is hidden or unmounted.
- [ ] **Active button highlight** — the button corresponding to whichever
  ```
  section is currently **most visible** in the viewport gets the active
  style. Use an `IntersectionObserver` on both section anchors to
  determine which is in view.

  ```tsx
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id); // 'standings-bracket' | 'standings-groups'
          }
        });
      },
      { threshold: 0.3 }   // section is "active" when 30% visible
    );

    observer.observe(document.getElementById('standings-bracket'));
    observer.observe(document.getElementById('standings-groups'));
    return () => observer.disconnect();
  }, []);
  ```
  ```

- [ ] Scroll behaviour: `element.scrollIntoView({ behavior: 'smooth', block: 'start' })`.
  ```
  Account for sticky bar + nav height offset using `scroll-margin-top`
  on each section anchor:

  ```css
  #standings-bracket,
  #standings-groups {
    scroll-margin-top: 104px;  /* nav height (56px) + sticky bar height (~48px) */
  }
  ```
  ```

- [ ] URL hash updates on scroll past each section:
  ```
  - Scrolling into bracket → URL becomes `/standings#bracket`
  - Scrolling into groups → URL becomes `/standings#groups`
  - On page load with `#groups` hash → auto-scrolls to Group Standings
  ```

---



### P2-3 — Sticky Bar Visual Spec

```
Bar container:
  position: sticky
  top: 56px              ← adjust to actual nav height
  z-index: 20
  background: #111111    ← same as page background, prevents content bleed-through
  border-bottom: 1px solid #2a2a2a
  display: flex
  padding: 0 0           ← full width, buttons have own padding
  margin-bottom: 0       ← sections start immediately below

Active button:
  color: #ffffff
  font-weight: 600
  border-bottom: 2px solid #c8f135
  background: transparent

Inactive button:
  color: #888888
  font-weight: 400
  border-bottom: 2px solid transparent
  background: transparent

Hover (inactive):
  color: #cccccc

Each <button>:
  padding: 12px 24px
  font-size: 14px
  border: none (except bottom)
  cursor: pointer
  display: inline-flex
  align-items: center
  gap: 6px
  transition: color 0.15s, border-bottom-color 0.15s
  margin-bottom: -1px
```

Visually identical to the `/predict` tab bar — same underline style, same
active accent colour, same font treatment. Consistent language across the
two pages even though the underlying mechanism differs.

---



### P2-4 — Page Header

Add a unified page header **above the sticky bar** (not inside either section):

```
id="standings-top"

h1:  Standings
p:   Follow the knockout bracket and group tables — edit scores to simulate outcomes.
```

- Same size and style as other page titles
- Subtitle references the what-if feature so users understand why both
sections are connected

Remove the current "Knockout Bracket" card-level title and "Group Standings"
h2 — the sticky bar buttons now serve those navigation labels. The bracket
card can retain a smaller internal label if needed for the Download/Share
button row context.

---



### P2-5 — Section Anchors

Add `id` attributes to the outermost wrapper of each section:

```tsx
{/* Section 1 */}
<div id="standings-bracket" className="standings-section">
  {/* existing KnockoutBracket component, unchanged */}
  <KnockoutBracket />
</div>

{/* Section 2 */}
<div id="standings-groups" className="standings-section">
  {/* existing GroupStandings component, unchanged */}
  <GroupStandings />
</div>
```

No other changes to the internal content of either section.

---



### P2-6 — What-if Feature — Preserved

The Group Standings subtitle currently reads:

> *"Real group tables from every played match. Try a score for the remaining
> fixture(s) below any group to see how the table — and the knockout bracket
> above — would change. Predictions aren't saved, reload to reset."*

The phrase "knockout bracket above" is still accurate after this change —
the bracket is literally above the group tables in the page. **No copy
changes needed.**

The score input fields in each group card and the real-time bracket update
logic are completely untouched — no changes to state, data flow, or event
handlers.

---



### P2-7 — Download & Share Buttons

The existing Download and Share buttons on the Knockout Bracket are preserved
in their current position (top right of the bracket card). No changes.

---



### P2-8 — Mobile (< 768px)

Button labels shorten on narrow viewports — CSS only:


| Viewport | Button 1         | Button 2        |
| -------- | ---------------- | --------------- |
| ≥ 768px  | Knockout Bracket | Group Standings |
| < 768px  | Bracket          | Groups          |


Same CSS pattern as P1-8:

```tsx
<button className="standings-anchor-btn" ...>
  <span className="tab-icon">🗂</span>
  <span className="label-full">Knockout Bracket</span>
  <span className="label-short">Bracket</span>
</button>
```

On mobile the sticky bar must not overlap the main nav if the main nav
is also sticky — test this at 390px and adjust `top` value accordingly.

---



### P2-9 — Accessibility

- [ ] Sticky bar container: `role="navigation"`, `aria-label="Page sections"`
- [ ] Each button: `aria-current="true"` when its section is the active one
  ```
  in viewport; `aria-current="false"` otherwise
  ```
- [ ] Each section div: `aria-labelledby` pointing to the corresponding
  ```
  button's `id` if needed for screen reader context
  ```
- [ ] Keyboard: Tab key moves between the two buttons; Enter/Space triggers
  ```
  the scroll. No arrow key requirement (this is navigation, not a tablist)
  ```
- [ ] Smooth scroll respects `prefers-reduced-motion`:
  ```
  ```css
  @media (prefers-reduced-motion: reduce) {
    html { scroll-behavior: auto; }
  }
  ```
  ```

---



### P2-10 — URL Hash Behaviour


| User action                        | URL result                              |
| ---------------------------------- | --------------------------------------- |
| Loads `/standings`                 | `/standings` (no hash, bracket visible) |
| Clicks "Group Standings" button    | `/standings#groups`                     |
| Scrolls back up to bracket         | `/standings#bracket`                    |
| Direct load of `/standings#groups` | Auto-scrolls to group tables on load    |


Implement hash sync with `window.history.replaceState` on scroll:

```tsx
// In the IntersectionObserver callback
if (entry.isIntersecting) {
  const hash = entry.target.id === 'standings-bracket' ? '#bracket' : '#groups';
  window.history.replaceState(null, '', hash);
  setActiveSection(entry.target.id);
}
```

On mount, read the hash and scroll if present:

```tsx
useEffect(() => {
  const hash = window.location.hash;
  if (hash === '#groups') {
    document.getElementById('standings-groups')?.scrollIntoView({ behavior: 'smooth' });
  }
}, []);
```

---



### P2-11 — Files to Touch


| Action                 | File                                                                                               |
| ---------------------- | -------------------------------------------------------------------------------------------------- |
| **Modify**             | `StandingsPage.tsx` — add page header, sticky bar, section `id` anchors, IntersectionObserver hook |
| **Create**             | `components/StandingsAnchorBar.tsx` — sticky bar component                                         |
| **Create** (or inline) | `hooks/useActiveSection.ts` — IntersectionObserver hook returning active section id                |


---



### P2-12 — Acceptance Criteria

- [ ] Sticky bar appears below the nav, above the bracket, on page load
- [ ] Bar stays visible (sticky) as user scrolls through both sections
- [ ] Clicking "Knockout Bracket" smoothly scrolls to the bracket section
- [ ] Clicking "Group Standings" smoothly scrolls to the group tables
- [ ] Active button highlight updates automatically as user scrolls between sections
- [ ] Both sections are always mounted — bracket updates when group scores change
- [ ] URL hash updates as user scrolls: `#bracket` / `#groups`
- [ ] `/standings#groups` direct load auto-scrolls to group tables
- [ ] Content is not obscured by the sticky bar (scroll-margin-top correct)
- [ ] Works at 1440px, 768px, 390px
- [ ] Reduced-motion: scroll is instant (not smooth) when `prefers-reduced-motion` is set
- [ ] No console errors

---

---



## PART 3 — Shared Visual Language

Even though `/predict` uses tabs (unmount/mount) and `/standings` uses a
sticky anchor bar (both always mounted), the two bars must look **visually
identical** to the user:

- Same button padding and font size
- Same active underline: `2px solid #c8f135`
- Same inactive text colour: `#888`
- Same hover colour: `#ccc`
- Same container border: `1px solid #2a2a2a` along the bottom
- Same icon + label layout

The only functional difference is internal — tabs control mounting,
the anchor bar controls scroll position.

---



## PART 4 — What NOT to Change

- [ ] No changes to data fetching, API calls, or state management beyond
  ```
  what's described above
  ```
- [ ] No changes to the existing Group filter tabs (All / A–L) inside
  ```
  the Group Standings section — they remain a secondary filter within
  that section
  ```
- [ ] No changes to bracket data, bracket layout, or bracket click-to-match behaviour
- [ ] No changes to the Predictor form logic, model selector, or result display
- [ ] No changes to Winner Probability data or bar chart layout
- [ ] No changes to any other page (Overview, Explore, Matches, Players)