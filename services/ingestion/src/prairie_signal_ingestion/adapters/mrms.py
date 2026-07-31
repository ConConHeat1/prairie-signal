"""Dependency-light transport for one verified MRMS reflectivity product.

This module deliberately stops at immutable GRIB2 acquisition.  Raster decoding,
normalization, database metadata, and tile generation belong to later pipeline
boundaries.
"""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import os
import re
import shutil
import tempfile
import zlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Final
from urllib.parse import quote
from xml.etree import ElementTree

import httpx

MRMS_PRODUCT: Final = "MergedReflectivityQCComposite_00.50"
MRMS_S3_BUCKET: Final = "noaa-mrms-pds"
MRMS_S3_BASE_URL: Final = "https://noaa-mrms-pds.s3.amazonaws.com"
MRMS_KEY_PREFIX: Final = f"CONUS/{MRMS_PRODUCT}"

_KEY_PATTERN = re.compile(
    rf"^{re.escape(MRMS_KEY_PREFIX)}/(?P<directory_day>[0-9]{{8}})/"
    rf"(?P<filename>MRMS_{re.escape(MRMS_PRODUCT)}_"
    rf"(?P<valid_time>[0-9]{{8}}-[0-9]{{6}})\.grib2\.gz)$",
)
_RETRYABLE_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})


class MRMSError(RuntimeError):
    """Base class for safe MRMS transport failures."""


class MRMSConfigurationError(MRMSError):
    """Raised when transport safety bounds are invalid."""


class MRMSDiscoveryError(MRMSError):
    """Raised when the anonymous S3 listing cannot be read safely."""


class MRMSNoObjectsError(MRMSDiscoveryError):
    """Raised when today and the prior UTC day contain no supported object."""


class MRMSFutureObjectError(MRMSDiscoveryError):
    """Raised when only implausibly future-dated supported objects are found."""


class MRMSInvalidObjectKeyError(MRMSDiscoveryError):
    """Raised when an object key does not exactly match the supported layout."""


class MRMSDownloadError(MRMSError):
    """Raised when an MRMS object cannot be downloaded completely."""


class MRMSContentLengthError(MRMSDownloadError):
    """Raised when the received byte count contradicts source metadata."""


class MRMSIntegrityError(MRMSDownloadError):
    """Raised when gzip or the enclosed GRIB2 message is invalid."""


class MRMSConflictError(MRMSDownloadError):
    """Raised rather than overwriting different bytes at an immutable path."""


class _RetryableDiscoveryError(MRMSDiscoveryError):
    pass


class _RetryableDownloadError(MRMSDownloadError):
    pass


@dataclass(frozen=True, slots=True)
class MRMSObject:
    """One strictly parsed object advertised by the anonymous MRMS bucket."""

    key: str
    filename: str
    valid_time: datetime
    discovered_at: datetime | None = None
    size: int | None = None
    etag: str | None = None
    last_modified: datetime | None = None


@dataclass(frozen=True, slots=True)
class MRMSDownloadedArtifact:
    """Checksummed immutable result of downloading one compressed GRIB2 file."""

    source: MRMSObject
    path: Path
    compressed_sha256: str
    decompressed_sha256: str
    compressed_size: int
    decompressed_size: int
    downloaded_at: datetime


@dataclass(frozen=True, slots=True)
class _ValidatedFile:
    compressed_sha256: str
    decompressed_sha256: str
    compressed_size: int
    decompressed_size: int


Sleep = Callable[[float], Awaitable[None]]
Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def parse_mrms_object_key(
    key: str,
    *,
    size: int | None = None,
    etag: str | None = None,
    last_modified: datetime | None = None,
    discovered_at: datetime | None = None,
) -> MRMSObject:
    """Parse only the configured product and exact operational key shape."""

    match = _KEY_PATTERN.fullmatch(key)
    if match is None:
        raise MRMSInvalidObjectKeyError("MRMS object key does not match the supported product.")
    try:
        valid_time = datetime.strptime(
            match.group("valid_time"),
            "%Y%m%d-%H%M%S",
        ).replace(tzinfo=UTC)
    except ValueError as exc:
        raise MRMSInvalidObjectKeyError("MRMS object key has an invalid UTC timestamp.") from exc
    if match.group("directory_day") != valid_time.strftime("%Y%m%d"):
        raise MRMSInvalidObjectKeyError(
            "MRMS object directory and meteorological valid date disagree.",
        )
    if size is not None and size < 0:
        raise MRMSInvalidObjectKeyError("MRMS object size cannot be negative.")
    if last_modified is not None:
        last_modified = _require_utc(last_modified, "last_modified")
    if discovered_at is not None:
        discovered_at = _require_utc(discovered_at, "discovered_at")
    return MRMSObject(
        key=key,
        filename=match.group("filename"),
        valid_time=valid_time,
        discovered_at=discovered_at,
        size=size,
        etag=etag,
        last_modified=last_modified,
    )


class MRMSTransportAdapter:
    """Discover and immutably acquire MRMS composite reflectivity objects."""

    product = MRMS_PRODUCT
    base_url = MRMS_S3_BASE_URL

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        max_attempts: int = 3,
        backoff_seconds: float = 0.25,
        future_skew: timedelta = timedelta(minutes=10),
        max_compressed_bytes: int = 256 * 1024 * 1024,
        max_decompressed_bytes: int = 1024 * 1024 * 1024,
        max_listing_bytes: int = 8 * 1024 * 1024,
        clock: Clock = _utc_now,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if max_attempts < 1:
            raise MRMSConfigurationError("max_attempts must be at least one.")
        if backoff_seconds < 0:
            raise MRMSConfigurationError("backoff_seconds cannot be negative.")
        if future_skew < timedelta(0):
            raise MRMSConfigurationError("future_skew cannot be negative.")
        if min(max_compressed_bytes, max_decompressed_bytes, max_listing_bytes) < 1:
            raise MRMSConfigurationError("Transport byte limits must be positive.")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            follow_redirects=False,
        )
        self._max_attempts = max_attempts
        self._backoff_seconds = backoff_seconds
        self._future_skew = future_skew
        self._max_compressed_bytes = max_compressed_bytes
        self._max_decompressed_bytes = max_decompressed_bytes
        self._max_listing_bytes = max_listing_bytes
        self._clock = clock
        self._sleep = sleep

    async def __aenter__(self) -> MRMSTransportAdapter:
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def discover_latest(self) -> MRMSObject:
        """Find the newest valid object, falling back across the UTC day boundary."""

        now = _require_utc(self._clock(), "clock")
        future_objects: list[MRMSObject] = []
        for candidate_day in (now.date(), now.date() - timedelta(days=1)):
            candidates = await self._list_day(candidate_day)
            usable: list[MRMSObject] = []
            for candidate in candidates:
                if candidate.valid_time > now + self._future_skew:
                    future_objects.append(candidate)
                else:
                    usable.append(candidate)
            if usable:
                selected = max(usable, key=lambda item: item.valid_time)
                return replace(
                    selected,
                    discovered_at=_require_utc(self._clock(), "clock"),
                )

        if future_objects:
            newest = max(future_objects, key=lambda item: item.valid_time)
            raise MRMSFutureObjectError(
                f"MRMS object {newest.filename!r} is beyond the allowed future skew.",
            )
        raise MRMSNoObjectsError(
            "No supported MRMS reflectivity object was found for today or the prior UTC day.",
        )

    async def download(
        self,
        source: MRMSObject,
        *,
        data_root: Path,
        temporary_directory: Path,
    ) -> MRMSDownloadedArtifact:
        """Download, validate, and atomically place an immutable raw object."""

        parsed = parse_mrms_object_key(
            source.key,
            size=source.size,
            etag=source.etag,
            last_modified=source.last_modified,
            discovered_at=source.discovered_at,
        )
        if parsed != source:
            raise MRMSInvalidObjectKeyError("MRMS object metadata is not canonical.")

        last_error: MRMSError | httpx.TransportError | None = None
        for attempt in range(self._max_attempts):
            try:
                return await self._download_once(
                    source,
                    data_root=data_root,
                    temporary_directory=temporary_directory,
                )
            except MRMSConflictError:
                raise
            except (
                httpx.TransportError,
                MRMSContentLengthError,
                MRMSIntegrityError,
                _RetryableDownloadError,
            ) as exc:
                last_error = exc
                if attempt + 1 == self._max_attempts:
                    break
                await self._sleep(self._backoff_seconds * (2**attempt))
        if isinstance(last_error, MRMSError):
            raise last_error
        raise MRMSDownloadError(
            f"MRMS download failed after {self._max_attempts} attempt(s).",
        ) from last_error

    async def _list_day(self, candidate_day: date) -> tuple[MRMSObject, ...]:
        prefix = f"{MRMS_KEY_PREFIX}/{candidate_day:%Y%m%d}/"
        continuation_token: str | None = None
        seen_tokens: set[str] = set()
        objects: dict[str, MRMSObject] = {}
        while True:
            params = {"list-type": "2", "prefix": prefix}
            if continuation_token is not None:
                params["continuation-token"] = continuation_token
            response = await self._get_listing_page(params)
            page_objects, is_truncated, next_token = self._parse_listing(response.content)
            for item in page_objects:
                objects[item.key] = item
            if not is_truncated:
                return tuple(objects.values())
            if not next_token or next_token in seen_tokens:
                raise MRMSDiscoveryError("MRMS S3 listing pagination is invalid.")
            seen_tokens.add(next_token)
            continuation_token = next_token

    async def _get_listing_page(self, params: dict[str, str]) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self._max_attempts):
            try:
                response = await self._client.get(self.base_url, params=params)
                if response.status_code in _RETRYABLE_STATUS_CODES:
                    raise _RetryableDiscoveryError(
                        f"MRMS listing returned retryable HTTP {response.status_code}.",
                    )
                if response.is_error:
                    raise MRMSDiscoveryError(
                        f"MRMS listing returned HTTP {response.status_code}.",
                    )
                if len(response.content) > self._max_listing_bytes:
                    raise MRMSDiscoveryError("MRMS listing exceeds the configured size limit.")
                return response
            except MRMSDiscoveryError as exc:
                if not isinstance(exc, _RetryableDiscoveryError):
                    raise
                last_error = exc
            except httpx.TransportError as exc:
                last_error = exc
            if attempt + 1 < self._max_attempts:
                await self._sleep(self._backoff_seconds * (2**attempt))
        raise MRMSDiscoveryError(
            f"MRMS listing failed after {self._max_attempts} attempt(s).",
        ) from last_error

    def _parse_listing(
        self,
        content: bytes,
    ) -> tuple[tuple[MRMSObject, ...], bool, str | None]:
        try:
            root = ElementTree.fromstring(content)
        except ElementTree.ParseError as exc:
            raise MRMSDiscoveryError("MRMS S3 listing returned invalid XML.") from exc

        objects: list[MRMSObject] = []
        for contents in _children_named(root, "Contents"):
            key = _child_text(contents, "Key")
            if key is None:
                continue
            try:
                item = parse_mrms_object_key(
                    key,
                    size=_optional_nonnegative_int(_child_text(contents, "Size")),
                    etag=_optional_etag(_child_text(contents, "ETag")),
                    last_modified=_optional_utc_datetime(
                        _child_text(contents, "LastModified"),
                    ),
                )
            except MRMSInvalidObjectKeyError:
                # Prefix listings can contain directory markers or unrelated sidecars.
                continue
            objects.append(item)

        is_truncated = (_child_text(root, "IsTruncated") or "false").casefold() == "true"
        next_token = _child_text(root, "NextContinuationToken")
        return tuple(objects), is_truncated, next_token

    async def _download_once(
        self,
        source: MRMSObject,
        *,
        data_root: Path,
        temporary_directory: Path,
    ) -> MRMSDownloadedArtifact:
        temporary_directory.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=temporary_directory,
            prefix=f"{source.filename}.",
            suffix=".part",
        )
        os.close(descriptor)
        temporary_path = Path(temporary_name)
        url = f"{self.base_url}/{quote(source.key, safe='/._-')}"
        try:
            compressed_size = await self._stream_to_file(url, temporary_path)
            if source.size is not None and compressed_size != source.size:
                raise MRMSContentLengthError(
                    "Downloaded bytes do not match the S3 listing size.",
                )
            validated = _validate_file(
                temporary_path,
                max_decompressed_bytes=self._max_decompressed_bytes,
            )
            target = (
                data_root
                / "raw"
                / "mrms"
                / self.product
                / f"{source.valid_time:%Y}"
                / f"{source.valid_time:%m}"
                / f"{source.valid_time:%d}"
                / source.filename
            )
            _place_immutable(temporary_path, target, validated.compressed_sha256)
            return MRMSDownloadedArtifact(
                source=source,
                path=target,
                compressed_sha256=validated.compressed_sha256,
                decompressed_sha256=validated.decompressed_sha256,
                compressed_size=validated.compressed_size,
                decompressed_size=validated.decompressed_size,
                downloaded_at=_require_utc(self._clock(), "clock"),
            )
        finally:
            temporary_path.unlink(missing_ok=True)

    async def _stream_to_file(self, url: str, destination: Path) -> int:
        async with self._client.stream("GET", url) as response:
            if response.status_code in _RETRYABLE_STATUS_CODES:
                raise _RetryableDownloadError(
                    f"MRMS object returned retryable HTTP {response.status_code}.",
                )
            if response.is_error:
                raise MRMSDownloadError(
                    f"MRMS object returned HTTP {response.status_code}.",
                )
            expected_size = _content_length(response.headers.get("content-length"))
            if expected_size is not None and expected_size > self._max_compressed_bytes:
                raise MRMSContentLengthError(
                    "MRMS Content-Length exceeds the configured compressed-byte limit.",
                )

            received = 0
            with destination.open("wb") as output:
                chunks = (
                    response.aiter_bytes() if response.is_stream_consumed else response.aiter_raw()
                )
                async for chunk in chunks:
                    received += len(chunk)
                    if received > self._max_compressed_bytes:
                        raise MRMSContentLengthError(
                            "MRMS download exceeds the configured compressed-byte limit.",
                        )
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            if expected_size is not None and received != expected_size:
                raise MRMSContentLengthError(
                    "MRMS response byte count does not match Content-Length.",
                )
            return received


def _validate_file(path: Path, *, max_decompressed_bytes: int) -> _ValidatedFile:
    compressed_sha256 = hashlib.sha256()
    compressed_size = 0
    with path.open("rb") as compressed:
        for chunk in iter(lambda: compressed.read(1024 * 1024), b""):
            compressed_size += len(chunk)
            compressed_sha256.update(chunk)

    decompressed_sha256 = hashlib.sha256()
    decompressed_size = 0
    prefix = bytearray()
    suffix = bytearray()
    try:
        with gzip.open(path, "rb") as source:
            while chunk := source.read(1024 * 1024):
                decompressed_size += len(chunk)
                if decompressed_size > max_decompressed_bytes:
                    raise MRMSIntegrityError(
                        "Decompressed MRMS data exceeds the configured size limit.",
                    )
                decompressed_sha256.update(chunk)
                if len(prefix) < 4:
                    prefix.extend(chunk[: 4 - len(prefix)])
                suffix.extend(chunk)
                if len(suffix) > 4:
                    del suffix[:-4]
    except (gzip.BadGzipFile, EOFError, OSError, zlib.error) as exc:
        raise MRMSIntegrityError("MRMS object is not an intact gzip stream.") from exc

    if bytes(prefix) != b"GRIB" or bytes(suffix) != b"7777":
        raise MRMSIntegrityError("Decompressed MRMS object is not a complete GRIB message.")
    return _ValidatedFile(
        compressed_sha256=compressed_sha256.hexdigest(),
        decompressed_sha256=decompressed_sha256.hexdigest(),
        compressed_size=compressed_size,
        decompressed_size=decompressed_size,
    )


def _place_immutable(source: Path, target: Path, expected_sha256: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        _require_same_checksum(target, expected_sha256)
        return

    descriptor, staging_name = tempfile.mkstemp(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".part",
    )
    staging = Path(staging_name)
    try:
        with os.fdopen(descriptor, "wb") as output, source.open("rb") as input_file:
            shutil.copyfileobj(input_file, output, length=1024 * 1024)
            output.flush()
            os.fsync(output.fileno())
        try:
            os.link(staging, target)
        except FileExistsError:
            _require_same_checksum(target, expected_sha256)
        else:
            _fsync_directory(target.parent)
    finally:
        staging.unlink(missing_ok=True)


def _require_same_checksum(path: Path, expected_sha256: str) -> None:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected_sha256:
        raise MRMSConflictError(
            f"Immutable MRMS target already exists with different bytes: {path.name}",
        )


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _children_named(
    element: ElementTree.Element, local_name: str
) -> tuple[ElementTree.Element, ...]:
    return tuple(
        child for child in element.iter() if child.tag.rsplit("}", maxsplit=1)[-1] == local_name
    )


def _child_text(element: ElementTree.Element, local_name: str) -> str | None:
    for child in element:
        if child.tag.rsplit("}", maxsplit=1)[-1] == local_name:
            return child.text
    return None


def _optional_nonnegative_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError as exc:
        raise MRMSDiscoveryError("MRMS listing contains an invalid object size.") from exc
    if parsed < 0:
        raise MRMSDiscoveryError("MRMS listing contains a negative object size.")
    return parsed


def _optional_etag(value: str | None) -> str | None:
    return value.strip('"') if value else None


def _optional_utc_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MRMSDiscoveryError("MRMS listing contains an invalid LastModified value.") from exc
    return _require_utc(parsed, "LastModified")


def _content_length(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError as exc:
        raise MRMSContentLengthError("MRMS Content-Length is not an integer.") from exc
    if parsed < 0:
        raise MRMSContentLengthError("MRMS Content-Length cannot be negative.")
    return parsed


def _require_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise MRMSConfigurationError(f"{field_name} must be timezone-aware.")
    return value.astimezone(UTC)


__all__ = [
    "MRMS_PRODUCT",
    "MRMS_S3_BASE_URL",
    "MRMS_S3_BUCKET",
    "MRMSConfigurationError",
    "MRMSConflictError",
    "MRMSContentLengthError",
    "MRMSDiscoveryError",
    "MRMSDownloadError",
    "MRMSDownloadedArtifact",
    "MRMSError",
    "MRMSFutureObjectError",
    "MRMSIntegrityError",
    "MRMSInvalidObjectKeyError",
    "MRMSNoObjectsError",
    "MRMSObject",
    "MRMSTransportAdapter",
    "parse_mrms_object_key",
]
