"""Public, versioned API contracts.

Measurements are normalized to SI at the API boundary.  The browser may convert
them for display, while explicit suffixes and metadata prevent unit ambiguity.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LocationKind(str, Enum):
    CITY = "city"
    ZCTA = "zcta"
    COORDINATE = "coordinate"


class QueryKind(str, Enum):
    CITY = "city"
    ZIP = "zip"
    COORDINATE = "coordinate"


class FreshnessStatus(str, Enum):
    FRESH = "fresh"
    DELAYED = "delayed"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class DataQuality(str, Enum):
    VERIFIED = "verified"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class AlertFeedStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class Location(APIModel):
    id: str
    name: str
    region: str
    country: Literal["US"] = "US"
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone: str
    kind: LocationKind
    label: str


class LocationSearchResponse(APIModel):
    results: list[Location]
    query_kind: QueryKind
    region_limit_km: float


class SourceAttribution(APIModel):
    name: str = "National Weather Service"
    url: HttpUrl = HttpUrl("https://www.weather.gov/")


class ResponseMetadata(APIModel):
    source_time: datetime | None
    fetched_at: datetime
    processed_at: datetime
    valid_from: datetime | None
    valid_to: datetime | None
    units: dict[str, str]
    attribution: SourceAttribution = Field(default_factory=SourceAttribution)
    freshness: FreshnessStatus
    quality: DataQuality
    confidence: None = None
    pipeline_version: str
    warnings: list[str] = Field(default_factory=list)
    from_cache: bool = False
    stale_fallback: bool = False


class CurrentConditions(APIModel):
    temperature_c: float | None
    apparent_temperature_c: float | None
    dewpoint_c: float | None
    relative_humidity_pct: float | None = Field(default=None, ge=0, le=100)
    wind_speed_kph: float | None = Field(default=None, ge=0)
    wind_gust_kph: float | None = Field(default=None, ge=0)
    wind_direction_deg: float | None = Field(default=None, ge=0, le=360)
    pressure_hpa: float | None = Field(default=None, ge=0)
    visibility_km: float | None = Field(default=None, ge=0)
    text_description: str | None
    icon_url: HttpUrl | None
    observed_at: datetime


class ObservationStation(APIModel):
    id: str
    name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    distance_km: float = Field(ge=0)
    observed_at: datetime


class CurrentWeatherResponse(APIModel):
    location: Location
    current: CurrentConditions
    station: ObservationStation
    meta: ResponseMetadata


class HourlyPeriod(APIModel):
    start_time: datetime
    end_time: datetime
    is_daytime: bool
    temperature_c: float | None
    dewpoint_c: float | None
    relative_humidity_pct: float | None = Field(default=None, ge=0, le=100)
    probability_of_precipitation_pct: float | None = Field(default=None, ge=0, le=100)
    wind_speed_kph: float | None = Field(default=None, ge=0)
    wind_gust_kph: float | None = Field(default=None, ge=0)
    wind_direction: str | None
    wind_direction_deg: float | None = Field(default=None, ge=0, le=360)
    short_forecast: str
    icon_url: HttpUrl | None


class HourlyWeatherResponse(APIModel):
    location: Location
    periods: list[HourlyPeriod]
    meta: ResponseMetadata


class DailyPeriod(APIModel):
    number: int = Field(ge=1)
    name: str
    start_time: datetime
    end_time: datetime
    is_daytime: bool
    temperature_c: float | None
    probability_of_precipitation_pct: float | None = Field(default=None, ge=0, le=100)
    wind_speed_min_kph: float | None = Field(default=None, ge=0)
    wind_speed_max_kph: float | None = Field(default=None, ge=0)
    wind_direction: str | None
    short_forecast: str
    detailed_forecast: str
    icon_url: HttpUrl | None


class DailyWeatherResponse(APIModel):
    location: Location
    periods: list[DailyPeriod]
    meta: ResponseMetadata


class OfficialAlert(APIModel):
    id: str
    revision_id: str
    event: str
    headline: str | None
    description: str
    instruction: str | None
    area_description: str
    issuing_office: str | None
    sent_at: datetime
    effective_at: datetime
    onset_at: datetime | None
    expires_at: datetime
    ends_at: datetime | None
    severity: str
    certainty: str
    urgency: str
    status: str
    message_type: str
    response: str | None
    geometry: dict[str, Any] | None


class ActiveAlertsResponse(APIModel):
    location: Location
    alerts: list[OfficialAlert]
    status: AlertFeedStatus
    meta: ResponseMetadata


class HealthResponse(APIModel):
    status: Literal["ok"]
    service: str
    version: str
    timestamp: datetime


class ReadinessCheck(APIModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, bool]
    timestamp: datetime


class SourceHealth(APIModel):
    name: str
    configured: bool
    circuit_state: Literal["closed", "open", "half_open"]
    consecutive_failures: int
    last_success_at: datetime | None
    last_failure_at: datetime | None


class SourcesResponse(APIModel):
    sources: list[SourceHealth]
    timestamp: datetime


class ErrorDetail(APIModel):
    code: str
    message: str
    retryable: bool = False


class ErrorResponse(APIModel):
    error: ErrorDetail
