"""Contract tests — analytics and predict services stay in their lanes."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "e2e"))

from helpers import build_xi, team_names_for_predict  # noqa: E402


def test_analytics_health(analytics_client: TestClient) -> None:
    response = analytics_client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "analytics"
    assert body["teams"] > 0
    assert "data_updated_at" in body


def test_predict_health(predict_client: TestClient) -> None:
    response = predict_client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "predict"
    assert "models_available" in body
    assert "poisson" in body["models_available"]
    assert "data_updated_at" in body


def test_predict_health_namespaced_route(predict_client: TestClient) -> None:
    response = predict_client.get("/api/predict/health")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "predict"
    assert "models_available" in body


def test_backtest_endpoint(predict_client: TestClient) -> None:
    response = predict_client.get("/api/backtest")
    # 200 when etl-train has written summary; 404 otherwise.
    assert response.status_code in (200, 404)
    if response.status_code == 200:
        body = response.json()
        assert "models" in body
    else:
        assert "backtest" in response.json()["detail"].lower()


def test_predict_defaults_to_dixon_coles_when_available(
    analytics_client: TestClient, predict_client: TestClient
) -> None:
    health = predict_client.get("/api/predict/health").json()
    team_a, team_b = team_names_for_predict(analytics_client)
    body = {
        "team_a": build_xi(analytics_client, team_a, home=True),
        "team_b": build_xi(analytics_client, team_b),
    }
    response = predict_client.post("/api/predict", json=body)
    assert response.status_code == 200
    result = response.json()
    if "dixon_coles" in health.get("models_available", []):
        assert result.get("model", {}).get("name") == "dixon_coles"
    else:
        assert result.get("model", {}).get("name") in ("poisson", "elo", "xgboost")
    assert "comparison" in result


def test_predict_health_not_on_analytics(analytics_client: TestClient) -> None:
    response = analytics_client.get("/api/predict/health")
    assert response.status_code == 404


def test_predict_not_on_analytics_service(analytics_client: TestClient) -> None:
    response = analytics_client.post(
        "/api/predict",
        json={"team_a": {"team_name": "x", "players": []}, "team_b": {"team_name": "y", "players": []}},
    )
    assert response.status_code == 404


def test_winner_probabilities_on_analytics(analytics_client: TestClient) -> None:
    response = analytics_client.get("/api/winner-probabilities")
    assert response.status_code == 200
    body = response.json()
    assert body["teams"]
    assert sum(t["probability"] for t in body["teams"]) > 0


def test_winner_probabilities_not_on_predict(predict_client: TestClient) -> None:
    response = predict_client.get("/api/winner-probabilities")
    assert response.status_code == 404


def test_analytics_overview(analytics_client: TestClient) -> None:
    response = analytics_client.get("/api/overview")
    assert response.status_code == 200
    assert response.json()["teams"]


def test_players_full_includes_all_metric_columns(analytics_client: TestClient) -> None:
    """Explore uses fields=full so every table column has a value, not just the sort key."""
    metric_keys = (
        "minutes",
        "totalGoals_total",
        "expectedGoals_p90",
        "expectedAssists_p90",
        "totalShots_p90",
        "duelsWon_p90",
        "defensiveInterventions_p90",
        "passPct",
    )
    full = analytics_client.get(
        "/api/players",
        params={"sort": "totalShots_p90", "dir": "desc", "limit": 5, "fields": "full"},
    )
    assert full.status_code == 200
    full_players = full.json()["players"]
    assert full_players
    for key in metric_keys:
        assert key in full_players[0], f"full payload missing {key}"

    slim = analytics_client.get(
        "/api/players",
        params={"sort": "totalShots_p90", "dir": "desc", "limit": 5, "fields": "slim"},
    )
    assert slim.status_code == 200
    slim_row = slim.json()["players"][0]
    assert "totalShots_p90" in slim_row
    assert "minutes" in slim_row
    assert "expectedGoals_p90" not in slim_row


def test_players_min_minutes_filter(analytics_client: TestClient) -> None:
    response = analytics_client.get(
        "/api/players",
        params={"sort": "minutes", "limit": 20, "min_minutes": 90, "fields": "full"},
    )
    assert response.status_code == 200
    players = response.json()["players"]
    assert players
    assert all(p["minutes"] >= 90 for p in players)


def test_predict_on_predict_service(
    analytics_client: TestClient, predict_client: TestClient
) -> None:
    team_a, team_b = team_names_for_predict(analytics_client)
    body = {
        "team_a": build_xi(analytics_client, team_a, home=True),
        "team_b": build_xi(analytics_client, team_b),
    }
    response = predict_client.post("/api/predict", json=body)
    assert response.status_code == 200
    result = response.json()
    total = (
        result["team_a"]["win_probability"]
        + result["draw_prob"]
        + result["team_b"]["win_probability"]
    )
    assert abs(total - 1.0) < 0.02
