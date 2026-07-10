"""Dispatch GitHub Actions ETL when match-based schedule triggers are due."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

from espn_status import match_completed
from schedule_triggers import (
    DEFAULT_CATCHUP_MINUTES,
    DEFAULT_GROUP_STAGE_TRIGGER_OFFSETS_MINUTES,
    DEFAULT_KNOCKOUT_TRIGGER_OFFSETS_MINUTES,
    DEFAULT_MATCH_DURATION_MINUTES,
    due_triggers,
    game_done_key,
    load_schedule,
    trigger_key,
    upcoming_triggers,
)

ETL_TRIGGER_PK = "ETL_TRIGGER#wc26"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "")
    if not raw:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "")
    if not raw:
        return default
    return int(raw)


def _env_offsets(name: str, default: tuple[int, ...]) -> tuple[int, ...]:
    raw = os.environ.get(name, "")
    if not raw:
        return default
    return tuple(int(part.strip()) for part in raw.split(",") if part.strip())


def _github_token() -> str:
    secret_arn = os.environ["GITHUB_TOKEN_SECRET_ARN"]
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_arn)
    return response["SecretString"]


def _load_schedule_payload() -> str:
    bucket = os.environ.get("SCHEDULE_S3_BUCKET", "")
    key = os.environ.get("SCHEDULE_S3_KEY", "data/schedule.json")
    if bucket:
        try:
            body = boto3.client("s3").get_object(Bucket=bucket, Key=key)["Body"].read()
            return body.decode("utf-8")
        except ClientError as exc:
            print(f"S3 schedule read failed s3://{bucket}/{key}: {exc}")

    owner = os.environ["GITHUB_OWNER"]
    repo = os.environ["GITHUB_REPO"]
    ref = os.environ.get("GITHUB_REF", "main")
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/data/schedule.json"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "atwc26-etl-scheduler"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def _already_dispatched(table_name: str, game_id: str, offset_minutes: int) -> bool:
    table = boto3.resource("dynamodb").Table(table_name)
    try:
        resp = table.get_item(
            Key={"PK": ETL_TRIGGER_PK, "SK": trigger_key(game_id, offset_minutes)}
        )
    except ClientError as exc:
        print(f"DynamoDB read failed for {game_id}+{offset_minutes}: {exc}")
        return True
    return bool(resp.get("Item"))


def _game_finished(table_name: str, game_id: str) -> bool:
    table = boto3.resource("dynamodb").Table(table_name)
    try:
        resp = table.get_item(Key={"PK": ETL_TRIGGER_PK, "SK": game_done_key(game_id)})
    except ClientError as exc:
        print(f"DynamoDB read failed for finished game {game_id}: {exc}")
        return False
    return bool(resp.get("Item"))


def _load_finished_game_ids(table_name: str, game_ids: list[str]) -> set[str]:
    if not game_ids:
        return set()
    finished: set[str] = set()
    table = boto3.resource("dynamodb").Table(table_name)
    for game_id in game_ids:
        if _game_finished(table_name, game_id):
            finished.add(str(game_id))
    return finished


def _mark_dispatched(
    table_name: str,
    game_id: str,
    offset_minutes: int,
    *,
    trigger_at: datetime,
) -> None:
    table = boto3.resource("dynamodb").Table(table_name)
    now = datetime.now(timezone.utc).isoformat()
    table.put_item(
        Item={
            "PK": ETL_TRIGGER_PK,
            "SK": trigger_key(game_id, offset_minutes),
            "game_id": game_id,
            "offset_minutes": offset_minutes,
            "trigger_at": trigger_at.astimezone(timezone.utc).isoformat(),
            "dispatched_at": now,
        }
    )


def _dispatch_workflow(*, reason: str, game_id: str) -> dict:
    owner = os.environ["GITHUB_OWNER"]
    repo = os.environ["GITHUB_REPO"]
    workflow = os.environ.get("GITHUB_WORKFLOW", "etl.yml")
    ref = os.environ.get("GITHUB_REF", "main")

    url = (
        f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/"
        f"{workflow}/dispatches"
    )
    body = json.dumps(
        {
            "ref": ref,
            "inputs": {
                "skip_scrape": "false",
                "trigger_game_id": game_id,
            },
        }
    ).encode("utf-8")
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
        print(f"GitHub API error {status} ({reason}): {payload}")
        raise

    print(f"Dispatched {workflow} on {owner}/{repo}@{ref} ({reason}, HTTP {status})")
    return {"statusCode": status, "body": payload or "workflow_dispatch accepted"}


def handler(event, context):
    table_name = os.environ.get("DYNAMODB_TABLE_NAME", "")
    if not table_name:
        raise RuntimeError("DYNAMODB_TABLE_NAME is required for ETL trigger deduplication")

    schedule = load_schedule(_load_schedule_payload())
    now = datetime.now(timezone.utc)
    group_offsets = _env_offsets(
        "GROUP_STAGE_TRIGGER_OFFSETS_MINUTES",
        DEFAULT_GROUP_STAGE_TRIGGER_OFFSETS_MINUTES,
    )
    knockout_offsets = _env_offsets(
        "KNOCKOUT_TRIGGER_OFFSETS_MINUTES",
        DEFAULT_KNOCKOUT_TRIGGER_OFFSETS_MINUTES,
    )
    require_completed = _env_bool("REQUIRE_COMPLETED", True)
    espn_league = os.environ.get("ESPN_LEAGUE", "fifa.world")
    finished_game_ids = _load_finished_game_ids(table_name, list(schedule.keys()))

    due = due_triggers(
        schedule,
        now,
        match_duration_minutes=_env_int("MATCH_DURATION_MINUTES", DEFAULT_MATCH_DURATION_MINUTES),
        group_offsets_minutes=group_offsets,
        knockout_offsets_minutes=knockout_offsets,
        catchup_minutes=_env_int("TRIGGER_CATCHUP_MINUTES", DEFAULT_CATCHUP_MINUTES),
        finished_game_ids=finished_game_ids,
    )

    if not due:
        next_slots = upcoming_triggers(
            schedule,
            now,
            match_duration_minutes=_env_int("MATCH_DURATION_MINUTES", DEFAULT_MATCH_DURATION_MINUTES),
            group_offsets_minutes=group_offsets,
            knockout_offsets_minutes=knockout_offsets,
            finished_game_ids=finished_game_ids,
        )
        if next_slots:
            preview = ", ".join(
                f"{game_id} end+{offset}m @ {trigger_at.isoformat()}"
                for game_id, offset, trigger_at in next_slots
            )
            print(
                f"No ETL triggers due at {now.isoformat()} UTC "
                f"(checked {len(schedule)} fixture(s)); next: {preview}"
            )
        else:
            print(f"No ETL triggers due at {now.isoformat()} UTC (checked {len(schedule)} fixture(s))")
        return {"statusCode": 204, "body": "no triggers due"}

    dispatched: list[str] = []
    for game_id, offset_minutes, trigger_at in due:
        if _game_finished(table_name, game_id):
            print(f"Skip finished game {game_id}")
            continue
        if _already_dispatched(table_name, game_id, offset_minutes):
            print(f"Skip already dispatched {trigger_key(game_id, offset_minutes)}")
            continue

        game = schedule.get(game_id, {})
        if require_completed:
            schedule_completed = bool(game.get("completed"))
            if not match_completed(
                game_id,
                league=espn_league,
                schedule_completed=schedule_completed,
            ):
                print(
                    f"Skip {game_id} end+{offset_minutes}m — ESPN reports match not completed"
                )
                continue

        reason = f"game {game_id} end+{offset_minutes}m ({trigger_at.isoformat()})"
        _dispatch_workflow(reason=reason, game_id=game_id)
        _mark_dispatched(
            table_name,
            game_id,
            offset_minutes,
            trigger_at=trigger_at,
        )
        dispatched.append(trigger_key(game_id, offset_minutes))

    if not dispatched:
        print("No ETL workflows dispatched (waiting on completion or already handled)")
        return {"statusCode": 204, "body": "no workflows dispatched"}

    return {
        "statusCode": 200,
        "body": json.dumps({"dispatched": dispatched}),
    }
