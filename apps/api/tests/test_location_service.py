from __future__ import annotations

from pathlib import Path

import pytest

from prairie_signal_api.config import Settings
from prairie_signal_api.location_service import (
    OutsideServiceRegion,
    UnsupportedLocationQuery,
    build_location_index,
    haversine_km,
    load_places_gazetteer,
    load_zcta_gazetteer,
)
from prairie_signal_api.schemas import LocationKind, QueryKind


def test_city_search_ranks_exact_name_first() -> None:
    index = build_location_index(Settings())

    result = index.search("Lincoln, Nebraska")

    assert result.kind is QueryKind.CITY
    assert result.locations[0].label == "Lincoln, NE"


def test_zip_is_labeled_as_approximation() -> None:
    index = build_location_index(Settings())

    result = index.search("68508")

    assert result.kind is QueryKind.ZIP
    assert result.locations[0].kind is LocationKind.ZCTA
    assert result.locations[0].label == "ZIP 68508 approximation"


def test_coordinate_query_is_rounded_for_nws_and_remains_in_region() -> None:
    index = build_location_index(Settings())

    result = index.search("40.8136123, -96.7026123")

    assert result.kind is QueryKind.COORDINATE
    assert result.locations[0].latitude == 40.8136
    assert result.locations[0].longitude == -96.7026


def test_outside_coordinate_is_rejected() -> None:
    index = build_location_index(Settings())

    with pytest.raises(OutsideServiceRegion):
        index.search("34.0522,-118.2437")


def test_street_address_is_explicitly_unsupported() -> None:
    index = build_location_index(Settings())

    with pytest.raises(UnsupportedLocationQuery, match="Street addresses"):
        index.search("123 O Street, Lincoln NE")


def test_gazetteer_importers_accept_census_tsv_headers(tmp_path: Path) -> None:
    places = tmp_path / "places.txt"
    places.write_text(
        "USPS\tGEOID\tNAME\tINTPTLAT\tINTPTLONG\nNE\t3131537\tLincoln city\t+40.8136\t-096.7026\n",
        encoding="utf-8",
    )
    zctas = tmp_path / "zcta.txt"
    zctas.write_text(
        "GEOID\tINTPTLAT\tINTPTLONG\n68508\t+40.8150\t-096.7045\n",
        encoding="utf-8",
    )

    loaded_places = load_places_gazetteer(places)
    loaded_zctas = load_zcta_gazetteer(zctas)

    assert loaded_places[0].label == "Lincoln, NE"
    assert loaded_zctas[0].label == "ZIP 68508 approximation"


def test_region_filter_removes_out_of_bounds_gazetteer_entries(tmp_path: Path) -> None:
    places = tmp_path / "places.txt"
    places.write_text(
        "USPS\tGEOID\tNAME\tINTPTLAT\tINTPTLONG\n"
        "NE\t3131537\tLincoln city\t+40.8136\t-096.7026\n"
        "CA\t0644000\tLos Angeles city\t+34.0522\t-118.2437\n",
        encoding="utf-8",
    )
    settings = Settings(census_places_path=places)

    index = build_location_index(settings)

    assert [location.name for location in index.locations] == ["Lincoln"]


def test_missing_configured_gazetteers_fall_back_to_packaged_index(
    tmp_path: Path,
) -> None:
    settings = Settings(
        census_places_path=tmp_path / "places.tsv",
        census_zcta_path=tmp_path / "zcta.tsv",
    )

    index = build_location_index(settings)

    assert index.search("Lincoln").locations[0].label == "Lincoln, NE"


def test_haversine_has_expected_scale() -> None:
    distance = haversine_km(40.8136, -96.7026, 41.2565, -95.9345)
    assert 70 < distance < 90
