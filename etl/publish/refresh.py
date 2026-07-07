"""Refresh compute after ETL publish (Lambda env bump, ECS rolling deploy).

ECS refresh warms the predict Fargate task only (POST /api/predict). Analytics
Lambda refresh invalidates read caches; Monte Carlo runs in GHA simulate, not AWS.
"""
from __future__ import annotations

import os

from atwc26_core import config

try:
    import boto3
except ImportError:  # pragma: no cover
    boto3 = None  # type: ignore[assignment]

DATA_VERSION_KEY = "ATWC26_DATA_VERSION"


def _lambda_function_names() -> list[str]:
    names: list[str] = []
    for key in ("ATWC26_LAMBDA_ANALYTICS_NAME", "ATWC26_LAMBDA_PREDICT_NAME"):
        value = os.getenv(key, "").strip()
        if value:
            names.append(value)
    return names


def refresh_lambda_functions(publish_id: str) -> list[str]:
    """Bump ``ATWC26_DATA_VERSION`` on configured Lambdas to force new containers."""
    if boto3 is None or not publish_id:
        return []

    names = _lambda_function_names()
    if not names:
        return []

    client = boto3.client("lambda", region_name=config.AWS_REGION)
    refreshed: list[str] = []
    for name in names:
        current = client.get_function_configuration(FunctionName=name)
        variables = dict(current.get("Environment", {}).get("Variables", {}))
        variables[DATA_VERSION_KEY] = publish_id
        client.update_function_configuration(
            FunctionName=name,
            Environment={"Variables": variables},
        )
        refreshed.append(name)
    return refreshed


def _ecs_service_names() -> list[str]:
    return [s.strip() for s in os.getenv("ATWC26_ECS_SERVICES", "").split(",") if s.strip()]


def refresh_ecs_services() -> list[str]:
    """Trigger rolling deployment on configured ECS services."""
    if boto3 is None:
        return []

    cluster = os.getenv("ATWC26_ECS_CLUSTER", "").strip()
    services = _ecs_service_names()
    if not cluster or not services:
        return []

    client = boto3.client("ecs", region_name=config.AWS_REGION)
    refreshed: list[str] = []
    for service in services:
        try:
            client.update_service(
                cluster=cluster,
                service=service,
                forceNewDeployment=True,
            )
        except client.exceptions.ClusterNotFoundException:
            print(
                f"warning: ECS cluster {cluster!r} not found — "
                "skipping ECS refresh (clear ATWC26_ECS_CLUSTER if compute is disabled)"
            )
            return refreshed
        except client.exceptions.ServiceNotFoundException:
            print(f"warning: ECS service {service!r} not found in {cluster!r} — skipping")
            continue
        refreshed.append(service)
    return refreshed


def refresh_predict_service(publish_id: str) -> bool:
    """
    POST /api/predict/reload on the running ECS predict service.
    Only fires when ATWC26_PREDICT_SERVICE_URL is set (ECS path).
    Lambda path: skipped — Lambda gets a new container via env-var bump.
    """
    import json as _json
    import urllib.request as _req

    url = os.getenv("ATWC26_PREDICT_SERVICE_URL", "").rstrip("/")
    secret = os.getenv("ATWC26_RELOAD_SECRET", "")
    if not url:
        return False

    body = _json.dumps({"publish_id": publish_id}).encode()
    request = _req.Request(
        f"{url}/api/predict/reload",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Reload-Secret": secret,
        },
    )
    try:
        with _req.urlopen(request, timeout=30) as resp:
            print(f"predict reload: HTTP {resp.status}")
            return resp.status == 200
    except Exception as exc:
        print(f"warning: predict reload failed — {exc}")
        return False
