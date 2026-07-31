"""Persistent, privacy-bounded records used by Prairie Signal.

Only public gazetteer entries and explicitly configured public benchmark
locations belong in these tables.  Interactive searches and user-supplied
coordinates are deliberately absent from the schema.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    event,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from prairie_signal_api.db import Base

JSON_DOCUMENT = JSON().with_variant(JSONB(), "postgresql")


class LocationKind(str, enum.Enum):
    CITY = "city"
    ZCTA = "zcta"


class SourceName(str, enum.Enum):
    NWS = "nws"
    CENSUS = "census"
    CONFIG = "config"


class ResourceKind(str, enum.Enum):
    POINT = "point"
    FORECAST = "forecast"
    HOURLY = "hourly"
    STATIONS = "stations"
    OBSERVATION = "observation"
    ALERTS = "alerts"
    GAZETTEER = "gazetteer"


def enum_column(enum_type: type[enum.Enum], name: str) -> Enum:
    return Enum(
        enum_type,
        name=name,
        values_callable=lambda members: [member.value for member in members],
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
    )


class Location(Base):
    """A public Census location or an explicitly configured benchmark."""

    __tablename__ = "locations"
    __table_args__ = (
        CheckConstraint(
            "latitude >= -90 AND latitude <= 90",
            name="latitude_range",
        ),
        CheckConstraint(
            "longitude >= -180 AND longitude <= 180",
            name="longitude_range",
        ),
        UniqueConstraint(
            "source_name",
            "source_record_id",
            name="uq_locations_source_record",
        ),
        Index("ix_locations_normalized_name_state", "normalized_name", "state_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    slug: Mapped[str] = mapped_column(String(160), unique=True)
    kind: Mapped[LocationKind] = mapped_column(
        enum_column(LocationKind, "location_kind"),
    )
    name: Mapped[str] = mapped_column(String(200))
    normalized_name: Mapped[str] = mapped_column(String(200), index=True)
    state_code: Mapped[str] = mapped_column(String(2), index=True)
    country_code: Mapped[str] = mapped_column(String(2), default="US")
    postal_code: Mapped[str | None] = mapped_column(String(5), index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    timezone: Mapped[str] = mapped_column(String(64))
    population: Mapped[int | None] = mapped_column(Integer)
    source_name: Mapped[SourceName] = mapped_column(
        enum_column(SourceName, "location_source_name"),
    )
    source_record_id: Mapped[str] = mapped_column(String(64))
    is_public_benchmark: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    source_fetches: Mapped[list[SourceFetch]] = relationship(
        back_populates="benchmark_location",
        passive_deletes=True,
    )
    archives: Mapped[list[BenchmarkArchive]] = relationship(
        back_populates="benchmark_location",
        passive_deletes=True,
    )
    alert_revisions: Mapped[list[AlertRevision]] = relationship(
        back_populates="benchmark_location",
        passive_deletes=True,
    )


class SourceFetch(Base):
    """Immutable metadata for one fetch made by benchmark ingestion."""

    __tablename__ = "source_fetches"
    __table_args__ = (
        CheckConstraint("duration_ms >= 0", name="duration_nonnegative"),
        CheckConstraint(
            "status_code IS NULL OR (status_code >= 100 AND status_code <= 599)",
            name="status_code_range",
        ),
        Index(
            "ix_source_fetches_benchmark_resource_fetched",
            "benchmark_location_id",
            "resource_kind",
            "fetched_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    benchmark_location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_name: Mapped[SourceName] = mapped_column(
        enum_column(SourceName, "fetch_source_name"),
    )
    resource_kind: Mapped[ResourceKind] = mapped_column(
        enum_column(ResourceKind, "resource_kind"),
    )
    # This URI is produced only from a configured public benchmark.
    resource_uri: Mapped[str] = mapped_column(Text)
    status_code: Mapped[int | None] = mapped_column(Integer)
    succeeded: Mapped[bool] = mapped_column(Boolean)
    etag: Mapped[str | None] = mapped_column(Text)
    last_modified: Mapped[str | None] = mapped_column(Text)
    cache_control: Mapped[str | None] = mapped_column(Text)
    content_sha256: Mapped[str | None] = mapped_column(String(64))
    response_headers: Mapped[dict[str, Any]] = mapped_column(
        JSON_DOCUMENT,
        default=dict,
    )
    error_code: Mapped[str | None] = mapped_column(String(80))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    benchmark_location: Mapped[Location] = relationship(
        back_populates="source_fetches",
    )
    archive: Mapped[BenchmarkArchive | None] = relationship(
        back_populates="source_fetch",
        uselist=False,
    )
    alert_revisions: Mapped[list[AlertRevision]] = relationship(
        back_populates="source_fetch",
    )


class BenchmarkArchive(Base):
    """An immutable upstream payload for a configured public benchmark."""

    __tablename__ = "benchmark_archives"
    __table_args__ = (
        CheckConstraint("byte_size >= 0", name="byte_size_nonnegative"),
        Index(
            "ix_benchmark_archives_location_resource_archived",
            "benchmark_location_id",
            "resource_kind",
            "archived_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    source_fetch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_fetches.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    benchmark_location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    resource_kind: Mapped[ResourceKind] = mapped_column(
        enum_column(ResourceKind, "archive_resource_kind"),
    )
    content_type: Mapped[str] = mapped_column(String(120))
    payload: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSON_DOCUMENT)
    content_sha256: Mapped[str] = mapped_column(String(64), index=True)
    byte_size: Mapped[int] = mapped_column(Integer)
    source_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    pipeline_version: Mapped[str] = mapped_column(String(80))

    source_fetch: Mapped[SourceFetch] = relationship(back_populates="archive")
    benchmark_location: Mapped[Location] = relationship(back_populates="archives")


class AlertRevision(Base):
    """An immutable, verbatim revision of an official NWS alert."""

    __tablename__ = "alert_revisions"
    __table_args__ = (
        UniqueConstraint(
            "benchmark_location_id",
            "alert_identifier",
            "content_sha256",
            name="uq_alert_revisions_location_identifier_content",
        ),
        Index(
            "ix_alert_revisions_identifier_observed",
            "alert_identifier",
            "observed_at",
        ),
        Index(
            "ix_alert_revisions_location_expires",
            "benchmark_location_id",
            "expires_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    benchmark_location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_fetch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_fetches.id", ondelete="RESTRICT"),
        nullable=False,
    )
    alert_identifier: Mapped[str] = mapped_column(Text)
    content_sha256: Mapped[str] = mapped_column(String(64))
    original_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT)
    geometry: Mapped[dict[str, Any] | None] = mapped_column(JSON_DOCUMENT)
    issuing_office: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str | None] = mapped_column(String(32))
    message_type: Mapped[str | None] = mapped_column(String(32))
    category: Mapped[str | None] = mapped_column(String(32))
    severity: Mapped[str | None] = mapped_column(String(32))
    certainty: Mapped[str | None] = mapped_column(String(32))
    urgency: Mapped[str | None] = mapped_column(String(32))
    event: Mapped[str | None] = mapped_column(String(200))
    headline: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    instruction: Mapped[str | None] = mapped_column(Text)
    area_description: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    onset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    benchmark_location: Mapped[Location] = relationship(
        back_populates="alert_revisions",
    )
    source_fetch: Mapped[SourceFetch] = relationship(
        back_populates="alert_revisions",
    )


class RadarArtifact(Base):
    """Immutable metadata for one completed, normalized MRMS artifact."""

    __tablename__ = "radar_artifacts"
    __table_args__ = (
        CheckConstraint("source = 'mrms'", name="source_mrms"),
        CheckConstraint(
            "processing_state = 'completed'",
            name="processing_state_completed",
        ),
        CheckConstraint(
            "length(compressed_sha256) = 64",
            name="compressed_sha256_length",
        ),
        CheckConstraint(
            "length(grib_sha256) = 64",
            name="grib_sha256_length",
        ),
        CheckConstraint(
            "horizontal_resolution_m > 0",
            name="horizontal_resolution_positive",
        ),
        CheckConstraint("width_pixels > 0", name="width_pixels_positive"),
        CheckConstraint("height_pixels > 0", name="height_pixels_positive"),
        CheckConstraint(
            "min_value IS NULL OR max_value IS NULL OR min_value <= max_value",
            name="value_range_ordered",
        ),
        CheckConstraint(
            "missing_percentage >= 0 AND missing_percentage <= 100",
            name="missing_percentage_range",
        ),
        CheckConstraint(
            "no_coverage_percentage >= 0 AND no_coverage_percentage <= 100",
            name="no_coverage_percentage_range",
        ),
        CheckConstraint(
            "missing_percentage + no_coverage_percentage <= 100",
            name="masked_percentage_total_range",
        ),
        CheckConstraint(
            "source_byte_size >= 0",
            name="source_byte_size_nonnegative",
        ),
        UniqueConstraint(
            "region_id",
            "source_object_key",
            "processing_version",
            name="uq_radar_artifacts_region_source_object_processing",
        ),
        UniqueConstraint(
            "region_id",
            "compressed_sha256",
            "processing_version",
            name="uq_radar_artifacts_region_compressed_sha_processing",
        ),
        Index(
            "ix_radar_artifacts_region_product_valid_time",
            "region_id",
            "product",
            "valid_time",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    source: Mapped[str] = mapped_column(
        String(16),
        default="mrms",
        server_default="mrms",
    )
    region_id: Mapped[str] = mapped_column(String(120))
    product: Mapped[str] = mapped_column(String(200))
    variable: Mapped[str] = mapped_column(String(120))
    units: Mapped[str] = mapped_column(String(32))
    source_object_key: Mapped[str] = mapped_column(String(512))
    source_url: Mapped[str] = mapped_column(Text)
    source_bucket: Mapped[str] = mapped_column(String(120))
    source_etag: Mapped[str | None] = mapped_column(Text)
    source_last_modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    compressed_sha256: Mapped[str] = mapped_column(String(64))
    grib_sha256: Mapped[str] = mapped_column(String(64))
    raw_path: Mapped[str] = mapped_column(Text)
    normalized_zarr_path: Mapped[str] = mapped_column(Text)
    preview_path: Mapped[str | None] = mapped_column(Text)
    observation_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    processing_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_projection: Mapped[str] = mapped_column(Text)
    target_projection: Mapped[str] = mapped_column(Text)
    geographic_bounds: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT)
    horizontal_resolution_m: Mapped[float] = mapped_column(Float)
    width_pixels: Mapped[int] = mapped_column(Integer)
    height_pixels: Mapped[int] = mapped_column(Integer)
    min_value: Mapped[float | None] = mapped_column(Float)
    max_value: Mapped[float | None] = mapped_column(Float)
    missing_percentage: Mapped[float] = mapped_column(Float)
    no_coverage_percentage: Mapped[float] = mapped_column(Float)
    source_byte_size: Mapped[int] = mapped_column(BigInteger)
    processing_version: Mapped[str] = mapped_column(String(80))
    processing_state: Mapped[str] = mapped_column(
        String(24),
        default="completed",
        server_default="completed",
    )
    quality_flags: Mapped[dict[str, Any]] = mapped_column(
        JSON_DOCUMENT,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class ImmutableRecordError(ValueError):
    """Raised when application code attempts to mutate archived provenance."""


def _reject_mutation(_mapper: Any, _connection: Any, target: Any) -> None:
    raise ImmutableRecordError(
        f"{type(target).__name__} records are append-only and cannot be mutated",
    )


for _immutable_model in (SourceFetch, BenchmarkArchive, AlertRevision, RadarArtifact):
    event.listen(_immutable_model, "before_update", _reject_mutation)
    event.listen(_immutable_model, "before_delete", _reject_mutation)


__all__ = [
    "AlertRevision",
    "BenchmarkArchive",
    "ImmutableRecordError",
    "Location",
    "LocationKind",
    "RadarArtifact",
    "ResourceKind",
    "SourceFetch",
    "SourceName",
]
