"""Tests for post-publish compute refresh."""
from __future__ import annotations

import pytest

from atwc26_core import config


def test_refresh_lambda_functions_no_names(monkeypatch):
    pytest.importorskip("boto3")
    monkeypatch.delenv("ATWC26_LAMBDA_ANALYTICS_NAME", raising=False)
    monkeypatch.delenv("ATWC26_LAMBDA_PREDICT_NAME", raising=False)

    from etl.publish.refresh import refresh_lambda_functions

    assert refresh_lambda_functions("publish123") == []


def test_refresh_lambda_functions_bumps_env(monkeypatch):
    pytest.importorskip("boto3")
    monkeypatch.setenv("ATWC26_LAMBDA_ANALYTICS_NAME", "atwc26-v2-dev-analytics")
    monkeypatch.setenv("ATWC26_LAMBDA_PREDICT_NAME", "atwc26-v2-dev-predict")
    monkeypatch.setattr(config, "AWS_REGION", "us-east-1")

    updates: list[dict] = []

    class FakeLambda:
        def get_function_configuration(self, FunctionName):
            return {
                "Environment": {
                    "Variables": {
                        "ATWC26_S3_BUCKET": "bucket",
                        "ATWC26_DATA_VERSION": "old",
                    },
                },
            }

        def update_function_configuration(self, **kwargs):
            updates.append(kwargs)
            return kwargs

    import etl.publish.refresh as refresh_mod

    monkeypatch.setattr(refresh_mod, "boto3", type("B", (), {"client": staticmethod(lambda *a, **k: FakeLambda())}))

    refreshed = refresh_mod.refresh_lambda_functions("publish456")
    assert refreshed == ["atwc26-v2-dev-analytics", "atwc26-v2-dev-predict"]
    assert len(updates) == 2
    for call in updates:
        assert call["Environment"]["Variables"]["ATWC26_DATA_VERSION"] == "publish456"
        assert call["Environment"]["Variables"]["ATWC26_S3_BUCKET"] == "bucket"


def test_refresh_compute_runs_lambda_and_ecs(monkeypatch):
    pytest.importorskip("boto3")
    calls: list[str] = []

    import etl.publish.refresh as refresh_mod

    def _lambda(_publish_id: str) -> list[str]:
        calls.append("lambda")
        return ["analytics"]

    def _ecs() -> list[str]:
        calls.append("ecs")
        return ["predict"]

    def _predict(_publish_id: str) -> bool:
        calls.append("predict")
        return True

    monkeypatch.setattr(refresh_mod, "refresh_lambda_functions", _lambda)
    monkeypatch.setattr(refresh_mod, "refresh_ecs_services", _ecs)
    monkeypatch.setattr(refresh_mod, "refresh_predict_service", _predict)

    result = refresh_mod.refresh_compute("publish789")
    assert set(calls) == {"lambda", "ecs", "predict"}
    assert result["lambdas"] == ["analytics"]
    assert result["services"] == ["predict"]
    assert result["predict_reloaded"] is True
