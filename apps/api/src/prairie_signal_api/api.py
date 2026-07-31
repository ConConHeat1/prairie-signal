"""Version 1 HTTP routes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from prairie_signal_api.config import Settings
from prairie_signal_api.location_service import LocationIndex, OutsideServiceRegion
from prairie_signal_api.nws_client import NWSClient
from prairie_signal_api.schemas import (
    ActiveAlertsResponse,
    CurrentWeatherResponse,
    DailyWeatherResponse,
    HealthResponse,
    HourlyWeatherResponse,
    LocationSearchResponse,
    ReadinessCheck,
    SourceHealth,
    SourcesResponse,
)
from prairie_signal_api.weather_service import WeatherService

router = APIRouter(prefix="/api/v1")
metrics_router = APIRouter()


def _weather(request: Request) -> WeatherService:
    return cast(WeatherService, request.app.state.weather_service)


def _locations(request: Request) -> LocationIndex:
    return cast(LocationIndex, request.app.state.location_index)


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def _nws(request: Request) -> NWSClient:
    return cast(NWSClient, request.app.state.nws_client)


def _validated_point(
    latitude: Annotated[float, Query(ge=-90, le=90)],
    longitude: Annotated[float, Query(ge=-180, le=180)],
    locations: Annotated[LocationIndex, Depends(_locations)],
) -> tuple[float, float]:
    if not locations.in_region(latitude, longitude):
        raise OutsideServiceRegion(
            f"Coordinates are outside the {locations.radius_km * 2:g} km-wide service region."
        )
    return latitude, longitude


@router.get("/location/search", response_model=LocationSearchResponse)
async def search_locations(
    q: Annotated[str, Query(min_length=1, max_length=100)],
    locations: Annotated[LocationIndex, Depends(_locations)],
    limit: Annotated[int, Query(ge=1, le=20)] = 8,
) -> LocationSearchResponse:
    result = locations.search(q, limit)
    return LocationSearchResponse(
        results=result.locations,
        query_kind=result.kind,
        region_limit_km=locations.radius_km * 2,
    )


@router.get("/weather/current", response_model=CurrentWeatherResponse)
async def current_weather(
    point: Annotated[tuple[float, float], Depends(_validated_point)],
    service: Annotated[WeatherService, Depends(_weather)],
) -> CurrentWeatherResponse:
    return await service.current(*point)


@router.get("/weather/hourly", response_model=HourlyWeatherResponse)
async def hourly_weather(
    point: Annotated[tuple[float, float], Depends(_validated_point)],
    service: Annotated[WeatherService, Depends(_weather)],
    hours: Annotated[int, Query(ge=1, le=168)] = 48,
) -> HourlyWeatherResponse:
    return await service.hourly(*point, hours=hours)


@router.get("/weather/daily", response_model=DailyWeatherResponse)
async def daily_weather(
    point: Annotated[tuple[float, float], Depends(_validated_point)],
    service: Annotated[WeatherService, Depends(_weather)],
) -> DailyWeatherResponse:
    return await service.daily(*point)


@router.get("/alerts/active", response_model=ActiveAlertsResponse)
async def active_alerts(
    point: Annotated[tuple[float, float], Depends(_validated_point)],
    service: Annotated[WeatherService, Depends(_weather)],
) -> ActiveAlertsResponse:
    return await service.alerts(*point)


@router.get("/health", response_model=HealthResponse)
async def health(
    settings: Annotated[Settings, Depends(_settings)],
) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="prairie-signal-api",
        version=settings.pipeline_version,
        timestamp=datetime.now(UTC),
    )


@router.get("/ready", response_model=ReadinessCheck)
async def readiness(
    response: Response,
    request: Request,
    settings: Annotated[Settings, Depends(_settings)],
) -> ReadinessCheck:
    cache_ready = await request.app.state.cache.ping()
    checks = {
        "api": True,
        "cache": cache_ready,
        "location_index": bool(request.app.state.location_index.locations),
        "nws_configured": settings.effective_nws_user_agent is not None,
    }
    ready = all(checks.values())
    if not ready:
        response.status_code = 503
    return ReadinessCheck(
        status="ready" if ready else "not_ready",
        checks=checks,
        timestamp=datetime.now(UTC),
    )


@router.get("/sources", response_model=SourcesResponse)
async def sources(
    nws: Annotated[NWSClient, Depends(_nws)],
) -> SourcesResponse:
    snapshot = nws.circuit.snapshot
    return SourcesResponse(
        sources=[
            SourceHealth(
                name="National Weather Service",
                configured=nws.configured,
                circuit_state=snapshot.state.value,
                consecutive_failures=snapshot.consecutive_failures,
                last_success_at=snapshot.last_success_at,
                last_failure_at=snapshot.last_failure_at,
            )
        ],
        timestamp=datetime.now(UTC),
    )


@metrics_router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
