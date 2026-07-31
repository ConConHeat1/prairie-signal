"""Privacy-preserving location search backed by local public Gazetteer data."""

from __future__ import annotations

import csv
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from prairie_signal_api.config import Settings
from prairie_signal_api.schemas import Location, LocationKind, QueryKind

_COORDINATES = re.compile(
    r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*,\s*"
    r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*$"
)
_ZIP = re.compile(r"^\d{5}$")
_STREETISH = re.compile(r"^\s*\d+\s+\S+")


class LocationSearchError(ValueError):
    code = "invalid_location_query"


class UnsupportedLocationQuery(LocationSearchError):
    code = "unsupported_location_query"


class OutsideServiceRegion(LocationSearchError):
    code = "outside_service_region"


@dataclass(frozen=True, slots=True)
class SearchResult:
    locations: list[Location]
    kind: QueryKind


def haversine_km(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    radius = 6371.0088
    lat1, lat2 = math.radians(lat_a), math.radians(lat_b)
    dlat = lat2 - lat1
    dlon = math.radians(lon_b - lon_a)
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


class LocationIndex:
    def __init__(
        self,
        locations: list[Location],
        *,
        center_latitude: float,
        center_longitude: float,
        radius_km: float,
    ) -> None:
        self.center_latitude = center_latitude
        self.center_longitude = center_longitude
        self.radius_km = radius_km
        self.locations = [
            location
            for location in locations
            if self.in_region(location.latitude, location.longitude)
        ]

    def in_region(self, latitude: float, longitude: float) -> bool:
        return (
            haversine_km(
                self.center_latitude,
                self.center_longitude,
                latitude,
                longitude,
            )
            <= self.radius_km
        )

    def search(self, query: str, limit: int = 8) -> SearchResult:
        query = query.strip()
        if not query:
            raise LocationSearchError("Enter a city, five-digit ZIP, or coordinates.")

        if match := _COORDINATES.fullmatch(query):
            latitude, longitude = (float(match.group(1)), float(match.group(2)))
            if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                raise LocationSearchError("Coordinates must be valid latitude and longitude.")
            if not self.in_region(latitude, longitude):
                raise OutsideServiceRegion(
                    f"Coordinates are outside the {self.radius_km * 2:g} km-wide service region."
                )
            location = Location(
                id=f"coordinate:{latitude:.4f}:{longitude:.4f}",
                name="Selected coordinates",
                region="Lincoln service region",
                latitude=round(latitude, 4),
                longitude=round(longitude, 4),
                timezone="America/Chicago",
                kind=LocationKind.COORDINATE,
                label=f"{latitude:.4f}, {longitude:.4f}",
            )
            return SearchResult([location], QueryKind.COORDINATE)

        if _ZIP.fullmatch(query):
            matches = [
                location
                for location in self.locations
                if location.kind is LocationKind.ZCTA and location.name == query
            ]
            return SearchResult(matches[:limit], QueryKind.ZIP)

        if _STREETISH.match(query) or any(character in query for character in "@;/"):
            raise UnsupportedLocationQuery(
                "Street addresses are not supported. Use a city, five-digit ZIP, or coordinates."
            )

        normalized = _normalize_city_query(query)
        if not normalized or normalized.isdigit():
            raise UnsupportedLocationQuery(
                "Use a US city, five-digit ZIP, or coordinates inside the service region."
            )

        ranked: list[tuple[int, int, float, str, Location]] = []
        for location in self.locations:
            if location.kind is not LocationKind.CITY:
                continue
            name = _normalize(location.name)
            label = _normalize(location.label)
            if normalized == name or normalized == label:
                match_class = 0
            elif name.startswith(normalized):
                match_class = 1
            elif normalized in name or normalized in label:
                match_class = 2
            else:
                continue
            distance = haversine_km(
                self.center_latitude,
                self.center_longitude,
                location.latitude,
                location.longitude,
            )
            ranked.append((match_class, len(name), distance, location.label, location))
        ranked.sort(key=lambda item: item[:4])
        return SearchResult([item[-1] for item in ranked[:limit]], QueryKind.CITY)


def build_location_index(settings: Settings) -> LocationIndex:
    locations: list[Location] = []
    if settings.census_places_path and settings.census_places_path.is_file():
        locations.extend(load_places_gazetteer(settings.census_places_path))
    if settings.census_zcta_path and settings.census_zcta_path.is_file():
        locations.extend(load_zcta_gazetteer(settings.census_zcta_path))
    if not locations:
        locations = load_builtin_locations()
    return LocationIndex(
        locations,
        center_latitude=settings.region_center_latitude,
        center_longitude=settings.region_center_longitude,
        radius_km=settings.region_radius_km,
    )


def load_builtin_locations() -> list[Location]:
    raw = files("prairie_signal_api.data").joinpath("lincoln_region.json").read_text()
    return [Location.model_validate(item) for item in json.loads(raw)]


def load_places_gazetteer(path: Path) -> list[Location]:
    locations: list[Location] = []
    for row in _read_gazetteer(path):
        try:
            region = _value(row, "USPS")
            name = _value(row, "NAME").removesuffix(" city").removesuffix(" village")
            geoid = _value(row, "GEOID")
            latitude = float(_value(row, "INTPTLAT"))
            longitude = float(_value(row, "INTPTLONG"))
        except (KeyError, ValueError):
            continue
        locations.append(
            Location(
                id=f"place:{geoid}",
                name=name,
                region=region,
                latitude=latitude,
                longitude=longitude,
                timezone="America/Chicago",
                kind=LocationKind.CITY,
                label=f"{name}, {region}",
            )
        )
    return locations


def load_zcta_gazetteer(path: Path) -> list[Location]:
    locations: list[Location] = []
    for row in _read_gazetteer(path):
        try:
            zcta = _value(row, "GEOID")
            latitude = float(_value(row, "INTPTLAT"))
            longitude = float(_value(row, "INTPTLONG"))
        except (KeyError, ValueError):
            continue
        if not _ZIP.fullmatch(zcta):
            continue
        locations.append(
            Location(
                id=f"zcta:{zcta}",
                name=zcta,
                region="",
                latitude=latitude,
                longitude=longitude,
                timezone="America/Chicago",
                kind=LocationKind.ZCTA,
                label=f"ZIP {zcta} approximation",
            )
        )
    return locations


def _read_gazetteer(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        delimiter = "\t" if "\t" in sample else ","
        return list(csv.DictReader(handle, delimiter=delimiter))


def _value(row: dict[str, str], key: str) -> str:
    for raw_key, value in row.items():
        if raw_key.strip() == key:
            return value.strip()
    raise KeyError(key)


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(re.sub(r"[^a-zA-Z0-9]+", " ", ascii_value).lower().split())


def _normalize_city_query(query: str) -> str:
    normalized = _normalize(query)
    tokens = normalized.split()
    state_names = {
        "ne": "ne",
        "nebraska": "ne",
        "ia": "ia",
        "iowa": "ia",
        "ks": "ks",
        "kansas": "ks",
        "mo": "mo",
        "missouri": "mo",
        "sd": "sd",
        "south dakota": "sd",
    }
    for suffix, abbreviation in state_names.items():
        suffix_tokens = suffix.split()
        if len(tokens) > len(suffix_tokens) and tokens[-len(suffix_tokens) :] == suffix_tokens:
            city = " ".join(tokens[: -len(suffix_tokens)])
            return f"{city} {abbreviation}"
    return normalized
