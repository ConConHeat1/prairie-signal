"""Transient response caches used for conditional requests and stale fallback."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Protocol


@dataclass(slots=True)
class CachedResponse:
    payload: dict[str, object]
    headers: dict[str, str]
    fetched_at: datetime
    expires_at: datetime

    def encode(self) -> str:
        data = asdict(self)
        data["fetched_at"] = self.fetched_at.isoformat()
        data["expires_at"] = self.expires_at.isoformat()
        return json.dumps(data, separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def decode(cls, raw: str | bytes) -> CachedResponse:
        data = json.loads(raw)
        return cls(
            payload=data["payload"],
            headers=data["headers"],
            fetched_at=_parse_datetime(data["fetched_at"]),
            expires_at=_parse_datetime(data["expires_at"]),
        )


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


class ResponseCache(Protocol):
    async def get(self, key: str) -> CachedResponse | None: ...

    async def set(self, key: str, value: CachedResponse, retention_seconds: int) -> None: ...

    async def ping(self) -> bool: ...

    async def close(self) -> None: ...


class MemoryResponseCache:
    """Process-local cache for development, tests, and graceful Redis fallback."""

    def __init__(self) -> None:
        self._records: dict[str, tuple[CachedResponse, datetime]] = {}

    async def get(self, key: str) -> CachedResponse | None:
        item = self._records.get(key)
        if item is None:
            return None
        record, retained_until = item
        if datetime.now(UTC) >= retained_until:
            self._records.pop(key, None)
            return None
        return record

    async def set(self, key: str, value: CachedResponse, retention_seconds: int) -> None:
        retained_until = datetime.now(UTC).replace(microsecond=0)
        from datetime import timedelta

        self._records[key] = (value, retained_until + timedelta(seconds=retention_seconds))

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        self._records.clear()


class RedisResponseCache:
    """Valkey/Redis implementation.

    Keys are already SHA-256 digests, so user coordinates never appear in Redis
    key listings. Values expire after the configured last-known-good window.
    """

    def __init__(self, client: object) -> None:
        self._client = client

    @classmethod
    def from_url(cls, url: str) -> RedisResponseCache:
        from redis.asyncio import Redis

        return cls(Redis.from_url(url, decode_responses=True))

    async def get(self, key: str) -> CachedResponse | None:
        raw = await self._client.get(f"nws:v1:{key}")  # type: ignore[attr-defined]
        if raw is None:
            return None
        try:
            return CachedResponse.decode(raw)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            await self._client.delete(f"nws:v1:{key}")  # type: ignore[attr-defined]
            return None

    async def set(self, key: str, value: CachedResponse, retention_seconds: int) -> None:
        await self._client.set(  # type: ignore[attr-defined]
            f"nws:v1:{key}",
            value.encode(),
            ex=retention_seconds,
        )

    async def ping(self) -> bool:
        try:
            return bool(await self._client.ping())  # type: ignore[attr-defined]
        except Exception:
            return False

    async def close(self) -> None:
        await self._client.aclose()  # type: ignore[attr-defined]
