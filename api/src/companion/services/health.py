from companion.ports.database import DatabaseProbe
from companion.schemas.health import ReadyStatus


class HealthService:
    """Readiness of the API's dependencies (design D2)."""

    def __init__(self, probe: DatabaseProbe) -> None:
        self._probe = probe

    def readiness(self) -> ReadyStatus:
        return ReadyStatus(status="ready" if self._probe.is_reachable() else "not_ready")
