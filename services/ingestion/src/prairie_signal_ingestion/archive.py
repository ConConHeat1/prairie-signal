"""Atomic persistence of immutable public-benchmark snapshots."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from prairie_signal_api.models import (
    AlertRevision,
    BenchmarkArchive,
    Location,
    LocationKind,
    ResourceKind,
    SourceFetch,
    SourceName,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prairie_signal_ingestion.config import BenchmarkRegistry, PublicBenchmark
from prairie_signal_ingestion.domain import SourcePayload


class ArchivePolicyError(ValueError):
    """Raised before persistence when a benchmark violates the allow-list."""


class ArchivePayloadError(ValueError):
    """Raised when an upstream document cannot be preserved safely."""


@dataclass(frozen=True, slots=True)
class ArchiveResult:
    benchmark_slug: str
    fetches_archived: int
    alert_revisions_added: int


def canonical_json(payload: dict[str, Any] | list[Any]) -> bytes:
    """Serialize upstream JSON deterministically for provenance hashing."""

    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def content_sha256(payload: dict[str, Any] | list[Any]) -> str:
    return hashlib.sha256(canonical_json(payload)).hexdigest()


class BenchmarkArchiveWriter:
    """Append-only writer gated by the configured public registry."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        registry: BenchmarkRegistry,
        *,
        pipeline_version: str,
    ) -> None:
        self._session_factory = session_factory
        self._registry = registry
        self._pipeline_version = pipeline_version

    async def archive(
        self,
        benchmark: PublicBenchmark,
        payloads: tuple[SourcePayload, ...],
    ) -> ArchiveResult:
        configured = self._registry.require(benchmark.slug)
        if configured != benchmark:
            raise ArchivePolicyError(
                "Benchmark details do not match the configured public allow-list.",
            )
        if not payloads:
            raise ArchivePayloadError("A benchmark run produced no source payloads.")

        alert_revisions_added = 0
        async with self._session_factory() as session:
            async with session.begin():
                location = await self._ensure_location(session, configured)
                for payload in payloads:
                    source_fetch = self._source_fetch(location, payload)
                    session.add(source_fetch)
                    await session.flush()

                    encoded = canonical_json(payload.payload)
                    digest = hashlib.sha256(encoded).hexdigest()
                    session.add(
                        BenchmarkArchive(
                            source_fetch_id=source_fetch.id,
                            benchmark_location_id=location.id,
                            resource_kind=payload.resource_kind,
                            content_type=payload.content_type[:120],
                            payload=payload.payload,
                            content_sha256=digest,
                            byte_size=len(encoded),
                            source_time=payload.source_time,
                            fetched_at=payload.fetched_at,
                            pipeline_version=self._pipeline_version,
                        ),
                    )
                    if payload.resource_kind is ResourceKind.ALERTS:
                        alert_revisions_added += await self._add_alert_revisions(
                            session,
                            location,
                            source_fetch,
                            payload,
                        )

        return ArchiveResult(
            benchmark_slug=benchmark.slug,
            fetches_archived=len(payloads),
            alert_revisions_added=alert_revisions_added,
        )

    async def _ensure_location(
        self,
        session: AsyncSession,
        benchmark: PublicBenchmark,
    ) -> Location:
        result = await session.execute(
            select(Location).where(Location.slug == benchmark.slug),
        )
        location = result.scalar_one_or_none()
        if location is None:
            location = Location(
                slug=benchmark.slug,
                kind=LocationKind.CITY,
                name=benchmark.name,
                normalized_name=benchmark.name.casefold(),
                state_code=benchmark.state_code,
                country_code="US",
                latitude=benchmark.latitude,
                longitude=benchmark.longitude,
                timezone=benchmark.timezone,
                source_name=SourceName.CONFIG,
                source_record_id=f"benchmark:{benchmark.slug}",
                is_public_benchmark=True,
            )
            session.add(location)
            await session.flush()
            return location

        if not location.is_public_benchmark:
            raise ArchivePolicyError(
                f"Location {benchmark.slug!r} exists but is not approved for archiving.",
            )
        if (
            abs(location.latitude - benchmark.latitude) > 0.000_001
            or abs(location.longitude - benchmark.longitude) > 0.000_001
        ):
            raise ArchivePolicyError(
                f"Location {benchmark.slug!r} does not match configured coordinates.",
            )
        return location

    @staticmethod
    def _source_fetch(
        location: Location,
        payload: SourcePayload,
    ) -> SourceFetch:
        digest = content_sha256(payload.payload)
        headers = payload.safe_headers
        return SourceFetch(
            benchmark_location_id=location.id,
            source_name=payload.source_name,
            resource_kind=payload.resource_kind,
            resource_uri=payload.resource_uri,
            status_code=payload.status_code,
            succeeded=200 <= payload.status_code < 300,
            etag=headers.get("etag"),
            last_modified=headers.get("last-modified"),
            cache_control=headers.get("cache-control"),
            content_sha256=digest,
            response_headers=headers,
            error_code=None,
            requested_at=payload.requested_at,
            fetched_at=payload.fetched_at,
            source_time=payload.source_time,
            duration_ms=payload.duration_ms,
        )

    async def _add_alert_revisions(
        self,
        session: AsyncSession,
        location: Location,
        source_fetch: SourceFetch,
        payload: SourcePayload,
    ) -> int:
        if not isinstance(payload.payload, dict):
            raise ArchivePayloadError("NWS alert collection must be a JSON object.")
        features = payload.payload.get("features")
        if not isinstance(features, list):
            raise ArchivePayloadError("NWS alert collection is missing features.")

        added = 0
        seen_revisions: set[tuple[str, str]] = set()
        for feature in features:
            if not isinstance(feature, dict):
                raise ArchivePayloadError("NWS alert features must be JSON objects.")
            properties = feature.get("properties")
            if not isinstance(properties, dict):
                raise ArchivePayloadError("NWS alert feature is missing properties.")
            identifier = feature.get("id") or properties.get("id")
            if not isinstance(identifier, str) or not identifier:
                raise ArchivePayloadError("NWS alert feature is missing its identifier.")
            digest = content_sha256(feature)
            revision_key = (identifier, digest)
            if revision_key in seen_revisions:
                continue
            seen_revisions.add(revision_key)
            existing = await session.scalar(
                select(AlertRevision.id).where(
                    AlertRevision.benchmark_location_id == location.id,
                    AlertRevision.alert_identifier == identifier,
                    AlertRevision.content_sha256 == digest,
                ),
            )
            if existing is not None:
                continue

            geometry = feature.get("geometry")
            session.add(
                AlertRevision(
                    benchmark_location_id=location.id,
                    source_fetch_id=source_fetch.id,
                    alert_identifier=identifier,
                    content_sha256=digest,
                    original_payload=feature,
                    geometry=geometry if isinstance(geometry, dict) else None,
                    issuing_office=_optional_text(
                        properties.get("sender") or properties.get("senderName"),
                    ),
                    status=_optional_text(properties.get("status")),
                    message_type=_optional_text(properties.get("messageType")),
                    category=_optional_text(properties.get("category")),
                    severity=_optional_text(properties.get("severity")),
                    certainty=_optional_text(properties.get("certainty")),
                    urgency=_optional_text(properties.get("urgency")),
                    event=_optional_text(properties.get("event")),
                    headline=_optional_text(properties.get("headline")),
                    description=_optional_text(properties.get("description")),
                    instruction=_optional_text(properties.get("instruction")),
                    area_description=_optional_text(properties.get("areaDesc")),
                    sent_at=_optional_datetime(properties.get("sent")),
                    effective_at=_optional_datetime(properties.get("effective")),
                    onset_at=_optional_datetime(properties.get("onset")),
                    expires_at=_optional_datetime(properties.get("expires")),
                    ends_at=_optional_datetime(properties.get("ends")),
                    observed_at=payload.fetched_at,
                ),
            )
            added += 1
        return added


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
