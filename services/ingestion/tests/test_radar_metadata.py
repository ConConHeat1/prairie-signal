from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from prairie_signal_ingestion.adapters.mrms import (
    MRMSDownloadedArtifact,
    parse_mrms_object_key,
)
from prairie_signal_ingestion.mrms_processing import NormalizedMRMSArtifact
from prairie_signal_ingestion.radar_metadata import build_radar_record

VALID_TIME = datetime(2026, 7, 31, 17, 45, tzinfo=UTC)
DISCOVERED_AT = VALID_TIME + timedelta(seconds=30)
SOURCE_LAST_MODIFIED = VALID_TIME + timedelta(seconds=20)


def test_normalized_artifact_maps_to_complete_radar_record(tmp_path: Path) -> None:
    key = (
        "CONUS/MergedReflectivityQCComposite_00.50/20260731/"
        "MRMS_MergedReflectivityQCComposite_00.50_20260731-174500.grib2.gz"
    )
    downloaded = MRMSDownloadedArtifact(
        source=parse_mrms_object_key(
            key,
            etag="fixture-etag",
            last_modified=SOURCE_LAST_MODIFIED,
            discovered_at=DISCOVERED_AT,
        ),
        path=tmp_path / "raw.grib2.gz",
        compressed_sha256="a" * 64,
        decompressed_sha256="b" * 64,
        compressed_size=1234,
        decompressed_size=5678,
        downloaded_at=VALID_TIME + timedelta(minutes=1),
    )
    metadata = {
        "product": "MergedReflectivityQCComposite_00.50",
        "variable": "composite_reflectivity",
        "units": "dBZ",
        "source_bucket": "noaa-mrms-pds",
        "source_url": f"https://noaa-mrms-pds.s3.amazonaws.com/{key}",
        "source_etag": "fixture-etag",
        "source_last_modified": "2026-07-31T17:45:20Z",
        "discovered_at": "2026-07-31T17:45:30Z",
        "expiration_time": "2026-07-31T18:00:00Z",
        "processing_version": "mrms-reflectivity-v1",
        "quality_flag_values": {
            "valid": 0,
            "missing": 1,
            "no_coverage": 2,
            "outside_source": 3,
        },
        "native_missing_value": -99,
        "native_no_coverage_value": -999,
        "resampling": "nearest",
        "source_grid": {"crs_wkt": "fixture-wkt"},
        "source_statistics": {"valid_cells": 100},
        "normalized_statistics": {"valid_cells": 90},
    }
    normalized = NormalizedMRMSArtifact(
        source=downloaded,
        region_id="lincoln-512km",
        zarr_path=tmp_path / "frame.zarr",
        preview_path=tmp_path / "frame.zarr" / "diagnostic-preview.png",
        processing_started_at=VALID_TIME + timedelta(minutes=1, seconds=1),
        processed_at=VALID_TIME + timedelta(minutes=1, seconds=2),
        published_at=VALID_TIME + timedelta(minutes=1, seconds=3),
        source_projection="EPSG:4326",
        target_projection="EPSG:5070",
        geographic_bounds={
            "west": -100,
            "south": 38,
            "east": -93,
            "north": 44,
        },
        width_pixels=512,
        height_pixels=512,
        horizontal_resolution_m=1000,
        minimum_dbz=-10,
        maximum_dbz=65,
        missing_percentage=1.5,
        no_coverage_percentage=2.5,
        metadata=metadata,
    )

    record = build_radar_record(normalized)

    assert record.source == "mrms"
    assert record.source_object_key == key
    assert record.observation_time == VALID_TIME
    assert record.discovered_at == DISCOVERED_AT
    assert record.source_bucket == "noaa-mrms-pds"
    assert record.source_etag == "fixture-etag"
    assert record.source_last_modified == SOURCE_LAST_MODIFIED
    assert record.expires_at == datetime(2026, 7, 31, 18, 0, tzinfo=UTC)
    assert record.width_pixels == 512
    assert record.quality_flags["native_missing_value"] == -99
    assert record.quality_flags["native_no_coverage_value"] == -999
