"""Database primitives for the Prairie Signal API.

The runtime uses SQLAlchemy's async API.  Sync factories are intentionally
available for one-off maintenance tools and tests, but neither engine nor a
connection is created at import time.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from prairie_signal_api.config import get_settings

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(AsyncAttrs, DeclarativeBase):
    """Declarative base shared by application and ingestion models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _configured_database_url() -> str:
    return str(get_settings().database_url)


def async_database_url(url: str | URL | None = None) -> URL:
    """Return an async-driver URL while preserving all URL components."""

    parsed = make_url(str(url) if url is not None else _configured_database_url())
    driver = parsed.drivername
    if driver in {"postgres", "postgresql"}:
        return parsed.set(drivername="postgresql+asyncpg")
    if driver in {"sqlite", "sqlite+pysqlite"}:
        return parsed.set(drivername="sqlite+aiosqlite")
    return parsed


def sync_database_url(url: str | URL | None = None) -> URL:
    """Return a sync-driver URL for maintenance commands.

    PostgreSQL uses psycopg 3 when an asyncpg URL is supplied.  Callers using
    this helper must install the optional ``psycopg`` dependency.  Alembic's
    normal online path remains async and therefore only needs asyncpg.
    """

    parsed = make_url(str(url) if url is not None else _configured_database_url())
    driver = parsed.drivername
    if driver == "postgresql+asyncpg":
        return parsed.set(drivername="postgresql+psycopg")
    if driver == "sqlite+aiosqlite":
        return parsed.set(drivername="sqlite+pysqlite")
    return parsed


def async_database_url_string(url: str | URL | None = None) -> str:
    """Render an async URL without SQLAlchemy's display-only password masking.

    This value is for database drivers and Alembic configuration only. It must
    never be logged.
    """

    return async_database_url(url).render_as_string(hide_password=False)


def create_database_engine(
    url: str | URL | None = None,
    **engine_options: Any,
) -> AsyncEngine:
    """Create an async engine with safe defaults for a request-driven API."""

    options: dict[str, Any] = {
        "pool_pre_ping": True,
        "pool_recycle": 1_800,
    }
    options.update(engine_options)
    return create_async_engine(async_database_url(url), **options)


def create_sync_database_engine(
    url: str | URL | None = None,
    **engine_options: Any,
) -> Engine:
    """Create a sync engine for migrations, data loading, or tests."""

    options: dict[str, Any] = {"pool_pre_ping": True}
    options.update(engine_options)
    return create_engine(sync_database_url(url), **options)


@lru_cache(maxsize=1)
def get_async_engine() -> AsyncEngine:
    """Return the process-wide async engine, initialized lazily."""

    return create_database_engine()


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the process-wide typed async session factory."""

    return async_sessionmaker(
        bind=get_async_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


def create_sync_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a typed sync session factory for bounded maintenance jobs."""

    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that always closes its request-scoped session."""

    async with get_session_factory()() as session:
        yield session


# A concise alias for consumers that follow FastAPI's conventional naming.
get_db = get_db_session


async def dispose_database_engine() -> None:
    """Dispose the cached engine, primarily for process shutdown and tests."""

    if get_async_engine.cache_info().currsize:
        await get_async_engine().dispose()
    get_session_factory.cache_clear()
    get_async_engine.cache_clear()


__all__ = [
    "NAMING_CONVENTION",
    "Base",
    "async_database_url",
    "async_database_url_string",
    "create_database_engine",
    "create_sync_database_engine",
    "create_sync_session_factory",
    "dispose_database_engine",
    "get_async_engine",
    "get_db",
    "get_db_session",
    "get_session_factory",
    "sync_database_url",
]
