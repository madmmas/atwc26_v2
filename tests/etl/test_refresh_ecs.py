"""Tests for ECS rolling deploy after publish."""
from __future__ import annotations

import pytest

from atwc26_core import config


def test_refresh_ecs_services_no_config(monkeypatch):
    pytest.importorskip("boto3")
    monkeypatch.delenv("ATWC26_ECS_CLUSTER", raising=False)
    monkeypatch.delenv("ATWC26_ECS_SERVICES", raising=False)

    from etl.publish.refresh import refresh_ecs_services

    assert refresh_ecs_services() == []


def test_refresh_ecs_services_force_new_deployment(monkeypatch):
    pytest.importorskip("boto3")
    monkeypatch.setenv("ATWC26_ECS_CLUSTER", "atwc26-v2-dev")
    monkeypatch.setenv("ATWC26_ECS_SERVICES", "analytics,predict")
    monkeypatch.setattr(config, "AWS_REGION", "us-east-1")

    calls: list[dict] = []

    class FakeECS:
        def update_service(self, **kwargs):
            calls.append(kwargs)
            return kwargs

    import etl.publish.refresh as refresh_mod

    monkeypatch.setattr(refresh_mod, "boto3", type("B", (), {"client": staticmethod(lambda *a, **k: FakeECS())}))

    refreshed = refresh_mod.refresh_ecs_services()
    assert refreshed == ["analytics", "predict"]
    assert len(calls) == 2
    assert all(c["cluster"] == "atwc26-v2-dev" and c["forceNewDeployment"] is True for c in calls)
