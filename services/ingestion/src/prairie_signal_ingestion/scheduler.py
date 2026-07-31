"""Small dependency-free interval scheduler for benchmark collection."""

from __future__ import annotations

import asyncio
import time

import structlog

from prairie_signal_ingestion.service import BenchmarkIngestionService


class BenchmarkScheduler:
    """Run every configured public benchmark at a bounded interval."""

    def __init__(
        self,
        service: BenchmarkIngestionService,
        *,
        interval_seconds: float,
    ) -> None:
        if interval_seconds < 60:
            raise ValueError("Benchmark ingestion interval must be at least 60 seconds.")
        self._service = service
        self._interval_seconds = interval_seconds
        self._stop_event = asyncio.Event()
        self._logger = structlog.get_logger("prairie_signal.ingestion")

    def stop(self) -> None:
        self._stop_event.set()

    async def run_forever(self) -> None:
        while not self._stop_event.is_set():
            started = time.monotonic()
            outcomes = await self._service.run_all()
            for outcome in outcomes:
                if outcome.result is None:
                    self._logger.error(
                        "benchmark_ingestion_failed",
                        benchmark_slug=outcome.benchmark_slug,
                        error_type=outcome.error_type,
                    )
                else:
                    self._logger.info(
                        "benchmark_ingestion_completed",
                        benchmark_slug=outcome.benchmark_slug,
                        fetches_archived=outcome.result.fetches_archived,
                        alert_revisions_added=outcome.result.alert_revisions_added,
                    )

            elapsed = time.monotonic() - started
            delay = max(0.0, self._interval_seconds - elapsed)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
            except TimeoutError:
                pass
