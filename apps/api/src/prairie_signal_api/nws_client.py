"""Resilient National Weather Service HTTP client."""

from __future__ import annotations

import asyncio
import hashlib
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from enum import Enum
from typing import Any

import httpx

from prairie_signal_api.cache import CachedResponse, ResponseCache
from prairie_signal_api.config import Settings
from prairie_signal_api.metrics import (
    SOURCE_CIRCUIT_OPEN,
    SOURCE_DURATION,
    SOURCE_REQUESTS,
    STALE_FALLBACKS,
)

_TRANSIENT_STATUSES = {408, 425, 429, 500, 502, 503, 504}
_SAFE_RESPONSE_HEADERS = {"cache-control", "etag", "last-modified", "date", "expires", "age"}


class NWSClientError(RuntimeError):
    """Base exception safe for translation at the API boundary."""


class NWSNotConfigured(NWSClientError):
    pass


class NWSUnavailable(NWSClientError):
    pass


class CircuitOpen(NWSUnavailable):
    pass


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(slots=True)
class CircuitSnapshot:
    state: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0
    opened_at_monotonic: float | None = None
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int,
        open_seconds: float,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.open_seconds = open_seconds
        self._monotonic = monotonic
        self.snapshot = CircuitSnapshot()

    def allow_request(self) -> bool:
        if self.snapshot.state is CircuitState.CLOSED:
            return True
        if self.snapshot.state is CircuitState.HALF_OPEN:
            return True
        assert self.snapshot.opened_at_monotonic is not None
        if self._monotonic() - self.snapshot.opened_at_monotonic >= self.open_seconds:
            self.snapshot.state = CircuitState.HALF_OPEN
            SOURCE_CIRCUIT_OPEN.labels("nws").set(0)
            return True
        return False

    def record_success(self, now: datetime) -> None:
        self.snapshot.state = CircuitState.CLOSED
        self.snapshot.consecutive_failures = 0
        self.snapshot.opened_at_monotonic = None
        self.snapshot.last_success_at = now
        SOURCE_CIRCUIT_OPEN.labels("nws").set(0)

    def record_failure(self, now: datetime) -> None:
        self.snapshot.consecutive_failures += 1
        self.snapshot.last_failure_at = now
        if self.snapshot.consecutive_failures >= self.failure_threshold:
            self.snapshot.state = CircuitState.OPEN
            self.snapshot.opened_at_monotonic = self._monotonic()
            SOURCE_CIRCUIT_OPEN.labels("nws").set(1)


@dataclass(slots=True)
class UpstreamJSON:
    payload: dict[str, Any]
    headers: dict[str, str]
    fetched_at: datetime
    from_cache: bool
    stale_fallback: bool
    warnings: list[str]


class _RetryableResponse(Exception):
    def __init__(self, response: httpx.Response) -> None:
        self.response = response


class NWSClient:
    def __init__(
        self,
        settings: Settings,
        cache: ResponseCache,
        http_client: httpx.AsyncClient | None = None,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        random_value: Callable[[], float] = random.random,
        now: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.settings = settings
        self.cache = cache
        self._owns_http_client = http_client is None
        self.http = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(settings.nws_timeout_seconds),
            follow_redirects=False,
        )
        self._sleep = sleep
        self._random = random_value
        self._now = now or (lambda: datetime.now(UTC))
        self.circuit = CircuitBreaker(
            settings.nws_circuit_failure_threshold,
            settings.nws_circuit_open_seconds,
            monotonic,
        )

    @property
    def configured(self) -> bool:
        return self.settings.effective_nws_user_agent is not None

    async def close(self) -> None:
        if self._owns_http_client:
            await self.http.aclose()

    async def get_json(self, path_or_url: str) -> UpstreamJSON:
        user_agent = self.settings.effective_nws_user_agent
        if user_agent is None:
            raise NWSNotConfigured("Live NWS access requires both NWS_USER_AGENT and NWS_CONTACT.")

        url = (
            path_or_url
            if path_or_url.startswith(("https://", "http://"))
            else f"{self.settings.nws_base_url}/{path_or_url.lstrip('/')}"
        )
        if not url.startswith(f"{self.settings.nws_base_url}/"):
            raise NWSUnavailable("NWS supplied an unexpected cross-origin resource URL.")

        cache_key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        cached = await self.cache.get(cache_key)
        now = self._utcnow()
        if cached is not None and now < cached.expires_at:
            SOURCE_REQUESTS.labels("nws", "cache_hit").inc()
            return self._from_cached(cached, stale=False)

        if not self.circuit.allow_request():
            SOURCE_REQUESTS.labels("nws", "circuit_open").inc()
            if cached is not None:
                return self._fallback(cached, "NWS circuit is temporarily open.")
            raise CircuitOpen("The National Weather Service is temporarily unavailable.")

        request_headers = {
            "Accept": "application/geo+json",
            "User-Agent": user_agent,
        }
        if cached is not None:
            if etag := cached.headers.get("etag"):
                request_headers["If-None-Match"] = etag
            if modified := cached.headers.get("last-modified"):
                request_headers["If-Modified-Since"] = modified

        failure: Exception | None = None
        started = time.monotonic()
        try:
            for attempt in range(self.settings.nws_max_retries + 1):
                try:
                    response = await self.http.get(url, headers=request_headers)
                    if response.status_code == 304 and cached is not None:
                        fetched_at = self._utcnow()
                        headers = self._merge_headers(cached.headers, response.headers)
                        ttl, cacheable = self._cache_policy(headers)
                        refreshed = CachedResponse(
                            payload=cached.payload,
                            headers=headers,
                            fetched_at=fetched_at,
                            expires_at=fetched_at + timedelta(seconds=ttl),
                        )
                        if cacheable:
                            await self.cache.set(
                                cache_key,
                                refreshed,
                                self.settings.stale_retention_seconds,
                            )
                        self.circuit.record_success(fetched_at)
                        SOURCE_REQUESTS.labels("nws", "not_modified").inc()
                        return self._from_cached(refreshed, stale=False)

                    if response.status_code in _TRANSIENT_STATUSES:
                        raise _RetryableResponse(response)
                    response.raise_for_status()
                    payload = response.json()
                    if not isinstance(payload, dict):
                        raise ValueError("NWS returned a non-object JSON document.")

                    fetched_at = self._utcnow()
                    safe_headers = self._safe_headers(response.headers)
                    ttl, cacheable = self._cache_policy(safe_headers)
                    record = CachedResponse(
                        payload=payload,
                        headers=safe_headers,
                        fetched_at=fetched_at,
                        expires_at=fetched_at + timedelta(seconds=ttl),
                    )
                    if cacheable:
                        await self.cache.set(
                            cache_key,
                            record,
                            self.settings.stale_retention_seconds,
                        )
                    self.circuit.record_success(fetched_at)
                    SOURCE_REQUESTS.labels("nws", "success").inc()
                    return UpstreamJSON(
                        payload=payload,
                        headers=safe_headers,
                        fetched_at=fetched_at,
                        from_cache=False,
                        stale_fallback=False,
                        warnings=[],
                    )
                except _RetryableResponse as exc:
                    failure = exc
                    if attempt >= self.settings.nws_max_retries:
                        break
                    await self._sleep(self._retry_delay(attempt, exc.response))
                except (httpx.TimeoutException, httpx.NetworkError, ValueError) as exc:
                    failure = exc
                    if attempt >= self.settings.nws_max_retries:
                        break
                    await self._sleep(self._retry_delay(attempt, None))
                except httpx.HTTPStatusError as exc:
                    failure = exc
                    break
        finally:
            SOURCE_DURATION.labels("nws").observe(time.monotonic() - started)

        failed_at = self._utcnow()
        self.circuit.record_failure(failed_at)
        SOURCE_REQUESTS.labels("nws", "failure").inc()
        if cached is not None:
            return self._fallback(cached, "NWS request failed; showing last-known-good data.")
        status = (
            failure.response.status_code
            if isinstance(failure, (_RetryableResponse, httpx.HTTPStatusError))
            else None
        )
        suffix = f" (HTTP {status})" if status is not None else ""
        raise NWSUnavailable(f"The National Weather Service request failed{suffix}.") from failure

    def _utcnow(self) -> datetime:
        now = self._now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        return now.astimezone(UTC)

    def _from_cached(self, cached: CachedResponse, *, stale: bool) -> UpstreamJSON:
        return UpstreamJSON(
            payload=cached.payload,
            headers=cached.headers,
            fetched_at=cached.fetched_at,
            from_cache=True,
            stale_fallback=stale,
            warnings=[],
        )

    def _fallback(self, cached: CachedResponse, warning: str) -> UpstreamJSON:
        STALE_FALLBACKS.labels("nws").inc()
        value = self._from_cached(cached, stale=True)
        value.warnings.append(warning)
        return value

    def _cache_policy(self, headers: dict[str, str]) -> tuple[int, bool]:
        cache_control = headers.get("cache-control", "")
        directives: dict[str, str | None] = {}
        for part in cache_control.split(","):
            key, _, value = part.strip().partition("=")
            if key:
                directives[key.lower()] = value.strip('"') or None
        if "no-store" in directives:
            return 0, False
        if "no-cache" in directives:
            return 0, True

        ttl: float | None = None
        raw_max_age = directives.get("s-maxage") or directives.get("max-age")
        if raw_max_age and raw_max_age.isdigit():
            ttl = float(raw_max_age)
            age = headers.get("age", "0")
            if age.isdigit():
                ttl = max(0, ttl - float(age))
        elif expires := headers.get("expires"):
            try:
                expiry = parsedate_to_datetime(expires).astimezone(UTC)
                ttl = max(0, (expiry - self._utcnow()).total_seconds())
            except (TypeError, ValueError, OverflowError):
                ttl = None
        if ttl is None:
            ttl = float(self.settings.cache_default_ttl_seconds)
        if ttl == 0:
            return 0, True
        bounded = max(
            self.settings.cache_min_ttl_seconds,
            min(int(ttl), self.settings.cache_max_ttl_seconds),
        )
        return bounded, True

    def _retry_delay(self, attempt: int, response: httpx.Response | None) -> float:
        if response is not None and (header := response.headers.get("retry-after")):
            try:
                return min(max(float(header), 0.0), 30.0)
            except ValueError:
                try:
                    target = parsedate_to_datetime(header).astimezone(UTC)
                    delay = (target - self._utcnow()).total_seconds()
                    return float(min(max(delay, 0.0), 30.0))
                except (TypeError, ValueError, OverflowError):
                    pass
        return float(min(0.5 * (2**attempt) + self._random() * 0.25, 5.0))

    @staticmethod
    def _safe_headers(headers: httpx.Headers | dict[str, str]) -> dict[str, str]:
        return {
            key.lower(): value
            for key, value in headers.items()
            if key.lower() in _SAFE_RESPONSE_HEADERS
        }

    @classmethod
    def _merge_headers(
        cls,
        old: dict[str, str],
        new: httpx.Headers,
    ) -> dict[str, str]:
        return {**old, **cls._safe_headers(new)}
