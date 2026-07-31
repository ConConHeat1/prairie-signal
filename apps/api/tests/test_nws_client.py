from __future__ import annotations

from datetime import timedelta

import httpx
import pytest

from prairie_signal_api.cache import CachedResponse, MemoryResponseCache
from prairie_signal_api.nws_client import CircuitOpen, CircuitState, NWSClient, NWSUnavailable


@pytest.mark.asyncio
async def test_fresh_response_is_cached_and_reused(settings, fixed_now) -> None:
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(
            200,
            json={"properties": {"value": 1}},
            headers={"Cache-Control": "max-age=300", "ETag": '"one"'},
            request=request,
        )

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = NWSClient(
        settings,
        MemoryResponseCache(),
        http,
        now=lambda: fixed_now,
    )

    first = await client.get_json("/points/40.8136,-96.7026")
    second = await client.get_json("/points/40.8136,-96.7026")

    assert requests == 1
    assert not first.from_cache
    assert second.from_cache
    assert second.payload == first.payload
    await http.aclose()


@pytest.mark.asyncio
async def test_expired_cache_uses_conditional_request_and_304(settings, fixed_now) -> None:
    cache = MemoryResponseCache()
    url = f"{settings.nws_base_url}/test"
    import hashlib

    key = hashlib.sha256(url.encode()).hexdigest()
    await cache.set(
        key,
        CachedResponse(
            payload={"properties": {"value": "old"}},
            headers={"etag": '"cached"', "cache-control": "max-age=0"},
            fetched_at=fixed_now - timedelta(minutes=5),
            expires_at=fixed_now - timedelta(minutes=1),
        ),
        86400,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["If-None-Match"] == '"cached"'
        return httpx.Response(
            304,
            headers={"Cache-Control": "max-age=60"},
            request=request,
        )

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = NWSClient(settings, cache, http, now=lambda: fixed_now)

    result = await client.get_json("/test")

    assert result.from_cache
    assert not result.stale_fallback
    assert result.fetched_at == fixed_now
    assert result.payload["properties"]["value"] == "old"
    await http.aclose()


@pytest.mark.asyncio
async def test_three_jittered_retries_then_success(settings, fixed_now) -> None:
    calls = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 4:
            return httpx.Response(503, request=request)
        return httpx.Response(200, json={"ok": True}, request=request)

    async def sleep(delay: float) -> None:
        delays.append(delay)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = NWSClient(
        settings,
        MemoryResponseCache(),
        http,
        sleep=sleep,
        random_value=lambda: 0.5,
        now=lambda: fixed_now,
    )

    result = await client.get_json("/retry")

    assert result.payload == {"ok": True}
    assert calls == 4
    assert delays == [0.625, 1.125, 2.125]
    await http.aclose()


@pytest.mark.asyncio
async def test_retry_after_header_is_honored(settings, fixed_now) -> None:
    calls = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "2"}, request=request)
        return httpx.Response(200, json={"ok": True}, request=request)

    async def sleep(delay: float) -> None:
        delays.append(delay)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = NWSClient(
        settings,
        MemoryResponseCache(),
        http,
        sleep=sleep,
        now=lambda: fixed_now,
    )

    await client.get_json("/retry-after")

    assert delays == [2.0]
    await http.aclose()


@pytest.mark.asyncio
async def test_failed_revalidation_returns_explicit_stale_fallback(settings, fixed_now) -> None:
    cache = MemoryResponseCache()
    url = f"{settings.nws_base_url}/stale"
    import hashlib

    key = hashlib.sha256(url.encode()).hexdigest()
    await cache.set(
        key,
        CachedResponse(
            payload={"last": "good"},
            headers={},
            fetched_at=fixed_now - timedelta(hours=2),
            expires_at=fixed_now - timedelta(hours=1),
        ),
        86400,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    async def no_sleep(_: float) -> None:
        return None

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = NWSClient(settings, cache, http, sleep=no_sleep, now=lambda: fixed_now)

    result = await client.get_json("/stale")

    assert result.payload == {"last": "good"}
    assert result.from_cache
    assert result.stale_fallback
    assert "last-known-good" in result.warnings[0]
    await http.aclose()


@pytest.mark.asyncio
async def test_circuit_opens_after_configured_failures(settings, fixed_now) -> None:
    settings.nws_max_retries = 0
    settings.nws_circuit_failure_threshold = 2

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = NWSClient(settings, MemoryResponseCache(), http, now=lambda: fixed_now)

    with pytest.raises(NWSUnavailable):
        await client.get_json("/first")
    with pytest.raises(NWSUnavailable):
        await client.get_json("/second")
    assert client.circuit.snapshot.state is CircuitState.OPEN
    with pytest.raises(CircuitOpen):
        await client.get_json("/third")
    await http.aclose()


@pytest.mark.asyncio
async def test_cross_origin_link_from_upstream_is_rejected(settings) -> None:
    client = NWSClient(settings, MemoryResponseCache())
    with pytest.raises(NWSUnavailable, match="cross-origin"):
        await client.get_json("https://example.com/location-bearing-url")
    await client.close()
