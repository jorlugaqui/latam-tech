from sqlalchemy import Engine, create_engine, make_url

CONNECT_TIMEOUT_SECONDS = 2


def build_engine(url: str) -> Engine:
    """Create an engine for PostgreSQL (runtime) or SQLite (unit tests)."""
    backend = make_url(url).get_backend_name()
    connect_args: dict[str, object] = {}
    if backend == "postgresql":
        connect_args["connect_timeout"] = CONNECT_TIMEOUT_SECONDS
    elif backend == "sqlite":
        connect_args["timeout"] = CONNECT_TIMEOUT_SECONDS
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)
