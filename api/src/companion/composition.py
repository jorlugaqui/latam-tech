"""Composition root: the only module that builds concrete adapters (DIP, design D1/D7).

Objects are built once in ``create_app`` and kept on ``app.state``; the providers below
expose them to routers as FastAPI dependencies, so tests can swap them with
``app.dependency_overrides``.
"""

from fastapi import Request

from companion.config import Settings
from companion.repositories.sql.engine import build_engine
from companion.repositories.sql.probe import SqlDatabaseProbe
from companion.services.health import HealthService


def build_health_service(settings: Settings) -> HealthService:
    engine = build_engine(settings.database_url.get_secret_value())
    return HealthService(probe=SqlDatabaseProbe(engine))


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_health_service(request: Request) -> HealthService:
    return request.app.state.health_service
