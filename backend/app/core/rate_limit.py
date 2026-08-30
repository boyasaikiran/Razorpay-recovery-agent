"""
In-memory rate limiting (Phase 15).

Per spec's MVP guidance ("Do not prematurely introduce Redis, Celery
... FastAPI + PostgreSQL + background tasks is enough"), this is a
simple in-process fixed-window limiter -- correct for a single-process
MVP deployment, not appropriate for multi-process/multi-instance
production (which would need a shared store like Redis). Stated
plainly as a known scaling limitation, not hidden.

Keyed by client IP. Each named limiter tracks its own window
independently, so /simulate/events and /evaluation/run can have
different limits.
"""
import time
from collections import defaultdict
from typing import Callable

from fastapi import Request, status

from app.core.config import get_settings
from app.core.exceptions import AppError

_WINDOWS: dict[str, dict[str, tuple[float, int]]] = defaultdict(dict)

WINDOW_SECONDS = 60


def _client_key(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def rate_limiter(name: str, limit_getter: Callable[[], int]) -> Callable:
    async def _dependency(request: Request) -> bool:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return True

        limit = limit_getter()
        key = _client_key(request)
        now = time.time()

        window = _WINDOWS[name]
        window_start, count = window.get(key, (now, 0))

        if now - window_start >= WINDOW_SECONDS:
            window_start, count = now, 0

        count += 1
        window[key] = (window_start, count)

        if count > limit:
            raise AppError(
                f"Rate limit exceeded for this endpoint ({limit} requests per {WINDOW_SECONDS}s).",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        return True

    return _dependency


def reset_rate_limits() -> None:
    """Test-only helper: clears all in-memory limiter state between tests."""
    _WINDOWS.clear()


rate_limit_simulate_events = rate_limiter(
    "simulate_events", lambda: get_settings().rate_limit_simulate_events_per_minute
)
rate_limit_evaluation = rate_limiter("evaluation", lambda: get_settings().rate_limit_evaluation_per_minute)
