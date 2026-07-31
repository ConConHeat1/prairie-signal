from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pytest

from prairie_signal_api.nws_client import UpstreamJSON
from prairie_signal_api.schemas import AlertFeedStatus, FreshnessStatus
from prairie_signal_api.weather_service import WeatherService

POINT_URL = "/points/40.8136,-96.7026"
STATIONS_URL = "https://api.weather.gov/gridpoints/OAX/40,72/stations"
HOURLY_URL = "https://api.weather.gov/gridpoints/OAX/40,72/forecast/hourly"
DAILY_URL = "https://api.weather.gov/gridpoints/OAX/40,72/forecast"


class ScriptedClient:
    def __init__(self, responses: dict[str, UpstreamJSON]) -> None:
        self.responses = responses
        self.requested: list[str] = []

    async def get_json(self, path: str) -> UpstreamJSON:
        self.requested.append(path)
        return self.responses[path]


class CapturingWriter:
    def __init__(self) -> None:
        self.items: list[tuple[Any, dict[str, Any]]] = []

    async def store(self, alert, raw_feature: dict[str, Any]) -> None:
        self.items.append((alert, raw_feature))


def upstream(payload, fixed_now, *, stale: bool = False) -> UpstreamJSON:
    return UpstreamJSON(
        payload=payload,
        headers={},
        fetched_at=fixed_now - timedelta(minutes=1),
        from_cache=stale,
        stale_fallback=stale,
        warnings=["upstream fallback"] if stale else [],
    )


def point_payload() -> dict[str, Any]:
    return {
        "properties": {
            "forecastHourly": HOURLY_URL,
            "forecast": DAILY_URL,
            "observationStations": STATIONS_URL,
            "timeZone": "America/Chicago",
            "relativeLocation": {
                "properties": {"city": "Lincoln", "state": "NE"},
            },
        }
    }


def station_feature(identifier: str, latitude: float, longitude: float) -> dict[str, Any]:
    return {
        "id": f"https://api.weather.gov/stations/{identifier}",
        "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
        "properties": {
            "@id": f"https://api.weather.gov/stations/{identifier}",
            "stationIdentifier": identifier,
            "name": f"Station {identifier}",
        },
    }


def observation_payload(fixed_now, temperature: float | None) -> dict[str, Any]:
    def quantity(value: float | None, unit: str) -> dict[str, Any]:
        return {"value": value, "unitCode": f"wmoUnit:{unit}"}

    return {
        "properties": {
            "timestamp": (fixed_now - timedelta(minutes=10)).isoformat(),
            "temperature": quantity(temperature, "degC"),
            "heatIndex": quantity(None, "degC"),
            "windChill": quantity(0, "degC"),
            "dewpoint": quantity(10, "degC"),
            "relativeHumidity": quantity(55, "percent"),
            "windSpeed": quantity(5, "km_h-1"),
            "windGust": quantity(10, "km_h-1"),
            "windDirection": quantity(180, "degree_(angle)"),
            "barometricPressure": quantity(101325, "Pa"),
            "visibility": quantity(16093.44, "m"),
            "textDescription": "Partly Cloudy",
            "icon": "https://api.weather.gov/icons/land/day/few",
        }
    }


@pytest.mark.asyncio
async def test_current_selects_nearest_valid_of_first_three(settings, fixed_now) -> None:
    stations = [
        station_feature("BAD", 40.82, -96.70),
        station_feature("FAR", 41.00, -96.70),
        station_feature("NEAR", 40.85, -96.70),
        station_feature("IGNORED", 40.8136, -96.7026),
    ]
    responses = {
        POINT_URL: upstream(point_payload(), fixed_now),
        STATIONS_URL: upstream({"features": stations}, fixed_now),
        "https://api.weather.gov/stations/BAD/observations/latest": upstream(
            observation_payload(fixed_now, None),
            fixed_now,
        ),
        "https://api.weather.gov/stations/FAR/observations/latest": upstream(
            observation_payload(fixed_now, 20),
            fixed_now,
        ),
        "https://api.weather.gov/stations/NEAR/observations/latest": upstream(
            observation_payload(fixed_now, 21),
            fixed_now,
        ),
    }
    service = WeatherService(
        settings,
        ScriptedClient(responses),  # type: ignore[arg-type]
        now=lambda: fixed_now,
    )

    result = await service.current(40.8136, -96.7026)

    assert result.station.id == "NEAR"
    assert result.current.temperature_c == 21
    assert result.current.apparent_temperature_c == 0
    assert result.current.pressure_hpa == 1013.25
    assert result.current.visibility_km == 16.09
    assert result.meta.freshness is FreshnessStatus.FRESH
    assert result.location.label == "Lincoln, NE"


@pytest.mark.asyncio
async def test_hourly_normalizes_units_and_limits_to_requested_hours(
    settings,
    fixed_now,
) -> None:
    periods = []
    for offset in range(3):
        start = fixed_now + timedelta(hours=offset)
        periods.append(
            {
                "startTime": start.isoformat(),
                "endTime": (start + timedelta(hours=1)).isoformat(),
                "isDaytime": True,
                "temperature": 68 + offset,
                "temperatureUnit": "F",
                "dewpoint": {"value": 10, "unitCode": "wmoUnit:degC"},
                "relativeHumidity": {"value": 60, "unitCode": "wmoUnit:percent"},
                "probabilityOfPrecipitation": {
                    "value": 25,
                    "unitCode": "wmoUnit:percent",
                },
                "windSpeed": "5 mph",
                "windGust": "10 mph",
                "windDirection": "SSW",
                "shortForecast": "Mostly Sunny",
                "icon": "https://api.weather.gov/icons/land/day/few",
            }
        )
    responses = {
        POINT_URL: upstream(point_payload(), fixed_now),
        HOURLY_URL: upstream(
            {
                "properties": {
                    "updateTime": (fixed_now - timedelta(hours=1)).isoformat(),
                    "periods": periods,
                }
            },
            fixed_now,
        ),
    }
    service = WeatherService(
        settings,
        ScriptedClient(responses),  # type: ignore[arg-type]
        now=lambda: fixed_now,
    )

    result = await service.hourly(40.8136, -96.7026, hours=2)

    assert len(result.periods) == 2
    assert result.periods[0].temperature_c == 20
    assert result.periods[0].wind_speed_kph == 8.05
    assert result.periods[0].wind_direction_deg == 202.5
    assert result.meta.valid_to == datetime.fromisoformat(periods[1]["endTime"])


@pytest.mark.asyncio
async def test_daily_preserves_day_night_periods_and_wind_range(
    settings,
    fixed_now,
) -> None:
    period = {
        "number": 1,
        "name": "Tonight",
        "startTime": fixed_now.isoformat(),
        "endTime": (fixed_now + timedelta(hours=12)).isoformat(),
        "isDaytime": False,
        "temperature": 50,
        "temperatureUnit": "F",
        "probabilityOfPrecipitation": {"value": 10, "unitCode": "wmoUnit:percent"},
        "windSpeed": "5 to 10 mph",
        "windDirection": "N",
        "shortForecast": "Clear",
        "detailedForecast": "Clear, with a low around 50.",
        "icon": "https://api.weather.gov/icons/land/night/skc",
    }
    responses = {
        POINT_URL: upstream(point_payload(), fixed_now),
        DAILY_URL: upstream(
            {
                "properties": {
                    "generatedAt": (fixed_now - timedelta(hours=2)).isoformat(),
                    "periods": [period],
                }
            },
            fixed_now,
        ),
    }
    service = WeatherService(
        settings,
        ScriptedClient(responses),  # type: ignore[arg-type]
        now=lambda: fixed_now,
    )

    result = await service.daily(40.8136, -96.7026)

    assert result.periods[0].name == "Tonight"
    assert not result.periods[0].is_daytime
    assert result.periods[0].wind_speed_min_kph == 8.05
    assert result.periods[0].wind_speed_max_kph == 16.09


def alert_feature(fixed_now, *, expired: bool, description: str) -> dict[str, Any]:
    expires = fixed_now - timedelta(minutes=1) if expired else fixed_now + timedelta(hours=1)
    return {
        "id": f"https://api.weather.gov/alerts/{'expired' if expired else 'active'}",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[-96.8, 40.7], [-96.6, 40.7], [-96.8, 40.7]]],
        },
        "properties": {
            "id": f"urn:oid:{'expired' if expired else 'active'}",
            "event": "Severe Thunderstorm Warning",
            "headline": "Severe Thunderstorm Warning issued July 30",
            "description": description,
            "instruction": "Move indoors.",
            "areaDesc": "Lancaster County",
            "senderName": "NWS Omaha/Valley NE",
            "sent": (fixed_now - timedelta(minutes=5)).isoformat(),
            "effective": (fixed_now - timedelta(minutes=5)).isoformat(),
            "onset": (fixed_now - timedelta(minutes=4)).isoformat(),
            "expires": expires.isoformat(),
            "ends": None,
            "severity": "Severe",
            "certainty": "Observed",
            "urgency": "Immediate",
            "status": "Actual",
            "messageType": "Alert",
            "response": "Shelter",
        },
    }


@pytest.mark.asyncio
async def test_alerts_preserve_official_text_and_hide_expired_revisions(
    settings,
    fixed_now,
) -> None:
    exact_text = "<script>official source text stays exact & is escaped by the UI</script>"
    active = alert_feature(fixed_now, expired=False, description=exact_text)
    expired = alert_feature(fixed_now, expired=True, description="expired")
    alert_url = "/alerts/active?point=40.8136,-96.7026"
    responses = {
        POINT_URL: upstream(point_payload(), fixed_now),
        alert_url: upstream(
            {
                "updated": (fixed_now - timedelta(minutes=1)).isoformat(),
                "features": [active, expired],
            },
            fixed_now,
        ),
    }
    writer = CapturingWriter()
    service = WeatherService(
        settings,
        ScriptedClient(responses),  # type: ignore[arg-type]
        alert_writer=writer,
        now=lambda: fixed_now,
    )

    result = await service.alerts(40.8136, -96.7026)

    assert result.status is AlertFeedStatus.AVAILABLE
    assert len(result.alerts) == 1
    assert result.alerts[0].description == exact_text
    assert result.alerts[0].geometry == active["geometry"]
    assert len(writer.items) == 2


@pytest.mark.asyncio
async def test_stale_alert_feed_cannot_claim_current_status(settings, fixed_now) -> None:
    active = alert_feature(fixed_now, expired=False, description="official")
    alert_url = "/alerts/active?point=40.8136,-96.7026"
    responses = {
        POINT_URL: upstream(point_payload(), fixed_now),
        alert_url: upstream(
            {
                "updated": (fixed_now - timedelta(minutes=1)).isoformat(),
                "features": [active],
            },
            fixed_now,
            stale=True,
        ),
    }
    service = WeatherService(
        settings,
        ScriptedClient(responses),  # type: ignore[arg-type]
        now=lambda: fixed_now,
    )

    result = await service.alerts(40.8136, -96.7026)

    assert result.status is AlertFeedStatus.UNAVAILABLE
    assert result.meta.freshness is FreshnessStatus.DELAYED
    assert any("cannot be confirmed" in warning for warning in result.meta.warnings)
