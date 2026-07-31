"""Application service for allow-listed benchmark ingestion."""

from __future__ import annotations

from dataclasses import dataclass

from prairie_signal_ingestion.archive import ArchiveResult, BenchmarkArchiveWriter
from prairie_signal_ingestion.config import BenchmarkRegistry
from prairie_signal_ingestion.domain import SourceAdapter


@dataclass(frozen=True, slots=True)
class BenchmarkRunOutcome:
    benchmark_slug: str
    result: ArchiveResult | None
    error_type: str | None

    @property
    def succeeded(self) -> bool:
        return self.result is not None


class BenchmarkIngestionService:
    """Coordinates source retrieval and atomic append-only persistence."""

    def __init__(
        self,
        registry: BenchmarkRegistry,
        adapter: SourceAdapter,
        writer: BenchmarkArchiveWriter,
    ) -> None:
        self._registry = registry
        self._adapter = adapter
        self._writer = writer

    async def run_one(self, benchmark_slug: str) -> ArchiveResult:
        # Resolve the allow-list before the adapter is invoked.  There is no
        # ingestion entry point that accepts a user query or raw coordinates.
        benchmark = self._registry.require(benchmark_slug)
        payloads = await self._adapter.fetch(benchmark)
        return await self._writer.archive(benchmark, payloads)

    async def run_all(self) -> tuple[BenchmarkRunOutcome, ...]:
        outcomes: list[BenchmarkRunOutcome] = []
        for benchmark in self._registry.all():
            try:
                result = await self.run_one(benchmark.slug)
            except Exception as exc:
                outcomes.append(
                    BenchmarkRunOutcome(
                        benchmark_slug=benchmark.slug,
                        result=None,
                        error_type=type(exc).__name__,
                    ),
                )
            else:
                outcomes.append(
                    BenchmarkRunOutcome(
                        benchmark_slug=benchmark.slug,
                        result=result,
                        error_type=None,
                    ),
                )
        return tuple(outcomes)
