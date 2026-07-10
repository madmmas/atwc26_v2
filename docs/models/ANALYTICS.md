# ANALYTICS.md — How the numbers and the prediction work

This document explains **every analytic and the prediction engines** in plain
language, then gives the exact formulas and weights so a reviewer can audit them
and a QA engineer can write assertions against them.

**Code locations (v2 canonical):**
- [`packages/atwc26_core/atwc26_core/data.py`](../../packages/atwc26_core/atwc26_core/data.py) — turns raw scraped rows into analysis-ready player/team profiles.
- [`packages/atwc26_core/atwc26_core/prediction.py`](../../packages/atwc26_core/atwc26_core/prediction.py) — Poisson XI predictor (with minutes shrinkage).
- [`packages/atwc26_core/atwc26_core/engines/`](../../packages/atwc26_core/atwc26_core/engines/) — Elo, Dixon-Coles, XGBoost engines + registry.
- [`etl/train/`](../../etl/train/) — fits Elo / Dixon-Coles / XGBoost; writes artifacts + backtest summary.

v1 mirrors live under `backend/app/` (same formulas; used by the monolith until cutover).

Shipped model-quality work (DC L2, XGB leak fix, backtest, DC-as-primary): [V2_PARITY_BACKPORT.md](V2_PARITY_BACKPORT.md).

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

### Cleaning (done once at DataStore load)
- Every stat column is coerced to numeric (`pd.to_numeric(..., errors="coerce")`)
  because a few arrive as strings.
- `minutes` missing → `0`.
- Each row gets a **role** via `classify_role()` (see below).

Everything downstream reads from cached, derived frames — the parquet is only
read once per process (or once per Lambda/ECS warm container after S3 sync).

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
(currently ≈ **1.58**). This anchors the Poisson XI model.

---

## 6. Prediction engines (multi-model)

> **In one sentence:** the predict API exposes four engines — **Dixon-Coles**
> (primary when available), **Poisson** (XI-based), **Elo**, and **XGBoost**.
> Omitting `model` runs all available engines and returns a comparison block;
> the **primary** result prefers Dixon-Coles, then Poisson, Elo, XGBoost
> (`PRIMARY_MODEL_ORDER` in `services/predict_api`).

| Engine | Artifact / input | What it models |
|--------|------------------|----------------|
| `dixon_coles` | `data/dc_params.json` | Team attack/defence + home; bivariate Poisson with τ correction |
| `poisson` | In-memory player profiles | User-built XIs → role-weighted ratings → independent Poisson scorelines |
| `elo` | `data/elo_ratings.json` | Rating gap → win/draw/loss |
| `xgboost` | `data/xgb_model.ubj` + `xgb_features.json` | Classifier on pre-match team features |

Frontend defaults (model selector, homepage quick-predict) follow the same
Dixon-Coles-first rule. Track record: `GET /api/backtest` + `TrackRecordPanel`
on `/predict` (see [V2_PARITY_BACKPORT.md](V2_PARITY_BACKPORT.md)).

### 6.0 Dixon-Coles (primary)

Fitted in `etl/train/dixon_coles.py` by MLE with:
- **L2** penalty on attack/defence (`L2_LAMBDA = 1.0`) so sparse international
  panels stay bounded.
- **Centering** after fit: `sum(α)=0`, `sum(β)=0` for identifiability.
- `converged` flag persisted in `dc_params.json`; tests refuse unbounded params
  (`MAX_ABS_PARAM = 3.0`).

At inference, the engine builds a scoreline matrix with the Dixon-Coles τ
low-score correction (not independent Poisson).

### 6.1 Poisson XI model — inputs
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

### 6.2b Minutes shrinkage (Empirical Bayes)

Before role-weighted aggregation, each player's per-90 **rates** used in scoring
are shrunk toward the role reference:

```
w = minutes / (minutes + k)   # k = MINUTES_SHRINK_K = 45
rate_shrunk = w * rate + (1 - w) * role_ref
```

Low-minute cameos therefore pull less weight than full starters. Leaderboards
still apply an explicit minutes floor for ranking; the predictor uses shrinkage
instead of a hard floor.

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

Goals are modeled as independent **Poisson** variables (Poisson engine only).
The probability of an exact scoreline _i–j_ is:

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

### 6.8 XGBoost features (no same-match leak)

**Training** uses **rolling pre-match** attack stats (`add_rolling_attack_stats`
in `etl/train/features.py`), shifted like form — never the current match's
xG/shots — plus rolling form (`h_form3` / `a_form3`).

**Inference** (`XGBoostEngine`) builds a related but not identical vector:
tournament per-90 XI sums for `xg_diff` / `shots_diff` / `sot_diff`, plus Elo
gap, DC attack/defence ratios, and home flag. `form3_wins` is not populated by
the predict API today, so `h_form3` / `a_form3` are typically **0** at serve
time. Same-match label leakage is fixed; a residual train/serve feature gap
remains for form (and XI p90 vs rolling attack means).

### 6.9 Out-of-sample backtest

`etl/eval/backtest.py` (invoked from `etl/train/run.py`) chronological 80/20
split → Elo + Dixon-Coles metrics → `data/backtest_summary.json`. Exposed at
`GET /api/backtest` on the predict service. See [ops/TESTING.md](../ops/TESTING.md).

**Publish note:** `backtest_summary.json` is written by train and registered in
`ARTIFACTS` (`packages/atwc26_core/.../artifacts.py`), so ETL publish uploads it
with other model artifacts. Predict loads it via `atwc26_core.backtest_io`
(no ETL package on Lambda/ECS). Served at `GET /api/backtest` (API Gateway →
predict).

### 6.10 Worked example (auto-picked Brazil home vs. Germany, Poisson engine)

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

- **Poisson engine uses independent goals.** Real goals are mildly correlated;
  the **Dixon-Coles** engine (primary) applies the τ low-score correction.
- **Form = tournament per-90 + shrinkage.** Cameo minutes are shrunk toward
  role references (`MINUTES_SHRINK_K = 45`); leaderboards still use a hard
  minutes floor for ranking.
- **Ratings are relative to *this* tournament**, not all-time strength (history
  blend helps the predictor sample, not a full Elo history for every nation).
- **Role = the slot you pick**, so you can play anyone anywhere; their *per-90
  numbers* travel with them, not positional context.
- **No fixtures, fatigue, injuries, tactics, or red-card dynamics.**

These are intentional simplifications that keep the model explainable.

---

## 8. Tuning guide (for contributors)

Everything tunable for the Poisson XI path is a named constant at the top of
`prediction.py`:

| Constant | Effect |
|---|---|
| `ATTACK_WEIGHTS` / `DEFENSE_WEIGHTS` | which metrics matter and how much |
| `ROLE_WEIGHTS` | how much each role drives attack vs. defense |
| `HOME_ADVANTAGE` | size of the home bump (1.0 = none) |
| `LAMBDA_CLAMP` | min/max expected goals |
| `MAX_GOALS` | scoreline grid size |
| `MINUTES_SHRINK_K` | Empirical-Bayes prior strength (minutes) |

Dixon-Coles training: `L2_LAMBDA`, `MAX_ABS_PARAM` in `etl/train/dixon_coles.py`.

After changing weights, re-run prediction / train tests (see
[TESTING.md](../ops/TESTING.md) and [V2_PARITY_TEST_PLAN.md](V2_PARITY_TEST_PLAN.md)).
Retrain with `make etl-train` so `dc_params.json`, `xgb_model.ubj`, and
`backtest_summary.json` match the new code.
