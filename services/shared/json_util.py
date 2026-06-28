"""JSON helpers shared by v2 API services."""
from __future__ import annotations

import math


def clean_json(obj):
    """Recursively replace NaN/inf with None so the JSON is valid."""
    if isinstance(obj, dict):
        return {k: clean_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_json(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj
