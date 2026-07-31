"""Decode one MRMS reflectivity object onto a configured regional Zarr grid."""

from __future__ import annotations

import errno
import gzip
import hashlib
import json
import math
import os
import re
import shutil
import tempfile
import warnings
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final

import numpy as np
import rasterio
import zarr
from PIL import Image
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.transform import Affine
from rasterio.warp import reproject, transform, transform_bounds
from rasterio.windows import Window

from prairie_signal_ingestion.adapters.mrms import (
    MRMS_PRODUCT,
    MRMSDownloadedArtifact,
)
from prairie_signal_ingestion.radar_config import MrmsConfig, RegionConfig

QUALITY_VALID: Final = np.uint8(0)
QUALITY_MISSING: Final = np.uint8(1)
QUALITY_NO_COVERAGE: Final = np.uint8(2)
QUALITY_OUTSIDE_SOURCE: Final = np.uint8(3)

_VALID_TIME_PATTERN = re.compile(r"^-?[0-9]+")


class MRMSProcessingError(RuntimeError):
    """Base class for safe decode/normalization failures."""


class MRMSContractError(MRMSProcessingError):
    """Raised when decoded data no longer matches the verified source contract."""


class MRMSPublicationConflict(MRMSProcessingError):
    """Raised rather than replacing an existing normalized artifact."""


@dataclass(frozen=True, slots=True)
class NormalizedMRMSArtifact:
    """Published normalized output and immutable metadata."""

    source: MRMSDownloadedArtifact
    region_id: str
    zarr_path: Path
    preview_path: Path
    processing_started_at: datetime
    processed_at: datetime
    published_at: datetime
    source_projection: str
    target_projection: str
    geographic_bounds: dict[str, float]
    width_pixels: int
    height_pixels: int
    horizontal_resolution_m: float
    minimum_dbz: float | None
    maximum_dbz: float | None
    missing_percentage: float
    no_coverage_percentage: float
    metadata: dict[str, Any]
    reused: bool = False


def process_mrms_reflectivity(
    source: MRMSDownloadedArtifact,
    *,
    data_root: Path,
    temporary_directory: Path,
    region: RegionConfig,
    config: MrmsConfig,
    fixture_mode: bool = False,
    now: datetime | None = None,
) -> NormalizedMRMSArtifact:
    """Validate, crop, reproject, and atomically publish one reflectivity frame."""

    if source.source.key.split("/", maxsplit=2)[1] != MRMS_PRODUCT:
        raise MRMSContractError("Downloaded artifact is not the configured MRMS product")
    if source.source.discovered_at is None:
        raise MRMSContractError("Downloaded artifact is missing its discovery timestamp")
    _require_utc(source.source.discovered_at, "discovered_at")
    processing_started_at = _require_utc(now or datetime.now(UTC), "processing start")
    target = _normalized_target(data_root, source, region, config)
    if target.exists():
        return _reuse_existing(target, source, region, config)

    temporary_directory.mkdir(parents=True, exist_ok=True)
    descriptor, grib_name = tempfile.mkstemp(
        dir=temporary_directory,
        prefix=f"{source.source.filename}.",
        suffix=".grib2.part",
    )
    os.close(descriptor)
    grib_path = Path(grib_name)
    staging: Path | None = None
    try:
        _decompress_checked(source, grib_path)
        decoded = _decode_region(
            grib_path,
            source=source,
            region=region,
            config=config,
            fixture_mode=fixture_mode,
        )
        processed_at = datetime.now(UTC)
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(
            tempfile.mkdtemp(
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".part",
            )
        )
        publication_time = datetime.now(UTC)
        metadata = _build_metadata(
            source,
            region=region,
            config=config,
            decoded=decoded,
            processing_started_at=processing_started_at,
            processed_at=processed_at,
            publication_time=publication_time,
            fixture_mode=fixture_mode,
        )
        _write_zarr(staging, decoded, metadata, config)
        preview_path = staging / "diagnostic-preview.png"
        _write_preview(preview_path, decoded.reflectivity_dbz, decoded.quality_flag)
        (staging / "metadata.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _fsync_tree(staging)
        _publish_directory(staging, target)
        staging = None
        published_at = datetime.now(UTC)
        return _artifact_from_metadata(
            source,
            target,
            metadata,
            published_at=published_at,
            reused=False,
        )
    finally:
        grib_path.unlink(missing_ok=True)
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)


@dataclass(frozen=True, slots=True)
class _DecodedRegion:
    reflectivity_dbz: np.ndarray[Any, np.dtype[np.float32]]
    quality_flag: np.ndarray[Any, np.dtype[np.uint8]]
    x: np.ndarray[Any, np.dtype[np.float64]]
    y: np.ndarray[Any, np.dtype[np.float64]]
    target_transform: Affine
    target_bounds: tuple[float, float, float, float]
    geographic_bounds: dict[str, float]
    source_metadata: dict[str, Any]
    source_statistics: dict[str, Any]
    normalized_statistics: dict[str, Any]


def _decode_region(
    path: Path,
    *,
    source: MRMSDownloadedArtifact,
    region: RegionConfig,
    config: MrmsConfig,
    fixture_mode: bool,
) -> _DecodedRegion:
    try:
        dataset = rasterio.open(path)
    except rasterio.errors.RasterioError as exc:
        raise MRMSContractError("MRMS GRIB2 could not be decoded by GDAL") from exc

    with dataset:
        if not fixture_mode and dataset.driver != "GRIB":
            raise MRMSContractError(f"Expected GRIB driver, received {dataset.driver!r}")
        if dataset.count != 1:
            raise MRMSContractError("MRMS reflectivity object must contain exactly one raster band")
        if dataset.crs is None or not dataset.crs.is_geographic:
            raise MRMSContractError("MRMS reflectivity grid must use geographic coordinates")
        if dataset.width < 1 or dataset.height < 1:
            raise MRMSContractError("MRMS reflectivity grid is empty")
        x_resolution = abs(float(dataset.transform.a))
        y_resolution = abs(float(dataset.transform.e))
        expected_resolution = config.product.source_resolution_degrees
        if not (
            math.isclose(x_resolution, expected_resolution, abs_tol=1e-6)
            and math.isclose(y_resolution, expected_resolution, abs_tol=1e-6)
        ):
            raise MRMSContractError(
                "MRMS source spacing changed from the verified 0.01-degree grid"
            )
        if not (
            math.isclose(float(dataset.transform.b), 0, abs_tol=1e-12)
            and math.isclose(float(dataset.transform.d), 0, abs_tol=1e-12)
            and float(dataset.transform.a) > 0
            and float(dataset.transform.e) < 0
        ):
            raise MRMSContractError(
                "MRMS source scanning order changed from west-to-east, north-to-south"
            )
        if not fixture_mode:
            expected_bounds = config.product.source_bounds_degrees
            observed_bounds = tuple(float(value) for value in dataset.bounds)
            configured_bounds = (
                expected_bounds.west,
                expected_bounds.south,
                expected_bounds.east,
                expected_bounds.north,
            )
            if (
                dataset.width != config.product.source_width_pixels
                or dataset.height != config.product.source_height_pixels
                or any(
                    not math.isclose(observed, expected, abs_tol=1e-3)
                    for observed, expected in zip(
                        observed_bounds,
                        configured_bounds,
                        strict=True,
                    )
                )
            ):
                raise MRMSContractError(
                    "MRMS source dimensions or CONUS extent changed from the verified grid"
                )

        tags = dataset.tags(1)
        _validate_band_contract(tags, source, config)
        target_crs = CRS.from_string(region.grid.projection)
        target_bounds, target_transform = _target_grid(region, target_crs)
        source_bounds = transform_bounds(
            target_crs,
            dataset.crs,
            *target_bounds,
            densify_pts=21,
        )
        window = _bounded_source_window(dataset, source_bounds, margin_pixels=2)
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="Setting the shape on a NumPy array has been deprecated.*",
                category=DeprecationWarning,
            )
            native = dataset.read(1, window=window, masked=False).astype(
                np.float32,
                copy=False,
            )
            native_mask = dataset.read_masks(1, window=window) == 0
        source_transform = dataset.window_transform(window)
        quality = _classify_quality(native, native_mask, config)
        valid_native = quality == QUALITY_VALID
        _validate_reflectivity_range(native, valid_native)

        destination: np.ndarray[Any, np.dtype[np.float32]] = np.full(
            (region.height_pixels, region.width_pixels),
            np.nan,
            dtype=np.float32,
        )
        source_values = np.where(valid_native, native, np.nan).astype(np.float32, copy=False)
        reproject(
            source=source_values,
            destination=destination,
            src_transform=source_transform,
            src_crs=dataset.crs,
            src_nodata=np.nan,
            dst_transform=target_transform,
            dst_crs=target_crs,
            dst_nodata=np.nan,
            resampling=Resampling.nearest,
            init_dest_nodata=True,
        )
        destination_quality: np.ndarray[Any, np.dtype[np.uint8]] = np.full(
            destination.shape,
            QUALITY_OUTSIDE_SOURCE,
            dtype=np.uint8,
        )
        reproject(
            source=quality,
            destination=destination_quality,
            src_transform=source_transform,
            src_crs=dataset.crs,
            src_nodata=None,
            dst_transform=target_transform,
            dst_crs=target_crs,
            dst_nodata=int(QUALITY_OUTSIDE_SOURCE),
            resampling=Resampling.nearest,
            init_dest_nodata=True,
        )
        destination[destination_quality != QUALITY_VALID] = np.nan
        _validate_reflectivity_range(
            destination,
            destination_quality == QUALITY_VALID,
        )

        x = (
            target_transform.c
            + (np.arange(region.width_pixels, dtype=np.float64) + 0.5) * target_transform.a
        )
        y = (
            target_transform.f
            + (np.arange(region.height_pixels, dtype=np.float64) + 0.5) * target_transform.e
        )
        geographic = transform_bounds(target_crs, "EPSG:4326", *target_bounds, densify_pts=21)
        geographic_bounds = {
            "west": float(geographic[0]),
            "south": float(geographic[1]),
            "east": float(geographic[2]),
            "north": float(geographic[3]),
        }
        source_crs_text = dataset.crs.to_string()
        return _DecodedRegion(
            reflectivity_dbz=destination,
            quality_flag=destination_quality,
            x=x,
            y=y,
            target_transform=target_transform,
            target_bounds=target_bounds,
            geographic_bounds=geographic_bounds,
            source_metadata={
                "driver": dataset.driver,
                "width_pixels": dataset.width,
                "height_pixels": dataset.height,
                "crs": source_crs_text,
                "crs_wkt": dataset.crs.to_wkt(),
                "bounds": [float(value) for value in dataset.bounds],
                "resolution_degrees": [x_resolution, y_resolution],
                "scanning_order": {
                    "x": config.product.source_x_scan,
                    "y": config.product.source_y_scan,
                },
                "transform": list(dataset.transform)[:6],
                "crop_window": {
                    "column_offset": int(window.col_off),
                    "row_offset": int(window.row_off),
                    "width": int(window.width),
                    "height": int(window.height),
                },
                "band_tags": tags,
            },
            source_statistics=_statistics(native, quality),
            normalized_statistics=_statistics(destination, destination_quality),
        )


def _validate_band_contract(
    tags: dict[str, str],
    source: MRMSDownloadedArtifact,
    config: MrmsConfig,
) -> None:
    unit_text = " ".join(value for key, value in tags.items() if "UNIT" in key.upper())
    if config.product.units.casefold() not in unit_text.casefold():
        raise MRMSContractError("Decoded MRMS band does not declare dBZ units")
    description_text = " ".join(tags.values()).casefold()
    if not any(
        marker in description_text
        for marker in ("composite reflectivity", "mergedreflectivityqccomposite")
    ):
        raise MRMSContractError("Decoded MRMS band identity is not composite reflectivity")
    raw_valid_time = tags.get("GRIB_VALID_TIME")
    if raw_valid_time is None:
        raise MRMSContractError("Decoded MRMS band has no GRIB valid time")
    match = _VALID_TIME_PATTERN.match(raw_valid_time.strip())
    if match is None:
        raise MRMSContractError("Decoded MRMS GRIB valid time is unreadable")
    decoded_time = datetime.fromtimestamp(int(match.group(0)), tz=UTC)
    difference = abs((decoded_time - source.source.valid_time).total_seconds())
    if difference > 2:
        raise MRMSContractError("Filename and decoded GRIB valid times disagree")


def _classify_quality(
    values: np.ndarray[Any, np.dtype[np.float32]],
    native_mask: np.ndarray[Any, np.dtype[np.bool_]],
    config: MrmsConfig,
) -> np.ndarray[Any, np.dtype[np.uint8]]:
    no_coverage = np.isclose(values, config.product.no_coverage_value, atol=1e-4)
    missing = (
        np.isclose(values, config.product.missing_value, atol=1e-4)
        | ~np.isfinite(values)
        | (native_mask & ~no_coverage)
    )
    unexpected_sentinel = (values <= -90) & ~missing & ~no_coverage
    if bool(np.any(unexpected_sentinel)):
        unexpected = float(values[unexpected_sentinel][0])
        raise MRMSContractError(f"Unexpected MRMS sentinel value {unexpected:g}")
    quality: np.ndarray[Any, np.dtype[np.uint8]] = np.full(
        values.shape,
        QUALITY_VALID,
        dtype=np.uint8,
    )
    quality[missing] = QUALITY_MISSING
    quality[no_coverage] = QUALITY_NO_COVERAGE
    return quality


def _validate_reflectivity_range(
    values: np.ndarray[Any, np.dtype[np.float32]],
    valid: np.ndarray[Any, np.dtype[np.bool_]],
) -> None:
    if not bool(np.any(valid)):
        return
    minimum = float(np.min(values[valid]))
    maximum = float(np.max(values[valid]))
    if minimum < -50 or maximum > 100:
        raise MRMSContractError(
            f"Decoded reflectivity range {minimum:g}..{maximum:g} dBZ is implausible"
        )


def _bounded_source_window(
    dataset: rasterio.io.DatasetReader,
    bounds: tuple[float, float, float, float],
    *,
    margin_pixels: int,
) -> Window:
    inverse = ~dataset.transform
    corners = [
        inverse * (bounds[0], bounds[1]),
        inverse * (bounds[0], bounds[3]),
        inverse * (bounds[2], bounds[1]),
        inverse * (bounds[2], bounds[3]),
    ]
    columns = [point[0] for point in corners]
    rows = [point[1] for point in corners]
    column_start = max(0, math.floor(min(columns)) - margin_pixels)
    row_start = max(0, math.floor(min(rows)) - margin_pixels)
    column_end = min(dataset.width, math.ceil(max(columns)) + margin_pixels)
    row_end = min(dataset.height, math.ceil(max(rows)) + margin_pixels)
    if column_start >= column_end or row_start >= row_end:
        raise MRMSContractError("Configured region does not intersect the MRMS source grid")
    return Window(
        col_off=column_start,
        row_off=row_start,
        width=column_end - column_start,
        height=row_end - row_start,
    )


def _target_grid(
    region: RegionConfig,
    target_crs: CRS,
) -> tuple[tuple[float, float, float, float], Affine]:
    center_x, center_y = transform(
        "EPSG:4326",
        target_crs,
        [region.center.longitude],
        [region.center.latitude],
    )
    half_width = region.extent_km.width * 500
    half_height = region.extent_km.height * 500
    bounds = (
        center_x[0] - half_width,
        center_y[0] - half_height,
        center_x[0] + half_width,
        center_y[0] + half_height,
    )
    resolution = float(region.grid.nominal_resolution_m)
    grid_transform = Affine(resolution, 0, bounds[0], 0, -resolution, bounds[3])
    return bounds, grid_transform


def _statistics(
    values: np.ndarray[Any, np.dtype[np.float32]],
    quality: np.ndarray[Any, np.dtype[np.uint8]],
) -> dict[str, Any]:
    valid = quality == QUALITY_VALID
    missing = quality == QUALITY_MISSING
    no_coverage = (quality == QUALITY_NO_COVERAGE) | (quality == QUALITY_OUTSIDE_SOURCE)
    total = int(values.size)
    valid_values = values[valid]
    if valid_values.size:
        quantiles = np.quantile(valid_values, [0.05, 0.5, 0.95])
        minimum: float | None = float(np.min(valid_values))
        maximum: float | None = float(np.max(valid_values))
        percentile_values: dict[str, float | None] = {
            "p05": float(quantiles[0]),
            "p50": float(quantiles[1]),
            "p95": float(quantiles[2]),
        }
    else:
        minimum = None
        maximum = None
        percentile_values = {"p05": None, "p50": None, "p95": None}
    return {
        "total_cells": total,
        "valid_cells": int(np.count_nonzero(valid)),
        "missing_cells": int(np.count_nonzero(missing)),
        "no_coverage_cells": int(np.count_nonzero(no_coverage)),
        "minimum_dbz": minimum,
        "maximum_dbz": maximum,
        **percentile_values,
    }


def _build_metadata(
    source: MRMSDownloadedArtifact,
    *,
    region: RegionConfig,
    config: MrmsConfig,
    decoded: _DecodedRegion,
    processing_started_at: datetime,
    processed_at: datetime,
    publication_time: datetime,
    fixture_mode: bool,
) -> dict[str, Any]:
    statistics = decoded.normalized_statistics
    total = statistics["total_cells"]
    missing_percentage = statistics["missing_cells"] / total * 100
    no_coverage_percentage = statistics["no_coverage_cells"] / total * 100
    return {
        "schema_version": 1,
        "source": "mrms",
        "official_source_name": config.official_name,
        "source_bucket": config.access.bucket,
        "source_object_key": source.source.key,
        "source_url": f"{config.access.base_url}/{source.source.key}",
        "source_etag": source.source.etag,
        "source_last_modified": _iso(source.source.last_modified),
        "product": config.product.id,
        "variable": config.product.variable,
        "units": config.product.units,
        "region_id": region.id,
        "observation_time": _iso(source.source.valid_time),
        "valid_time": _iso(source.source.valid_time),
        "forecast_initialization_time": None,
        "discovered_at": _iso(source.source.discovered_at),
        "downloaded_at": _iso(source.downloaded_at),
        "processing_started_at": _iso(processing_started_at),
        "processed_at": _iso(processed_at),
        "publication_time": _iso(publication_time),
        "expiration_time": _iso(
            source.source.valid_time + timedelta(minutes=config.download.stale_after_minutes)
        ),
        "data_age_seconds_at_processing": max(
            0,
            (processed_at - source.source.valid_time).total_seconds(),
        ),
        "compressed_sha256": source.compressed_sha256,
        "grib_sha256": source.decompressed_sha256,
        "compressed_size_bytes": source.compressed_size,
        "grib_size_bytes": source.decompressed_size,
        "raw_path": str(source.path),
        "processing_version": config.processing.version,
        "resampling": config.processing.resampling,
        "target_projection": region.grid.projection,
        "target_bounds": [float(value) for value in decoded.target_bounds],
        "geographic_bounds": decoded.geographic_bounds,
        "horizontal_resolution_m": region.grid.nominal_resolution_m,
        "width_pixels": region.width_pixels,
        "height_pixels": region.height_pixels,
        "quality_flag_values": {
            "valid": int(QUALITY_VALID),
            "missing": int(QUALITY_MISSING),
            "no_coverage": int(QUALITY_NO_COVERAGE),
            "outside_source": int(QUALITY_OUTSIDE_SOURCE),
        },
        "native_missing_value": config.product.missing_value,
        "native_no_coverage_value": config.product.no_coverage_value,
        "missing_percentage": missing_percentage,
        "no_coverage_percentage": no_coverage_percentage,
        "source_grid": decoded.source_metadata,
        "source_statistics": decoded.source_statistics,
        "normalized_statistics": decoded.normalized_statistics,
        "synthetic_test_fixture": fixture_mode,
    }


def _write_zarr(
    path: Path,
    decoded: _DecodedRegion,
    metadata: dict[str, Any],
    config: MrmsConfig,
) -> None:
    group = zarr.open_group(str(path), mode="w")
    chunk = config.processing.zarr_chunk_size
    chunks = (
        min(chunk, decoded.reflectivity_dbz.shape[0]),
        min(chunk, decoded.reflectivity_dbz.shape[1]),
    )
    group.create_array(
        "reflectivity_dbz",
        data=decoded.reflectivity_dbz,
        chunks=chunks,
    )
    group.create_array(
        "quality_flag",
        data=decoded.quality_flag,
        chunks=chunks,
    )
    group.create_array(
        "missing_mask",
        data=decoded.quality_flag == QUALITY_MISSING,
        chunks=chunks,
    )
    group.create_array(
        "no_coverage_mask",
        data=(decoded.quality_flag == QUALITY_NO_COVERAGE)
        | (decoded.quality_flag == QUALITY_OUTSIDE_SOURCE),
        chunks=chunks,
    )
    group.create_array("x", data=decoded.x, chunks=(min(chunk, decoded.x.size),))
    group.create_array("y", data=decoded.y, chunks=(min(chunk, decoded.y.size),))
    group.attrs.update(metadata)


def _write_preview(
    path: Path,
    reflectivity: np.ndarray[Any, np.dtype[np.float32]],
    quality: np.ndarray[Any, np.dtype[np.uint8]],
) -> None:
    rgba = np.zeros((*reflectivity.shape, 4), dtype=np.uint8)
    thresholds: tuple[tuple[float, tuple[int, int, int, int]], ...] = (
        (5, (4, 233, 231, 185)),
        (10, (1, 159, 244, 195)),
        (20, (3, 0, 244, 205)),
        (30, (2, 253, 2, 215)),
        (40, (253, 248, 2, 225)),
        (50, (253, 0, 0, 235)),
        (60, (188, 0, 0, 240)),
        (70, (248, 0, 253, 245)),
    )
    for threshold, color in thresholds:
        rgba[(quality == QUALITY_VALID) & (reflectivity >= threshold)] = color
    rgba[quality == QUALITY_MISSING] = (125, 132, 142, 180)
    rgba[(quality == QUALITY_NO_COVERAGE) | (quality == QUALITY_OUTSIDE_SOURCE)] = (35, 42, 52, 210)
    Image.fromarray(rgba, mode="RGBA").save(path, format="PNG", optimize=True)


def _decompress_checked(source: MRMSDownloadedArtifact, destination: Path) -> None:
    digest = hashlib.sha256()
    size = 0
    try:
        with gzip.open(source.path, "rb") as compressed, destination.open("wb") as output:
            while chunk := compressed.read(1024 * 1024):
                size += len(chunk)
                if size > source.decompressed_size:
                    raise MRMSContractError("Raw MRMS object exceeds its validated GRIB size")
                digest.update(chunk)
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
    except (gzip.BadGzipFile, EOFError, OSError) as exc:
        raise MRMSContractError("Immutable raw MRMS gzip failed revalidation") from exc
    if size != source.decompressed_size or digest.hexdigest() != source.decompressed_sha256:
        raise MRMSContractError("Immutable raw MRMS checksum changed before processing")


def _normalized_target(
    data_root: Path,
    source: MRMSDownloadedArtifact,
    region: RegionConfig,
    config: MrmsConfig,
) -> Path:
    valid_time = source.source.valid_time
    return (
        data_root
        / "normalized"
        / "mrms"
        / region.id
        / config.product.id
        / config.processing.version
        / f"{valid_time:%Y}"
        / f"{valid_time:%m}"
        / f"{valid_time:%d}"
        / f"{valid_time:%Y%m%dT%H%M%SZ}.zarr"
    )


def _reuse_existing(
    target: Path,
    source: MRMSDownloadedArtifact,
    region: RegionConfig,
    config: MrmsConfig,
) -> NormalizedMRMSArtifact:
    metadata_path = target / "metadata.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MRMSPublicationConflict(
            "Normalized target exists without readable provenance metadata"
        ) from exc
    expected = {
        "source_object_key": source.source.key,
        "compressed_sha256": source.compressed_sha256,
        "grib_sha256": source.decompressed_sha256,
        "region_id": region.id,
        "processing_version": config.processing.version,
    }
    if any(metadata.get(key) != value for key, value in expected.items()):
        raise MRMSPublicationConflict("Normalized target has conflicting scientific identity")
    return _artifact_from_metadata(
        source,
        target,
        metadata,
        published_at=_parse_utc(metadata["publication_time"]),
        reused=True,
    )


def _artifact_from_metadata(
    source: MRMSDownloadedArtifact,
    target: Path,
    metadata: dict[str, Any],
    *,
    published_at: datetime,
    reused: bool,
) -> NormalizedMRMSArtifact:
    statistics = metadata["normalized_statistics"]
    return NormalizedMRMSArtifact(
        source=source,
        region_id=str(metadata["region_id"]),
        zarr_path=target,
        preview_path=target / "diagnostic-preview.png",
        processing_started_at=_parse_utc(metadata["processing_started_at"]),
        processed_at=_parse_utc(metadata["processed_at"]),
        published_at=published_at,
        source_projection=str(metadata["source_grid"]["crs"]),
        target_projection=str(metadata["target_projection"]),
        geographic_bounds={
            key: float(value) for key, value in metadata["geographic_bounds"].items()
        },
        width_pixels=int(metadata["width_pixels"]),
        height_pixels=int(metadata["height_pixels"]),
        horizontal_resolution_m=float(metadata["horizontal_resolution_m"]),
        minimum_dbz=_optional_float(statistics["minimum_dbz"]),
        maximum_dbz=_optional_float(statistics["maximum_dbz"]),
        missing_percentage=float(metadata["missing_percentage"]),
        no_coverage_percentage=float(metadata["no_coverage_percentage"]),
        metadata=metadata,
        reused=reused,
    )


def _publish_directory(staging: Path, target: Path) -> None:
    try:
        os.rename(staging, target)
    except OSError as exc:
        if exc.errno not in {errno.EEXIST, errno.ENOTEMPTY}:
            raise
        raise MRMSPublicationConflict("Normalized target appeared during publication") from exc
    _fsync_directory(target.parent)


def _fsync_tree(path: Path) -> None:
    for file_path in path.rglob("*"):
        if file_path.is_file():
            with file_path.open("rb") as file_handle:
                os.fsync(file_handle.fileno())
    _fsync_directory(path)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _require_utc(value, "timestamp").isoformat().replace("+00:00", "Z")


def _parse_utc(value: object) -> datetime:
    if not isinstance(value, str):
        raise MRMSPublicationConflict("Normalized metadata timestamp is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MRMSPublicationConflict("Normalized metadata timestamp is invalid") from exc
    return _require_utc(parsed, "metadata timestamp")


def _require_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise MRMSContractError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if not isinstance(value, int | float):
        raise MRMSPublicationConflict("Normalized metadata statistic is invalid")
    return float(value)


__all__ = [
    "MRMSContractError",
    "MRMSProcessingError",
    "MRMSPublicationConflict",
    "NormalizedMRMSArtifact",
    "process_mrms_reflectivity",
]
