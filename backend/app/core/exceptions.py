"""
Centralized exception handling.

Ensures every error returned by the API has a consistent, safe shape and
is logged with its request_id for traceability. Never leak stack traces
or internal details to the client in production.
"""
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """Base class for domain-level application errors."""

    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def register_exception_handlers(app: FastAPI) -> None:
    settings = get_settings()

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        request_id = _request_id(request)
        logger.warning("AppError request_id=%s message=%s", request_id, exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "message": exc.message,
                    "request_id": request_id,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        request_id = _request_id(request)
        # exc.errors() can include a 'ctx' dict with the raw exception object
        # from a custom validator (Pydantic v2) — not JSON serializable.
        # Strip it down to plain, safe fields.
        safe_errors = [
            {
                "loc": err.get("loc"),
                "msg": err.get("msg"),
                "type": err.get("type"),
            }
            for err in exc.errors()
        ]
        logger.info("ValidationError request_id=%s errors=%s", request_id, safe_errors)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "error": {
                    "message": "Validation failed.",
                    "details": safe_errors,
                    "request_id": request_id,
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        request_id = _request_id(request)
        logger.info("HTTPException request_id=%s status=%s detail=%s", request_id, exc.status_code, exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "message": exc.detail,
                    "request_id": request_id,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = _request_id(request)
        logger.exception("UnhandledException request_id=%s", request_id)
        detail = str(exc) if not settings.is_production else "Internal server error."
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "message": detail,
                    "request_id": request_id,
                }
            },
        )
