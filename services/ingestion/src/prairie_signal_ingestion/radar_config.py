"""Strict runtime configuration for the first MRMS processing slice."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class RadarConfigurationError(ValueError):
    """Raised when a checked-in region or source definition is invalid."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RegionCenter(StrictModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class RegionExtent(StrictModel):
    width: float = Field(gt=0, le=5000)
    height: float = Field(gt=0, le=5000)


class RegionGridDefinition(StrictModel):
    projection: str = Field(pattern=r"^EPSG:\d+$")
    nominal_resolution_m: int = Field(gt=0, le=100_000)
    interval_minutes: int = Field(gt=0, le=60)
    history_minutes: int = Field(ge=0, le=1440)
    forecast_minutes: int = Field(ge=0, le=1440)


class SearchDefinition(StrictModel):
    countries: list[str]
    enforce_extent: bool


class BenchmarkLocation(StrictModel):
    id: str
    name: str
    state: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class RegionConfig(StrictModel):
    id: str
    name: str
    center: RegionCenter
    extent_km: RegionExtent
    grid: RegionGridDefinition
    presentation_timezone: str
    search: SearchDefinition
    benchmark_locations: list[BenchmarkLocation]

    @model_validator(mode="after")
    def validate_pixel_dimensions(self) -> RegionConfig:
        for extent_km in (self.extent_km.width, self.extent_km.height):
            pixels = extent_km * 1000 / self.grid.nominal_resolution_m
            if abs(pixels - round(pixels)) > 1e-6:
                raise ValueError("Region extent must be an integer number of grid cells")
        return self

    @property
    def width_pixels(self) -> int:
        return round(self.extent_km.width * 1000 / self.grid.nominal_resolution_m)

    @property
    def height_pixels(self) -> int:
        return round(self.extent_km.height * 1000 / self.grid.nominal_resolution_m)


class MrmsAccess(StrictModel):
    base_url: str = Field(pattern=r"^https://")
    bucket: Literal["noaa-mrms-pds"]
    domain: Literal["CONUS"]
    anonymous: Literal[True]


class MrmsSourceBounds(StrictModel):
    west: float = Field(ge=-130, le=-130)
    south: float = Field(ge=20, le=20)
    east: float = Field(ge=-60, le=-60)
    north: float = Field(ge=55, le=55)


class MrmsProduct(StrictModel):
    id: Literal["MergedReflectivityQCComposite_00.50"]
    source_name: Literal["MergedReflectivityQCComposite"]
    variable: Literal["composite_reflectivity"]
    units: Literal["dBZ"]
    cadence_minutes: Literal[2]
    source_grid_type: Literal["regular_latitude_longitude"]
    source_resolution_degrees: float = Field(ge=0.01, le=0.01)
    source_width_pixels: Literal[7000]
    source_height_pixels: Literal[3500]
    source_bounds_degrees: MrmsSourceBounds
    source_x_scan: Literal["west_to_east"]
    source_y_scan: Literal["north_to_south"]
    missing_value: Literal[-99]
    no_coverage_value: Literal[-999]


class MrmsDownload(StrictModel):
    timeout_seconds: float = Field(ge=1, le=300)
    max_retries: int = Field(ge=0, le=5)
    max_compressed_bytes: int = Field(gt=0, le=1_073_741_824)
    max_decompressed_bytes: int = Field(gt=0, le=2_147_483_648)
    max_future_skew_seconds: int = Field(ge=0, le=600)
    stale_after_minutes: int = Field(ge=2, le=120)


class MrmsProcessing(StrictModel):
    version: str = Field(min_length=1, max_length=80)
    resampling: Literal["nearest"]
    zarr_chunk_size: int = Field(ge=32, le=2048)


class MrmsConfig(StrictModel):
    id: Literal["noaa-mrms"]
    official_name: Literal["NOAA Multi-Radar Multi-Sensor System"]
    access: MrmsAccess
    product: MrmsProduct
    download: MrmsDownload
    processing: MrmsProcessing


def _read_yaml(path: Path) -> object:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RadarConfigurationError(f"Could not read configuration {path}") from exc
    if not isinstance(document, dict):
        raise RadarConfigurationError(f"Configuration {path} must contain a mapping")
    return document


def load_region_config(path: Path) -> RegionConfig:
    try:
        return RegionConfig.model_validate(_read_yaml(path))
    except ValueError as exc:
        raise RadarConfigurationError(f"Invalid region configuration {path}: {exc}") from exc


def load_mrms_config(path: Path) -> MrmsConfig:
    try:
        return MrmsConfig.model_validate(_read_yaml(path))
    except ValueError as exc:
        raise RadarConfigurationError(f"Invalid MRMS configuration {path}: {exc}") from exc
