"""Fingerprint scrape inputs and detect whether content changed between runs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from atwc26_core import config as core_config

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


def fingerprint() -> dict[str, str]:
    """Map stable path key -> sha256 for ESPN scrape inputs."""
    out: dict[str, str] = {}
    data = core_config.DATA_DIR

    def add(path: Path) -> None:
        if not path.is_file() or path.name in _IGNORE_NAMES:
            return
        out[_path_key(path)] = _sha256_file(path)

    raw = data / "raw"
    if raw.is_dir():
        for path in sorted(raw.glob("*.json")):
            add(path)

    for path in (
        core_config.MASTER_PARQUET,
        core_config.MATCH_EVENTS,
        core_config.SQUADS_RAW,
        core_config.STANDINGS,
        core_config.BRACKET,
        core_config.GLOSSARY_CSV,
        core_config.TEAM_FLAGS,
        data / "schedule.json",
        LINKS_CSV,
    ):
        add(path)

    return out


def save_snapshot(path: Path) -> int:
    fp = fingerprint()
    path.write_text(json.dumps(fp, indent=2, sort_keys=True) + "\n")
    print(f"snapshot -> {path} ({len(fp)} file(s))")
    return 0


def compare_snapshot(path: Path) -> int:
    before = json.loads(path.read_text())
    after = fingerprint()
    if before == after:
        print("no data changes")
        return 1

    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    modified = sorted(k for k in before.keys() & after.keys() if before[k] != after[k])
    print(
        f"data changed: +{len(added)} -{len(removed)} ~{len(modified)}"
        + (f" ({', '.join(modified[:5])}{'...' if len(modified) > 5 else ''})" if modified else "")
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detect ETL scrape input changes")
    sub = parser.add_subparsers(dest="command", required=True)

    snap = sub.add_parser("snapshot", help="Write a fingerprint JSON file")
    snap.add_argument("path", type=Path)

    cmp = sub.add_parser("compare", help="Exit 0 when data changed since snapshot")
    cmp.add_argument("path", type=Path)

    args = parser.parse_args(argv)
    if args.command == "snapshot":
        return save_snapshot(args.path)
    return compare_snapshot(args.path)
