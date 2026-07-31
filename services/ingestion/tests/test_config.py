from __future__ import annotations

import pytest

from prairie_signal_ingestion.cli import build_parser
from prairie_signal_ingestion.config import (
    BenchmarkConfigurationError,
    BenchmarkRegistry,
    UnknownBenchmarkError,
    parse_benchmark_locations,
)


def test_default_benchmark_format_builds_public_lincoln_record() -> None:
    (lincoln,) = parse_benchmark_locations("lincoln-ne:40.8136:-96.7026")

    assert lincoln.slug == "lincoln-ne"
    assert lincoln.name == "Lincoln"
    assert lincoln.state_code == "NE"
    assert lincoln.timezone == "America/Chicago"


def test_registry_rejects_unconfigured_slug() -> None:
    registry = BenchmarkRegistry(
        parse_benchmark_locations("lincoln-ne:40.8136:-96.7026"),
    )

    with pytest.raises(UnknownBenchmarkError, match="not a configured public benchmark"):
        registry.require("private-runtime-point")


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "Lincoln, NE",
        "lincoln-ne:not-a-latitude:-96.7026",
        "Lincoln NE:40.8136:-96.7026",
        "lincoln-ne:91:-96.7026",
        "lincoln-ne:40.8136:-181",
    ],
)
def test_parser_rejects_queries_and_invalid_coordinates(raw: str) -> None:
    with pytest.raises(BenchmarkConfigurationError):
        parse_benchmark_locations(raw)


def test_cli_exposes_explicit_one_shot_mrms_mode() -> None:
    args = build_parser().parse_args(["--mrms-latest"])

    assert args.mrms_latest is True
    assert args.interval_seconds is None
