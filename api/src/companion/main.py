"""Application factory: ``uvicorn companion.main:create_app --factory``."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from companion.composition import build_container
from companion.config import Settings
from companion.presentation.errors import install_error_handlers
from companion.presentation.request_id import RequestIdMiddleware, install_request_id_logging
from companion.presentation.routers.api_v1 import api_v1_router
from companion.presentation.routers.health import health_router

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s"


def _configure_logging(level: str) -> None:
    install_request_id_logging()
    logging.basicConfig(level=level, format=LOG_FORMAT)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    _configure_logging(settings.log_level)

    docs = settings.enable_docs
    container = build_container(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        container.close()

    app = FastAPI(
        lifespan=lifespan,
        title="Disruption Companion API",
        version="0.1.0",
        docs_url="/docs" if docs else None,
        openapi_url="/openapi.json" if docs else None,
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.container = container

    install_error_handlers(app)
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health_router)
    app.include_router(api_v1_router)
    return app
