"""Census Gazetteer acquisition and Lincoln-region index construction."""

from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import json
import math
import os
import re
import tempfile
import unicodedata
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx
from prairie_signal_api.models import Location, LocationKind, SourceName
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

CENSUS_2025_BASE_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer"
DEFAULT_PLACES_SOURCE = f"{CENSUS_2025_BASE_URL}/2025_Gaz_place_national.zip"
DEFAULT_ZCTA_SOURCE = f"{CENSUS_2025_BASE_URL}/2025_Gaz_zcta_national.zip"
DEFAULT_PLACES_SHA256 = "49644173a453469d9bd77fb7a493b027f87567e209edaf2078aac7543ac2ee29"
DEFAULT_ZCTA_SHA256 = "51516a4283bab5cd2376eec75609ddc4b363a18297e8adeeaac7b03cf7c84dbe"
MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024


class CensusIngestionError(RuntimeError):
    """A safe error for invalid, corrupt, or unexpected Census input."""


@dataclass(frozen=True, slots=True)
class CensusSource:
    """An official URL or operator-provided local Gazetteer file."""

    value: str
    expected_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.expected_sha256 is not None and not re.fullmatch(
            r"[0-9a-fA-F]{64}",
            self.expected_sha256,
        ):
            raise CensusIngestionError("Expected SHA-256 must contain 64 hex characters.")
        if self.value.startswith(("http://", "https://")):
            parsed = httpx.URL(self.value)
            if parsed.scheme != "https":
                raise CensusIngestionError("Remote Census sources must use HTTPS.")
            if parsed.host not in {"www2.census.gov", "www.census.gov"}:
                raise CensusIngestionError(
                    "Remote Gazetteer sources must use an official census.gov host.",
                )


@dataclass(frozen=True, slots=True)
class AcquiredSource:
    source_label: str
    filename: str
    content: bytes
    sha256: str
    fetched_at: datetime
    etag: str | None
    last_modified: str | None
    raw_archive_path: Path


@dataclass(frozen=True, slots=True)
class CensusLocationRecord:
    kind: LocationKind
    source_record_id: str
    slug: str
    name: str
    normalized_name: str
    state_code: str
    postal_code: str | None
    latitude: float
    longitude: float
    timezone: str


@dataclass(frozen=True, slots=True)
class UpsertResult:
    created: int
    updated: int
    unchanged: int


@dataclass(frozen=True, slots=True)
class CensusIngestionResult:
    places_count: int
    zcta_count: int
    places_sha256: str
    zcta_sha256: str
    places_output_path: Path
    zcta_output_path: Path
    upsert: UpsertResult


class CensusGazetteerIngestor:
    """Build a current local index from immutable raw public source files."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        raw_archive_directory: Path,
        output_directory: Path,
        center_latitude: float,
        center_longitude: float,
        radius_km: float,
        timezone: str = "America/Chicago",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._raw_archive_directory = raw_archive_directory
        self._output_directory = output_directory
        self._center_latitude = center_latitude
        self._center_longitude = center_longitude
        self._radius_km = radius_km
        self._timezone = timezone
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(60.0),
            follow_redirects=False,
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def ingest(
        self,
        places_source: CensusSource,
        zcta_source: CensusSource,
    ) -> CensusIngestionResult:
        places_acquired, zcta_acquired = await asyncio.gather(
            self._acquire(places_source, "places"),
            self._acquire(zcta_source, "zcta"),
        )
        places, zctas = await asyncio.gather(
            asyncio.to_thread(
                parse_gazetteer,
                places_acquired.content,
                LocationKind.CITY,
                self._timezone,
            ),
            asyncio.to_thread(
                parse_gazetteer,
                zcta_acquired.content,
                LocationKind.ZCTA,
                self._timezone,
            ),
        )
        filtered_places = tuple(record for record in places if self._in_region(record))
        filtered_zctas = tuple(record for record in zctas if self._in_region(record))

        self._output_directory.mkdir(parents=True, exist_ok=True)
        places_output = self._output_directory / "places.tsv"
        zcta_output = self._output_directory / "zcta.tsv"
        await asyncio.gather(
            asyncio.to_thread(write_filtered_gazetteer, places_output, filtered_places),
            asyncio.to_thread(write_filtered_gazetteer, zcta_output, filtered_zctas),
        )
        upsert = await self._upsert(filtered_places + filtered_zctas)
        return CensusIngestionResult(
            places_count=len(filtered_places),
            zcta_count=len(filtered_zctas),
            places_sha256=places_acquired.sha256,
            zcta_sha256=zcta_acquired.sha256,
            places_output_path=places_output,
            zcta_output_path=zcta_output,
            upsert=upsert,
        )

    def _in_region(self, record: CensusLocationRecord) -> bool:
        return (
            haversine_km(
                self._center_latitude,
                self._center_longitude,
                record.latitude,
                record.longitude,
            )
            <= self._radius_km
        )

    async def _acquire(
        self,
        source: CensusSource,
        source_type: str,
    ) -> AcquiredSource:
        fetched_at = datetime.now(UTC)
        etag: str | None = None
        last_modified: str | None = None
        if source.value.startswith("https://"):
            response = await self._client.get(
                source.value,
                headers={"User-Agent": "PrairieSignal-CensusIngestion/0.1"},
            )
            response.raise_for_status()
            content = response.content
            filename = Path(response.request.url.path).name
            source_label = str(response.request.url)
            etag = response.headers.get("etag")
            last_modified = response.headers.get("last-modified")
        else:
            path = Path(source.value)
            content = await asyncio.to_thread(path.read_bytes)
            filename = path.name
            # Do not persist an operator's absolute filesystem path.
            source_label = f"local:{filename}"

        digest = hashlib.sha256(content).hexdigest()
        if source.expected_sha256 is not None and digest != source.expected_sha256.lower():
            raise CensusIngestionError(
                f"SHA-256 verification failed for {source_type} Gazetteer source.",
            )
        archive_path = await asyncio.to_thread(
            archive_raw_source,
            self._raw_archive_directory,
            source_type,
            filename,
            content,
            digest,
            source_label,
            fetched_at,
            etag,
            last_modified,
            source.expected_sha256,
        )
        return AcquiredSource(
            source_label=source_label,
            filename=filename,
            content=content,
            sha256=digest,
            fetched_at=fetched_at,
            etag=etag,
            last_modified=last_modified,
            raw_archive_path=archive_path,
        )

    async def _upsert(
        self,
        records: tuple[CensusLocationRecord, ...],
    ) -> UpsertResult:
        created = 0
        updated = 0
        unchanged = 0
        async with self._session_factory() as session:
            async with session.begin():
                existing_records = (
                    await session.scalars(
                        select(Location).where(
                            Location.source_name == SourceName.CENSUS,
                        ),
                    )
                ).all()
                existing = {location.source_record_id: location for location in existing_records}
                for record in records:
                    location = existing.get(record.source_record_id)
                    if location is None:
                        session.add(
                            Location(
                                slug=record.slug,
                                kind=record.kind,
                                name=record.name,
                                normalized_name=record.normalized_name,
                                state_code=record.state_code,
                                country_code="US",
                                postal_code=record.postal_code,
                                latitude=record.latitude,
                                longitude=record.longitude,
                                timezone=record.timezone,
                                population=None,
                                source_name=SourceName.CENSUS,
                                source_record_id=record.source_record_id,
                                is_public_benchmark=False,
                            ),
                        )
                        created += 1
                        continue

                    changes = {
                        "slug": record.slug,
                        "kind": record.kind,
                        "name": record.name,
                        "normalized_name": record.normalized_name,
                        "state_code": record.state_code,
                        "postal_code": record.postal_code,
                        "latitude": record.latitude,
                        "longitude": record.longitude,
                        "timezone": record.timezone,
                    }
                    if all(getattr(location, key) == value for key, value in changes.items()):
                        unchanged += 1
                        continue
                    for key, value in changes.items():
                        setattr(location, key, value)
                    updated += 1
        return UpsertResult(created=created, updated=updated, unchanged=unchanged)


def parse_gazetteer(
    content: bytes,
    kind: LocationKind,
    timezone: str = "America/Chicago",
) -> tuple[CensusLocationRecord, ...]:
    """Read an official zip/plain Gazetteer without extracting filesystem paths."""

    text = _gazetteer_text(content)
    sample = text[:8_192]
    if "|" in sample:
        delimiter = "|"
    elif "\t" in sample:
        delimiter = "\t"
    else:
        delimiter = ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    records: list[CensusLocationRecord] = []
    for unclean_row in reader:
        row = {
            str(key).strip(): value.strip()
            for key, value in unclean_row.items()
            if key is not None and value is not None
        }
        try:
            geoid = row["GEOID"]
            latitude = float(row["INTPTLAT"])
            longitude = float(row["INTPTLONG"])
        except (KeyError, ValueError):
            continue
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            continue

        if kind is LocationKind.ZCTA:
            if not re.fullmatch(r"\d{5}", geoid):
                continue
            name = geoid
            state_code = "NA"
            postal_code = geoid
            source_record_id = f"zcta:{geoid}"
            slug = f"zcta-{geoid}"
        else:
            raw_name = row.get("NAME", "").strip()
            state_code = row.get("USPS", "").upper()
            if not raw_name or not re.fullmatch(r"[A-Z]{2}", state_code):
                continue
            name = _place_display_name(raw_name)
            postal_code = None
            source_record_id = f"place:{geoid}"
            slug = f"place-{geoid.lower()}"

        records.append(
            CensusLocationRecord(
                kind=kind,
                source_record_id=source_record_id,
                slug=slug,
                name=name,
                normalized_name=_normalize(name),
                state_code=state_code,
                postal_code=postal_code,
                latitude=latitude,
                longitude=longitude,
                timezone=timezone,
            ),
        )
    return tuple(records)


def _gazetteer_text(content: bytes) -> str:
    if content.startswith(b"PK\x03\x04"):
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            candidates = [
                info
                for info in archive.infolist()
                if not info.is_dir() and info.filename.lower().endswith((".txt", ".csv"))
            ]
            if len(candidates) != 1:
                raise CensusIngestionError(
                    "Gazetteer zip must contain exactly one text data file.",
                )
            member = candidates[0]
            if member.file_size > MAX_UNCOMPRESSED_BYTES:
                raise CensusIngestionError("Gazetteer data exceeds the extraction limit.")
            content = archive.read(member)
    if len(content) > MAX_UNCOMPRESSED_BYTES:
        raise CensusIngestionError("Gazetteer data exceeds the parsing limit.")
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CensusIngestionError("Gazetteer source is not UTF-8 text.") from exc


def write_filtered_gazetteer(
    path: Path,
    records: tuple[CensusLocationRecord, ...],
) -> None:
    """Atomically replace the derived index; raw inputs remain immutable."""

    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["USPS", "GEOID", "NAME", "INTPTLAT", "INTPTLONG"],
                delimiter="\t",
                lineterminator="\n",
            )
            writer.writeheader()
            for record in records:
                writer.writerow(
                    {
                        "USPS": "" if record.kind is LocationKind.ZCTA else record.state_code,
                        "GEOID": record.source_record_id.split(":", maxsplit=1)[1],
                        "NAME": record.name,
                        "INTPTLAT": f"{record.latitude:.7f}",
                        "INTPTLONG": f"{record.longitude:.7f}",
                    },
                )
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def archive_raw_source(
    archive_directory: Path,
    source_type: str,
    filename: str,
    content: bytes,
    digest: str,
    source_label: str,
    fetched_at: datetime,
    etag: str | None,
    last_modified: str | None,
    expected_sha256: str | None = None,
) -> Path:
    """Write content-addressed source bytes and provenance without overwrites."""

    target_directory = archive_directory / "census" / "2025" / source_type
    target_directory.mkdir(parents=True, exist_ok=True)
    safe_filename = re.sub(r"[^A-Za-z0-9._-]+", "-", filename).strip(".-")
    if not safe_filename:
        safe_filename = "gazetteer.bin"
    target = target_directory / f"{digest}-{safe_filename}"
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise CensusIngestionError("Existing raw archive failed integrity verification.")
    else:
        try:
            with target.open("xb") as handle:
                handle.write(content)
        except FileExistsError as exc:
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise CensusIngestionError(
                    "Concurrent raw archive write failed integrity verification.",
                ) from exc

    manifest = target.with_suffix(target.suffix + ".provenance.json")
    manifest_payload = {
        "dataset": "US Census Bureau 2025 Gazetteer",
        "source_type": source_type,
        "source": source_label,
        "sha256": digest,
        "byte_size": len(content),
        "fetched_at": fetched_at.isoformat(),
        "etag": etag,
        "last_modified": last_modified,
        "expected_sha256": expected_sha256,
        "checksum_verified": expected_sha256 is not None,
    }
    encoded_manifest = (
        json.dumps(manifest_payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode()
    if manifest.exists():
        existing_manifest = json.loads(manifest.read_text(encoding="utf-8"))
        # Fetch time may differ when an identical immutable source is acquired
        # again; identity and content provenance must remain the same.
        for key in ("dataset", "source_type", "source", "sha256", "byte_size"):
            if existing_manifest.get(key) != manifest_payload[key]:
                raise CensusIngestionError("Existing provenance manifest does not match.")
    else:
        try:
            with manifest.open("xb") as handle:
                handle.write(encoded_manifest)
        except FileExistsError:
            pass
    return target


def haversine_km(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    radius = 6_371.0088
    lat_a = math.radians(latitude_a)
    lat_b = math.radians(latitude_b)
    delta_latitude = lat_b - lat_a
    delta_longitude = math.radians(longitude_b - longitude_a)
    value = (
        math.sin(delta_latitude / 2) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_longitude / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def _place_display_name(value: str) -> str:
    return re.sub(
        r"\s+(city|village|town|borough|municipality|CDP)$",
        "",
        value,
        flags=re.IGNORECASE,
    )


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(re.sub(r"[^a-zA-Z0-9]+", " ", ascii_value).lower().split())
