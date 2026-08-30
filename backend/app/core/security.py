"""
API key authentication (Phase 15).

Applied as a FastAPI dependency to state-changing / abuse-prone
endpoints (ingesting synthetic events, running a case, running the
evaluation engine). Read-only dashboard endpoints are left open in
this demo configuration so the Phase 14 dashboard works without every
fetch call needing a credential -- documented explicitly, not a silent
gap. The Razorpay webhook is authenticated separately via HMAC
signature (Phase 4), not this mechanism.

FAIL-SAFE DEFAULT, consistent with Phase 9's policy engine philosophy:
if API_KEY is not configured, protected endpoints are DENIED (503),
never silently left open. Comparison uses hmac.compare_digest to avoid
timing side-channels.
"""
import hmac

from fastapi import Header, status

from app.core.config import get_settings
from app.core.exceptions import AppError


async def require_api_key(x_api_key: str = Header(None, alias="X-API-Key")) -> bool:
    settings = get_settings()

    if not settings.api_key:
        raise AppError(
            "API key authentication is not configured on this server.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    if not x_api_key or not hmac.compare_digest(x_api_key, settings.api_key):
        raise AppError(
            "Invalid or missing API key.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    return True
