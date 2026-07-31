"""Alembic environment using the application's async database driver."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig
from typing import Any

from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from prairie_signal_api import models as _models  # noqa: F401
from prairie_signal_api.db import Base, async_database_url_string

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
_POSTGIS_MANAGED_TABLES = frozenset({"spatial_ref_sys"})


def include_object(
    _object: Any,
    name: str | None,
    type_: str,
    reflected: bool,
    _compare_to: Any,
) -> bool:
    """Keep PostGIS extension tables outside application migration drift."""

    return not (reflected and type_ == "table" and name in _POSTGIS_MANAGED_TABLES)


def configured_url() -> str:
    """Prefer application settings while retaining Alembic's ini fallback."""

    try:
        return async_database_url_string()
    except Exception:
        ini_url = config.get_main_option("sqlalchemy.url")
        return async_database_url_string(ini_url)


def run_migrations_offline() -> None:
    context.configure(
        url=configured_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    if connection.dialect.name == "postgresql":
        # The PostGIS image adds topology/tiger to the role's search path. Restrict
        # reflection to application-owned public objects during autogenerate/check.
        connection.exec_driver_sql("SET search_path TO public")
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = configured_url()
    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
