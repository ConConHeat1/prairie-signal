from __future__ import annotations

from pathlib import Path

import pytest

from prairie_signal_ingestion.radar_config import (
    RadarConfigurationError,
    load_mrms_config,
    load_region_config,
)

ROOT = Path(__file__).parents[3]


def test_checked_in_region_and_mrms_configs_are_valid() -> None:
    region = load_region_config(ROOT / "configs/regions/lincoln-512km.yaml")
    source = load_mrms_config(ROOT / "configs/sources/mrms.yaml")

    assert region.grid.projection == "EPSG:5070"
    assert region.width_pixels == 512
    assert region.height_pixels == 512
    assert source.product.units == "dBZ"
    assert source.product.source_grid_type == "regular_latitude_longitude"
    assert source.product.source_width_pixels == 7000
    assert source.product.source_height_pixels == 3500
    assert source.product.source_bounds_degrees.west == -130
    assert source.product.source_x_scan == "west_to_east"
    assert source.product.source_y_scan == "north_to_south"
    assert source.product.missing_value == -99
    assert source.product.no_coverage_value == -999


def test_region_config_rejects_fractional_grid_dimensions(tmp_path: Path) -> None:
    path = tmp_path / "region.yaml"
    path.write_text(
        """
id: bad
name: Bad grid
center: {latitude: 40, longitude: -96}
extent_km: {width: 10.5, height: 10}
grid:
  projection: EPSG:5070
  nominal_resolution_m: 1000
  interval_minutes: 5
  history_minutes: 90
  forecast_minutes: 120
presentation_timezone: America/Chicago
search: {countries: [US], enforce_extent: true}
benchmark_locations: []
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(RadarConfigurationError, match="integer number of grid cells"):
        load_region_config(path)


def test_mrms_config_rejects_unverified_product(tmp_path: Path) -> None:
    checked_in = (ROOT / "configs/sources/mrms.yaml").read_text(encoding="utf-8")
    path = tmp_path / "mrms.yaml"
    path.write_text(
        checked_in.replace(
            "MergedReflectivityQCComposite_00.50",
            "UnverifiedProduct_00.00",
        ),
        encoding="utf-8",
    )

    with pytest.raises(RadarConfigurationError, match="Invalid MRMS configuration"):
        load_mrms_config(path)
