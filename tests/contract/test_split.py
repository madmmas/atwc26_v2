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


def test_predict_health(predict_client: TestClient) -> None:
    response = predict_client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["service"] == "predict"


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
