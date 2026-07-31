"""Idempotent persistence for completed normalized radar artifacts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from prairie_signal_api.models import RadarArtifact
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prairie_signal_ingestion.adapters.mrms import MRMS_S3_BUCKET
from prairie_signal_ingestion.mrms_processing import NormalizedMRMSArtifact


class RadarMetadataConflict(RuntimeError):
    """Raised when an immutable radar identity points at conflicting metadata."""


def build_radar_record(artifact: NormalizedMRMSArtifact) -> RadarArtifact:
    """Map a validated artifact to the complete append-only database record."""

    metadata = artifact.metadata
    source_grid = metadata["source_grid"]
    quality_flags: dict[str, Any] = {
        "flag_values": metadata["quality_flag_values"],
        "native_missing_value": metadata["native_missing_value"],
        "native_no_coverage_value": metadata["native_no_coverage_value"],
        "resampling": metadata["resampling"],
        "source_crs_wkt": source_grid["crs_wkt"],
        "source_statistics": metadata["source_statistics"],
        "normalized_statistics": metadata["normalized_statistics"],
    }
    return RadarArtifact(
        source="mrms",
        region_id=artifact.region_id,
        product=str(metadata["product"]),
        variable=str(metadata["variable"]),
        units=str(metadata["units"]),
        source_object_key=artifact.source.source.key,
        source_url=str(metadata["source_url"]),
        source_bucket=_nonempty_string(
            metadata.get("source_bucket", MRMS_S3_BUCKET),
            "source_bucket",
        ),
        source_etag=_optional_string(
            metadata.get("source_etag", artifact.source.source.etag),
            "source_etag",
        ),
        source_last_modified=_optional_datetime(
            metadata.get(
                "source_last_modified",
                artifact.source.source.last_modified,
            ),
            "source_last_modified",
        ),
        compressed_sha256=artifact.source.compressed_sha256,
        grib_sha256=artifact.source.decompressed_sha256,
        raw_path=str(artifact.source.path),
        normalized_zarr_path=str(artifact.zarr_path),
        preview_path=str(artifact.preview_path),
        observation_time=artifact.source.source.valid_time,
        valid_time=artifact.source.source.valid_time,
        discovered_at=_required_datetime(
            metadata.get("discovered_at", artifact.source.source.discovered_at),
            "discovered_at",
        ),
        downloaded_at=artifact.source.downloaded_at,
        processing_started_at=artifact.processing_started_at,
        processed_at=artifact.processed_at,
        published_at=artifact.published_at,
        expires_at=_optional_datetime(metadata.get("expiration_time"), "expiration_time"),
        source_projection=artifact.source_projection,
        target_projection=artifact.target_projection,
        geographic_bounds=artifact.geographic_bounds,
        horizontal_resolution_m=artifact.horizontal_resolution_m,
        width_pixels=artifact.width_pixels,
        height_pixels=artifact.height_pixels,
        min_value=artifact.minimum_dbz,
        max_value=artifact.maximum_dbz,
        missing_percentage=artifact.missing_percentage,
        no_coverage_percentage=artifact.no_coverage_percentage,
        source_byte_size=artifact.source.compressed_size,
        processing_version=str(metadata["processing_version"]),
        processing_state="completed",
        quality_flags=quality_flags,
    )


class RadarArtifactWriter:
    """Insert completed radar metadata once, returning an exact existing row on rerun."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def record(self, artifact: NormalizedMRMSArtifact) -> RadarArtifact:
        candidate = build_radar_record(artifact)
        async with self._session_factory() as session:
            async with session.begin():
                existing = await session.scalar(
                    select(RadarArtifact).where(
                        RadarArtifact.region_id == candidate.region_id,
                        RadarArtifact.processing_version == candidate.processing_version,
                        or_(
                            RadarArtifact.source_object_key == candidate.source_object_key,
                            RadarArtifact.compressed_sha256 == candidate.compressed_sha256,
                        ),
                    )
                )
                if existing is not None:
                    _require_same_identity(existing, candidate)
                    return existing
                session.add(candidate)
                await session.flush()
                return candidate


def _require_same_identity(existing: RadarArtifact, candidate: RadarArtifact) -> None:
    fields = (
        "source_object_key",
        "compressed_sha256",
        "grib_sha256",
        "raw_path",
        "normalized_zarr_path",
        "product",
        "variable",
        "units",
        "valid_time",
    )
    conflicts = [
        field_name
        for field_name in fields
        if getattr(existing, field_name) != getattr(candidate, field_name)
    ]
    if conflicts:
        raise RadarMetadataConflict("Existing radar metadata conflicts on: " + ", ".join(conflicts))


def _required_datetime(value: object, field_name: str) -> datetime:
    parsed = _optional_datetime(value, field_name)
    if parsed is None:
        raise RadarMetadataConflict(f"Radar {field_name} timestamp is required")
    return parsed


def _optional_datetime(value: object, field_name: str) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise RadarMetadataConflict(f"Radar {field_name} timestamp is invalid") from exc
    else:
        raise RadarMetadataConflict(f"Radar {field_name} timestamp is invalid")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RadarMetadataConflict(f"Radar {field_name} timestamp must be timezone-aware")
    return parsed.astimezone(UTC)


def _nonempty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RadarMetadataConflict(f"Radar {field_name} is invalid")
    return value


def _optional_string(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _nonempty_string(value, field_name)


__all__ = [
    "RadarArtifactWriter",
    "RadarMetadataConflict",
    "build_radar_record",
]
