"""
Thin LLM client wrapper. Returns None when no API key is configured
rather than raising, so callers can decide how to degrade (Phase 6's
diagnosis orchestrator falls back to Path B in that case).
"""
from typing import Optional

import anthropic

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_client: Optional[anthropic.Anthropic] = None
_client_initialized = False


def get_llm_client() -> Optional[anthropic.Anthropic]:
    global _client, _client_initialized
    if _client_initialized:
        return _client

    settings = get_settings()
    if not settings.llm_api_key:
        logger.info("LLM_API_KEY not configured; LLM diagnosis path (Path C) is unavailable.")
        _client = None
    else:
        _client = anthropic.Anthropic(api_key=settings.llm_api_key)
    _client_initialized = True
    return _client
