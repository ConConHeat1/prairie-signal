from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from prairie_signal_api.db import Base, async_database_url_string
from prairie_signal_api.models import (
    BenchmarkArchive,
    ImmutableRecordError,
    Location,
    LocationKind,
    ResourceKind,
    SourceFetch,
    SourceName,
)


def _records() -> tuple[Location, SourceFetch, BenchmarkArchive]:
    now = datetime.now(UTC)
    location = Location(
        slug="lincoln-ne",
        kind=LocationKind.CITY,
        name="Lincoln",
        normalized_name="lincoln",
        state_code="NE",
        country_code="US",
        latitude=40.8136,
        longitude=-96.7026,
        timezone="America/Chicago",
        source_name=SourceName.CONFIG,
        source_record_id="benchmark:lincoln-ne",
        is_public_benchmark=True,
    )
    fetch = SourceFetch(
        benchmark_location=location,
        source_name=SourceName.NWS,
        resource_kind=ResourceKind.POINT,
        resource_uri="https://api.weather.gov/points/40.8136,-96.7026",
        status_code=200,
        succeeded=True,
        content_sha256="a" * 64,
        response_headers={"etag": '"fixture"'},
        requested_at=now,
        fetched_at=now,
        duration_ms=10,
    )
    archive = BenchmarkArchive(
        source_fetch=fetch,
        benchmark_location=location,
        resource_kind=ResourceKind.POINT,
        content_type="application/geo+json",
        payload={"type": "Feature"},
        content_sha256="a" * 64,
        byte_size=18,
        fetched_at=now,
        pipeline_version="test-v1",
    )
    return location, fetch, archive


def test_models_use_portable_enum_values_and_append_only_archives() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    _, _, archive = _records()

    with Session(engine, expire_on_commit=False) as session:
        session.add(archive)
        session.commit()
        stored = session.scalar(select(Location))
        assert stored is not None
        assert stored.kind is LocationKind.CITY
        assert stored.source_name is SourceName.CONFIG

        archive.pipeline_version = "rewritten"
        with pytest.raises(ImmutableRecordError, match="append-only"):
            session.commit()
    engine.dispose()


def test_provenance_schema_requires_a_public_location_reference() -> None:
    for table in (
        SourceFetch.__table__,
        BenchmarkArchive.__table__,
    ):
        assert table.c.benchmark_location_id.nullable is False

    persisted_columns = {
        column.name for table in Base.metadata.sorted_tables for column in table.columns
    }
    assert persisted_columns.isdisjoint(
        {
            "client_ip",
            "ip_address",
            "query",
            "query_string",
            "search_text",
            "user_id",
        },
    )


def _load_initial_migration() -> ModuleType:
    migration_path = (
        Path(__file__).parent.parent
        / "alembic"
        / "versions"
        / "20260730_0001_initial_persistence.py"
    )
    spec = importlib.util.spec_from_file_location(
        "prairie_signal_initial_migration",
        migration_path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_initial_migration_round_trips_on_sqlite() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    migration = _load_initial_migration()

    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()

        assert {
            "locations",
            "source_fetches",
            "benchmark_archives",
            "alert_revisions",
        }.issubset(inspect(connection).get_table_names())

        with Operations.context(context):
            migration.downgrade()
        assert inspect(connection).get_table_names() == []
    engine.dispose()


def test_database_driver_url_does_not_replace_password_with_mask() -> None:
    rendered = async_database_url_string(
        "postgresql://prairie:actual-password@db:5432/prairie_signal"
    )

    assert rendered == ("postgresql+asyncpg://prairie:actual-password@db:5432/prairie_signal")
    assert "***" not in rendered
