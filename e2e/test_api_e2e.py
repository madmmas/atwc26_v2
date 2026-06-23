"""End-to-end tests for the v1 FastAPI monolith (in-process TestClient)."""
from __future__ import annotations

import math

from fastapi.testclient import TestClient

from helpers import build_xi, team_names, team_names_for_predict


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "AnalyseThisWC26"
    assert body["teams"] > 0
    assert body["players"] > 0


def test_overview(client: TestClient) -> None:
    response = client.get("/api/overview")
    assert response.status_code == 200
    body = response.json()
    assert "league" in body
    assert isinstance(body["teams"], list) and body["teams"]
    assert isinstance(body["top_scorers"], list)


def test_teams(client: TestClient) -> None:
    response = client.get("/api/teams")
    assert response.status_code == 200
    teams = response.json()["teams"]
    assert teams
    assert "team_name" in teams[0]


def test_team_players(client: TestClient) -> None:
    team_a, _ = team_names(client)
    response = client.get(f"/api/teams/{team_a}/players")
    assert response.status_code == 200
    body = response.json()
    assert body["team_name"] == team_a
    assert body["players"]


def test_players_list_and_sort(client: TestClient) -> None:
    response = client.get("/api/players", params={"sort": "minutes", "limit": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["count"] <= 5
    assert body["players"]

    bad_sort = client.get("/api/players", params={"sort": "not_a_real_column"})
    assert bad_sort.status_code == 400


def test_matches(client: TestClient) -> None:
    response = client.get("/api/matches")
    assert response.status_code == 200
    matches = response.json()["matches"]
    assert isinstance(matches, list)
    if matches:
        game_id = matches[0]["game_id"]
        detail = client.get(f"/api/matches/{game_id}")
        assert detail.status_code == 200
        assert detail.json()["meta"]["game_id"] == game_id


def test_unknown_team_returns_404(client: TestClient) -> None:
    response = client.get("/api/teams/Nowhere/players")
    assert response.status_code == 404


def test_predict_probabilities_sum_to_one(client: TestClient) -> None:
    team_a, team_b = team_names_for_predict(client)
    body = {
        "team_a": build_xi(client, team_a, home=True),
        "team_b": build_xi(client, team_b),
    }
    response = client.post("/api/predict", json=body)
    assert response.status_code == 200, response.text
    data = response.json()
    total = (
        data["team_a"]["win_probability"]
        + data["team_b"]["win_probability"]
        + data["draw_prob"]
    )
    assert math.isclose(total, 1.0, abs_tol=1e-3)
    for key in ("team_a", "team_b"):
        assert 0.0 <= data[key]["win_probability"] <= 1.0
        assert data[key]["expected_goals"] >= 0.0


def test_predict_requires_players(client: TestClient) -> None:
    team_a, team_b = team_names(client)
    body = {
        "team_a": {"team_name": team_a, "players": []},
        "team_b": {"team_name": team_b, "players": []},
    }
    response = client.post("/api/predict", json=body)
    assert response.status_code == 400
    assert "at least one" in response.json()["detail"].lower()
