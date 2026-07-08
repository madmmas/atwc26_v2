"""Pydantic request/response models for the API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class PlayerSelection(BaseModel):
    player_id: int
    role: str = Field("MID", description="Slot role: GK | DEF | MID | FWD")


class TeamSelection(BaseModel):
    team_name: str
    players: list[PlayerSelection]
    home: bool = False


class PredictRequest(BaseModel):
    team_a: TeamSelection
    team_b: TeamSelection
    model: str | None = Field(None, description="poisson|elo|dixon_coles|xgboost|None=all")
