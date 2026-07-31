from datetime import UTC, datetime, timedelta

import pytest

from prairie_signal_api.cache import CachedResponse, MemoryResponseCache


def test_cached_response_serialization_round_trip() -> None:
    now = datetime(2026, 7, 30, 12, tzinfo=UTC)
    original = CachedResponse(
        payload={"features": [{"id": "one"}]},
        headers={"etag": '"v1"'},
        fetched_at=now,
        expires_at=now + timedelta(minutes=2),
    )

    decoded = CachedResponse.decode(original.encode())

    assert decoded == original


@pytest.mark.asyncio
async def test_memory_cache_ping_and_close() -> None:
    cache = MemoryResponseCache()
    assert await cache.ping()
    await cache.close()
