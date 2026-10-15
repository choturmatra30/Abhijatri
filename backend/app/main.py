import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.config import get_settings


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
