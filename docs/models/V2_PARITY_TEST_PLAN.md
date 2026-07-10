# V2 parity backport — test plan

Companion to [V2_PARITY_BACKPORT.md](V2_PARITY_BACKPORT.md).

---

## 1. Automated tests (CI / local)

```bash
# Core unit + ETL training tests
python3 -m pytest tests/etl/test_train.py tests/etl/test_engines.py tests/etl/test_backtest.py -q

# Predictor shrinkage
python3 -m pytest tests/etl/test_predictor_shrinkage.py -q

# Contract (needs services fixtures)
python3 -m pytest tests/contract/test_split.py -q
```

| Test | Asserts |
|------|---------|
| `test_train_dixon_coles_converges` | Synthetic matrix still converges |
| `test_dc_l2_keeps_params_bounded` | Attack/defence abs max ≤ 3.0 on synthetic sparse data |
| `test_dc_params_centered` | Mean attack ≈ 0, mean defence ≈ 0 |
| `test_xgb_features_use_prematch_stats` | First-row rolling attack diffs are 0 (no same-match leak) |
| `test_rolling_attack_shifted` | Current match stats do not enter same-row rolling means |
| `test_backtest_summary_shape` | Summary has models, metrics, holdout_n |
| `test_low_minute_player_shrinks_toward_ref` | 20-min outlier closer to ref than raw |
| Contract health | `data_updated_at` present; `/api/backtest` 200 or 404 with clear body |

Optional (needs committed parquet):

| Test | Asserts |
|------|---------|
| `test_dc_converges_on_real_match_matrix` | `converged is True` and param abs max ≤ 3.0 |

---

## 2. Manual / operator checks after `make etl-train`

1. **Dixon-Coles artifact**
   ```bash
   python3 -c "import json; d=json.load(open('data/dc_params.json')); \
     print(d['converged'], max(abs(v) for v in d['attack'].values()))"
   ```
   Expect: `True` and max |α| ≲ 2.5.

2. **Backtest summary**
   ```bash
   cat data/backtest_summary.json | python3 -m json.tool | head
   ```
   Expect: `elo` and `dixon_coles` entries with `log_loss`, `accuracy`, `brier`.

3. **Health freshness**
   ```bash
   curl -s localhost:8000/api/predict/health | python3 -m json.tool
   curl -s localhost:8001/api/health | python3 -m json.tool
   ```
   Expect: `data_updated_at` ISO timestamp.

4. **Backtest API**
   ```bash
   curl -s localhost:8000/api/backtest | python3 -m json.tool
   ```

5. **Primary model**
   - POST `/api/predict` without `model` → primary block should be Dixon-Coles
     when DC is available (`model.name == "dixon_coles"`).
   - Quick-predict on homepage fixtures should request `dixon_coles`.

6. **UI**
   - Predict page default selector = Dixon-Coles (when available).
   - Track-record panel shows hold-out metrics when summary exists.

---

## 3. Acceptance criteria

- [ ] All new/updated pytest modules pass without committed data (skip real-data tests if missing).
- [ ] With data: DC train reports `converged=true` and bounded params.
- [ ] XGBoost training features are pre-match only (no same-row xG).
- [ ] Shrinkage reduces influence of sub-45-minute players.
- [ ] `backtest_summary.json` written by train step.
- [ ] Health exposes `data_updated_at`; predict exposes `/api/backtest`.
- [ ] Default predict path prefers Dixon-Coles over Poisson.

---

## 4. Out of scope for this branch

- Full LOOCV / calibration plots in notebooks.
- Retraining and committing new binary artifacts (`xgb_model.ubj`, etc.) —
  left to the next ETL publish run.
- Dropping XGBoost entirely (kept, but leak fixed).
