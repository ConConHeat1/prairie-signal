from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from prairie_signal_api.location_service import (
    load_places_gazetteer,
    load_zcta_gazetteer,
)
from prairie_signal_api.models import LocationKind

from prairie_signal_ingestion.census import (
    CensusIngestionError,
    CensusSource,
    archive_raw_source,
    haversine_km,
    parse_gazetteer,
    write_filtered_gazetteer,
)


def _zip_gazetteer(text: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w") as archive:
        archive.writestr("fixture.txt", text)
    return output.getvalue()


def test_places_and_zctas_parse_from_official_pipe_shape() -> None:
    places = parse_gazetteer(
        _zip_gazetteer(
            "USPS|GEOID|NAME|INTPTLAT|INTPTLONG\n"
            "NE|3128000|Lincoln city|40.8136|-96.7026\n"
            "NY|3651000|New York city|40.7128|-74.0060\n",
        ),
        LocationKind.CITY,
    )
    zctas = parse_gazetteer(
        _zip_gazetteer(
            "GEOID|NAME|INTPTLAT|INTPTLONG\n68508|ZCTA5 68508|40.8150|-96.7000\n",
        ),
        LocationKind.ZCTA,
    )

    assert places[0].name == "Lincoln"
    assert places[0].state_code == "NE"
    assert zctas[0].postal_code == "68508"
    assert haversine_km(
        40.8136,
        -96.7026,
        places[0].latitude,
        places[0].longitude,
    ) == pytest.approx(0)
    assert (
        haversine_km(
            40.8136,
            -96.7026,
            places[1].latitude,
            places[1].longitude,
        )
        > 512
    )


def test_derived_files_are_compatible_with_api_location_loader(
    tmp_path: Path,
) -> None:
    place_record = parse_gazetteer(
        b"USPS|GEOID|NAME|INTPTLAT|INTPTLONG\nNE|3128000|Lincoln city|40.8136|-96.7026\n",
        LocationKind.CITY,
    )
    zcta_record = parse_gazetteer(
        b"GEOID|NAME|INTPTLAT|INTPTLONG\n68508|ZCTA5 68508|40.8150|-96.7000\n",
        LocationKind.ZCTA,
    )
    places_path = tmp_path / "places.tsv"
    zcta_path = tmp_path / "zcta.tsv"

    write_filtered_gazetteer(places_path, place_record)
    write_filtered_gazetteer(zcta_path, zcta_record)

    assert load_places_gazetteer(places_path)[0].label == "Lincoln, NE"
    assert load_zcta_gazetteer(zcta_path)[0].label == "ZIP 68508 approximation"


def test_raw_archive_is_content_addressed_and_never_rewritten(
    tmp_path: Path,
) -> None:
    content = b"public census fixture"
    digest = hashlib.sha256(content).hexdigest()
    fetched_at = datetime.now(UTC)
    first = archive_raw_source(
        tmp_path,
        "places",
        "places.zip",
        content,
        digest,
        "local:places.zip",
        fetched_at,
        None,
        None,
    )
    second = archive_raw_source(
        tmp_path,
        "places",
        "places.zip",
        content,
        digest,
        "local:places.zip",
        fetched_at,
        None,
        None,
    )

    assert first == second
    assert first.read_bytes() == content
    assert first.with_suffix(first.suffix + ".provenance.json").exists()


def test_remote_sources_are_restricted_to_official_https_hosts() -> None:
    with pytest.raises(CensusIngestionError, match="HTTPS"):
        CensusSource("http://www2.census.gov/places.zip")
    with pytest.raises(CensusIngestionError, match="official"):
        CensusSource("https://example.com/places.zip")
