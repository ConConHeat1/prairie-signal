"""Runtime configuration.

No setting contains a user location or search value.  Public benchmark locations
are configuration, not user data, and are the only coordinates eligible for
long-term source archiving.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "Prairie Signal"
    environment: str = Field(
        default="development",
        validation_alias=AliasChoices("APP_ENV", "ENVIRONMENT"),
    )
    pipeline_version: str = "phase1-v1"
    log_level: str = "INFO"

    nws_base_url: str = "https://api.weather.gov"
    nws_user_agent: str | None = None
    nws_contact: str | None = None
    nws_timeout_seconds: float = Field(default=12.0, ge=1.0, le=60.0)
    nws_max_retries: int = Field(default=3, ge=0, le=5)
    nws_circuit_failure_threshold: int = Field(default=3, ge=1, le=20)
    nws_circuit_open_seconds: float = Field(default=60.0, ge=1.0, le=900.0)

    cache_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("REDIS_URL", "CACHE_URL"),
    )
    database_url: str = (
        "postgresql+asyncpg://prairie_signal:development-only-change-me@db:5432/prairie_signal"
    )
    cache_default_ttl_seconds: int = Field(default=120, ge=5, le=3600)
    cache_min_ttl_seconds: int = Field(default=15, ge=1, le=300)
    cache_max_ttl_seconds: int = Field(default=900, ge=30, le=86400)
    stale_retention_seconds: int = Field(default=86400, ge=600, le=604800)

    observation_fresh_minutes: int = Field(default=30, ge=1, le=240)
    observation_delayed_minutes: int = Field(default=90, ge=2, le=1440)
    forecast_fresh_minutes: int = Field(default=360, ge=5, le=1440)
    forecast_delayed_minutes: int = Field(default=720, ge=10, le=2880)
    alerts_fresh_minutes: int = Field(
        default=2,
        ge=1,
        le=60,
        validation_alias=AliasChoices("ALERTS_FRESH_MINUTES", "ALERT_FRESH_MINUTES"),
    )
    alerts_delayed_minutes: int = Field(
        default=10,
        ge=2,
        le=240,
        validation_alias=AliasChoices("ALERTS_DELAYED_MINUTES", "ALERT_DELAYED_MINUTES"),
    )

    region_center_latitude: float = Field(default=40.8136, ge=-90, le=90)
    region_center_longitude: float = Field(default=-96.7026, ge=-180, le=180)
    # The configured Phase 1 box is 512 km wide, so its center-to-edge limit is 256 km.
    region_radius_km: float = Field(default=256.0, gt=0, le=2000)
    census_places_path: Path | None = None
    census_zcta_path: Path | None = None

    benchmark_locations: str = "lincoln-ne:40.8136:-96.7026"
    data_directory: Path = Path("data")
    region_config_path: Path = Path("configs/regions/lincoln-512km.yaml")
    mrms_source_config_path: Path = Path("configs/sources/mrms.yaml")
    archive_directory: Path = Field(
        default=Path("/var/lib/prairie-signal/archive"),
        validation_alias=AliasChoices("RAW_ARCHIVE_PATH", "ARCHIVE_DIRECTORY"),
    )

    @field_validator("nws_base_url")
    @classmethod
    def strip_base_url(cls, value: str) -> str:
        return value.rstrip("/")

    @property
    def effective_nws_user_agent(self) -> str | None:
        """Return an identifying User-Agent only when both identity parts exist."""
        if not self.nws_user_agent or not self.nws_contact:
            return None
        if "example.invalid" in self.nws_contact.casefold():
            return None
        return f"{self.nws_user_agent} ({self.nws_contact})"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
