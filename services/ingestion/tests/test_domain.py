from __future__ import annotations

from datetime import UTC, datetime

import pytest
from prairie_signal_api.models import ResourceKind, SourceName

from prairie_signal_ingestion.archive import canonical_json, content_sha256
from prairie_signal_ingestion.domain import SourcePayload


def _payload(headers: dict[str, str]) -> SourcePayload:
    now = datetime.now(UTC)
    return SourcePayload(
        source_name=SourceName.NWS,
        resource_kind=ResourceKind.POINT,
        resource_uri="https://api.weather.gov/points/40.8136,-96.7026",
        payload={"b": 2, "a": 1},
        requested_at=now,
        fetched_at=now,
        duration_ms=1,
        headers=headers,
    )


def test_payload_allows_only_provenance_safe_headers() -> None:
    with pytest.raises(ValueError, match="provenance-safe"):
        _payload({"Authorization": "secret"})

    safe = _payload({"ETag": '"abc"', "Cache-Control": "max-age=60"})
    assert safe.safe_headers == {
        "etag": '"abc"',
        "cache-control": "max-age=60",
    }


def test_canonical_hash_is_stable_across_key_order() -> None:
    first = {"properties": {"b": 2, "a": 1}}
    second = {"properties": {"a": 1, "b": 2}}

    assert canonical_json(first) == canonical_json(second)
    assert content_sha256(first) == content_sha256(second)
