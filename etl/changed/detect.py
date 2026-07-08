"""Fingerprint scrape inputs and detect whether content changed between runs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from atwc26_core import config as core_config

from .store import load_fingerprint, restore_scrape_state, save_fingerprint, save_scrape_state

ROOT = Path(__file__).resolve().parents[2]
LINKS_CSV = ROOT / "etl" / "scrape" / "game_links.csv"

# Updated every poll even when match payloads are unchanged.
_IGNORE_NAMES = frozenset({"processed_games.json", "historical_state.json"})


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path_key(path: Path) -> str:
    path = path.resolve()
    data = core_config.DATA_DIR.resolve()
    if path == data or data in path.parents:
        return str(Path("data") / path.relative_to(data))
    if path == ROOT or ROOT in path.parents:
        return path.relative_to(ROOT).as_posix()
    return path.as_posix()


def _is_raw_key(key: str) -> bool:
    return key.startswith("data/raw/") and key.endswith(".json")


def match_fingerprint() -> dict[str, str]:
    """Fingerprint raw match payloads only (inputs to model training)."""
    out: dict[str, str] = {}
    raw = core_config.DATA_DIR / "raw"
    if not raw.is_dir():
        return out
    for path in sorted(raw.glob("*.json")):
        if path.name in _IGNORE_NAMES:
            continue
        out[_path_key(path)] = _sha256_file(path)
    return out


def fingerprint() -> dict[str, str]:
    """Map stable path key -> sha256 for ESPN scrape inputs that drive ETL.

    Only source-of-truth files are included — not derived artifacts (parquet,
    match_events) or files re-fetched every poll with identical content
    (squads, schedule).
    """
    out = match_fingerprint()
    data = core_config.DATA_DIR

    def add(path: Path) -> None:
        if not path.is_file() or path.name in _IGNORE_NAMES:
            return
        out[_path_key(path)] = _sha256_file(path)

    for path in (
        core_config.STANDINGS,
        core_config.BRACKET,
    ):
        add(path)

    return out


def data_changed(before: dict[str, str], after: dict[str, str]) -> bool:
    """Return True when ``after`` has new or modified content vs ``before``.

    Keys present in ``before`` but missing locally in ``after`` are ignored so
    a fresh git checkout (fewer raw JSON files than the last publish) does not
    force a full transform.
    """
    added = set(after) - set(before)
    if added:
        return True
    for key in before.keys() & after.keys():
        if before[key] != after[key]:
            return True
    return False


def describe_changes(before: dict[str, str], after: dict[str, str]) -> str:
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    modified = sorted(k for k in before.keys() & after.keys() if before[k] != after[k])
    return (
        f"+{len(added)} -{len(removed)} ~{len(modified)}"
        + (f" ({', '.join((added + modified)[:5])}{'...' if len(added + modified) > 5 else ''})"
           if added or modified else "")
    )


def save_snapshot(path: Path) -> int:
    fp = fingerprint()
    path.write_text(json.dumps(fp, indent=2, sort_keys=True) + "\n")
    print(f"snapshot -> {path} ({len(fp)} file(s))")
    return 0


def load_remote_snapshot(path: Path) -> int:
    """Write the DynamoDB fingerprint to a local file; fall back to git snapshot."""
    remote = load_fingerprint()
    if remote:
        path.write_text(json.dumps(remote, indent=2, sort_keys=True) + "\n")
        print(f"loaded remote fingerprint -> {path} ({len(remote)} file(s))")
        return 0
    print("no remote fingerprint — falling back to local git snapshot")
    return save_snapshot(path)


def compare_snapshot(path: Path) -> int:
    before = json.loads(path.read_text())
    after = fingerprint()
    if not data_changed(before, after):
        print("no data changes")
        return 1

    print(f"data changed: {describe_changes(before, after)}")
    return 0


def compare_matches_snapshot(path: Path) -> int:
    """Exit 0 when raw match JSON changed since snapshot (training required)."""
    before = json.loads(path.read_text())
    before_raw = {k: v for k, v in before.items() if _is_raw_key(k)}
    after_raw = match_fingerprint()
    if not data_changed(before_raw, after_raw):
        print("no match data changes")
        return 1

    print(f"match data changed: {describe_changes(before_raw, after_raw)}")
    return 0


def restore_state() -> int:
    restore_scrape_state()
    return 0


def persist_scrape_state() -> int:
    from .store import read_scrape_state

    state = read_scrape_state()
    if state:
        save_scrape_state(state)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detect ETL scrape input changes")
    sub = parser.add_subparsers(dest="command", required=True)

    snap = sub.add_parser("snapshot", help="Write a fingerprint JSON file")
    snap.add_argument("path", type=Path)

    load = sub.add_parser("load-remote", help="Load DynamoDB fingerprint (or git fallback)")
    load.add_argument("path", type=Path)

    cmp = sub.add_parser("compare", help="Exit 0 when data changed since snapshot")
    cmp.add_argument("path", type=Path)

    cmp_matches = sub.add_parser(
        "compare-matches",
        help="Exit 0 when raw match JSON changed since snapshot",
    )
    cmp_matches.add_argument("path", type=Path)

    sub.add_parser("restore-state", help="Restore processed_games.json from DynamoDB")
    sub.add_parser("save-scrape-state", help="Persist processed_games.json to DynamoDB")

    args = parser.parse_args(argv)
    if args.command == "snapshot":
        return save_snapshot(args.path)
    if args.command == "load-remote":
        return load_remote_snapshot(args.path)
    if args.command == "restore-state":
        return restore_state()
    if args.command == "save-scrape-state":
        return persist_scrape_state()
    if args.command == "compare-matches":
        return compare_matches_snapshot(args.path)
    return compare_snapshot(args.path)


__all__ = [
    "data_changed",
    "describe_changes",
    "fingerprint",
    "match_fingerprint",
    "save_fingerprint",
    "compare_snapshot",
    "compare_matches_snapshot",
    "save_snapshot",
]
