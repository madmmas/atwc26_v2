"""Artifact validation rules for the ETL pipeline."""
from __future__ import annotations

import json
from dataclasses import dataclass

import pandas as pd

from atwc26_core.artifacts import ARTIFACTS
from atwc26_core.data import DataStore


@dataclass
class QAResult:
    name: str
    ok: bool
    detail: str = ""


def check_required_artifacts() -> list[QAResult]:
    results: list[QAResult] = []
    for spec in ARTIFACTS:
        if not spec.required:
            continue
        if spec.path.exists():
            results.append(QAResult(spec.name, True, f"found {spec.path.name}"))
        else:
            results.append(QAResult(spec.name, False, f"missing {spec.path}"))
    return results


def check_master_parquet() -> QAResult:
    spec = next(a for a in ARTIFACTS if a.name == "master_parquet")
    if not spec.path.exists():
        return QAResult("master_parquet_rows", False, "file missing")
    df = pd.read_parquet(spec.path)
    if df.empty:
        return QAResult("master_parquet_rows", False, "zero rows")
    if "player_id" not in df.columns:
        return QAResult("master_parquet_rows", False, "missing player_id column")
    return QAResult("master_parquet_rows", True, f"{len(df)} rows")


def check_match_events() -> QAResult:
    spec = next(a for a in ARTIFACTS if a.name == "match_events")
    if not spec.path.exists():
        return QAResult("match_events_shape", False, "file missing")
    data = json.loads(spec.path.read_text())
    if not isinstance(data, dict) or not data:
        return QAResult("match_events_shape", False, "expected non-empty object")
    sample = next(iter(data.values()))
    for key in ("home_team", "away_team", "events", "momentum"):
        if key not in sample:
            return QAResult("match_events_shape", False, f"missing {key} in entry")
    return QAResult("match_events_shape", True, f"{len(data)} matches")


def check_datastore_loads() -> QAResult:
    try:
        store = DataStore()
        store.load()
    except Exception as exc:  # noqa: BLE001 — surface load failures in QA output
        return QAResult("datastore_load", False, str(exc))
    if store.teams is None or store.teams.empty:
        return QAResult("datastore_load", False, "no teams loaded")
    return QAResult("datastore_load", True, f"{len(store.teams)} teams")


def run_all_checks() -> list[QAResult]:
    return [
        *check_required_artifacts(),
        check_master_parquet(),
        check_match_events(),
        check_datastore_loads(),
    ]


def main() -> int:
    results = run_all_checks()
    failed = [r for r in results if not r.ok]
    for r in results:
        status = "OK" if r.ok else "FAIL"
        suffix = f" — {r.detail}" if r.detail else ""
        print(f"[{status}] {r.name}{suffix}")
    if failed:
        print(f"\n{len(failed)} check(s) failed")
        return 1
    print(f"\n{len(results)} check(s) passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
