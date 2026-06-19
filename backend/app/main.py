"""AnalyseThisWC26 — FastAPI application (a NeuNov Technologies demo, neunov.com).

Serves tournament analytics (teams, players, leaderboards) and the player-driven
match-prediction engine to the Next.js frontend.
"""
from __future__ import annotations

import math

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .data import get_store
from .prediction import get_predictor
from .schemas import PredictRequest

app = FastAPI(title=config.APP_NAME, version=config.APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _clean(obj):
    """Recursively replace NaN/inf with None so the JSON is valid."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


@app.on_event("startup")
def _warm() -> None:
    store = get_store()
    get_predictor(store)          # build reference ratings up front


@app.get("/api/health")
def health():
    store = get_store()
    return {"status": "ok", "app": config.APP_NAME, "version": config.APP_VERSION,
            **store.league}


@app.get("/api/overview")
def overview():
    """Tournament headline numbers + quick leaderboards for the landing page."""
    store = get_store()
    players = store.players
    top_scorers = (players.sort_values("totalGoals_total", ascending=False)
                   .head(8)[["player_id", "player_name", "team_name", "flag_url", "role",
                             "totalGoals_total", "expectedGoals_total", "minutes"]]
                   .to_dict("records"))
    top_xg = (players.sort_values("expectedGoals_p90", ascending=False)
              .query("minutes >= 90")
              .head(8)[["player_id", "player_name", "team_name", "flag_url", "role",
                        "expectedGoals_p90", "minutes"]].to_dict("records"))
    top_creators = (players.sort_values("expectedAssists_p90", ascending=False)
                    .query("minutes >= 90")
                    .head(8)[["player_id", "player_name", "team_name", "flag_url", "role",
                              "expectedAssists_p90", "minutes"]].to_dict("records"))
    return _clean({
        "league": store.league,
        "teams": store.teams.to_dict("records"),
        "top_scorers": top_scorers,
        "top_xg_per90": top_xg,
        "top_creators_per90": top_creators,
    })


@app.get("/api/teams")
def teams():
    store = get_store()
    return _clean({"teams": store.teams.to_dict("records")})


@app.get("/api/teams/{team_name}/players")
def team_players(team_name: str):
    store = get_store()
    sub = store.players[store.players["team_name"] == team_name]
    if sub.empty:
        raise HTTPException(404, f"No players found for team '{team_name}'")
    return _clean({
        "team_name": team_name,
        "players": sub.sort_values(["role", "minutes"],
                                   ascending=[True, False]).to_dict("records"),
    })


@app.get("/api/players")
def players(
    team: str | None = None,
    role: str | None = None,
    sort: str = Query("minutes"),
    limit: int = Query(100, le=2000),
):
    store = get_store()
    df = store.players
    if team:
        df = df[df["team_name"] == team]
    if role:
        df = df[df["role"] == role.upper()]
    if sort not in df.columns:
        raise HTTPException(400, f"Unknown sort field '{sort}'")
    df = df.sort_values(sort, ascending=False).head(limit)
    return _clean({"count": int(len(df)), "players": df.to_dict("records")})


@app.get("/api/matches")
def matches():
    """All played matches, most recent first (for Match Analysis)."""
    store = get_store()
    return _clean({"matches": store.matches})


@app.get("/api/matches/{game_id}")
def match_detail(game_id: str):
    store = get_store()
    detail = store.match_detail(game_id)
    if detail is None:
        raise HTTPException(404, f"No match data for game {game_id}")
    return _clean(detail)


@app.get("/api/players/{player_id}")
def player_detail(player_id: int):
    """Per-match breakdown + tournament aggregate for one player."""
    store = get_store()
    detail = store.player_detail(player_id)
    if detail is None:
        raise HTTPException(404, f"No data for player {player_id}")
    return _clean(detail)


@app.get("/api/leaderboard")
def leaderboard(metric: str = Query("expectedGoals_p90"),
                role: str | None = None,
                min_minutes: int = 90,
                limit: int = 20):
    store = get_store()
    df = store.players
    if metric not in df.columns:
        raise HTTPException(400, f"Unknown metric '{metric}'")
    df = df[df["minutes"] >= min_minutes]
    if role:
        df = df[df["role"] == role.upper()]
    df = df.sort_values(metric, ascending=False).head(limit)
    cols = ["player_id", "player_name", "team_name", "flag_url", "role", "minutes", metric]
    return _clean({"metric": metric, "leaders": df[cols].to_dict("records")})


@app.post("/api/predict")
def predict(req: PredictRequest):
    store = get_store()
    predictor = get_predictor(store)
    a = req.team_a.model_dump()
    b = req.team_b.model_dump()
    if not a["players"] or not b["players"]:
        raise HTTPException(400, "Each team needs at least one selected player.")
    return _clean(predictor.predict(a, b))
