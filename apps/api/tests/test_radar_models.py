from __future__ import annotations

import importlib.util
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import MetaData, Table, create_engine, func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from prairie_signal_api.db import Base
from prairie_signal_api.models import ImmutableRecordError, RadarArtifact

OBSERVATION_TIME = datetime(2026, 7, 31, 17, 45, tzinfo=UTC)


def _artifact(**overrides: Any) -> RadarArtifact:
    values: dict[str, Any] = {
        "source": "mrms",
        "region_id": "lincoln-ne",
        "product": "MergedReflectivityQCComposite_00.50",
        "variable": "composite_reflectivity",
        "units": "dBZ",
        "source_object_key": (
            "CONUS/MergedReflectivityQCComposite_00.50/20260731/"
            "MRMS_MergedReflectivityQCComposite_00.50_20260731-174500.grib2.gz"
        ),
        "source_url": (
            "https://noaa-mrms-pds.s3.amazonaws.com/CONUS/"
            "MergedReflectivityQCComposite_00.50/20260731/"
            "MRMS_MergedReflectivityQCComposite_00.50_20260731-174500.grib2.gz"
        ),
        "source_bucket": "noaa-mrms-pds",
        "source_etag": "fixture-etag",
        "source_last_modified": OBSERVATION_TIME + timedelta(seconds=20),
        "compressed_sha256": "a" * 64,
        "grib_sha256": "b" * 64,
        "raw_path": "raw/mrms/composite-reflectivity/a.grib2.gz",
        "normalized_zarr_path": (
            "normalized/mrms/lincoln-ne/composite-reflectivity/"
            "20260731T174500Z/mrms-reflectivity-v1.zarr"
        ),
        "preview_path": None,
        "observation_time": OBSERVATION_TIME,
        "valid_time": OBSERVATION_TIME,
        "discovered_at": OBSERVATION_TIME + timedelta(seconds=30),
        "downloaded_at": OBSERVATION_TIME + timedelta(minutes=1),
        "processing_started_at": OBSERVATION_TIME + timedelta(minutes=1, seconds=5),
        "processed_at": OBSERVATION_TIME + timedelta(minutes=1, seconds=12),
        "published_at": OBSERVATION_TIME + timedelta(minutes=1, seconds=13),
        "expires_at": OBSERVATION_TIME + timedelta(minutes=15),
        "source_projection": "EPSG:4326",
        "target_projection": "EPSG:5070",
        "geographic_bounds": {
            "west": -98.2,
            "south": 39.7,
            "east": -95.2,
            "north": 41.9,
        },
        "horizontal_resolution_m": 1000.0,
        "width_pixels": 300,
        "height_pixels": 240,
        "min_value": -10.0,
        "max_value": 62.5,
        "missing_percentage": 1.25,
        "no_coverage_percentage": 2.5,
        "source_byte_size": 12_345,
        "processing_version": "mrms-reflectivity-v1",
        "processing_state": "completed",
        "quality_flags": {
            "missing_value": -99,
            "no_coverage_value": -999,
            "resampling": "nearest",
        },
        "created_at": OBSERVATION_TIME + timedelta(minutes=1, seconds=13),
    }
    values.update(overrides)
    return RadarArtifact(**values)


def test_radar_artifact_persists_complete_metadata_with_aware_timestamps() -> None:
    artifact = _artifact()
    for field_name in (
        "source_last_modified",
        "observation_time",
        "valid_time",
        "discovered_at",
        "downloaded_at",
        "processing_started_at",
        "processed_at",
        "published_at",
        "expires_at",
        "created_at",
    ):
        value = getattr(artifact, field_name)
        assert value is not None
        assert value.tzinfo is not None
        assert value.utcoffset() is not None

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(artifact)
        session.commit()

        stored = session.scalar(select(RadarArtifact))
        assert stored is not None
        assert stored.source == "mrms"
        assert stored.source_bucket == "noaa-mrms-pds"
        assert stored.source_etag == "fixture-etag"
        assert stored.source_last_modified is not None
        assert stored.source_last_modified.replace(tzinfo=UTC) == OBSERVATION_TIME + timedelta(
            seconds=20
        )
        assert stored.processing_state == "completed"
        assert stored.geographic_bounds["west"] == -98.2
        assert stored.quality_flags["no_coverage_value"] == -999
    engine.dispose()


def test_radar_artifact_uniqueness_covers_source_key_and_compressed_content() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(_artifact())
        session.commit()

        session.add(_artifact(compressed_sha256="c" * 64))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            _artifact(
                source_object_key="CONUS/alternate-object.grib2.gz",
                compressed_sha256="a" * 64,
            ),
        )
        with pytest.raises(IntegrityError):
            session.commit()
    engine.dispose()


def test_radar_artifact_is_append_only() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    artifact = _artifact()

    with Session(engine, expire_on_commit=False) as session:
        session.add(artifact)
        session.commit()

        artifact.preview_path = "previews/replacement.png"
        with pytest.raises(ImmutableRecordError, match="append-only"):
            session.commit()
        session.rollback()

        session.delete(artifact)
        with pytest.raises(ImmutableRecordError, match="append-only"):
            session.commit()
    engine.dispose()


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    (
        ("source", "hrrr"),
        ("processing_state", "processing"),
        ("horizontal_resolution_m", 0),
        ("width_pixels", 0),
        ("missing_percentage", -0.01),
        ("no_coverage_percentage", 100.01),
        ("source_byte_size", -1),
    ),
)
def test_radar_artifact_rejects_invalid_fixed_and_range_values(
    field_name: str,
    invalid_value: Any,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(_artifact(**{field_name: invalid_value}))
        with pytest.raises(IntegrityError):
            session.commit()
    engine.dispose()


def _load_migration(filename: str, module_name: str) -> ModuleType:
    migration_path = Path(__file__).parent.parent / "alembic" / "versions" / filename
    spec = importlib.util.spec_from_file_location(module_name, migration_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_radar_artifact_migration_round_trips_after_initial_revision_on_sqlite() -> None:
    initial = _load_migration(
        "20260730_0001_initial_persistence.py",
        "prairie_signal_initial_migration_for_radar",
    )
    radar = _load_migration(
        "20260731_0002_radar_artifacts.py",
        "prairie_signal_radar_artifact_migration",
    )
    engine = create_engine("sqlite+pysqlite:///:memory:")

    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            initial.upgrade()
        assert "radar_artifacts" not in inspect(connection).get_table_names()

        with Operations.context(context):
            radar.upgrade()
        assert "radar_artifacts" in inspect(connection).get_table_names()
        columns = {column["name"] for column in inspect(connection).get_columns("radar_artifacts")}
        assert {
            "source_object_key",
            "compressed_sha256",
            "raw_path",
            "normalized_zarr_path",
            "geographic_bounds",
            "quality_flags",
            "processing_version",
            "processing_state",
        }.issubset(columns)
        column_types = {
            column["name"]: type(column["type"]).__name__
            for column in inspect(connection).get_columns("radar_artifacts")
        }
        assert column_types["source_projection"] == "TEXT"
        assert column_types["target_projection"] == "TEXT"

        with Operations.context(context):
            radar.downgrade()
        remaining_tables = set(inspect(connection).get_table_names())
        assert "radar_artifacts" not in remaining_tables
        assert {
            "locations",
            "source_fetches",
            "benchmark_archives",
            "alert_revisions",
        }.issubset(remaining_tables)

        with Operations.context(context):
            initial.downgrade()
        assert inspect(connection).get_table_names() == []
    engine.dispose()


def test_mrms_provenance_migration_backfills_existing_rows_on_sqlite() -> None:
    initial = _load_migration(
        "20260730_0001_initial_persistence.py",
        "prairie_signal_initial_migration_for_provenance",
    )
    radar = _load_migration(
        "20260731_0002_radar_artifacts.py",
        "prairie_signal_radar_migration_for_provenance",
    )
    provenance = _load_migration(
        "20260731_0003_mrms_acquisition_provenance.py",
        "prairie_signal_mrms_acquisition_provenance_migration",
    )
    engine = create_engine("sqlite+pysqlite:///:memory:")

    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            initial.upgrade()
            radar.upgrade()

        legacy_table = Table("radar_artifacts", MetaData(), autoload_with=connection)
        legacy_id = uuid.uuid4()
        legacy_artifact = _artifact(id=legacy_id)
        legacy_values = {
            column.name: getattr(legacy_artifact, column.name) for column in legacy_table.columns
        }
        legacy_values["id"] = legacy_id.hex
        connection.execute(legacy_table.insert().values(**legacy_values))

        with Operations.context(context):
            provenance.upgrade()

        columns = {
            column["name"]: column for column in inspect(connection).get_columns("radar_artifacts")
        }
        assert {
            "discovered_at",
            "source_bucket",
            "source_etag",
            "source_last_modified",
        }.issubset(columns)
        assert columns["discovered_at"]["nullable"] is False
        assert columns["source_bucket"]["nullable"] is False

        migrated_table = Table("radar_artifacts", MetaData(), autoload_with=connection)
        migrated = connection.execute(select(migrated_table)).mappings().one()
        assert migrated["discovered_at"] == migrated["downloaded_at"]
        assert migrated["source_bucket"] == "noaa-mrms-pds"
        assert migrated["source_etag"] is None
        assert migrated["source_last_modified"] is None

        with Operations.context(context):
            provenance.downgrade()
        downgraded_columns = {
            column["name"] for column in inspect(connection).get_columns("radar_artifacts")
        }
        assert {
            "discovered_at",
            "source_bucket",
            "source_etag",
            "source_last_modified",
        }.isdisjoint(downgraded_columns)
        downgraded_table = Table(
            "radar_artifacts",
            MetaData(),
            autoload_with=connection,
        )
        assert connection.scalar(select(func.count()).select_from(downgraded_table)) == 1

        with Operations.context(context):
            radar.downgrade()
            initial.downgrade()
    engine.dispose()
