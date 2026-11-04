"""Mock tool service. This change ships the health endpoint only; the tool contracts
(get_trip_context, get_operational_events, ...) arrive with the decision engine change."""

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="Disruption Companion mock tools", docs_url=None, redoc_url=None)

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    return app
