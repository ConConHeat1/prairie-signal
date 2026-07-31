"""Configuration boundary that prevents ingestion of interactive locations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class BenchmarkConfigurationError(ValueError):
    """Raised when the public benchmark allow-list is invalid."""


class UnknownBenchmarkError(LookupError):
    """Raised before any fetch when a slug is not explicitly configured."""


class BenchmarkSettings(Protocol):
    benchmark_locations: str


@dataclass(frozen=True, slots=True)
class PublicBenchmark:
    """A non-user location approved for repeatable, long-term collection."""

    slug: str
    latitude: float
    longitude: float
    name: str
    state_code: str
    timezone: str = "America/Chicago"

    def __post_init__(self) -> None:
        if not _SLUG_PATTERN.fullmatch(self.slug):
            raise BenchmarkConfigurationError(
                "Benchmark slugs must contain lowercase letters, digits, and hyphens only.",
            )
        if not -90 <= self.latitude <= 90:
            raise BenchmarkConfigurationError("Benchmark latitude is outside [-90, 90].")
        if not -180 <= self.longitude <= 180:
            raise BenchmarkConfigurationError("Benchmark longitude is outside [-180, 180].")
        if len(self.state_code) != 2 or not self.state_code.isalpha():
            raise BenchmarkConfigurationError("Benchmark state_code must be two letters.")


def _display_name(slug: str) -> str:
    tokens = slug.split("-")
    if tokens and len(tokens[-1]) == 2:
        tokens = tokens[:-1]
    return " ".join(token.capitalize() for token in tokens)


def _state_code(slug: str) -> str:
    suffix = slug.rsplit("-", maxsplit=1)[-1]
    if len(suffix) == 2 and suffix.isalpha():
        return suffix.upper()
    # The Phase 1 region is Nebraska-centered; explicit richer configuration
    # can still supply another state via the extended format below.
    return "NE"


def parse_benchmark_locations(raw: str) -> tuple[PublicBenchmark, ...]:
    """Parse the allow-list from Settings.benchmark_locations.

    Supported semicolon-separated forms:

    ``slug:latitude:longitude``
    ``slug:latitude:longitude:state:timezone``

    There is intentionally no parser for a query string, IP-derived location,
    or arbitrary runtime coordinates.
    """

    benchmarks: list[PublicBenchmark] = []
    seen: set[str] = set()
    for raw_entry in raw.split(";"):
        entry = raw_entry.strip()
        if not entry:
            continue
        parts = entry.split(":")
        if len(parts) not in {3, 5}:
            raise BenchmarkConfigurationError(
                "Each benchmark must be slug:latitude:longitude or "
                "slug:latitude:longitude:state:timezone.",
            )
        slug, latitude_text, longitude_text = parts[:3]
        if slug in seen:
            raise BenchmarkConfigurationError(f"Duplicate benchmark slug: {slug}")
        try:
            latitude = float(latitude_text)
            longitude = float(longitude_text)
        except ValueError as exc:
            raise BenchmarkConfigurationError(
                f"Benchmark {slug!r} has non-numeric coordinates.",
            ) from exc

        if len(parts) == 5:
            state_code = parts[3].upper()
            timezone = parts[4]
        else:
            state_code = _state_code(slug)
            timezone = "America/Chicago"

        benchmarks.append(
            PublicBenchmark(
                slug=slug,
                latitude=latitude,
                longitude=longitude,
                name=_display_name(slug),
                state_code=state_code,
                timezone=timezone,
            ),
        )
        seen.add(slug)

    if not benchmarks:
        raise BenchmarkConfigurationError(
            "At least one public benchmark location must be configured.",
        )
    return tuple(benchmarks)


class BenchmarkRegistry:
    """Read-only allow-list used by every scheduler and command entry point."""

    def __init__(self, benchmarks: tuple[PublicBenchmark, ...]) -> None:
        if not benchmarks:
            raise BenchmarkConfigurationError("The benchmark registry cannot be empty.")
        self._by_slug = {benchmark.slug: benchmark for benchmark in benchmarks}
        if len(self._by_slug) != len(benchmarks):
            raise BenchmarkConfigurationError("Benchmark slugs must be unique.")

    @classmethod
    def from_settings(cls, settings: BenchmarkSettings) -> BenchmarkRegistry:
        raw = settings.benchmark_locations
        if not isinstance(raw, str):
            raise BenchmarkConfigurationError(
                "Settings.benchmark_locations must be an allow-list string.",
            )
        return cls(parse_benchmark_locations(raw))

    def require(self, slug: str) -> PublicBenchmark:
        """Resolve a configured public slug; never accept raw coordinates."""

        try:
            return self._by_slug[slug]
        except KeyError as exc:
            raise UnknownBenchmarkError(
                f"{slug!r} is not a configured public benchmark.",
            ) from exc

    def all(self) -> tuple[PublicBenchmark, ...]:
        return tuple(self._by_slug.values())

    def slugs(self) -> tuple[str, ...]:
        return tuple(self._by_slug)
