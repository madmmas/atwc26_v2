"""pytest wrappers for etl.qa.checks."""
from __future__ import annotations

from etl.qa.checks import (
    check_bracket_match_coverage,
    check_datastore_loads,
    check_master_parquet,
    check_match_events,
    check_required_artifacts,
)


def test_required_artifacts():
    results = check_required_artifacts()
    assert results, "no required artifact checks defined"
    missing = [r for r in results if not r.ok]
    assert not missing, missing


def test_master_parquet():
    result = check_master_parquet()
    assert result.ok, result.detail


def test_match_events():
    result = check_match_events()
    assert result.ok, result.detail


def test_datastore_loads():
    result = check_datastore_loads()
    assert result.ok, result.detail


def test_bracket_match_coverage():
    result = check_bracket_match_coverage()
    assert result.ok, result.detail
