"""Command-line entry point with no raw location or query arguments."""

from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path

import httpx
import structlog
from prairie_signal_api.config import Settings, get_settings
from prairie_signal_api.db import dispose_database_engine, get_session_factory
from prairie_signal_api.logging import configure_logging

from prairie_signal_ingestion.adapters.mrms import MRMSTransportAdapter
from prairie_signal_ingestion.adapters.nws import NWSBenchmarkAdapter
from prairie_signal_ingestion.archive import BenchmarkArchiveWriter
from prairie_signal_ingestion.census import (
    DEFAULT_PLACES_SHA256,
    DEFAULT_PLACES_SOURCE,
    DEFAULT_ZCTA_SHA256,
    DEFAULT_ZCTA_SOURCE,
    CensusGazetteerIngestor,
    CensusSource,
)
from prairie_signal_ingestion.config import BenchmarkRegistry
from prairie_signal_ingestion.mrms_processing import process_mrms_reflectivity
from prairie_signal_ingestion.radar_config import load_mrms_config, load_region_config
from prairie_signal_ingestion.radar_metadata import RadarArtifactWriter
from prairie_signal_ingestion.scheduler import BenchmarkScheduler
from prairie_signal_ingestion.service import BenchmarkIngestionService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="prairie-signal-ingest",
        description=(
            "Build the Census index, archive configured NWS benchmarks, or process one "
            "current MRMS reflectivity frame."
        ),
    )
    parser.add_argument(
        "--benchmark",
        metavar="SLUG",
        help="Run one slug from BENCHMARK_LOCATIONS; defaults to all.",
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        help="Continue on an interval of at least 60 seconds.",
    )
    parser.add_argument(
        "--load-census",
        action="store_true",
        help="Build the regional Places/ZCTA index from Census Gazetteers.",
    )
    parser.add_argument(
        "--places-source",
        default=DEFAULT_PLACES_SOURCE,
        help="Official census.gov HTTPS URL or local Places zip/text file.",
    )
    parser.add_argument(
        "--zcta-source",
        default=DEFAULT_ZCTA_SOURCE,
        help="Official census.gov HTTPS URL or local ZCTA zip/text file.",
    )
    parser.add_argument(
        "--places-sha256",
        help="Optional expected SHA-256 for the complete Places source file.",
    )
    parser.add_argument(
        "--zcta-sha256",
        help="Optional expected SHA-256 for the complete ZCTA source file.",
    )
    parser.add_argument(
        "--census-output-directory",
        type=Path,
        help="Derived TSV directory; defaults under ARCHIVE_DIRECTORY.",
    )
    parser.add_argument(
        "--also-benchmarks",
        action="store_true",
        help="After Census loading, also run configured NWS benchmarks.",
    )
    parser.add_argument(
        "--mrms-latest",
        action="store_true",
        help=(
            "Discover, download, normalize, and record one current verified MRMS "
            "composite-reflectivity object."
        ),
    )
    return parser


async def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = get_settings()

    if args.mrms_latest:
        if any(
            (
                args.benchmark is not None,
                args.interval_seconds is not None,
                args.load_census,
                args.also_benchmarks,
            )
        ):
            raise ValueError("--mrms-latest cannot be combined with Census or NWS modes.")
        return await _run_mrms_latest(settings)

    registry = BenchmarkRegistry.from_settings(settings)

    # Validate a requested slug before creating a network client or DB session.
    if args.benchmark is not None:
        registry.require(args.benchmark)

    if args.load_census:
        output_directory = (
            args.census_output_directory
            if args.census_output_directory is not None
            else settings.archive_directory / "location-index"
        )
        census_ingestor = CensusGazetteerIngestor(
            get_session_factory(),
            raw_archive_directory=settings.archive_directory,
            output_directory=output_directory,
            center_latitude=settings.region_center_latitude,
            center_longitude=settings.region_center_longitude,
            radius_km=settings.region_radius_km,
        )
        try:
            places_sha256 = args.places_sha256
            if places_sha256 is None and args.places_source == DEFAULT_PLACES_SOURCE:
                places_sha256 = DEFAULT_PLACES_SHA256
            zcta_sha256 = args.zcta_sha256
            if zcta_sha256 is None and args.zcta_source == DEFAULT_ZCTA_SOURCE:
                zcta_sha256 = DEFAULT_ZCTA_SHA256
            census_result = await census_ingestor.ingest(
                CensusSource(args.places_source, places_sha256),
                CensusSource(args.zcta_source, zcta_sha256),
            )
        finally:
            await census_ingestor.close()
        structlog.get_logger("prairie_signal.ingestion").info(
            "census_location_index_completed",
            places_count=census_result.places_count,
            zcta_count=census_result.zcta_count,
            places_sha256=census_result.places_sha256,
            zcta_sha256=census_result.zcta_sha256,
            created=census_result.upsert.created,
            updated=census_result.upsert.updated,
            unchanged=census_result.upsert.unchanged,
        )
        if not args.also_benchmarks:
            await dispose_database_engine()
            return 0

    adapter = NWSBenchmarkAdapter.from_settings(settings)
    writer = BenchmarkArchiveWriter(
        get_session_factory(),
        registry,
        pipeline_version=settings.pipeline_version,
    )
    service = BenchmarkIngestionService(registry, adapter, writer)

    try:
        if args.interval_seconds is not None:
            if args.benchmark is not None:
                raise ValueError(
                    "Scheduled mode always runs the complete configured allow-list.",
                )
            scheduler = BenchmarkScheduler(
                service,
                interval_seconds=args.interval_seconds,
            )
            await scheduler.run_forever()
            return 0

        if args.benchmark is not None:
            archive_result = await service.run_one(args.benchmark)
            structlog.get_logger("prairie_signal.ingestion").info(
                "benchmark_ingestion_completed",
                benchmark_slug=archive_result.benchmark_slug,
                fetches_archived=archive_result.fetches_archived,
                alert_revisions_added=archive_result.alert_revisions_added,
            )
            return 0

        outcomes = await service.run_all()
        logger = structlog.get_logger("prairie_signal.ingestion")
        for outcome in outcomes:
            if outcome.result is None:
                logger.error(
                    "benchmark_ingestion_failed",
                    benchmark_slug=outcome.benchmark_slug,
                    error_type=outcome.error_type,
                )
            else:
                logger.info(
                    "benchmark_ingestion_completed",
                    benchmark_slug=outcome.benchmark_slug,
                    fetches_archived=outcome.result.fetches_archived,
                    alert_revisions_added=outcome.result.alert_revisions_added,
                )
        return 0 if all(outcome.succeeded for outcome in outcomes) else 1
    finally:
        await adapter.close()
        await dispose_database_engine()


async def _run_mrms_latest(settings: Settings) -> int:
    """Run the controlled Milestone 2 Slice 1 path exactly once."""

    region = load_region_config(settings.region_config_path)
    config = load_mrms_config(settings.mrms_source_config_path)
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(config.download.timeout_seconds),
        follow_redirects=False,
    ) as client:
        adapter = MRMSTransportAdapter(
            client=client,
            max_attempts=config.download.max_retries + 1,
            future_skew=timedelta(seconds=config.download.max_future_skew_seconds),
            max_compressed_bytes=config.download.max_compressed_bytes,
            max_decompressed_bytes=config.download.max_decompressed_bytes,
        )
        try:
            discovered = await adapter.discover_latest()
            if discovered.discovered_at is None:
                raise RuntimeError("MRMS discovery did not record a discovery timestamp.")
            age = discovered.discovered_at - discovered.valid_time
            if age > timedelta(minutes=config.download.stale_after_minutes):
                raise RuntimeError(
                    "Latest MRMS reflectivity object is stale; refusing to publish it as current."
                )
            with tempfile.TemporaryDirectory(prefix="prairie-signal-mrms-") as temporary:
                temporary_path = Path(temporary)
                downloaded = await adapter.download(
                    discovered,
                    data_root=settings.data_directory,
                    temporary_directory=temporary_path,
                )
                normalized = process_mrms_reflectivity(
                    downloaded,
                    data_root=settings.data_directory,
                    temporary_directory=temporary_path,
                    region=region,
                    config=config,
                )
            record = await RadarArtifactWriter(get_session_factory()).record(normalized)
            output = {
                "radar_artifact_id": str(record.id),
                "source_bucket": config.access.bucket,
                "source_object_key": discovered.key,
                "source_etag": discovered.etag,
                "source_last_modified": (
                    discovered.last_modified.isoformat().replace("+00:00", "Z")
                    if discovered.last_modified is not None
                    else None
                ),
                "valid_time": discovered.valid_time.isoformat().replace("+00:00", "Z"),
                "discovered_at": discovered.discovered_at.isoformat().replace("+00:00", "Z"),
                "downloaded_at": downloaded.downloaded_at.isoformat().replace("+00:00", "Z"),
                "data_age_seconds": max(
                    0,
                    (downloaded.downloaded_at - discovered.valid_time).total_seconds(),
                ),
                "compressed_size_bytes": downloaded.compressed_size,
                "compressed_sha256": downloaded.compressed_sha256,
                "grib_sha256": downloaded.decompressed_sha256,
                "raw_path": str(downloaded.path),
                "normalized_zarr_path": str(normalized.zarr_path),
                "diagnostic_preview_path": str(normalized.preview_path),
                "source_statistics": normalized.metadata["source_statistics"],
                "normalized_statistics": normalized.metadata["normalized_statistics"],
                "processing_version": config.processing.version,
                "reused": normalized.reused,
            }
            print(json.dumps(output, indent=2, sort_keys=True))
            return 0
        finally:
            await adapter.close()
            await dispose_database_engine()


def main() -> None:
    configure_logging(get_settings().log_level)
    raise SystemExit(asyncio.run(run()))
