"""Lightweight data bootstrap for the predict service (player profiles only)."""
from __future__ import annotations

import json
from pathlib import Path

from atwc26_core import config


def ensure_predictor_data() -> list[str]:
    """
    Sync only the artifacts the Predictor needs from S3.
    Much faster than the full sync_from_manifest().

    Returns artifact names downloaded.
    """
    bucket = config.S3_BUCKET
    table_name = config.DYNAMODB_TABLE
    if not bucket or not table_name:
        return []

    import boto3

    ddb = boto3.resource("dynamodb", region_name=config.AWS_REGION)
    s3 = boto3.client("s3", region_name=config.AWS_REGION)

    table = ddb.Table(table_name)
    resp = table.get_item(Key={"PK": "DATASET#wc26", "SK": "LATEST"})
    latest = resp.get("Item")
    if not latest:
        return []

    artifacts_meta = latest.get("artifacts", {})
    targets = [
        ("player_profiles", config.PLAYER_PROFILES),
        ("historical_form", config.HISTORICAL_FORM),
        ("squads_raw", config.SQUADS_RAW),
        ("master_parquet", config.MASTER_PARQUET),
        ("elo_ratings", config.ELO_RATINGS),
        ("dc_params", config.DC_PARAMS),
        ("xgb_model", config.XGB_MODEL),
        ("xgb_features", config.XGB_FEATURES),
    ]

    updated = []
    local_hashes = _load_local_hashes()

    for name, local_path in targets:
        meta = artifacts_meta.get(name)
        if not meta:
            continue
        sha = meta.get("sha256", "")
        if local_hashes.get(name) == sha and local_path.exists():
            continue
        key = meta.get("s3_key") or f"{config.S3_PREFIX}/{local_path.name}"
        local_path.parent.mkdir(parents=True, exist_ok=True)
        s3.download_file(bucket, key, str(local_path))
        updated.append(name)

    if updated:
        _save_local_hashes(
            {
                name: artifacts_meta[name]["sha256"]
                for name, _ in targets
                if name in artifacts_meta
            }
        )

    return updated


def _local_hashes_path() -> Path:
    return config.DATA_DIR / ".etl" / "predict-hashes.json"


def _load_local_hashes() -> dict:
    p = _local_hashes_path()
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def _save_local_hashes(hashes: dict) -> None:
    p = _local_hashes_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(hashes, indent=2))


def build_predictor_store():
    """
    Build a minimal store with only the fields the Predictor reads:
      - store.predictor_players
      - store.predictor_avg_goals
      - store.league (for /api/health)

    Avoids loading standings, bracket, events, matches, and team profiles.
    """
    import pandas as pd

    from atwc26_core.data import DataStore, ID_COLS, classify_role

    if not config.PLAYER_PROFILES.exists():
        ds = DataStore()
        ds.load(force=True)
        return ds

    ds = DataStore()
    ds._loaded = True
    ds.flags = ds._load_flags()
    ds.players = pd.read_parquet(config.PLAYER_PROFILES)

    if config.MASTER_PARQUET.exists():
        df = pd.read_parquet(config.MASTER_PARQUET)
        df = ds._merge_squads(df)
        for c in df.columns:
            if c not in ID_COLS:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        df["team_score"] = pd.to_numeric(df["team_score"], errors="coerce")
        df["opp_score"] = pd.to_numeric(df["opp_score"], errors="coerce")
        df["minutes"] = pd.to_numeric(df["minutes"], errors="coerce").fillna(0)
        df = df.assign(
            role=[
                classify_role(p, a)
                for p, a in zip(df["position"], df["position_abbr"])
            ]
        )
        ds.raw = df
        ds.league = ds._build_league_context(df)
        ds.predictor_players, ds.predictor_avg_goals = ds._load_predictor_inputs(df)
    else:
        ds.predictor_players = ds.players
        ds.predictor_avg_goals = 1.3
        ds.league = {"avg_team_goals": ds.predictor_avg_goals}

    return ds
