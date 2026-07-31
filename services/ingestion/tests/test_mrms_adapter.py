from __future__ import annotations

import gzip
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from prairie_signal_ingestion.adapters.mrms import (
    MRMSConfigurationError,
    MRMSConflictError,
    MRMSContentLengthError,
    MRMSDiscoveryError,
    MRMSDownloadError,
    MRMSIntegrityError,
    MRMSInvalidObjectKeyError,
    MRMSObject,
    MRMSTransportAdapter,
    parse_mrms_object_key,
)

FIXED_NOW = datetime(2026, 7, 31, 18, 0, tzinfo=UTC)
PRODUCT = "MergedReflectivityQCComposite_00.50"


def _key(timestamp: str) -> str:
    day = timestamp[:8]
    return f"CONUS/{PRODUCT}/{day}/MRMS_{PRODUCT}_{timestamp}.grib2.gz"


def _listing(*keys: str) -> bytes:
    contents = "".join(
        f"<Contents><Key>{key}</Key><Size>123</Size>"
        "<ETag>&quot;fixture&quot;</ETag>"
        "<LastModified>2026-07-31T17:59:00Z</LastModified></Contents>"
        for key in keys
    )
    return (
        '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
        f"{contents}<IsTruncated>false</IsTruncated></ListBucketResult>"
    ).encode()


def _grib_gzip(payload: bytes = b"reflectivity") -> bytes:
    return gzip.compress(b"GRIB" + payload + b"7777", mtime=0)


def _object(timestamp: str, size: int | None = None) -> MRMSObject:
    return parse_mrms_object_key(
        _key(timestamp),
        size=size,
        discovered_at=FIXED_NOW,
    )


async def _no_sleep(_delay: float) -> None:
    return None


def test_filename_timestamp_is_strictly_parsed_as_utc() -> None:
    parsed = _object("20260731-174500")

    assert parsed.valid_time == datetime(2026, 7, 31, 17, 45, tzinfo=UTC)
    assert parsed.filename == f"MRMS_{PRODUCT}_20260731-174500.grib2.gz"
    assert parsed.discovered_at == FIXED_NOW

    with pytest.raises(MRMSInvalidObjectKeyError):
        parse_mrms_object_key(
            f"CONUS/{PRODUCT}/20260730/MRMS_{PRODUCT}_20260731-174500.grib2.gz",
        )
    with pytest.raises(MRMSInvalidObjectKeyError):
        parse_mrms_object_key(_key("20260731-176100"))
    with pytest.raises(MRMSInvalidObjectKeyError):
        parse_mrms_object_key(_key("20260731-174500").replace(PRODUCT, "OtherProduct"))
    with pytest.raises(MRMSConfigurationError, match="discovered_at"):
        parse_mrms_object_key(
            _key("20260731-174500"),
            discovered_at=datetime(2026, 7, 31, 18, 0),
        )


@pytest.mark.asyncio
async def test_discovery_sorts_by_valid_time_not_listing_order() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_listing(
                _key("20260731-175500"),
                _key("20260731-171000"),
                _key("20260731-174500"),
            ),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = MRMSTransportAdapter(client=client, clock=lambda: FIXED_NOW)
        latest = await adapter.discover_latest()

    assert latest.valid_time == datetime(2026, 7, 31, 17, 55, tzinfo=UTC)
    assert latest.discovered_at == FIXED_NOW
    assert latest.etag == "fixture"
    assert latest.last_modified == datetime(2026, 7, 31, 17, 59, tzinfo=UTC)


@pytest.mark.asyncio
async def test_discovery_falls_back_from_today_to_previous_utc_day() -> None:
    prefixes: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        prefix = request.url.params["prefix"]
        prefixes.append(prefix)
        if prefix.endswith("20260731/"):
            return httpx.Response(200, content=_listing())
        return httpx.Response(200, content=_listing(_key("20260730-235900")))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = MRMSTransportAdapter(client=client, clock=lambda: FIXED_NOW)
        latest = await adapter.discover_latest()

    assert latest.valid_time == datetime(2026, 7, 30, 23, 59, tzinfo=UTC)
    assert prefixes == [
        f"CONUS/{PRODUCT}/20260731/",
        f"CONUS/{PRODUCT}/20260730/",
    ]


@pytest.mark.asyncio
async def test_discovery_outage_has_bounded_retries_and_explicit_failure() -> None:
    calls = 0
    delays: list[float] = []

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = MRMSTransportAdapter(
            client=client,
            max_attempts=3,
            backoff_seconds=0.125,
            clock=lambda: FIXED_NOW,
            sleep=record_sleep,
        )
        with pytest.raises(
            MRMSDiscoveryError,
            match=r"MRMS listing failed after 3 attempt\(s\)",
        ):
            await adapter.discover_latest()

    assert calls == 3
    assert delays == [0.125, 0.25]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content",
    [
        b"not-a-gzip-stream",
        _grib_gzip()[:-4],
        gzip.compress(b"GRIBmissing-end-marker", mtime=0),
    ],
)
async def test_corruption_and_truncation_are_rejected_and_cleaned(
    tmp_path: Path,
    content: bytes,
) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content)

    temporary = tmp_path / "temporary"
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = MRMSTransportAdapter(
            client=client,
            max_attempts=1,
            clock=lambda: FIXED_NOW,
        )
        with pytest.raises(MRMSIntegrityError):
            await adapter.download(
                _object("20260731-175500"),
                data_root=tmp_path / "data",
                temporary_directory=temporary,
            )

    assert list(temporary.iterdir()) == []
    assert not (tmp_path / "data" / "raw").exists()


class _InterruptedStream(httpx.AsyncByteStream):
    def __init__(self, request: httpx.Request) -> None:
        self._request = request

    async def __aiter__(self):
        yield b"partial"
        raise httpx.ReadError("interrupted", request=self._request)


@pytest.mark.asyncio
async def test_partial_transport_failure_removes_unique_part_file(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=_InterruptedStream(request))

    temporary = tmp_path / "temporary"
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = MRMSTransportAdapter(
            client=client,
            max_attempts=1,
            sleep=_no_sleep,
            clock=lambda: FIXED_NOW,
        )
        with pytest.raises(MRMSDownloadError):
            await adapter.download(
                _object("20260731-175500"),
                data_root=tmp_path / "data",
                temporary_directory=temporary,
            )

    assert list(temporary.iterdir()) == []


@pytest.mark.asyncio
async def test_content_length_mismatch_is_rejected(tmp_path: Path) -> None:
    content = _grib_gzip()

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=content,
            headers={"Content-Length": str(len(content) + 7)},
        )

    temporary = tmp_path / "temporary"
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = MRMSTransportAdapter(
            client=client,
            max_attempts=1,
            clock=lambda: FIXED_NOW,
        )
        with pytest.raises(MRMSContentLengthError):
            await adapter.download(
                _object("20260731-175500"),
                data_root=tmp_path / "data",
                temporary_directory=temporary,
            )

    assert list(temporary.iterdir()) == []


@pytest.mark.asyncio
async def test_duplicate_checksum_is_idempotent_and_conflict_is_preserved(tmp_path: Path) -> None:
    content = _grib_gzip()
    calls = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=content)

    source = _object("20260731-175500", size=len(content))
    temporary = tmp_path / "temporary"
    data_root = tmp_path / "data"
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = MRMSTransportAdapter(client=client, clock=lambda: FIXED_NOW)
        first = await adapter.download(
            source,
            data_root=data_root,
            temporary_directory=temporary,
        )
        second = await adapter.download(
            source,
            data_root=data_root,
            temporary_directory=temporary,
        )

        assert first.path == second.path
        assert first.compressed_sha256 == second.compressed_sha256
        assert first.path.read_bytes() == content
        assert first.source.discovered_at == FIXED_NOW

        first.path.write_bytes(b"conflicting-existing-bytes")
        with pytest.raises(MRMSConflictError):
            await adapter.download(
                source,
                data_root=data_root,
                temporary_directory=temporary,
            )

    assert calls == 3
    assert first.path.read_bytes() == b"conflicting-existing-bytes"
    assert list(temporary.iterdir()) == []
