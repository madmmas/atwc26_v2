"""Helpers for building API request bodies in tests."""
from __future__ import annotations

from fastapi.testclient import TestClient

FORMATION = {"GK": 1, "DEF": 4, "MID": 3, "FWD": 3}


def _role_counts(client: TestClient, team_name: str) -> dict[str, int]:
    response = client.get(f"/api/teams/{team_name}/players")
    assert response.status_code == 200, response.text
    counts: dict[str, int] = {}
    for player in response.json()["players"]:
        counts[player["role"]] = counts.get(player["role"], 0) + 1
    return counts


def can_build_xi(client: TestClient, team_name: str) -> bool:
    counts = _role_counts(client, team_name)
    return all(counts.get(role, 0) >= needed for role, needed in FORMATION.items())


def team_names(client: TestClient, count: int = 2) -> list[str]:
    teams = client.get("/api/teams").json()["teams"]
    assert len(teams) >= count
    return [t["team_name"] for t in teams[:count]]


def team_names_for_predict(client: TestClient) -> tuple[str, str]:
    names = [t["team_name"] for t in client.get("/api/teams").json()["teams"]]
    for i, team_a in enumerate(names):
        if not can_build_xi(client, team_a):
            continue
        for team_b in names[i + 1 :]:
            if can_build_xi(client, team_b):
                return team_a, team_b
    raise AssertionError("No two teams with enough players for a 4-3-3 XI")


def build_xi(client: TestClient, team_name: str, *, home: bool = False) -> dict:
    response = client.get(f"/api/teams/{team_name}/players")
    assert response.status_code == 200, response.text
    players = response.json()["players"]
    picks: list[dict] = []
    for role, needed in FORMATION.items():
        role_players = [p for p in players if p["role"] == role][:needed]
        assert len(role_players) >= needed, f"{team_name} missing {role} players"
        for player in role_players:
            picks.append({"player_id": player["player_id"], "role": role})
    return {"team_name": team_name, "players": picks, "home": home}
