from fastapi import FastAPI

from app.api import router


def create_app() -> FastAPI:
    application = FastAPI(
        title="Abhijatri API",
        version="0.1.0",
        description="Bangla-first, offline-ready travel platform API",
    )
    application.include_router(router)
    return application


app = create_app()

