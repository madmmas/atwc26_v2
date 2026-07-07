"""DynamoDB-first API read helper with TTL-aware in-process cache."""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, TypeVar

from atwc26_core.api_cache.store import get_api_cache_store

T = TypeVar("T")

# TTL in seconds for each cache key prefix.
# Keys not matched get DEFAULT_TTL.
_TTL_RULES: list[tuple[str, int]] = [
    ("API#match#", 86400),  # match detail: immutable after FT
    ("API#player#", 3600),  # player detail: stable during tournament
    ("API#team#", 300),  # team players: squad rarely changes
    ("API#standings", 60),  # standings: changes after each match
    ("API#matches", 60),  # match list: live scores
    ("API#bracket", 300),  # bracket: changes 6× at most
    ("API#overview", 120),  # overview: aggregated stats
    ("API#winner-prob", 300),  # winner probs: post-match simulation
    ("API#teams", 300),  # team list: stable
    ("API#players#", 60),  # default players list
    ("API#leaderboard#", 120),  # precomputed leaderboard variants
]
DEFAULT_TTL = 120

_memory: dict[str, tuple[Any, float]] = {}  # key → (payload, expires_at)


def _ttl_for(sk: str) -> int:
    for prefix, ttl in _TTL_RULES:
        if sk.startswith(prefix):
            return ttl
    return DEFAULT_TTL


def read_cached(pk: str, sk: str, fallback: Callable[[], T]) -> T:
    """Return cached payload when present and not expired, else compute via fallback."""
    mem_key = f"{pk}|{sk}"
    now = time.monotonic()

    # Memory hit (fast path — no DynamoDB round trip)
    if mem_key in _memory:
        payload, expires_at = _memory[mem_key]
        if now < expires_at:
            return payload
        del _memory[mem_key]  # expired

    # DynamoDB hit
    payload = get_api_cache_store().get_payload(pk, sk)
    if payload is not None:
        _memory[mem_key] = (payload, now + _ttl_for(sk))
        return payload

    # Fallback: compute from DataStore
    value = fallback()
    _memory[mem_key] = (value, now + _ttl_for(sk))
    return value


def invalidate(pk: str, sk: str) -> None:
    """Evict a single key from the memory cache."""
    _memory.pop(f"{pk}|{sk}", None)


def clear_memory_cache() -> None:
    _memory.clear()
