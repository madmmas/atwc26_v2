# ANALYTICS.md — How the numbers and the prediction work

This document explains **every analytic and the prediction engine** in plain
language, then gives the exact formulas and weights so a reviewer can audit them
and a QA engineer can write assertions against them.

All of this lives in two backend files:
- [backend/app/data.py](backend/app/data.py) — turns raw scraped rows into
  analysis-ready player/team profiles.
- [backend/app/prediction.py](backend/app/prediction.py) — the match predictor.

---

## 1. The data foundation

### Where the data comes from
`etl/scrape/scrape_wc26.py` pulls **per-player, per-game** statistics from ESPN's public
JSON APIs (the rich Opta-style feed: ~140 metrics per player — xG, xA, touches,
duels, defensive actions, goalkeeping, etc.). One scraped **row = one player in
one game**. The combined dataset is `data/all_players_stats.parquet`.

Each row carries:
- **Identity:** `game_id`, `team_name`, `player_id`, `player_name`, `position`,
  `minutes`, `team_score`, `opp_score`, …
- **Stats:** ~140 numeric columns (e.g. `expectedGoals`, `expectedAssists`,
  `touches`, `duelsWon`, `defensiveInterventions`, `saves`, `goalsPrevented`).

### Cleaning (done once at backend startup)
- Every stat column is coerced to numeric (`pd.to_numeric(..., errors="coerce")`)
  because a few arrive as strings.
- `minutes` missing → `0`.
- Each row gets a **role** via `classify_role()` (see below).

Everything downstream reads from cached, derived frames — the parquet is only
read once per process.

---

## 2. Roles (GK / DEF / MID / FWD)

ESPN positions are detailed (e.g. "Center Left Defender", "Attacking Midfielder
Right", "Substitute"). `classify_role(position, abbr)` collapses them into four
buckets used everywhere:

| Role | Matched from |
|---|---|
| **GK** | "goalkeeper", abbr `G` |
| **FWD** | "forward/striker/winger", abbr `CF-L/CF-R/LF/RF/F/ST` |
| **MID** | "midfield", abbr `CM/DM/AM/LM/RM/M` (+ variants) |
| **DEF** | "defender/back/sweeper", abbr `CD/LB/RB/SW` (+ variants) |
| _default_ | **MID** (for ambiguous/substitute rows) |

A player's **dominant role** is the most frequent non-substitute role across
their games.

---

## 3. Per-90 normalization (the core idea)

Counting stats scale with minutes played. To compare a substitute (20 min) with a
starter (90 min) we express counting stats **per 90 minutes**:

```
stat_per90 = stat_total / minutes_total × 90
```

- Applied to **counting** stats (goals, xG, shots, tackles, touches, …).
- **Not** applied to stats that are already rates/percentages
  (`passPct`, `duelWinPct`, `tacklePct`) or to ratings — those are **averaged**.

Player profiles expose both: e.g. `expectedGoals_p90` (rate) and
`expectedGoals_total` (tournament total).

---

## 4. Player profiles  (`_build_player_profiles`)

One row per player, aggregated across all their games:

| Field | Meaning |
|---|---|
| `role`, `team_name`, `games`, `minutes` | identity & sample size |
| `rating` | mean of ESPN's data-feed match rating |
| `*_p90` | per-90 for each tracked counting stat |
| `passPct`, `duelWinPct`, `tacklePct` | mean of rate stats |
| `*_total` | tournament totals for goals, assists, xG, xA |

These power the **Explore** page and all **leaderboards** (sort by any metric,
filter by team/role, with a minutes floor to avoid tiny-sample noise).

---

## 5. Team profiles  (`_build_team_profiles`)

The data is first reduced to **one row per team per game**, then averaged per
team:

| Field | Meaning |
|---|---|
| `goals_per_game`, `conceded_per_game` | scoring / defending rate |
| `xg_per_game`, `xga_per_game` | expected goals for / against |
| `shots_per_game`, `sot_per_game`, `big_chances_per_game` | chance creation |

These feed the **Overview** chart and KPIs.

### League baseline
`avg_team_goals` = mean goals scored by a team in a game across the tournament
(currently ≈ **1.58**). This anchors the prediction model.

---

## 6. The prediction engine

> **In one sentence:** we turn each selected XI into an *attack rating*, a
> *defense rating*, and a *goalkeeping factor*, convert those into an expected
> number of goals for each side, and run a **Poisson goals model** to get
> win/draw/loss probabilities and the most likely scoreline.

This is the standard, well-understood approach to football match prediction. We
keep every step transparent so the output is explainable.

### 6.1 Inputs
Two teams, each a list of `{player_id, role}` (the role = the **slot** the user
assigned in the formation, not necessarily the player's natural position). Plus an
optional `home` flag per team.

### 6.2 Step 1 — raw per-player scores

For each selected outfield player we read their **per-90** profile and compute:

**Raw attack score**
```
attack_raw = 2.00·xG/90 + 1.50·xA/90 + 0.40·bigChanceCreated/90
           + 0.30·shotsOnTarget/90 + 0.12·touchesInOppBox/90
```

**Raw defense score**
```
defense_raw = 0.40·interceptions/90 + 0.35·duelsWon/90 + 0.30·totalClearance/90
            + 0.30·totalTackles/90 + 0.18·ballRecovery/90
            + 0.12·defensiveInterventions/90
```

**Goalkeeper factor** (only the GK slot)
```
gk_raw = 1.0 + 1.2·goalsPrevented/90 + 0.10·saves/90
```
`goalsPrevented` = saves above expectation, the single best shot-stopping signal;
it can be negative for a keeper conceding more than expected.

> Weights live in `ATTACK_WEIGHTS`, `DEFENSE_WEIGHTS`, and `_raw_gk()` in
> `prediction.py`. They are deliberately simple and editable.

### 6.3 Step 2 — normalize so an average player ≈ 1.0

Raw scores are arbitrary units, so we divide each player by the **league average
raw score for their role** (computed once over all players with ≥ 45 minutes):

```
attack_norm  = attack_raw  / ref_attack_by_role[role]
defense_norm = defense_raw / ref_defense_by_role[role]
gk_factor    = gk_raw      / ref_gk
```

Now `1.0` = "an average player in this role"; `1.5` = "50% better than average".

### 6.4 Step 3 — role-weighted team ratings

Each role contributes differently to team attack vs. defense:

| Role | attack weight | defense weight |
|---|---|---|
| GK | — | — (handled by `gk_factor`) |
| DEF | 0.30 | 1.00 |
| MID | 0.70 | 0.70 |
| FWD | 1.00 | 0.25 |

```
team_attack  = Σ (attack_norm  × role_attack_weight)   over outfield players
team_defense = Σ (defense_norm × role_defense_weight)  over outfield players
```

We normalize each sum by the **reference total for the chosen slots** (the sum of
the role weights), so a fully-average XI again lands at `attack_rating ≈ 1.0` and
`defense_rating ≈ 1.0`:

```
attack_rating  = team_attack  / Σ role_attack_weight(slots)
defense_rating = team_defense / Σ role_defense_weight(slots)
```

Here **higher `defense_rating` = better defense** (suppresses opponent goals).

### 6.5 Step 4 — expected goals (Poisson rates)

A team scores more when its **attack** is strong and the opponent's **defense**
and **keeper** are weak:

```
λ_A = avg_team_goals × attack_A / defense_B / gk_B × home_A
λ_B = avg_team_goals × attack_B / defense_A / gk_A × home_B
```

- `avg_team_goals` ≈ 1.58 (tournament baseline).
- `home_X` = 1.10 if that team is flagged home, else 1.0.
- λ is clamped to **[0.2, 5.0]** to keep things realistic.

An average XI vs. an average XI on neutral ground → `λ ≈ 1.58` each, exactly the
tournament norm. Strong attack or a weak opponent pushes it up; vice-versa.

### 6.6 Step 5 — scoreline matrix → probabilities

Goals are modeled as independent **Poisson** variables. The probability of an
exact scoreline _i–j_ is:

```
P(i, j) = Poisson(i; λ_A) × Poisson(j; λ_B)
          where Poisson(k; λ) = e^(−λ) · λ^k / k!
```

We sum over a 9×9 grid (0–8 goals each, `MAX_GOALS = 8`):

- **Win A** = Σ P(i,j) for i > j
- **Draw** = Σ P(i,j) for i = j
- **Win B** = Σ P(i,j) for i < j
- **Most likely score** = the (i,j) with the highest P
- **Top scorelines** = the highest-probability cells

Probabilities are renormalized to sum to 1.0 (they're verified to in tests).

### 6.7 The radar (team-shape comparison)

Five dimensions, each mapped to a 0–100 dial via `_scale(v) = clamp(50·v, 5, 100)`
(so the average team sits near 50):

| Dimension | From |
|---|---|
| Attack | `attack_rating` |
| Creativity | xA/90 + 0.5·bigChanceCreated/90 (aggregated) |
| Possession | touches & passing volume |
| Defense | `defense_rating` |
| Goalkeeping | `gk_factor` |

### 6.8 Worked example (auto-picked Brazil home vs. Germany)

```
Brazil : attack 0.76  defense 0.97  gk 0.96  → xG 2.60  win 19%
Germany: attack 2.63  defense 0.94  gk 0.54  → xG 4.45  win 68%
draw 13%   most likely 2–4
```
Germany's selected players have far higher attacking per-90 output in this
tournament, so the model favours them strongly. (Extreme XIs produce extreme
numbers — that's expected and good for a demo.)

---

## 7. Assumptions & limitations (read before trusting it)

- **Independent Poisson goals.** Real goals are mildly correlated (e.g. game
  state); a Dixon-Coles low-score correction could be added later.
- **Form = tournament per-90.** A player who's played 45 minutes is judged on a
  small sample. Leaderboards apply a minutes floor; the predictor does not, so an
  XI of cameo players can look misleadingly strong/weak.
- **Ratings are relative to *this* tournament**, not all-time strength.
- **Role = the slot you pick**, so you can play anyone anywhere; their *per-90
  numbers* travel with them, not positional context.
- **No fixtures, fatigue, injuries, tactics, or red-card dynamics.**

These are intentional simplifications that keep the model explainable. They are
the first things to improve if this graduates from a demo.

---

## 8. Tuning guide (for contributors)

Everything tunable is a named constant at the top of `prediction.py`:

| Constant | Effect |
|---|---|
| `ATTACK_WEIGHTS` / `DEFENSE_WEIGHTS` | which metrics matter and how much |
| `ROLE_WEIGHTS` | how much each role drives attack vs. defense |
| `HOME_ADVANTAGE` | size of the home bump (1.0 = none) |
| `LAMBDA_CLAMP` | min/max expected goals |
| `MAX_GOALS` | scoreline grid size |

After changing weights, re-run the prediction tests (see
[TESTING.md](TESTING.md)) to confirm probabilities still sum to 1.0 and an
average-vs-average matchup still yields ~1.58 xG per side.
