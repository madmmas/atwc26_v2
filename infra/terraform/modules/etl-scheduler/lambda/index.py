"""Dispatch the GitHub Actions ETL workflow on an EventBridge schedule."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

import boto3


def _github_token() -> str:
    secret_arn = os.environ["GITHUB_TOKEN_SECRET_ARN"]
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_arn)
    return response["SecretString"]


def handler(event, context):
    owner = os.environ["GITHUB_OWNER"]
    repo = os.environ["GITHUB_REPO"]
    workflow = os.environ.get("GITHUB_WORKFLOW", "etl.yml")
    ref = os.environ.get("GITHUB_REF", "main")

    url = (
        f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/"
        f"{workflow}/dispatches"
    )
    body = json.dumps({"ref": ref}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {_github_token()}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "atwc26-etl-scheduler",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = response.status
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        payload = exc.read().decode("utf-8")
        print(f"GitHub API error {status}: {payload}")
        raise

    print(f"Dispatched {workflow} on {owner}/{repo}@{ref} (HTTP {status})")
    return {"statusCode": status, "body": payload or "workflow_dispatch accepted"}
