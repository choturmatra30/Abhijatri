import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.config import get_settings
from app.destination_api import router as destination_router
from app.errors import ApiError, error_response, install_error_handlers
from app.limits import limiter

logger = logging.getLogger(__name__)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Cache-Control": "no-store",
}


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
    install_error_handlers(application)

    @application.middleware("http")
    async def guardrails(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = request_id = str(uuid.uuid4())
        declared = request.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > settings.max_request_body_bytes:
            return error_response(request, "PAYLOAD_TOO_LARGE")
        try:
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > settings.max_request_body_bytes:
                    raise ApiError("PAYLOAD_TOO_LARGE")

            # request.stream() consumes the ASGI body. Cache the validated body so
            # FastAPI can still parse JSON/form payloads in the downstream handler.
            request._body = bytes(body)
            response = await asyncio.wait_for(
                call_next(request), timeout=settings.request_timeout_seconds
            )
        except ApiError as error:
            return error_response(request, error.code)
        except TimeoutError:
            logger.error("request timed out: %s %s", request.method, request.url.path)
            return error_response(request, "REQUEST_TIMEOUT")
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
    application.include_router(destination_router)
    return application


app = create_app()
