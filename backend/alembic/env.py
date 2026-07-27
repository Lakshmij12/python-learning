"""Alembic migration environment.

The target metadata is ``app.models.Base.metadata`` (importing ``app.models``
registers every table). The database URL comes from application settings
(sync DSN using the psycopg driver), so no credentials live in ``alembic.ini``.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import the application metadata (registers all models).
from app.config.settings import get_settings
from app.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject the runtime database URL (sync driver for migrations). An explicit
# ALEMBIC_DATABASE_URL wins — handy for CI/tests (e.g. a SQLite URL).
config.set_main_option(
    "sqlalchemy.url",
    os.environ.get("ALEMBIC_DATABASE_URL") or get_settings().db.sync_dsn,
)

target_metadata = Base.metadata


def _include_object(obj, name, type_, reflected, compare_to):  # noqa: ANN001, ANN202
    """Hook to exclude objects from autogenerate if ever needed."""
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a DBAPI connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
        include_object=_include_object,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against a live connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_object=_include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
