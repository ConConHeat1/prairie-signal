from __future__ import annotations

from datetime import UTC, datetime

import pytest
from prairie_signal_api.models import ResourceKind, SourceName

from prairie_signal_ingestion.archive import ArchiveResult
from prairie_signal_ingestion.config import (
    BenchmarkRegistry,
    PublicBenchmark,
    UnknownBenchmarkError,
    parse_benchmark_locations,
)
from prairie_signal_ingestion.domain import SourcePayload
from prairie_signal_ingestion.service import BenchmarkIngestionService


class FakeAdapter:
    source_name = SourceName.NWS

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def fetch(
        self,
        benchmark: PublicBenchmark,
    ) -> tuple[SourcePayload, ...]:
        self.calls.append(benchmark.slug)
        now = datetime.now(UTC)
        return (
            SourcePayload(
                source_name=SourceName.NWS,
                resource_kind=ResourceKind.POINT,
                resource_uri="https://api.weather.gov/points/40.8136,-96.7026",
                payload={"type": "Feature"},
                requested_at=now,
                fetched_at=now,
                duration_ms=1,
            ),
        )


class FakeWriter:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def archive(
        self,
        benchmark: PublicBenchmark,
        payloads: tuple[SourcePayload, ...],
    ) -> ArchiveResult:
        self.calls.append(benchmark.slug)
        return ArchiveResult(benchmark.slug, len(payloads), 0)


@pytest.mark.asyncio
async def test_unknown_slug_is_rejected_before_network_or_storage() -> None:
    registry = BenchmarkRegistry(
        parse_benchmark_locations("lincoln-ne:40.8136:-96.7026"),
    )
    adapter = FakeAdapter()
    writer = FakeWriter()
    service = BenchmarkIngestionService(
        registry,
        adapter,
        writer,  # type: ignore[arg-type]
    )

    with pytest.raises(UnknownBenchmarkError):
        await service.run_one("user-supplied-location")

    assert adapter.calls == []
    assert writer.calls == []
