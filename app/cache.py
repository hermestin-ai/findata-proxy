"""Simple diskcache-backed TTL cache wrapper."""
from __future__ import annotations

import functools
import hashlib
import json
from typing import Any, Callable

from diskcache import Cache

from .config import CACHE_DIR, CACHE_TTL

_cache = Cache(CACHE_DIR)


def _make_key(prefix: str, args: tuple, kwargs: dict) -> str:
    payload = json.dumps({"a": args, "k": kwargs}, default=str, sort_keys=True)
    digest = hashlib.md5(payload.encode()).hexdigest()
    return f"{prefix}:{digest}"


def cached(prefix: str, ttl: int | None = None) -> Callable:
    """Decorator: cache function return value on disk with TTL (seconds)."""

    effective_ttl = ttl if ttl is not None else CACHE_TTL

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = _make_key(prefix or fn.__name__, args, kwargs)
            hit = _cache.get(key)
            if hit is not None:
                return hit
            result = fn(*args, **kwargs)
            try:
                _cache.set(key, result, expire=effective_ttl)
            except Exception:
                pass
            return result

        return wrapper

    return decorator


def cache_get(key: str) -> Any:
    return _cache.get(key)


def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    _cache.set(key, value, expire=ttl if ttl is not None else CACHE_TTL)
