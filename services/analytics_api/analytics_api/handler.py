"""AWS Lambda entrypoint for the analytics API."""
from __future__ import annotations

from mangum import Mangum

from .main import app
from services.shared.bootstrap import ensure_data_available

# Mangum(lifespan="off") skips FastAPI startup — bootstrap S3 data on cold start.
ensure_data_available()

handler = Mangum(app, lifespan="off")
