"""AnalyseThisWC26 analytics API — tournament data and leaderboards."""
from __future__ import annotations

import sys
from pathlib import Path

# Repo root on path for services.shared (local dev + Lambda zip layout).
def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in (here.parent, *here.parents):
        if (parent / "services" / "shared").is_dir():
            return parent
    return here.parents[3]


_REPO_ROOT = _repo_root()
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from atwc26_core import config
from atwc26_core.data import get_store
from atwc26_core.tournament import get_bracket_predictions
from services.shared.bootstrap import ensure_data_available
from services.shared.json_util import clean_json

app = FastAPI(title=f"{config.APP_NAME} Analytics", version=config.APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _warm() -> None:
    ensure_data_available()
    store = get_store()
    get_bracket_predictions(store)


@app.get("/api/health")
def health():
    store = get_store()
    return {
        "status": "ok",
        "service": "analytics",
        "app": config.APP_NAME,
        "version": config.APP_VERSION,
        **store.league,
    }


@app.get("/api/overview")
def overview():
    store = get_store()
    players = store.players
    top_scorers = (
        players.sort_values("totalGoals_total", ascending=False)
        .head(8)[
            [
                "player_id",
                "player_name",
                "team_name",
                "flag_url",
                "role",
                "totalGoals_total",
                "expectedGoals_total",
                "minutes",
            ]
        ]
        .to_dict("records")
    )
    top_xg = (
        players.sort_values("expectedGoals_p90", ascending=False)
        .query("minutes >= 90")
        .head(8)[
            [
                "player_id",
                "player_name",
                "team_name",
                "flag_url",
                "role",
                "expectedGoals_p90",
                "minutes",
            ]
        ]
        .to_dict("records")
    )
    top_creators = (
        players.sort_values("expectedAssists_p90", ascending=False)
        .query("minutes >= 90")
        .head(8)[
            [
                "player_id",
                "player_name",
                "team_name",
                "flag_url",
                "role",
                "expectedAssists_p90",
                "minutes",
            ]
        ]
        .to_dict("records")
    )
    return clean_json(
        {
            "league": store.league,
            "teams": store.teams.to_dict("records"),
            "top_scorers": top_scorers,
            "top_xg_per90": top_xg,
            "top_creators_per90": top_creators,
        }
    )


@app.get("/api/teams")
def teams():
    store = get_store()
    return clean_json({"teams": store.teams.to_dict("records")})


@app.get("/api/teams/{team_name}/players")
def team_players(team_name: str):
    store = get_store()
    sub = store.players[store.players["team_name"] == team_name]
    if sub.empty:
        raise HTTPException(404, f"No players found for team '{team_name}'")
    return clean_json(
        {
            "team_name": team_name,
            "players": sub.sort_values(
                ["role", "minutes"], ascending=[True, False]
            ).to_dict("records"),
        }
    )


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
    return clean_json({"count": int(len(df)), "players": df.to_dict("records")})


@app.get("/api/matches")
def matches():
    store = get_store()
    return clean_json({"matches": store.matches})


@app.get("/api/matches/{game_id}")
def match_detail(game_id: str):
    store = get_store()
    detail = store.match_detail(game_id)
    if detail is None:
        raise HTTPException(404, f"No match data for game {game_id}")
    return clean_json(detail)


@app.get("/api/players/{player_id}")
def player_detail(player_id: int):
    store = get_store()
    detail = store.player_detail(player_id)
    if detail is None:
        raise HTTPException(404, f"No data for player {player_id}")
    return clean_json(detail)


@app.get("/api/standings")
def standings():
    store = get_store()
    return clean_json({"groups": store.standings})


@app.get("/api/bracket")
def bracket():
    store = get_store()
    preds = get_bracket_predictions(store)
    result = {
        "rounds": [
            {
                **round_def,
                "matches": [
                    {**m, "prediction": preds.get(str(m["game_id"]))}
                    for m in round_def["matches"]
                ],
            }
            for round_def in store.bracket.get("rounds", [])
        ]
    }
    return clean_json(result)


@app.get("/api/leaderboard")
def leaderboard(
    metric: str = Query("expectedGoals_p90"),
    role: str | None = None,
    min_minutes: int = 90,
    limit: int = 20,
):
    store = get_store()
    df = store.players
    if metric not in df.columns:
        raise HTTPException(400, f"Unknown metric '{metric}'")
    df = df[df["minutes"] >= min_minutes]
    if role:
        df = df[df["role"] == role.upper()]
    df = df.sort_values(metric, ascending=False).head(limit)
    cols = [
        "player_id",
        "player_name",
        "team_name",
        "flag_url",
        "role",
        "minutes",
        metric,
    ]
    return clean_json({"metric": metric, "leaders": df[cols].to_dict("records")})
