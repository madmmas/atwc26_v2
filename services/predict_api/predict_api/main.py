"""AnalyseThisWC26 predict API — match outcome prediction."""
from __future__ import annotations

import sys
import threading
from pathlib import Path


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in (here.parent, *here.parents):
        if (parent / "services" / "shared").is_dir():
            return parent
    return here.parents[3]


_REPO_ROOT = _repo_root()
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from atwc26_core import config
from atwc26_core.engines import available_engines, load_engines
from atwc26_core.prediction import get_predictor
from atwc26_core.schemas import PredictRequest
from services.shared.json_util import clean_json
from services.shared.predict_bootstrap import build_predictor_store, ensure_predictor_data
from services.shared.freshness import data_updated_at
from atwc26_core.backtest_io import load_backtest_summary

_RELOAD_SECRET = config.RELOAD_SECRET
_reload_lock = threading.Lock()

PRIMARY_MODEL_ORDER = ("dixon_coles", "poisson", "elo", "xgboost")

app = FastAPI(title=f"{config.APP_NAME} Predict", version=config.APP_VERSION)

if config.use_cors_middleware():
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )


@app.on_event("startup")
def _warm() -> None:
    global _store
    ensure_predictor_data()
    _store = build_predictor_store()
    get_predictor(_store)
    load_engines(_store)


_store: object | None = None


def _get_store():
    global _store
    if _store is None:
        _store = build_predictor_store()
    return _store


def _health_payload() -> dict:
    store = _get_store()
    payload = {
        "status": "ok",
        "service": "predict",
        "app": config.APP_NAME,
        "version": config.APP_VERSION,
        "models_available": list(available_engines().keys()),
        **store.league,
    }
    updated = data_updated_at()
    if updated:
        payload["data_updated_at"] = updated
    return payload


@app.get("/api/health")
def health():
    return _health_payload()


@app.get("/api/predict/health")
def predict_health():
    """Routed via API Gateway on CloudFront (GET /api/health hits analytics)."""
    return _health_payload()


@app.post("/api/predict")
def predict(req: PredictRequest):
    a = req.team_a.model_dump()
    b = req.team_b.model_dump()
    if not a["players"] or not b["players"]:
        raise HTTPException(400, "Each team needs at least one selected player.")

    store = _get_store()
    _enrich_players(a["players"], store)
    _enrich_players(b["players"], store)

    engines = available_engines()
    if not engines:
        raise HTTPException(503, "No prediction models available.")

    model_name = req.model
    if model_name:
        engine = engines.get(model_name)
        if engine is None:
            raise HTTPException(
                400,
                f"Model '{model_name}' not available. Available: {list(engines.keys())}",
            )
        return clean_json(engine.predict(a, b))

    results = {}
    for name, engine in engines.items():
        try:
            results[name] = engine.predict(a, b)
        except Exception as exc:
            results[name] = {"error": str(exc)}

    primary_name = next(
        (name for name in PRIMARY_MODEL_ORDER if name in results and "error" not in results[name]),
        next(iter(results)),
    )
    primary = results[primary_name]
    return clean_json({
        **primary,
        "comparison": {
            name: {
                "win_probability_a": r.get("win_probability_a"),
                "draw_probability": r.get("draw_probability"),
                "win_probability_b": r.get("win_probability_b"),
                "model_name": r.get("model", {}).get("name"),
            }
            for name, r in results.items()
            if "error" not in r
        },
    })


@app.get("/api/backtest")
def backtest():
    """Return the latest out-of-sample backtest summary (written by etl-train)."""
    summary = load_backtest_summary()
    if summary is None:
        raise HTTPException(404, "No backtest summary found. Run make etl-train first.")
    return clean_json(summary)


def _enrich_players(player_selections: list[dict], store) -> None:
    """Attach per-90 stats to each player selection dict in-place."""
    players_df = store.predictor_players.set_index("player_id")
    p90_cols = [c for c in players_df.columns if c.endswith("_p90")]
    for sel in player_selections:
        pid = sel.get("player_id")
        if pid in players_df.index:
            row = players_df.loc[pid]
            for col in p90_cols:
                sel[col] = float(row.get(col, 0) or 0)


@app.post("/api/predict/reload")
def reload_predictor(request: Request):
    """
    Hot-reload player profiles from S3 and rebuild the Predictor.
    Called by ETL publish after new player_profiles.parquet is uploaded.
    No container restart needed.
    """
    from atwc26_core import prediction as _pred

    if _RELOAD_SECRET:
        if request.headers.get("X-Reload-Secret", "") != _RELOAD_SECRET:
            raise HTTPException(403, "Invalid reload secret")

    if not _reload_lock.acquire(blocking=False):
        return {"status": "reload_in_progress"}

    try:
        updated = ensure_predictor_data()
        global _store
        _store = build_predictor_store()
        _pred._predictor = None
        get_predictor(_store)
        load_engines(_store)
        return {
            "status": "reloaded",
            "updated": updated,
            "players": len(_store.predictor_players),
        }
    finally:
        _reload_lock.release()
