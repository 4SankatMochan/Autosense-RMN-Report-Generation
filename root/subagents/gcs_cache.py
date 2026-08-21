"""Module-level GCS blob cache with TTL.

Avoids re-downloading persona.json and persona_report.xlsx from GCS on
every agent invocation. Thread-safe via a lock; safe for asyncio because
dict reads/writes in CPython are atomic and the lock only guards the
cache metadata update.
"""
import threading
import time
from typing import Any, Callable

_cache: dict[str, tuple[Any, float]] = {}
_lock = threading.Lock()

CACHE_TTL: int = 3600  # seconds — refresh persona data once per hour


def get_cached(blob, loader: Callable) -> Any:
    """Return a cached value or call loader(blob) and store the result.

    Args:
        blob: A google.cloud.storage.Blob object (used as cache key via .name).
        loader: Callable that accepts the blob and returns the value to cache.
    """
    key = blob.name
    now = time.time()

    with _lock:
        if key in _cache:
            value, ts = _cache[key]
            if now - ts < CACHE_TTL:
                return value

    # Download outside the lock so other threads aren't blocked during I/O.
    value = loader(blob)

    with _lock:
        _cache[key] = (value, time.time())

    return value


def invalidate(blob_name: str | None = None) -> None:
    """Invalidate one entry or the entire cache (pass None to clear all)."""
    with _lock:
        if blob_name is None:
            _cache.clear()
        else:
            _cache.pop(blob_name, None)