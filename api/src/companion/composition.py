"""Composition root: the only module that builds concrete adapters (DIP, design D1/D7).

Objects are built once in ``create_app`` and kept on ``app.state``; the providers below
expose them to routers as FastAPI dependencies, so tests can swap them with
``app.dependency_overrides``.
"""

from dataclasses import dataclass

from fastapi import Request
from sqlalchemy import Engine

from companion.config import Settings
from companion.repositories.clock import SystemClock
from companion.repositories.sql.assessments import SqlAssessmentLog
from companion.repositories.sql.engine import build_engine
from companion.repositories.sql.probe import SqlDatabaseProbe
from companion.repositories.sql.rules import SqlAirportDirectory, SqlRuleSetRepository
from companion.repositories.tools.http import HttpToolsClient
from companion.services.assessment.explanation import TemplateComposer
from companion.services.assessment.solver import DeterministicSolver
from companion.services.health import HealthService
from companion.services.trip_status import TripStatusService


@dataclass
class Container:
    health_service: HealthService
    trip_status_service: TripStatusService
    tools_client: HttpToolsClient

    def close(self) -> None:
        self.tools_client.close()


def build_container(settings: Settings) -> Container:
    engine: Engine = build_engine(settings.database_url.get_secret_value())
    tools = HttpToolsClient(
        str(settings.tools_base_url),
        settings.tools_api_token.get_secret_value(),
        settings.tools_timeout_seconds,
    )
    trip_status = TripStatusService(
        trips=tools,
        events=tools,
        rules=SqlRuleSetRepository(engine),
        airports=SqlAirportDirectory(engine),
        clock=SystemClock(),
        # Strategy seams (design D4): deterministic only in this demo.
        solver=DeterministicSolver(),
        composer=TemplateComposer(),
        assessment_log=SqlAssessmentLog(engine),
    )
    return Container(
        health_service=HealthService(probe=SqlDatabaseProbe(engine)),
        trip_status_service=trip_status,
        tools_client=tools,
    )


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_health_service(request: Request) -> HealthService:
    return request.app.state.container.health_service


def get_trip_status_service(request: Request) -> TripStatusService:
    return request.app.state.container.trip_status_service
