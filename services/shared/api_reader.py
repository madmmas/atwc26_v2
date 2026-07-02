"""DynamoDB-first API read helper with in-process fallback."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from atwc26_core.api_cache.store import get_api_cache_store

T = TypeVar("T")

_memory: dict[str, Any] = {}


def read_cached(pk: str, sk: str, fallback: Callable[[], T]) -> T:
    """Return cached payload when present, else compute via fallback."""
    mem_key = f"{pk}|{sk}"
    if mem_key in _memory:
        return _memory[mem_key]

    payload = get_api_cache_store().get_payload(pk, sk)
    if payload is not None:
        _memory[mem_key] = payload
        return payload

    value = fallback()
    _memory[mem_key] = value
    return value


def clear_memory_cache() -> None:
    _memory.clear()
