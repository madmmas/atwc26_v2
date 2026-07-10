"""Cache-Control response headers for analytics API endpoints."""
from __future__ import annotations

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

CACHE_RULES: list[tuple[str, str]] = [
    # Specific sub-paths FIRST — startswith() matches the first hit
    ("/api/health", "no-store"),
    ("/api/backtest", "public, max-age=300, stale-while-revalidate=60"),
    ("/api/matches/", "public, max-age=86400, stale-while-revalidate=3600"),
    ("/api/players/", "public, max-age=3600, stale-while-revalidate=600"),
    ("/api/teams/", "public, max-age=300, stale-while-revalidate=120"),
    # Generic collection endpoints AFTER sub-paths
    ("/api/standings", "public, max-age=60, stale-while-revalidate=30"),
    ("/api/matches", "public, max-age=30, stale-while-revalidate=15"),
    ("/api/bracket", "public, max-age=300, stale-while-revalidate=60"),
    ("/api/winner-probabilities", "public, max-age=300, stale-while-revalidate=60"),
    ("/api/overview", "public, max-age=120, stale-while-revalidate=60"),
    ("/api/teams", "public, max-age=300, stale-while-revalidate=120"),
    ("/api/leaderboard", "public, max-age=120, stale-while-revalidate=60"),
    ("/api/players", "public, max-age=60, stale-while-revalidate=30"),
]


class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        if response.status_code != 200:
            return response
        path = request.url.path
        for prefix, directive in CACHE_RULES:
            if path == prefix or path.startswith(prefix):
                response.headers["Cache-Control"] = directive
                response.headers["Vary"] = "Accept-Encoding"
                break
        return response
