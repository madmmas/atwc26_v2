"""AWS Lambda entrypoint for the predict API."""
from __future__ import annotations

from mangum import Mangum

from .main import app

handler = Mangum(app, lifespan="off")
