import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import DBAPIError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError

from app.api import router
from app.config import get_settings
from app.limits import limiter

logger = logging.getLogger(__name__)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Cache-Control": "no-store",
}


def _error(status_code: int, detail: str, request_id: str, retry_after: int | None = None) -> JSONResponse:
    headers = {"X-Request-ID": request_id}
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse({"detail": detail}, status_code=status_code, headers=headers)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "-")


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())
    docs = settings.docs_are_enabled
    application = FastAPI(
        title="Abhijatri API",
        version="0.1.0",
        description="Bangla-first, offline-ready travel platform API",
        docs_url="/docs" if docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs else None,
    )
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    @application.exception_handler(DBAPIError)
    async def database_unavailable(request: Request, error: DBAPIError) -> JSONResponse:
        logger.error("database error on %s", request.url.path, exc_info=error)
        return _error(503, "temporarily unavailable", _request_id(request), retry_after=5)

    @application.exception_handler(PoolTimeoutError)
    async def pool_exhausted(request: Request, error: PoolTimeoutError) -> JSONResponse:
        logger.error("connection pool exhausted on %s", request.url.path, exc_info=error)
        return _error(503, "temporarily unavailable", _request_id(request), retry_after=5)

    @application.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception) -> JSONResponse:
        logger.error("unhandled error on %s", request.url.path, exc_info=error)
        return _error(500, "internal server error", _request_id(request))

    @application.middleware("http")
    async def guardrails(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = request_id = uuid.uuid4().hex
        declared = request.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > settings.max_request_body_bytes:
            return _error(413, "request body too large", request_id)
        try:
            response = await asyncio.wait_for(
                call_next(request), timeout=settings.request_timeout_seconds
            )
        except TimeoutError:
            logger.error("request timed out: %s %s", request.method, request.url.path)
            return _error(504, "request timed out", request_id)
        response.headers["X-Request-ID"] = request_id
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        if settings.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH"],
        allow_headers=["Content-Type", "Idempotency-Key"],
        allow_credentials=False,
        max_age=600,
    )
    application.include_router(router)
    return application


app = create_app()
