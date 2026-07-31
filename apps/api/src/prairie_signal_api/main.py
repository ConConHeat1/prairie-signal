"""FastAPI application entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from prairie_signal_api.api import metrics_router, router
from prairie_signal_api.cache import MemoryResponseCache, RedisResponseCache, ResponseCache
from prairie_signal_api.config import Settings, get_settings
from prairie_signal_api.location_service import LocationSearchError, build_location_index
from prairie_signal_api.logging import PrivacySafeRequestMiddleware, configure_logging
from prairie_signal_api.nws_client import NWSClient, NWSClientError, NWSNotConfigured
from prairie_signal_api.schemas import ErrorDetail, ErrorResponse
from prairie_signal_api.weather_service import WeatherDataError, WeatherService


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        cache = await _build_cache(resolved_settings)
        nws_client = NWSClient(resolved_settings, cache)
        app.state.settings = resolved_settings
        app.state.cache = cache
        app.state.nws_client = nws_client
        app.state.location_index = build_location_index(resolved_settings)
        app.state.weather_service = WeatherService(resolved_settings, nws_client)
        try:
            yield
        finally:
            await nws_client.close()
            await cache.close()

    app = FastAPI(
        title=resolved_settings.app_name,
        summary="Official NWS weather data for the Lincoln service region",
        description=(
            "Prairie Signal exposes attributed official observations, forecasts, and alerts. "
            "It does not provide radar, generated forecasts, or experimental hazard guidance."
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(PrivacySafeRequestMiddleware)
    app.include_router(router)
    app.include_router(metrics_router)

    @app.exception_handler(LocationSearchError)
    async def location_error(_: Request, exc: LocationSearchError) -> JSONResponse:
        return _error_response(422, exc.code, str(exc), retryable=False)

    @app.exception_handler(NWSNotConfigured)
    async def nws_configuration_error(_: Request, exc: NWSNotConfigured) -> JSONResponse:
        return _error_response(503, "nws_not_configured", str(exc), retryable=False)

    @app.exception_handler(NWSClientError)
    async def nws_error(_: Request, exc: NWSClientError) -> JSONResponse:
        return _error_response(503, "nws_unavailable", str(exc), retryable=True)

    @app.exception_handler(WeatherDataError)
    async def weather_data_error(_: Request, exc: WeatherDataError) -> JSONResponse:
        return _error_response(502, "invalid_upstream_data", str(exc), retryable=True)

    return app


async def _build_cache(settings: Settings) -> ResponseCache:
    if not settings.cache_url:
        return MemoryResponseCache()
    logger = structlog.get_logger("cache")
    redis_cache = RedisResponseCache.from_url(settings.cache_url)
    if await redis_cache.ping():
        return redis_cache
    await redis_cache.close()
    logger.warning("cache_unavailable", backend="redis", fallback="memory")
    return MemoryResponseCache()


def _error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    retryable: bool,
) -> JSONResponse:
    payload = ErrorResponse(error=ErrorDetail(code=code, message=message, retryable=retryable))
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


app = create_app()
