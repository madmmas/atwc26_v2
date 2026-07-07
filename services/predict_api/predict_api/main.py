"""AnalyseThisWC26 predict API — match outcome prediction."""
from __future__ import annotations

import sys
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

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from atwc26_core import config
from atwc26_core.data import get_store
from atwc26_core.prediction import get_predictor
from atwc26_core.schemas import PredictRequest
from services.shared.bootstrap import ensure_data_available
from services.shared.json_util import clean_json

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
    ensure_data_available()
    store = get_store()
    get_predictor(store)


@app.get("/api/health")
def health():
    store = get_store()
    return {
        "status": "ok",
        "service": "predict",
        "app": config.APP_NAME,
        "version": config.APP_VERSION,
        **store.league,
    }


@app.post("/api/predict")
def predict(req: PredictRequest):
    store = get_store()
    predictor = get_predictor(store)
    a = req.team_a.model_dump()
    b = req.team_b.model_dump()
    if not a["players"] or not b["players"]:
        raise HTTPException(400, "Each team needs at least one selected player.")
    return clean_json(predictor.predict(a, b))
