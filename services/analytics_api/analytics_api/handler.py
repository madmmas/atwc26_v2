"""AWS Lambda entrypoint for the analytics API."""
from __future__ import annotations

from mangum import Mangum

from .main import app

handler = Mangum(app, lifespan="off")
