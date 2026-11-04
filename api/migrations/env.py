"""Alembic environment (design D11).

- URL: ``sqlalchemy.url`` when set programmatically (unit tests), otherwise DATABASE_URL.
- ``render_as_batch=True`` so ALTER/DROP work on SQLite as well as PostgreSQL, which is
  what lets expand/migrate/contract revisions be unit-tested.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from companion.config import DatabaseSettings
from companion.repositories.sql.tables import metadata

config = context.config

if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = metadata


def _database_url() -> str:
    explicit = config.get_main_option("sqlalchemy.url")
    if explicit:
        return explicit
    return DatabaseSettings().database_url.get_secret_value()


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        {"sqlalchemy.url": _database_url()},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
