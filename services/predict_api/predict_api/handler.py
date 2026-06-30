"""AWS Lambda entrypoint for the predict API."""
from __future__ import annotations

from mangum import Mangum

from .main import app
from services.shared.bootstrap import ensure_data_available

ensure_data_available()

handler = Mangum(app, lifespan="off")
