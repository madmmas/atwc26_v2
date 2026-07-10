"""Tests for ESPN completion probe used by the ETL scheduler Lambda."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
LAMBDA_DIR = ROOT / "infra" / "terraform" / "modules" / "etl-scheduler" / "lambda"
sys.path.insert(0, str(LAMBDA_DIR))

from espn_status import match_completed  # noqa: E402


def _response(payload: dict) -> MagicMock:
    body = MagicMock()
    body.read.return_value = json.dumps(payload).encode("utf-8")
    response = MagicMock()
    response.__enter__.return_value = body
    response.__exit__.return_value = False
    return response


def test_match_completed_true_from_espn_payload() -> None:
    payload = {
        "header": {
            "competitions": [
                {"status": {"type": {"completed": True, "name": "STATUS_FULL_TIME"}}}
            ]
        }
    }
    with patch("espn_status.urllib.request.urlopen", return_value=_response(payload)):
        assert match_completed("760510", league="fifa.world", schedule_completed=False) is True


def test_match_completed_false_from_espn_payload() -> None:
    payload = {
        "competitions": [
            {"status": {"type": {"completed": False, "name": "STATUS_IN_PROGRESS"}}}
        ]
    }
    with patch("espn_status.urllib.request.urlopen", return_value=_response(payload)):
        assert match_completed("760510", league="fifa.world", schedule_completed=True) is False


def test_match_completed_falls_back_to_schedule_on_error() -> None:
    with patch("espn_status.urllib.request.urlopen", side_effect=TimeoutError("timeout")):
        assert match_completed("760510", league="fifa.world", schedule_completed=True) is True
        assert match_completed("760510", league="fifa.world", schedule_completed=False) is False
