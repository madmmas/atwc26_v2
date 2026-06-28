"""Contract tests for split analytics + predict APIs."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]


def _load_app(service: str, package: str):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    main_file = ROOT / "services" / service / package / "main.py"
    module_name = f"contract_{package}_main"
    spec = importlib.util.spec_from_file_location(module_name, main_file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module.app


@pytest.fixture(scope="module")
def analytics_client() -> TestClient:
    app = _load_app("analytics_api", "analytics_api")
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="module")
def predict_client() -> TestClient:
    app = _load_app("predict_api", "predict_api")
    with TestClient(app) as client:
        yield client
