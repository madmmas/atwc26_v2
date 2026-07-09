# atwc26_v2 — Next moves (based on Cursor evaluation)
#
# This file contains ONLY the remaining code changes.
# Parts 1–4 (AWS bootstrap, ECS, CloudFront, DNS) are operational
# and must be done by the human in AWS console + GitHub UI.
# This file covers everything that is pure code — no AWS access needed.
#
# Work in this order:
#   A  ci.yml one-line fix          (2 min)
#   B  stage probabilities          (the main feature, ~6 files)
#   C  models.ipynb into repo       (copy file)
#   D  commit untracked ML artifacts (git add)
#
# ═══════════════════════════════════════════════════════════════════
# A — Fix ci.yml simulate trials (one line)
# ═══════════════════════════════════════════════════════════════════
#
# File: .github/workflows/ci.yml
#
# FIND (inside the "etl" job, Transform + QA step):
#           ATWC26_SIMULATE_TRIALS: "100"
# REPLACE WITH:
#           ATWC26_SIMULATE_TRIALS: "1000"
#
# That is the only change in this file.
# etl.yml already uses 1000 — this brings ci.yml in sync.

# ═══════════════════════════════════════════════════════════════════
# B — Stage probabilities (Parts 6A–6G of the production spec)
# ═══════════════════════════════════════════════════════════════════
#
# What we're adding:
#   run_simulation currently returns dict[str, float]  (team → P(title))
#   After this change it returns dict with two keys:
#     "probabilities"      → same dict as before (title probability per team)
#     "stage_probabilities"→ dict[team → dict[round → probability]]
#
#   Example output:
#   {
#     "probabilities": {"Belgium": 0.32, "Spain": 0.20, ...},
#     "stage_probabilities": {
#       "Belgium": {
#         "Round of 16": 1.0,       ← already qualified (real result)
#         "Quarterfinals": 0.89,
#         "Semifinals": 0.74,
#         "Final": 0.54,
#         "title": 0.32
#       },
#       ...
#     }
#   }
#
# The round names come directly from bracket.json "rounds[].name":
#   "Round of 32", "Round of 16", "Quarterfinals",
#   "Semifinals", "Third Place Match", "Final"
# We also track "title" for the winner.

# ───────────────────────────────────────────────────────────────────
# B1 — packages/atwc26_core/atwc26_core/tournament.py
# ───────────────────────────────────────────────────────────────────
#
# CHANGE 1: Return type annotation on line 4
# FIND:
# ) -> dict[str, float]:
# REPLACE WITH:
# ) -> dict:
#
# CHANGE 2: Add stage_reaches counter — insert AFTER line 14 (wins = defaultdict(int)):
# FIND:
#     wins = defaultdict(int)
# REPLACE WITH:
#     wins: defaultdict[str, int] = defaultdict(int)
#     stage_reaches: defaultdict[str, defaultdict[str, int]] = defaultdict(
#         lambda: defaultdict(int)
#     )
#
# CHANGE 3: Track winner per round — insert AFTER line 44 (round_results[(rname,...)] = loser):
# FIND:
#                 round_results[(rname, m["position"], "match_loser")] = loser
#                 if rname == "Final":
#                     champion = winner[1]
# REPLACE WITH:
#                 round_results[(rname, m["position"], "match_loser")] = loser
#                 # Track which round each team reached in this trial
#                 if winner[1]:
#                     stage_reaches[winner[1]][rname] += 1
#                 if rname == "Final":
#                     champion = winner[1]
#
# CHANGE 4: Track title winner — FIND (line 48-49):
#         if champion:
#             wins[champion] += 1
# REPLACE WITH:
#         if champion:
#             wins[champion] += 1
#             stage_reaches[champion]["title"] += 1
#
# CHANGE 5: Replace the entire return block (lines 51-59):
# FIND (the entire block from the comment to the closing brace):
#     # Real (non-simulated) elimination overrides the simulated frequency —
#     # a team can legitimately simulate to 0/trials title wins without being
#     # mathematically out yet (a longshot, not an impossibility); only a real
#     # confirmed elimination should report exactly 0%.
#     real_eliminated = eliminated_teams(store)
#     return {
#         name: 0.0 if name in real_eliminated else wins.get(name, 0) / trials
#         for name in all_names
#     }
# REPLACE WITH:
#     # Real elimination overrides — a team can score 0/trials without being
#     # mathematically eliminated yet; only confirmed real elimination → 0%.
#     real_eliminated = eliminated_teams(store)
#
#     probabilities = {
#         name: 0.0 if name in real_eliminated else wins.get(name, 0) / trials
#         for name in all_names
#     }
#
#     # Per-round reach probabilities. Real results (completed=True) are
#     # already baked into every trial via the completed-match branch, so
#     # teams that have genuinely reached a round will show 1.0 for it.
#     stage_probabilities: dict[str, dict[str, float]] = {}
#     for name in all_names:
#         if probabilities.get(name, 0.0) == 0.0 and name in real_eliminated:
#             continue  # skip truly eliminated teams
#         stages = stage_reaches.get(name, {})
#         if stages:
#             stage_probabilities[name] = {
#                 stage: round(count / trials, 4)
#                 for stage, count in stages.items()
#             }
#
#     return {
#         "probabilities": probabilities,
#         "stage_probabilities": stage_probabilities,
#     }

# ───────────────────────────────────────────────────────────────────
# B2 — etl/simulate/run.py
# ───────────────────────────────────────────────────────────────────
#
# run_simulate() calls run_simulation() and passes the result directly
# to write_winner_probabilities(). We must split it now that the result
# is a dict with two keys.
#
# FIND:
#     probabilities = run_simulation(store, predictor, trials=trials, seed=seed)
#     predictions = predict_bracket_path(store, predictor)
#     generated_at = datetime.now(timezone.utc).isoformat()
#
#     winner_path = write_winner_probabilities(
#         probabilities,
#         trials=trials,
#         seed=seed,
#         generated_at=generated_at,
#     )
# REPLACE WITH:
#     result = run_simulation(store, predictor, trials=trials, seed=seed)
#     probabilities = result["probabilities"]
#     stage_probabilities = result.get("stage_probabilities", {})
#     predictions = predict_bracket_path(store, predictor)
#     generated_at = datetime.now(timezone.utc).isoformat()
#
#     winner_path = write_winner_probabilities(
#         probabilities,
#         stage_probabilities=stage_probabilities,
#         trials=trials,
#         seed=seed,
#         generated_at=generated_at,
#     )
#
# ALSO update the return dict at the bottom — ADD teams_with_stages:
# FIND:
#     return {
#         "trials": trials,
#         "seed": seed,
#         "winner_probabilities": str(winner_path),
#         "bracket_predictions": str(bracket_path),
#         "teams": len(probabilities),
#         "bracket_matches": len(predictions),
#     }
# REPLACE WITH:
#     return {
#         "trials": trials,
#         "seed": seed,
#         "winner_probabilities": str(winner_path),
#         "bracket_predictions": str(bracket_path),
#         "teams": len(probabilities),
#         "teams_with_stages": len(stage_probabilities),
#         "bracket_matches": len(predictions),
#     }

# ───────────────────────────────────────────────────────────────────
# B3 — packages/atwc26_core/atwc26_core/simulation_artifacts.py
# ───────────────────────────────────────────────────────────────────
#
# CHANGE 1: Add stage_probabilities parameter to write_winner_probabilities.
# FIND the full function signature:
# def write_winner_probabilities(
#     probabilities: dict[str, float],
#     *,
#     trials: int,
#     seed: int,
#     generated_at: str,
#     path: Path | None = None,
# ) -> Path:
# REPLACE WITH:
# def write_winner_probabilities(
#     probabilities: dict[str, float],
#     *,
#     stage_probabilities: dict[str, dict[str, float]] | None = None,
#     trials: int,
#     seed: int,
#     generated_at: str,
#     path: Path | None = None,
# ) -> Path:
#
# CHANGE 2: Include stage_probabilities in the payload dict.
# FIND:
#     payload = {
#         "trials": trials,
#         "seed": seed,
#         "generated_at": generated_at,
#         "probabilities": {k: round(float(v), 6) for k, v in probabilities.items()},
#     }
# REPLACE WITH:
#     payload = {
#         "trials": trials,
#         "seed": seed,
#         "generated_at": generated_at,
#         "probabilities": {k: round(float(v), 6) for k, v in probabilities.items()},
#         "stage_probabilities": stage_probabilities or {},
#     }
#
# CHANGE 3: Update load_winner_probabilities to also return stage data.
# The function currently returns dict[str, float] | None.
# We need callers that only want probabilities to keep working unchanged,
# so DO NOT change the return type of load_winner_probabilities.
# Instead, add a NEW function below it:
#
# ADD this new function after load_winner_probabilities:
# def load_stage_probabilities(path: Path | None = None) -> dict[str, dict[str, float]] | None:
#     """Load per-round reach probabilities from winner_probabilities.json."""
#     path = path or config.WINNER_PROBABILITIES
#     if not path.exists():
#         return None
#     try:
#         data = json.loads(path.read_text())
#     except (json.JSONDecodeError, OSError):
#         return None
#     stages = data.get("stage_probabilities")
#     if not isinstance(stages, dict):
#         return None
#     return {
#         str(team): {str(k): float(v) for k, v in rounds.items()}
#         for team, rounds in stages.items()
#         if isinstance(rounds, dict)
#     }
#
# CHANGE 4: Update winner_probabilities_api_payload to include stage data.
# FIND:
# def winner_probabilities_api_payload(
#     probabilities: dict[str, float],
#     *,
#     flag_lookup: Any,
# ) -> dict[str, Any]:
#     """Shape for GET /api/winner-probabilities."""
#     teams = sorted(
#         (
#             {
#                 "team_name": name,
#                 "flag_url": flag_lookup(name),
#                 "probability": round(float(p), 4),
#                 "eliminated": float(p) == 0.0,
#             }
#             for name, p in probabilities.items()
#         ),
#         key=lambda t: -t["probability"],
#     )
#     return {"teams": teams}
# REPLACE WITH:
# def winner_probabilities_api_payload(
#     probabilities: dict[str, float],
#     *,
#     flag_lookup: Any,
#     stage_probabilities: dict[str, dict[str, float]] | None = None,
# ) -> dict[str, Any]:
#     """Shape for GET /api/winner-probabilities."""
#     teams = sorted(
#         (
#             {
#                 "team_name": name,
#                 "flag_url": flag_lookup(name),
#                 "probability": round(float(p), 4),
#                 "eliminated": float(p) == 0.0,
#                 "stage_probabilities": (stage_probabilities or {}).get(name),
#             }
#             for name, p in probabilities.items()
#         ),
#         key=lambda t: -t["probability"],
#     )
#     return {"teams": teams}

# ───────────────────────────────────────────────────────────────────
# B4 — packages/atwc26_core/atwc26_core/api_cache/builders.py
# ───────────────────────────────────────────────────────────────────
#
# build_winner_probabilities() calls winner_probabilities_api_payload.
# We need to pass stage_probabilities to it.
#
# FIND the full build_winner_probabilities function:
# def build_winner_probabilities(
#     store: ..., manifest: dict, ...
# ) -> ...:
#     from ..simulation_artifacts import load_winner_probabilities, winner_probabilities_api_payload
#     from ..tournament import get_winner_probabilities
#
#     probs = load_winner_probabilities()
#     if probs is None:
#         probs = get_winner_probabilities(store)
#     payload = winner_probabilities_api_payload(probs, flag_lookup=store.flag)
#     source_sha = _artifact_hash(manifest, "winner_probabilities")
#     return payload, source_sha, ["winner_probabilities"]
# REPLACE WITH:
# def build_winner_probabilities(
#     store: ..., manifest: dict, ...
# ) -> ...:
#     from ..simulation_artifacts import (
#         load_winner_probabilities,
#         load_stage_probabilities,
#         winner_probabilities_api_payload,
#     )
#     from ..tournament import get_winner_probabilities
#
#     probs = load_winner_probabilities()
#     if probs is None:
#         probs = get_winner_probabilities(store)
#     stage_probs = load_stage_probabilities()   # None if not yet generated
#     payload = winner_probabilities_api_payload(
#         probs,
#         flag_lookup=store.flag,
#         stage_probabilities=stage_probs,
#     )
#     source_sha = _artifact_hash(manifest, "winner_probabilities")
#     return payload, source_sha, ["winner_probabilities"]
#
# NOTE: Do NOT change the function signature of build_winner_probabilities
# (name, parameters) — only the body. The caller in analytics/main.py
# passes (store, manifest) which remains correct.

# ───────────────────────────────────────────────────────────────────
# B5 — services/analytics_api/analytics_api/main.py
# ───────────────────────────────────────────────────────────────────
#
# The _fallback() inside the winner_probabilities endpoint calls
# winner_probabilities_api_payload without stage_probabilities.
# Update it to also load stage data.
#
# FIND inside the winner_probabilities endpoint function:
#     def _fallback():
#         store = get_store()
#         payload, _, _ = builders.build_winner_probabilities(store, {})
#         if payload is None:
#             probs = load_winner_probabilities() or get_winner_probabilities(store)
#             payload = winner_probabilities_api_payload(probs, flag_lookup=store.flag)
# REPLACE WITH:
#     def _fallback():
#         from atwc26_core.simulation_artifacts import load_stage_probabilities
#         store = get_store()
#         payload, _, _ = builders.build_winner_probabilities(store, {})
#         if payload is None:
#             probs = load_winner_probabilities() or get_winner_probabilities(store)
#             stage_probs = load_stage_probabilities()
#             payload = winner_probabilities_api_payload(
#                 probs,
#                 flag_lookup=store.flag,
#                 stage_probabilities=stage_probs,
#             )

# ───────────────────────────────────────────────────────────────────
# B6 — frontend/lib/api.ts
# ───────────────────────────────────────────────────────────────────
#
# CHANGE 1: Add StageProbabilities type — INSERT before WinnerProbability:
# FIND:
# export type WinnerProbability = {
# INSERT BEFORE IT:
# export type StageProbabilities = {
#   "Round of 32"?:       number;
#   "Round of 16"?:       number;
#   "Quarterfinals"?:     number;
#   "Semifinals"?:        number;
#   "Third Place Match"?: number;
#   "Final"?:             number;
#   title?:               number;
# };
#
# CHANGE 2: Add stage_probabilities to WinnerProbability:
# FIND:
# export type WinnerProbability = {
#   team_name: string;
#   flag_url?: string | null;
#   probability: number;
#   eliminated: boolean;
# };
# REPLACE WITH:
# export type WinnerProbability = {
#   team_name: string;
#   flag_url?: string | null;
#   probability: number;
#   eliminated: boolean;
#   stage_probabilities?: StageProbabilities | null;
# };

# ───────────────────────────────────────────────────────────────────
# B7 — tests/etl/test_simulate.py
# ───────────────────────────────────────────────────────────────────
#
# The existing test calls run_simulate() and checks the result dict.
# run_simulate() return shape hasn't changed (still has "teams" key).
# But winner_probabilities.json now has a "stage_probabilities" key.
# Add one assertion to the existing test function.
#
# FIND inside test_run_simulate_writes_artifacts, AFTER:
#     winner_doc = json.loads((data_dir / "winner_probabilities.json").read_text())
#     assert winner_doc["trials"] == 20
#     assert winner_doc["seed"] == 1
# ADD:
#     # Stage probabilities present after simulation
#     assert "stage_probabilities" in winner_doc
#     # At least the surviving teams should have stage data
#     alive = {t for t, p in winner_doc["probabilities"].items() if p > 0}
#     stages = winner_doc["stage_probabilities"]
#     # Every alive team should appear in stage_probabilities
#     for team in alive:
#         assert team in stages, f"{team} missing from stage_probabilities"
#         # title probability should match probabilities dict
#         title_p = stages[team].get("title", 0.0)
#         assert abs(title_p - winner_doc["probabilities"][team]) < 1e-4, (
#             f"{team}: stage title={title_p} != probabilities={winner_doc['probabilities'][team]}"
#         )

# ───────────────────────────────────────────────────────────────────
# B8 — Run tests and verify
# ───────────────────────────────────────────────────────────────────
#
# After all B1–B7 changes, run:
#
#   ATWC26_SIMULATE_TRIALS=50 PYTHONPATH=. pytest tests/etl/test_simulate.py -v
#   # All tests must pass before proceeding
#
#   make etl-simulate
#   # Verify winner_probabilities.json now has stage_probabilities:
#   python3 -c "
#   import json; from pathlib import Path
#   wp = json.loads(Path('data/winner_probabilities.json').read_text())
#   print('keys:', sorted(wp.keys()))
#   alive = [t for t,p in wp['probabilities'].items() if p > 0]
#   print('alive:', alive)
#   for t in alive[:2]:
#       print(t, wp['stage_probabilities'].get(t))
#   "
#   # Expected output:
#   # keys: ['generated_at', 'probabilities', 'seed', 'stage_probabilities', 'trials']
#   # Belgium {'Round of 16': 1.0, 'Quarterfinals': 0.89, 'Semifinals': 0.74, 'Final': 0.54, 'title': 0.322}

# ═══════════════════════════════════════════════════════════════════
# C — Add models.ipynb to the repo
# ═══════════════════════════════════════════════════════════════════
#
# The models.ipynb notebook was built and is available as a downloaded file.
# Copy it into notebooks/:
#
#   notebooks/models.ipynb   ← NEW file (26 cells, full model deep-dive)
#
# This notebook references data/elo_ratings.json, data/dc_params.json,
# data/xgb_model.ubj, data/xgb_features.json — all of which exist locally.
#
# Verify it runs before committing:
#   jupyter nbconvert --to notebook --execute notebooks/models.ipynb \
#     --inplace --ExecutePreprocessor.timeout=120
#   # Should complete without errors.
#
# If ML artifacts are not present locally, run first:
#   make etl-train
#   # Then re-run the notebook execution above.

# ═══════════════════════════════════════════════════════════════════
# D — Commit untracked ML artifacts
# ═══════════════════════════════════════════════════════════════════
#
# These files exist locally but are untracked (not in .gitignore, just
# never git-added). They are needed for notebooks and for the predict
# service when it first cold-starts without a live S3 bucket.
#
# Check which exist:
#   ls data/elo_ratings.json data/dc_params.json data/xgb_model.ubj data/xgb_features.json
#
# If any are missing, regenerate:
#   make etl-train
#
# Add to git (they're small JSON + binary, fine to track):
#   git add data/elo_ratings.json data/dc_params.json \
#           data/xgb_features.json data/xgb_model.ubj
#
# NOTE: data/xgb_model.ubj is a binary file (~50 KB). This is acceptable
# for a showcase repo. If it grows in future tournaments, move to Git LFS.

# ═══════════════════════════════════════════════════════════════════
# E — Single commit for everything
# ═══════════════════════════════════════════════════════════════════
#
#   git add \
#     .github/workflows/ci.yml \
#     packages/atwc26_core/atwc26_core/tournament.py \
#     etl/simulate/run.py \
#     packages/atwc26_core/atwc26_core/simulation_artifacts.py \
#     packages/atwc26_core/atwc26_core/api_cache/builders.py \
#     services/analytics_api/analytics_api/main.py \
#     frontend/lib/api.ts \
#     tests/etl/test_simulate.py \
#     notebooks/models.ipynb \
#     data/elo_ratings.json \
#     data/dc_params.json \
#     data/xgb_features.json \
#     data/xgb_model.ubj
#
#   git commit -m "feat: stage probabilities in simulation + models notebook + ML artifacts"
#   git push
#
# CI will run and the ETL job will exercise the changed tournament.py.
# The next scheduled ETL run (or a manual workflow_dispatch → etl.yml)
# will publish the enriched winner_probabilities.json to S3/DynamoDB.

# ═══════════════════════════════════════════════════════════════════
# VERIFICATION CHECKLIST (run after commit + CI passes)
# ═══════════════════════════════════════════════════════════════════
#
# 1. CI green:
#    gh run list --workflow ci.yml --limit 3
#    # All checks: etl, contract, v2-smoke must pass
#
# 2. Stage probabilities in JSON:
#    python3 -c "
#    import json; from pathlib import Path
#    wp = json.loads(Path('data/winner_probabilities.json').read_text())
#    assert 'stage_probabilities' in wp
#    alive = [t for t,p in wp['probabilities'].items() if p > 0]
#    for t in alive:
#        sp = wp['stage_probabilities'].get(t, {})
#        title = sp.get('title', 0)
#        prob  = wp['probabilities'][t]
#        assert abs(title - prob) < 1e-4, f'{t}: title={title} prob={prob}'
#    print(f'OK: {len(alive)} alive teams, stage_probabilities consistent')
#    "
#
# 3. API response includes stage_probabilities:
#    # Locally (after make analytics):
#    curl -s http://localhost:8001/api/winner-probabilities | \
#      python3 -c "import json,sys; d=json.load(sys.stdin); \
#      t=d['teams'][0]; print(t['team_name'], t.get('stage_probabilities'))"
#    # Expected: Belgium {'Round of 16': 1.0, 'Quarterfinals': 0.89, ...}
#
# 4. TypeScript compiles (no type errors):
#    cd frontend && npx tsc --noEmit
#    # Expected: no output (no errors)
#
# 5. models.ipynb executes cleanly:
#    jupyter nbconvert --to notebook --execute notebooks/models.ipynb \
#      --inplace --ExecutePreprocessor.timeout=120
#    # Expected: exits 0, no "Error" cells in output