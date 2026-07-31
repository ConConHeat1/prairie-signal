"""Provider-neutral values exchanged between ingestion adapters and storage."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from prairie_signal_api.models import ResourceKind, SourceName

from prairie_signal_ingestion.config import PublicBenchmark

SAFE_PROVENANCE_HEADERS = frozenset(
    {
        "age",
        "cache-control",
        "content-type",
        "date",
        "etag",
        "expires",
        "last-modified",
    },
)


@dataclass(frozen=True, slots=True)
class SourcePayload:
    """A JSON response and the bounded provenance required to archive it."""

    source_name: SourceName
    resource_kind: ResourceKind
    resource_uri: str
    payload: dict[str, Any] | list[Any]
    requested_at: datetime
    fetched_at: datetime
    duration_ms: int
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    source_time: datetime | None = None
    content_type: str = "application/geo+json"

    def __post_init__(self) -> None:
        if self.duration_ms < 0:
            raise ValueError("duration_ms cannot be negative")
        if not 100 <= self.status_code <= 599:
            raise ValueError("status_code must be a valid HTTP status")
        unsafe_headers = {
            header.lower()
            for header in self.headers
            if header.lower() not in SAFE_PROVENANCE_HEADERS
        }
        if unsafe_headers:
            raise ValueError(
                "Only provenance-safe response headers may be persisted: "
                + ", ".join(sorted(unsafe_headers)),
            )

    @property
    def safe_headers(self) -> dict[str, str]:
        return {
            key.lower(): value
            for key, value in self.headers.items()
            if key.lower() in SAFE_PROVENANCE_HEADERS
        }


class SourceAdapter(Protocol):
    """Replaceable adapter whose input is necessarily a public benchmark."""

    source_name: SourceName

    async def fetch(self, benchmark: PublicBenchmark) -> tuple[SourcePayload, ...]: ...
