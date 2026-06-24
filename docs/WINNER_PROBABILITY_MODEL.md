# WINNER_PROBABILITY_MODEL.md — World Cup winner probability

This document explains how each team's "chance of winning the World Cup"
percentage (shown on the Predictor page, above the match predictor) is
computed, why this is a reasonable estimate given the data available, and
what would make it more accurate.

All of this lives in [backend/app/tournament.py](../backend/app/tournament.py),
reusing the rating math in
[backend/app/prediction.py](../backend/app/prediction.py) — nothing here is a
separate model; it's the same per-90, history-blended player ratings that
power the head-to-head match predictor, just run forward thousands of times
instead of once.

---

## 1. What it computes

For every one of the 48 WC26 teams: the fraction of simulated tournaments in
which that team wins the Final. This is exposed at `GET /api/winner-probabilities`
and rendered by `frontend/components/WinnerProbabilityChart.tsx`.

It is recomputed once per backend process (at startup, via `_warm()` in
`main.py`) and cached for the life of that process — the same pattern
`prediction.py`'s `get_predictor` already uses. The existing data-refresh
cron restarts the backend after every `make refresh`/`refresh-full` cycle,
so "rerun after every finished match" falls directly out of that existing
restart, with no separate scheduling added.

A team that's actually eliminated (not just unlikely to win) is forced to
exactly **0%** — see §5.

---

## 2. Method: Monte Carlo tournament simulation

This is the standard approach for "probability of winning a whole
tournament" (the same technique FiveThirtyEight/Opta-style models use) —
chosen over trying to compute it analytically because the cross-group
"best 8 of 12 third-placed teams" qualification rule creates dependencies
between all 12 groups that are awkward to solve in closed form, while
random simulation handles it for free.

One **trial** = one full hypothetical run of the rest of the tournament:

1. **Simulate the real remaining group matches.** Each group's already-played
   results (GP/W/D/L/F/A/GD/P, from `data/standings.json`, real ESPN data) are
   the fixed starting point. For each group's still-unplayed fixture(s), draw
   a random scoreline (§3) and add it to that group's table, then re-rank by
   Points → Goal Difference → Goals Scored — the exact same tiebreak and the
   exact same arithmetic as the live standings page
   (`frontend/components/GroupTable.tsx`'s `applyHypotheticalResults`, ported
   to Python as `simulate_group_stage`/`qualifying_third_place`), so the
   simulator and the page you can manually experiment with agree with each
   other.
2. **Walk the real knockout bracket, in order**, Round of 32 → Round of 16 →
   Quarterfinals → Semifinals → Final (+ 3rd-place match). For each fixture
   not yet actually played, resolve who's actually in it (§4), then simulate
   it (§3, with no draws allowed). For a fixture that's *already* really been
   played, its real result is used as-is, not re-simulated.
3. Record who wins the Final.

Repeat for `trials = 10_000` (the default in `tournament.py`), then
`probability(team) = times_won / trials`.

**Why 10,000 trials**: empirically verified — two independent 10,000-trial
runs (different random seeds) of the current tournament state produced
probabilities for all 48 teams differing by at most **0.47 percentage
points**. That's tight enough for the leading contenders to be meaningfully
distinguishable. Longshot teams with a true probability under ~0.1% are
noisier at this trial count — see §5's note on that.

---

## 3. Simulating one match

```
lambda_a = avg_goals * attack_a / defense_b / gk_b
lambda_b = avg_goals * attack_b / defense_a / gk_a
goals_a  = Poisson(lambda_a)
goals_b  = Poisson(lambda_b)
```

This is **exactly** `Predictor.predict()`'s formula in `prediction.py` —
same `attack`/`defense`/`gk` ratings (from each team's auto-picked best XI,
§4 below), same `avg_goals` baseline (which itself already blends in ~1 year
of qualifier/friendly history via `store.predictor_avg_goals`). The only
difference: `predict()` reports the *expected* scoreline for a single
head-to-head comparison; the simulator draws an actual random scoreline from
that same distribution, because a tournament's outcome depends on the
sequence of actual results, not just their average.

**No home advantage is applied** here (see §5 — this is a deliberate
simplification, not an oversight).

**Knockout draws**: a tied Poisson draw can't happen in a real knockout
match (extra time + penalties resolve it). Modeled as a coin flip weighted
by each side's expected-goal share (`lambda_a / (lambda_a + lambda_b)`) — a
reasonable proxy for "the side that was expected to score more is slightly
more likely to win it," not an actual penalty-shootout model.

---

## 4. Team strength and bracket resolution

### Team strength, computed once
A team's rating doesn't change between trials — only match *outcomes* are
randomized. So each of the 48 teams' best XI is auto-picked once per
process (`auto_pick_xi()`, a Python port of the frontend's `autoFill` in
`predict/page.tsx`: best-by-minutes per role, falling back across roles if
a team is short at a position) and rated once via the existing
`Predictor._rate_team()`. This keeps 10,000 trials × ~56 matches/trial fast
(~6 seconds total) since only the cheap Poisson draw repeats per trial, not
the rating computation.

### Resolving who's actually in a future bracket match
This is the part that needed real verification, not assumption. ESPN
publishes the entire Round-of-32-through-Final fixture skeleton in advance,
with each not-yet-decided slot encoded as a placeholder — e.g. `abbreviation:
"2A"` (Group A runner-up), `"3RD"` with `displayName: "Third Place Group
A/B/C/D/F"` (one of the four third-place wildcard slots), or later-round text
like `"Round of 32 3 Winner"`.

**Confirmed empirically** (not assumed): a later round's reference number
("Round of 32 **3** Winner") is exactly that round's **1-indexed position**
in ESPN's own discovery order. Verified for every link in the chain — R32→R16,
R16→QF, QF→SF, SF→Final, SF→3rd-place ("Loser") — every reference number in
every later round matched its source round's position with zero exceptions,
across all 32 knockout fixtures. This means the entire bracket can be wired
up purely from ESPN's own data, with **no hardcoded FIFA bracket-sheet
table** required anywhere in this codebase.

`etl/scrape/fetch_groups.py`'s `parse_slot()` turns every slot into one of
four explicit types at scrape time:
- `group_rank` (`{group, rank}`) — resolved against that trial's (real +
  simulated) group order.
- `third_place` (`{candidate_groups}`) — resolved by checking which of its
  named candidate groups has a 3rd-placed team inside the simulated
  top-8-of-12 pool (§5's tiebreak applies here too).
- `match_winner` / `match_loser` (`{round, position}`) — resolved by
  looking up that exact `(round, position)` in the current trial's own
  results-so-far (built up as the simulator walks rounds in order).
- `team` — already a real, decided team; used as-is.

---

## 5. Documented simplifications (why this is the *best feasible* accuracy, not perfect accuracy)

- **Group/third-place tiebreak**: Points → Goal Difference → Goals Scored
  only. Official FIFA rules also use head-to-head results and disciplinary
  (card) points as later tiebreakers — skipped because disciplinary points
  aren't even in our scraped dataset, and head-to-head adds real complexity
  for a rare edge case. Same scope decision as the standings page, so the
  two stay consistent with each other.
- **Neutral venues, no home advantage.** ESPN's `homeAway` label on a World
  Cup fixture isn't a real home-advantage signal for 45 of 48 teams (it's
  schedule/admin metadata) — the genuine exception is the three co-hosts
  (USA/Canada/Mexico) playing in their own country, which would need
  venue-city-to-team-country matching we don't do yet. Left out entirely
  rather than applied incorrectly to teams it doesn't apply to.
- **Knockout draws resolved by a weighted coin flip**, not a penalty-shootout
  model — see §3.
- **History window**: `store.predictor_players` blends in whatever
  `scrape_history.py` pulled (~1 year of qualifiers/friendlies), flat —
  a match from 11 months ago counts the same as one from last week. A
  team's *current* form could differ from that blended average.
- **Trial-count precision floor**: a team that wins 0/10,000 simulated
  tournaments shows 0.0% *only if* it's also confirmed eliminated by real
  data (§ below). A team that's still mathematically alive but extremely
  unlikely (true probability somewhere under ~0.05%) can also land on
  exactly 0/10,000 by chance alone — that's an honest precision limit of
  10,000 trials, not a claim that they're impossible. Raising the trial
  count narrows this floor at the cost of slower startup.

### Eliminated teams show exactly 0%, distinctly from "very unlikely"
`eliminated_teams()` in `tournament.py` computes this from **real data
only**, never from simulation noise:
1. Lost a real, already-completed knockout match.
2. Finished 4th in an already-finished real group — always eliminated,
   independent of every other group (4th place never competes for a
   third-place wildcard slot).
3. Finished 3rd in an already-finished real group but missed the real
   best-8-of-12 cutoff — only assessable once **every** group has finished,
   since that cutoff is inherently cross-group.

This was a real bug caught during testing, not a hypothetical: an earlier
version of this module forced 0% for any team that simply never reached the
Round of 32 across 10,000 trials. Two genuinely-still-alive-but-weak teams
(Panama, Tunisia) reached the Round of 32 in a meaningful fraction of trials
yet won 0/10,000 simulated tournaments outright — the old logic mislabeled
them "eliminated" when they were just longshots. Fixed by deriving
elimination from real standings/bracket data exclusively, never from a
simulation count.

---

## 6. What would increase accuracy further

Roughly in order of expected impact for the effort involved:

1. **Recency-weighted form** instead of a flat ~1-year blend — e.g. an
   Elo-style decay so a team's last few matches count more than one from
   11 months ago. Currently the single biggest known gap between this model
   and how a human pundit would actually weigh form.
2. **Real host-nation home advantage** (USA/Canada/Mexico in their own
   country) via venue-city-to-team-country matching — currently omitted
   entirely rather than guessed.
3. **Head-to-head and disciplinary-points tiebreakers** for the genuinely
   rare cases where Points/GD/Goals-scored alone doesn't separate two teams
   — low frequency, but would make the group-stage edge cases exactly match
   the official rules instead of an documented approximation.
4. **A real penalty-shootout sub-model** (e.g. a fixed ~50/50 with a small
   goalkeeping-rating adjustment, calibrated against real shootout base
   rates) instead of the expected-goal-share coin flip used for knockout
   draws now.
5. **More trials** (e.g. 50,000–100,000) to push the longshot-team precision
   floor down further — straightforward, just slower to (re)compute at
   startup.
6. **More historical data sources** — currently only ESPN's qualifier/friendly
   coverage for the last year; additional competitions (e.g. continental
   cups, more friendlies further back) would widen the sample, especially
   for teams with thin WC26 minutes so far.
