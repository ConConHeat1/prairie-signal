from __future__ import annotations

import gzip
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
import rasterio
import zarr
from rasterio.transform import from_origin

import prairie_signal_ingestion.mrms_processing as processing_module
from prairie_signal_ingestion.adapters.mrms import (
    MRMSDownloadedArtifact,
    parse_mrms_object_key,
)
from prairie_signal_ingestion.mrms_processing import (
    MRMSContractError,
    process_mrms_reflectivity,
)
from prairie_signal_ingestion.radar_config import (
    MrmsConfig,
    RegionConfig,
    load_mrms_config,
    load_region_config,
)

ROOT = Path(__file__).parents[3]
VALID_TIME = datetime(2026, 7, 31, 17, 45, tzinfo=UTC)
DISCOVERED_AT = VALID_TIME + timedelta(seconds=30)
SOURCE_LAST_MODIFIED = VALID_TIME + timedelta(seconds=20)


def _configs() -> tuple[RegionConfig, MrmsConfig]:
    return (
        load_region_config(ROOT / "configs/regions/lincoln-512km.yaml"),
        load_mrms_config(ROOT / "configs/sources/mrms.yaml"),
    )


def _artifact(
    tmp_path: Path,
    *,
    units: str = "[dBZ]",
    valid_time: datetime = VALID_TIME,
    resolution: float = 0.01,
    unexpected_sentinel: float | None = None,
) -> MRMSDownloadedArtifact:
    grib_fixture = tmp_path / "synthetic-test-fixture.tif"
    values = np.full((700, 700), 25, dtype=np.float32)
    values[260:320, 280:340] = 55
    values[330:350, 330:350] = -99
    values[350:370, 350:370] = -999
    if unexpected_sentinel is not None:
        values[370:390, 370:390] = unexpected_sentinel
    transform = from_origin(-100.2, 44.3, resolution, resolution)
    with rasterio.open(
        grib_fixture,
        "w",
        driver="GTiff",
        width=values.shape[1],
        height=values.shape[0],
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
    ) as dataset:
        dataset.write(values, 1)
        dataset.update_tags(
            1,
            GRIB_UNIT=units,
            GRIB_COMMENT="Composite Reflectivity Mosaic (optimal method)",
            GRIB_VALID_TIME=str(round(valid_time.timestamp())),
        )
    payload = grib_fixture.read_bytes()
    raw_path = tmp_path / "raw" / "fixture.grib2.gz"
    raw_path.parent.mkdir(parents=True)
    with raw_path.open("wb") as output:
        with gzip.GzipFile(fileobj=output, mode="wb", mtime=0) as compressed:
            compressed.write(payload)
    key = (
        "CONUS/MergedReflectivityQCComposite_00.50/20260731/"
        "MRMS_MergedReflectivityQCComposite_00.50_20260731-174500.grib2.gz"
    )
    return MRMSDownloadedArtifact(
        source=parse_mrms_object_key(
            key,
            etag="fixture-etag",
            last_modified=SOURCE_LAST_MODIFIED,
            discovered_at=DISCOVERED_AT,
        ),
        path=raw_path,
        compressed_sha256=hashlib.sha256(raw_path.read_bytes()).hexdigest(),
        decompressed_sha256=hashlib.sha256(payload).hexdigest(),
        compressed_size=raw_path.stat().st_size,
        decompressed_size=len(payload),
        downloaded_at=VALID_TIME + timedelta(seconds=45),
    )


def test_fixture_normalizes_to_chunked_zarr_with_separate_masks(tmp_path: Path) -> None:
    region, config = _configs()
    source = _artifact(tmp_path)

    result = process_mrms_reflectivity(
        source,
        data_root=tmp_path / "data",
        temporary_directory=tmp_path / "work",
        region=region,
        config=config,
        fixture_mode=True,
    )

    group = zarr.open_group(str(result.zarr_path), mode="r")
    reflectivity = group["reflectivity_dbz"][:]
    missing = group["missing_mask"][:]
    no_coverage = group["no_coverage_mask"][:]
    x = group["x"][:]
    y = group["y"][:]
    assert reflectivity.shape == (512, 512)
    assert group["quality_flag"].chunks == (256, 256)
    assert x.shape == (512,)
    assert y.shape == (512,)
    assert np.all(np.diff(x) == 1000)
    assert np.all(np.diff(y) == -1000)
    assert x[0] == pytest.approx(result.metadata["target_bounds"][0] + 500)
    assert y[0] == pytest.approx(result.metadata["target_bounds"][3] - 500)
    assert bool(np.any(missing))
    assert bool(np.any(no_coverage))
    assert not bool(np.any(reflectivity == -99))
    assert not bool(np.any(reflectivity == -999))
    assert np.isnan(reflectivity[missing | no_coverage]).all()
    assert result.minimum_dbz == 25
    assert result.maximum_dbz == 55
    assert result.preview_path.is_file()
    assert result.metadata["synthetic_test_fixture"] is True
    assert result.metadata["normalized_statistics"]["valid_cells"] > 0
    assert result.metadata["processed_at"] < result.metadata["publication_time"]
    assert result.metadata["source_bucket"] == "noaa-mrms-pds"
    assert result.metadata["source_etag"] == "fixture-etag"
    assert result.metadata["source_last_modified"] == "2026-07-31T17:45:20Z"
    assert result.metadata["discovered_at"] == "2026-07-31T17:45:30Z"


def test_repeat_processing_reuses_immutable_artifact(tmp_path: Path) -> None:
    region, config = _configs()
    source = _artifact(tmp_path)
    arguments = {
        "data_root": tmp_path / "data",
        "temporary_directory": tmp_path / "work",
        "region": region,
        "config": config,
        "fixture_mode": True,
    }

    first = process_mrms_reflectivity(source, **arguments)
    metadata_mtime = (first.zarr_path / "metadata.json").stat().st_mtime_ns
    second = process_mrms_reflectivity(source, **arguments)

    assert second.zarr_path == first.zarr_path
    assert second.reused is True
    assert (first.zarr_path / "metadata.json").stat().st_mtime_ns == metadata_mtime


def test_changed_processing_version_coexists_without_overwriting_v1(
    tmp_path: Path,
) -> None:
    region, config = _configs()
    source = _artifact(tmp_path)
    arguments = {
        "data_root": tmp_path / "data",
        "temporary_directory": tmp_path / "work",
        "region": region,
        "fixture_mode": True,
    }

    first = process_mrms_reflectivity(source, config=config, **arguments)
    first_metadata_path = first.zarr_path / "metadata.json"
    first_metadata_bytes = first_metadata_path.read_bytes()
    version_two = config.model_copy(
        update={
            "processing": config.processing.model_copy(
                update={"version": "mrms-reflectivity-v2"},
            ),
        },
    )

    second = process_mrms_reflectivity(source, config=version_two, **arguments)

    assert first.zarr_path != second.zarr_path
    assert "mrms-reflectivity-v1" in first.zarr_path.parts
    assert "mrms-reflectivity-v2" in second.zarr_path.parts
    assert first.zarr_path.is_dir()
    assert second.zarr_path.is_dir()
    assert first_metadata_path.read_bytes() == first_metadata_bytes
    assert json.loads(first_metadata_bytes)["processing_version"] == "mrms-reflectivity-v1"
    assert second.metadata["processing_version"] == "mrms-reflectivity-v2"
    assert second.reused is False


def test_unexpected_negative_sentinel_fails_closed_without_publication(
    tmp_path: Path,
) -> None:
    region, config = _configs()
    source = _artifact(tmp_path, unexpected_sentinel=-95)

    with pytest.raises(MRMSContractError, match="Unexpected MRMS sentinel value -95"):
        process_mrms_reflectivity(
            source,
            data_root=tmp_path / "data",
            temporary_directory=tmp_path / "work",
            region=region,
            config=config,
            fixture_mode=True,
        )

    assert not (tmp_path / "data" / "normalized").exists()
    assert list((tmp_path / "work").glob("*.part")) == []


def test_zarr_write_failure_leaves_no_reader_visible_or_staging_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    region, config = _configs()
    source = _artifact(tmp_path)

    def fail_after_partial_write(path: Path, *_args: object) -> None:
        (path / "partial-chunk").write_bytes(b"incomplete")
        raise OSError("forced Zarr write interruption")

    monkeypatch.setattr(processing_module, "_write_zarr", fail_after_partial_write)

    with pytest.raises(OSError, match="forced Zarr write interruption"):
        process_mrms_reflectivity(
            source,
            data_root=tmp_path / "data",
            temporary_directory=tmp_path / "work",
            region=region,
            config=config,
            fixture_mode=True,
        )

    normalized_root = tmp_path / "data" / "normalized"
    assert list(normalized_root.rglob("*.zarr")) == []
    assert list(normalized_root.rglob("*.part")) == []


@pytest.mark.parametrize(
    ("units", "valid_time", "resolution", "message"),
    (
        ("[mm/hr]", VALID_TIME, 0.01, "dBZ units"),
        ("[dBZ]", datetime(2026, 7, 31, 17, 40, tzinfo=UTC), 0.01, "valid times"),
        ("[dBZ]", VALID_TIME, 0.02, "0.01-degree grid"),
    ),
)
def test_contract_changes_fail_without_publishing(
    tmp_path: Path,
    units: str,
    valid_time: datetime,
    resolution: float,
    message: str,
) -> None:
    region, config = _configs()
    source = _artifact(
        tmp_path,
        units=units,
        valid_time=valid_time,
        resolution=resolution,
    )

    with pytest.raises(MRMSContractError, match=message):
        process_mrms_reflectivity(
            source,
            data_root=tmp_path / "data",
            temporary_directory=tmp_path / "work",
            region=region,
            config=config,
            fixture_mode=True,
        )

    assert not (tmp_path / "data" / "normalized").exists()
    assert list((tmp_path / "work").glob("*.part")) == []
