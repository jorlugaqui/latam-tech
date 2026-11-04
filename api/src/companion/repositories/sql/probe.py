import logging

from sqlalchemy import Engine, text

logger = logging.getLogger(__name__)


class SqlDatabaseProbe:
    """``DatabaseProbe`` adapter: runs ``SELECT 1`` against the configured engine."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def is_reachable(self) -> bool:
        try:
            with self._engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception as exc:
            # Log only the exception type: driver messages carry host, user and sometimes
            # connection parameters, which must stay out of logs (spec api-health).
            logger.warning("database probe failed: %s", type(exc).__name__)
            return False
        return True
