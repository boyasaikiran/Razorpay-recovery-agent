"""
Recovery Orchestrator — FastAPI application entrypoint.

This wires together configuration, logging, middleware (request ID,
CORS), centralized exception handling, and the versioned API router.

Business logic lives in app/services, app/agents, app/policies, etc.
This file should stay thin.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestIDMiddleware

settings = get_settings()
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Starting %s v%s in %s mode (razorpay_mode=%s)",
        settings.app_name,
        settings.app_version,
        settings.app_env,
        settings.razorpay_mode,
    )
    yield
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Recovery Orchestrator",
        description=(
            "AI-native revenue recovery platform: diagnoses why a payment, "
            "checkout, or invoice failed, estimates recoverability, proposes "
            "a cause-specific recovery action, validates it through a "
            "deterministic policy engine, and executes only approved actions."
        ),
        version=settings.app_version,
        lifespan=lifespan,
    )

    # Request ID must be added before other middleware that might log.
    app.add_middleware(RequestIDMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
