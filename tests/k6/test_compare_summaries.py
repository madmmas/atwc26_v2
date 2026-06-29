"""Tests for k6/compare_summaries.py A/B logic."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPARE_PATH = ROOT / "k6" / "compare_summaries.py"


def _load_compare():
    spec = importlib.util.spec_from_file_location("compare_summaries", COMPARE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["compare_summaries"] = module
    spec.loader.exec_module(module)
    return module


def test_compare_passes_when_candidate_faster():
    compare = _load_compare()
    baseline = {
        "metrics": {
            "http_req_failed": {"rate": 0.01},
            "http_req_duration": {"p95": 1000},
        },
        "endpoints": {
            "health": {"p95": 200},
            "predict": {"p95": 800},
        },
    }
    candidate = {
        "metrics": {
            "http_req_failed": {"rate": 0.01},
            "http_req_duration": {"p95": 900},
        },
        "endpoints": {
            "health": {"p95": 180},
            "predict": {"p95": 700},
        },
    }
    diff = compare.compare(baseline, candidate)
    assert diff["passed"] is True


def test_compare_fails_on_large_regression():
    compare = _load_compare()
    baseline = {
        "metrics": {
            "http_req_failed": {"rate": 0.01},
            "http_req_duration": {"p95": 1000},
        },
        "endpoints": {"predict": {"p95": 800}},
    }
    candidate = {
        "metrics": {
            "http_req_failed": {"rate": 0.02},
            "http_req_duration": {"p95": 2000},
        },
        "endpoints": {"predict": {"p95": 1500}},
    }
    diff = compare.compare(baseline, candidate)
    assert diff["passed"] is False
