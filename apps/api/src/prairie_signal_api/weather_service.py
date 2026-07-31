"""NWS response normalization and weather-domain policies."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import ValidationError

from prairie_signal_api.config import Settings
from prairie_signal_api.location_service import haversine_km
from prairie_signal_api.nws_client import NWSClient, NWSClientError, NWSUnavailable, UpstreamJSON
from prairie_signal_api.schemas import (
    ActiveAlertsResponse,
    AlertFeedStatus,
    CurrentConditions,
    CurrentWeatherResponse,
    DailyPeriod,
    DailyWeatherResponse,
    DataQuality,
    FreshnessStatus,
    HourlyPeriod,
    HourlyWeatherResponse,
    Location,
    LocationKind,
    ObservationStation,
    OfficialAlert,
    ResponseMetadata,
)

_WIND = re.compile(r"(\d+(?:\.\d+)?)")
_COMPASS_DEGREES = {
    "N": 0.0,
    "NNE": 22.5,
    "NE": 45.0,
    "ENE": 67.5,
    "E": 90.0,
    "ESE": 112.5,
    "SE": 135.0,
    "SSE": 157.5,
    "S": 180.0,
    "SSW": 202.5,
    "SW": 225.0,
    "WSW": 247.5,
    "W": 270.0,
    "WNW": 292.5,
    "NW": 315.0,
    "NNW": 337.5,
}


class WeatherDataError(RuntimeError):
    pass


class AlertRevisionWriter(Protocol):
    async def store(self, alert: OfficialAlert, raw_feature: dict[str, Any]) -> None: ...


class NullAlertRevisionWriter:
    async def store(self, alert: OfficialAlert, raw_feature: dict[str, Any]) -> None:
        return None


@dataclass(slots=True)
class _StationObservation:
    station: ObservationStation
    current: CurrentConditions
    upstream: UpstreamJSON


class WeatherService:
    def __init__(
        self,
        settings: Settings,
        client: NWSClient,
        *,
        alert_writer: AlertRevisionWriter | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings
        self.client = client
        self.alert_writer = alert_writer or NullAlertRevisionWriter()
        self._now = now or (lambda: datetime.now(UTC))

    async def current(self, latitude: float, longitude: float) -> CurrentWeatherResponse:
        point = await self.client.get_json(self._point_path(latitude, longitude))
        properties = _properties(point.payload, "point metadata")
        location = _location(latitude, longitude, properties)
        stations_url = _required_url(properties, "observationStations")
        station_collection = await self.client.get_json(stations_url)
        candidates = station_collection.payload.get("features")
        if not isinstance(candidates, list):
            raise WeatherDataError("NWS station collection is missing features.")

        observations: list[_StationObservation] = []
        warnings = _warnings(point, station_collection)
        for raw_station in candidates[:3]:
            try:
                observation = await self._station_observation(
                    raw_station,
                    latitude=latitude,
                    longitude=longitude,
                )
                observations.append(observation)
            except (
                NWSClientError,
                WeatherDataError,
                ValidationError,
                KeyError,
                TypeError,
                ValueError,
            ):
                continue
        if not observations:
            raise NWSUnavailable(
                "No valid recent observation was available from the three nearest NWS stations."
            )

        selected = min(observations, key=lambda item: item.station.distance_km)
        warnings.extend(selected.upstream.warnings)
        freshness = self._freshness(
            selected.current.observed_at,
            self.settings.observation_fresh_minutes,
            self.settings.observation_delayed_minutes,
            fallback=selected.upstream.stale_fallback,
        )
        nullable_values = (
            selected.current.temperature_c,
            selected.current.dewpoint_c,
            selected.current.relative_humidity_pct,
            selected.current.wind_speed_kph,
            selected.current.pressure_hpa,
            selected.current.visibility_km,
        )
        quality = (
            DataQuality.PARTIAL
            if selected.upstream.stale_fallback
            or sum(value is not None for value in nullable_values) < 3
            else DataQuality.VERIFIED
        )
        processed_at = self._utcnow()
        return CurrentWeatherResponse(
            location=location,
            current=selected.current,
            station=selected.station,
            meta=ResponseMetadata(
                source_time=selected.current.observed_at,
                fetched_at=selected.upstream.fetched_at,
                processed_at=processed_at,
                valid_from=selected.current.observed_at,
                valid_to=None,
                units={
                    "temperature": "degC",
                    "apparent_temperature": "degC",
                    "dewpoint": "degC",
                    "relative_humidity": "percent",
                    "wind_speed": "km/h",
                    "wind_gust": "km/h",
                    "wind_direction": "degree",
                    "pressure": "hPa",
                    "visibility": "km",
                    "station_distance": "km",
                },
                freshness=freshness,
                quality=quality,
                pipeline_version=self.settings.pipeline_version,
                warnings=_unique(warnings),
                from_cache=any(
                    item.from_cache for item in (point, station_collection, selected.upstream)
                ),
                stale_fallback=any(
                    item.stale_fallback for item in (point, station_collection, selected.upstream)
                ),
            ),
        )

    async def hourly(
        self,
        latitude: float,
        longitude: float,
        *,
        hours: int = 48,
    ) -> HourlyWeatherResponse:
        point = await self.client.get_json(self._point_path(latitude, longitude))
        properties = _properties(point.payload, "point metadata")
        location = _location(latitude, longitude, properties)
        forecast = await self.client.get_json(_required_url(properties, "forecastHourly"))
        forecast_properties = _properties(forecast.payload, "hourly forecast")
        raw_periods = forecast_properties.get("periods")
        if not isinstance(raw_periods, list):
            raise WeatherDataError("NWS hourly forecast is missing periods.")

        periods = [_hourly_period(item) for item in raw_periods[:hours]]
        if not periods:
            raise WeatherDataError("NWS hourly forecast contains no periods.")
        source_time = _source_time(forecast_properties, fallback=forecast.fetched_at)
        fallback = point.stale_fallback or forecast.stale_fallback
        return HourlyWeatherResponse(
            location=location,
            periods=periods,
            meta=self._forecast_meta(
                source_time=source_time,
                valid_from=periods[0].start_time,
                valid_to=periods[-1].end_time,
                fetched_at=forecast.fetched_at,
                from_cache=point.from_cache or forecast.from_cache,
                stale_fallback=fallback,
                warnings=_warnings(point, forecast),
                units={
                    "temperature": "degC",
                    "dewpoint": "degC",
                    "relative_humidity": "percent",
                    "probability_of_precipitation": "percent",
                    "wind_speed": "km/h",
                    "wind_gust": "km/h",
                    "wind_direction": "degree",
                },
            ),
        )

    async def daily(self, latitude: float, longitude: float) -> DailyWeatherResponse:
        point = await self.client.get_json(self._point_path(latitude, longitude))
        properties = _properties(point.payload, "point metadata")
        location = _location(latitude, longitude, properties)
        forecast = await self.client.get_json(_required_url(properties, "forecast"))
        forecast_properties = _properties(forecast.payload, "daily forecast")
        raw_periods = forecast_properties.get("periods")
        if not isinstance(raw_periods, list):
            raise WeatherDataError("NWS daily forecast is missing periods.")

        periods = [_daily_period(item) for item in raw_periods]
        if not periods:
            raise WeatherDataError("NWS daily forecast contains no periods.")
        source_time = _source_time(forecast_properties, fallback=forecast.fetched_at)
        fallback = point.stale_fallback or forecast.stale_fallback
        return DailyWeatherResponse(
            location=location,
            periods=periods,
            meta=self._forecast_meta(
                source_time=source_time,
                valid_from=periods[0].start_time,
                valid_to=periods[-1].end_time,
                fetched_at=forecast.fetched_at,
                from_cache=point.from_cache or forecast.from_cache,
                stale_fallback=fallback,
                warnings=_warnings(point, forecast),
                units={
                    "temperature": "degC",
                    "probability_of_precipitation": "percent",
                    "wind_speed": "km/h",
                },
            ),
        )

    async def alerts(self, latitude: float, longitude: float) -> ActiveAlertsResponse:
        point: UpstreamJSON | None = None
        try:
            point = await self.client.get_json(self._point_path(latitude, longitude))
            point_properties = _properties(point.payload, "point metadata")
            location = _location(latitude, longitude, point_properties)
        except NWSClientError:
            location = _coordinate_location(latitude, longitude)

        processed_at = self._utcnow()
        try:
            feed = await self.client.get_json(
                f"/alerts/active?point={latitude:.4f},{longitude:.4f}"
            )
        except NWSClientError:
            return ActiveAlertsResponse(
                location=location,
                alerts=[],
                status=AlertFeedStatus.UNAVAILABLE,
                meta=ResponseMetadata(
                    source_time=None,
                    fetched_at=processed_at,
                    processed_at=processed_at,
                    valid_from=None,
                    valid_to=None,
                    units={},
                    freshness=FreshnessStatus.UNAVAILABLE,
                    quality=DataQuality.UNAVAILABLE,
                    pipeline_version=self.settings.pipeline_version,
                    warnings=[
                        "Current official alert status cannot be confirmed because "
                        "the NWS alert feed is unavailable."
                    ],
                ),
            )

        raw_features = feed.payload.get("features")
        if not isinstance(raw_features, list):
            raise WeatherDataError("NWS alert feed is missing features.")
        alerts: list[OfficialAlert] = []
        for raw_feature in raw_features:
            try:
                alert = _official_alert(raw_feature)
            except (KeyError, TypeError, ValueError, ValidationError):
                continue
            if _alert_is_active(alert, processed_at):
                alerts.append(alert)
            await self.alert_writer.store(alert, raw_feature)
        alerts.sort(key=lambda value: (value.sent_at, value.event), reverse=True)

        source_time = _optional_datetime(feed.payload.get("updated")) or feed.fetched_at
        status = AlertFeedStatus.UNAVAILABLE if feed.stale_fallback else AlertFeedStatus.AVAILABLE
        warnings = list(feed.warnings)
        if feed.stale_fallback:
            warnings.append(
                "Current official alert status cannot be confirmed; "
                "this is the last-known-good feed."
            )
        if point is not None:
            warnings.extend(point.warnings)
        return ActiveAlertsResponse(
            location=location,
            alerts=alerts,
            status=status,
            meta=ResponseMetadata(
                source_time=source_time,
                fetched_at=feed.fetched_at,
                processed_at=processed_at,
                valid_from=source_time,
                valid_to=None,
                units={},
                freshness=self._freshness(
                    source_time,
                    self.settings.alerts_fresh_minutes,
                    self.settings.alerts_delayed_minutes,
                    fallback=feed.stale_fallback,
                ),
                quality=(DataQuality.PARTIAL if feed.stale_fallback else DataQuality.VERIFIED),
                pipeline_version=self.settings.pipeline_version,
                warnings=_unique(warnings),
                from_cache=feed.from_cache or (point.from_cache if point else False),
                stale_fallback=feed.stale_fallback,
            ),
        )

    async def _station_observation(
        self,
        raw_station: object,
        *,
        latitude: float,
        longitude: float,
    ) -> _StationObservation:
        if not isinstance(raw_station, dict):
            raise WeatherDataError("Invalid NWS station feature.")
        properties = _properties(raw_station, "station")
        station_url = properties.get("@id") or raw_station.get("id")
        if not isinstance(station_url, str):
            raise WeatherDataError("NWS station is missing its resource URL.")
        upstream = await self.client.get_json(f"{station_url.rstrip('/')}/observations/latest")
        observed = _properties(upstream.payload, "observation")
        observed_at = _required_datetime(observed, "timestamp")
        station_lat, station_lon = _point_coordinates(raw_station)
        station_id = str(properties.get("stationIdentifier") or station_url.rsplit("/", 1)[-1])
        station_name = str(properties.get("name") or station_id)
        heat_index = _quantity(observed, "heatIndex", "temperature")
        wind_chill = _quantity(observed, "windChill", "temperature")
        current = CurrentConditions(
            temperature_c=_quantity(observed, "temperature", "temperature"),
            apparent_temperature_c=heat_index if heat_index is not None else wind_chill,
            dewpoint_c=_quantity(observed, "dewpoint", "temperature"),
            relative_humidity_pct=_quantity(observed, "relativeHumidity", "percent"),
            wind_speed_kph=_quantity(observed, "windSpeed", "speed"),
            wind_gust_kph=_quantity(observed, "windGust", "speed"),
            wind_direction_deg=_quantity(observed, "windDirection", "degree"),
            pressure_hpa=_quantity(observed, "barometricPressure", "pressure"),
            visibility_km=_quantity(observed, "visibility", "distance"),
            text_description=_optional_text(observed.get("textDescription")),
            icon_url=_optional_url(observed.get("icon")),
            observed_at=observed_at,
        )
        if current.temperature_c is None:
            raise WeatherDataError("NWS observation has no usable current temperature.")
        station = ObservationStation(
            id=station_id,
            name=station_name,
            latitude=station_lat,
            longitude=station_lon,
            distance_km=round(
                haversine_km(latitude, longitude, station_lat, station_lon),
                2,
            ),
            observed_at=observed_at,
        )
        return _StationObservation(station=station, current=current, upstream=upstream)

    def _forecast_meta(
        self,
        *,
        source_time: datetime,
        valid_from: datetime,
        valid_to: datetime,
        fetched_at: datetime,
        from_cache: bool,
        stale_fallback: bool,
        warnings: list[str],
        units: dict[str, str],
    ) -> ResponseMetadata:
        return ResponseMetadata(
            source_time=source_time,
            fetched_at=fetched_at,
            processed_at=self._utcnow(),
            valid_from=valid_from,
            valid_to=valid_to,
            units=units,
            freshness=self._freshness(
                source_time,
                self.settings.forecast_fresh_minutes,
                self.settings.forecast_delayed_minutes,
                fallback=stale_fallback,
            ),
            quality=DataQuality.PARTIAL if stale_fallback else DataQuality.VERIFIED,
            pipeline_version=self.settings.pipeline_version,
            warnings=_unique(warnings),
            from_cache=from_cache,
            stale_fallback=stale_fallback,
        )

    def _freshness(
        self,
        source_time: datetime,
        fresh_minutes: int,
        delayed_minutes: int,
        *,
        fallback: bool,
    ) -> FreshnessStatus:
        age_minutes = max(0.0, (self._utcnow() - source_time).total_seconds() / 60)
        if age_minutes <= fresh_minutes:
            return FreshnessStatus.DELAYED if fallback else FreshnessStatus.FRESH
        if age_minutes <= delayed_minutes:
            return FreshnessStatus.DELAYED
        return FreshnessStatus.STALE

    @staticmethod
    def _point_path(latitude: float, longitude: float) -> str:
        return f"/points/{latitude:.4f},{longitude:.4f}"

    def _utcnow(self) -> datetime:
        now = self._now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        return now.astimezone(UTC)


def _location(latitude: float, longitude: float, point_properties: dict[str, Any]) -> Location:
    relative = point_properties.get("relativeLocation")
    relative_properties = relative.get("properties", {}) if isinstance(relative, dict) else {}
    city = _optional_text(relative_properties.get("city")) or "Selected coordinates"
    region = _optional_text(relative_properties.get("state")) or "Lincoln service region"
    timezone = _optional_text(point_properties.get("timeZone")) or "America/Chicago"
    label = (
        f"{city}, {region}"
        if city != "Selected coordinates"
        else f"{latitude:.4f}, {longitude:.4f}"
    )
    return Location(
        id=f"point:{latitude:.4f}:{longitude:.4f}",
        name=city,
        region=region,
        latitude=round(latitude, 4),
        longitude=round(longitude, 4),
        timezone=timezone,
        kind=LocationKind.COORDINATE,
        label=label,
    )


def _coordinate_location(latitude: float, longitude: float) -> Location:
    return Location(
        id=f"point:{latitude:.4f}:{longitude:.4f}",
        name="Selected coordinates",
        region="Lincoln service region",
        latitude=round(latitude, 4),
        longitude=round(longitude, 4),
        timezone="America/Chicago",
        kind=LocationKind.COORDINATE,
        label=f"{latitude:.4f}, {longitude:.4f}",
    )


def _hourly_period(raw: object) -> HourlyPeriod:
    if not isinstance(raw, dict):
        raise WeatherDataError("Invalid hourly forecast period.")
    temperature = _forecast_temperature(raw.get("temperature"), raw.get("temperatureUnit"))
    wind_values = _wind_kph(raw.get("windSpeed"))
    direction = _optional_text(raw.get("windDirection"))
    return HourlyPeriod(
        start_time=_required_datetime(raw, "startTime"),
        end_time=_required_datetime(raw, "endTime"),
        is_daytime=bool(raw.get("isDaytime")),
        temperature_c=temperature,
        dewpoint_c=_nested_value(raw.get("dewpoint"), "temperature"),
        relative_humidity_pct=_nested_value(raw.get("relativeHumidity"), "percent"),
        probability_of_precipitation_pct=_nested_value(
            raw.get("probabilityOfPrecipitation"),
            "percent",
        ),
        wind_speed_kph=wind_values[0] if wind_values else None,
        wind_gust_kph=_single_wind_kph(raw.get("windGust")),
        wind_direction=direction,
        wind_direction_deg=_COMPASS_DEGREES.get(direction or ""),
        short_forecast=str(raw.get("shortForecast") or "Forecast unavailable"),
        icon_url=_optional_url(raw.get("icon")),
    )


def _daily_period(raw: object) -> DailyPeriod:
    if not isinstance(raw, dict):
        raise WeatherDataError("Invalid daily forecast period.")
    wind_values = _wind_kph(raw.get("windSpeed"))
    return DailyPeriod(
        number=int(raw.get("number") or 1),
        name=str(raw.get("name") or "Forecast period"),
        start_time=_required_datetime(raw, "startTime"),
        end_time=_required_datetime(raw, "endTime"),
        is_daytime=bool(raw.get("isDaytime")),
        temperature_c=_forecast_temperature(raw.get("temperature"), raw.get("temperatureUnit")),
        probability_of_precipitation_pct=_nested_value(
            raw.get("probabilityOfPrecipitation"),
            "percent",
        ),
        wind_speed_min_kph=min(wind_values) if wind_values else None,
        wind_speed_max_kph=max(wind_values) if wind_values else None,
        wind_direction=_optional_text(raw.get("windDirection")),
        short_forecast=str(raw.get("shortForecast") or "Forecast unavailable"),
        detailed_forecast=str(raw.get("detailedForecast") or ""),
        icon_url=_optional_url(raw.get("icon")),
    )


def _official_alert(raw_feature: object) -> OfficialAlert:
    if not isinstance(raw_feature, dict):
        raise WeatherDataError("Invalid NWS alert feature.")
    properties = _properties(raw_feature, "alert")
    alert_id = str(properties.get("id") or raw_feature.get("id") or "")
    if not alert_id:
        raise WeatherDataError("NWS alert is missing its identifier.")
    sent_at = _required_datetime(properties, "sent")
    canonical_payload = json.dumps(raw_feature, sort_keys=True, separators=(",", ":"))
    revision_id = hashlib.sha256(
        f"{alert_id}\0{sent_at.isoformat()}\0{canonical_payload}".encode()
    ).hexdigest()
    geometry = raw_feature.get("geometry")
    return OfficialAlert(
        id=alert_id,
        revision_id=revision_id,
        event=str(properties.get("event") or "Weather alert"),
        headline=_optional_text(properties.get("headline")),
        description=str(properties.get("description") or ""),
        instruction=_optional_text(properties.get("instruction")),
        area_description=str(properties.get("areaDesc") or ""),
        issuing_office=_optional_text(properties.get("senderName") or properties.get("sender")),
        sent_at=sent_at,
        effective_at=_required_datetime(properties, "effective"),
        onset_at=_optional_datetime(properties.get("onset")),
        expires_at=_required_datetime(properties, "expires"),
        ends_at=_optional_datetime(properties.get("ends")),
        severity=str(properties.get("severity") or "Unknown"),
        certainty=str(properties.get("certainty") or "Unknown"),
        urgency=str(properties.get("urgency") or "Unknown"),
        status=str(properties.get("status") or "Actual"),
        message_type=str(properties.get("messageType") or "Alert"),
        response=_optional_text(properties.get("response")),
        geometry=geometry if isinstance(geometry, dict) else None,
    )


def _alert_is_active(alert: OfficialAlert, now: datetime) -> bool:
    boundary = min(alert.expires_at, alert.ends_at) if alert.ends_at else alert.expires_at
    return boundary > now


def _properties(document: dict[str, Any], label: str) -> dict[str, Any]:
    properties = document.get("properties")
    if not isinstance(properties, dict):
        raise WeatherDataError(f"NWS {label} is missing properties.")
    return properties


def _required_url(properties: dict[str, Any], key: str) -> str:
    value = properties.get(key)
    if not isinstance(value, str) or not value.startswith("https://"):
        raise WeatherDataError(f"NWS metadata is missing {key}.")
    return value


def _point_coordinates(feature: dict[str, Any]) -> tuple[float, float]:
    geometry = feature.get("geometry")
    coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
    if (
        not isinstance(coordinates, list)
        or len(coordinates) < 2
        or not all(isinstance(value, (int, float)) for value in coordinates[:2])
    ):
        raise WeatherDataError("NWS station is missing point coordinates.")
    return float(coordinates[1]), float(coordinates[0])


def _quantity(properties: dict[str, Any], key: str, kind: str) -> float | None:
    raw = properties.get(key)
    if not isinstance(raw, dict):
        return None
    value = raw.get("value")
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    unit = str(raw.get("unitCode") or "")
    return _convert_quantity(float(value), unit, kind)


def _nested_value(raw: object, kind: str) -> float | None:
    if not isinstance(raw, dict):
        return None
    value = raw.get("value")
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    unit = str(raw.get("unitCode") or "")
    return _convert_quantity(float(value), unit, kind)


def _convert_quantity(value: float, unit: str, kind: str) -> float:
    if kind == "temperature":
        if unit.endswith("degF"):
            return round((value - 32) * 5 / 9, 2)
        if unit.endswith("K"):
            return round(value - 273.15, 2)
        return round(value, 2)
    if kind == "speed":
        if unit.endswith("m_s-1"):
            return round(value * 3.6, 2)
        if unit.endswith("mi_h-1") or unit.endswith("mph"):
            return round(value * 1.609344, 2)
        return round(value, 2)
    if kind == "pressure":
        if unit.endswith("hPa"):
            return round(value, 2)
        if unit.endswith("Pa"):
            return round(value / 100, 2)
        return round(value, 2)
    if kind == "distance":
        if unit.endswith("m"):
            return round(value / 1000, 2)
        if unit.endswith("mi"):
            return round(value * 1.609344, 2)
        return round(value, 2)
    return round(value, 2)


def _forecast_temperature(value: object, unit: object) -> float | None:
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    unit_name = str(unit or "").upper()
    if unit_name == "F":
        return round((float(value) - 32) * 5 / 9, 2)
    if unit_name == "K":
        return round(float(value) - 273.15, 2)
    return round(float(value), 2)


def _wind_kph(value: object) -> list[float]:
    if not isinstance(value, str):
        return []
    numbers = [float(match) for match in _WIND.findall(value)]
    if "mph" in value.lower():
        return [round(number * 1.609344, 2) for number in numbers]
    if "kt" in value.lower() or "knot" in value.lower():
        return [round(number * 1.852, 2) for number in numbers]
    return [round(number, 2) for number in numbers]


def _single_wind_kph(value: object) -> float | None:
    values = _wind_kph(value)
    return values[0] if values else None


def _required_datetime(properties: dict[str, Any], key: str) -> datetime:
    value = _optional_datetime(properties.get(key))
    if value is None:
        raise WeatherDataError(f"NWS data is missing {key}.")
    return value


def _optional_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _source_time(properties: dict[str, Any], fallback: datetime) -> datetime:
    for key in ("updateTime", "generatedAt", "updated"):
        if parsed := _optional_datetime(properties.get(key)):
            return parsed
    return fallback


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _optional_url(value: object) -> str | None:
    return value if isinstance(value, str) and value.startswith("https://") else None


def _warnings(*responses: UpstreamJSON) -> list[str]:
    return _unique(warning for response in responses for warning in response.warnings)


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))
