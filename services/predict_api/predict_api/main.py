"""AnalyseThisWC26 predict API — match outcome prediction."""
from __future__ import annotations

import os as _os
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
from atwc26_core.prediction import get_predictor
from atwc26_core.schemas import PredictRequest
from services.shared.json_util import clean_json
from services.shared.predict_bootstrap import build_predictor_store, ensure_predictor_data

_RELOAD_SECRET = _os.getenv("ATWC26_RELOAD_SECRET", "")
_reload_lock = threading.Lock()

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


_store: object | None = None


def _get_store():
    global _store
    if _store is None:
        _store = build_predictor_store()
    return _store


@app.get("/api/health")
def health():
    store = _get_store()
    return {
        "status": "ok",
        "service": "predict",
        "app": config.APP_NAME,
        "version": config.APP_VERSION,
        **store.league,
    }


@app.post("/api/predict")
def predict(req: PredictRequest):
    store = _get_store()
    predictor = get_predictor(store)
    a = req.team_a.model_dump()
    b = req.team_b.model_dump()
    if not a["players"] or not b["players"]:
        raise HTTPException(400, "Each team needs at least one selected player.")
    return clean_json(predictor.predict(a, b))


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
        return {
            "status": "reloaded",
            "updated": updated,
            "players": len(_store.predictor_players),
        }
    finally:
        _reload_lock.release()
