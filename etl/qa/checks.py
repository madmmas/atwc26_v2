"""Artifact validation rules for the ETL pipeline."""
from __future__ import annotations

import json
from dataclasses import dataclass

import pandas as pd

from atwc26_core.artifacts import ARTIFACTS
from atwc26_core import config
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


def _completed_bracket_game_ids() -> set[str]:
    path = config.BRACKET
    if not path.is_file():
        return set()
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError):
        return set()
    out: set[str] = set()
    for rnd in payload.get("rounds") or []:
        for match in rnd.get("matches") or []:
            if match.get("completed") and match.get("game_id") is not None:
                out.add(str(match["game_id"]))
    return out


def check_bracket_match_coverage() -> QAResult:
    """Fail when bracket shows a finished match that master stats omitted.

    Standings/bracket come from the scoreboard scrape; matches/scorers come
    from all_players_stats. This catches the dual-pipeline gap that previously
    published a complete bracket with missing knockout player stats.
    """
    completed = _completed_bracket_game_ids()
    if not completed:
        return QAResult("bracket_match_coverage", True, "no completed bracket games")

    spec = next(a for a in ARTIFACTS if a.name == "master_parquet")
    if not spec.path.exists():
        return QAResult(
            "bracket_match_coverage",
            False,
            f"{len(completed)} completed bracket games but master parquet missing",
        )
    df = pd.read_parquet(spec.path, columns=["game_id"])
    master = {str(g) for g in df["game_id"].dropna().unique()}
    missing = sorted(completed - master)
    if missing:
        preview = ", ".join(missing[:8])
        more = f" (+{len(missing) - 8} more)" if len(missing) > 8 else ""
        return QAResult(
            "bracket_match_coverage",
            False,
            f"completed bracket games missing from master: {preview}{more}",
        )
    return QAResult(
        "bracket_match_coverage",
        True,
        f"{len(completed)} completed bracket games present in master",
    )


def run_all_checks() -> list[QAResult]:
    return [
        *check_required_artifacts(),
        check_master_parquet(),
        check_match_events(),
        check_datastore_loads(),
        check_bracket_match_coverage(),
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
