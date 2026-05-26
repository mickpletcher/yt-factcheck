from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from evidencechain.api.router import api_router
from evidencechain.core.config import Settings, get_settings
from evidencechain.storage.database import initialize_database
from evidencechain.utils.logging import configure_logging, get_logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings)
    logger = get_logger(__name__)
    logger.info("application_starting", extra={"app_name": settings.app_name})
    await initialize_database(settings)
    yield
    logger.info("application_stopping", extra={"app_name": settings.app_name})


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings)

    app = FastAPI(
        title=resolved_settings.app_name,
        version="0.1.0",
        debug=resolved_settings.app_debug,
        lifespan=lifespan,
    )
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()
