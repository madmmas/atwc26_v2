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
from atwc26_core.api_cache import builders, keys
from atwc26_core.data import get_store
from atwc26_core.simulation_artifacts import (
    load_winner_probabilities,
    winner_probabilities_api_payload,
)
from atwc26_core.tournament import get_winner_probabilities
from services.shared.api_reader import read_cached
from services.shared.bootstrap import ensure_data_available
from services.shared.json_util import clean_json

app = FastAPI(title=f"{config.APP_NAME} Analytics", version=config.APP_VERSION)

if config.use_cors_middleware():
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


@app.get("/api/winner-probabilities")
def winner_probabilities():
    pk = keys.dataset_pk()

    def _fallback():
        store = get_store()
        payload, _, _ = builders.build_winner_probabilities(store, {})
        if payload is None:
            probs = load_winner_probabilities() or get_winner_probabilities(store)
            payload = winner_probabilities_api_payload(probs, flag_lookup=store.flag)
        return payload

    return clean_json(read_cached(pk, keys.winner_probabilities_sk(), _fallback))


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
    pk = keys.dataset_pk()

    def _fallback():
        store = get_store()
        payload, _, _ = builders.build_overview(store, {})
        return payload

    return clean_json(read_cached(pk, keys.overview_sk(), _fallback))


@app.get("/api/teams")
def teams():
    pk = keys.dataset_pk()

    def _fallback():
        store = get_store()
        return {"teams": store.teams.to_dict("records")}

    return clean_json(read_cached(pk, keys.teams_sk(), _fallback))


@app.get("/api/teams/{team_name}/players")
def team_players(team_name: str):
    pk = keys.dataset_pk()
    sk = keys.team_players_sk(team_name)

    def _fallback():
        store = get_store()
        sub = store.players[store.players["team_name"] == team_name]
        if sub.empty:
            raise HTTPException(404, f"No players found for team '{team_name}'")
        return {
            "team_name": team_name,
            "players": sub.sort_values(
                ["role", "minutes"], ascending=[True, False]
            ).to_dict("records"),
        }

    try:
        return clean_json(read_cached(pk, sk, _fallback))
    except HTTPException:
        raise


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
    pk = keys.dataset_pk()

    def _fallback():
        store = get_store()
        return {"matches": store.matches}

    return clean_json(read_cached(pk, keys.matches_sk(), _fallback))


@app.get("/api/matches/{game_id}")
def match_detail(game_id: str):
    pk = keys.dataset_pk()
    sk = keys.match_detail_sk(game_id)

    def _fallback():
        store = get_store()
        detail = store.match_detail(game_id)
        if detail is None:
            raise HTTPException(404, f"No match data for game {game_id}")
        return detail

    try:
        return clean_json(read_cached(pk, sk, _fallback))
    except HTTPException:
        raise


@app.get("/api/players/{player_id}")
def player_detail(player_id: int):
    pk = keys.dataset_pk()
    sk = keys.player_detail_sk(player_id)

    def _fallback():
        store = get_store()
        detail = store.player_detail(player_id)
        if detail is None:
            raise HTTPException(404, f"No data for player {player_id}")
        return detail

    try:
        return clean_json(read_cached(pk, sk, _fallback))
    except HTTPException:
        raise


@app.get("/api/standings")
def standings():
    pk = keys.dataset_pk()

    def _fallback():
        store = get_store()
        return {"groups": store.standings}

    return clean_json(read_cached(pk, keys.standings_sk(), _fallback))


@app.get("/api/bracket")
def bracket():
    pk = keys.dataset_pk()

    def _fallback():
        store = get_store()
        payload, _, _ = builders.build_bracket(store, {})
        return payload

    return clean_json(read_cached(pk, keys.bracket_sk(), _fallback))


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
