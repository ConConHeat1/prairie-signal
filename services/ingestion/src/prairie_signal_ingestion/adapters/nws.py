"""National Weather Service adapter for scheduled public benchmarks."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urljoin

import httpx
from prairie_signal_api.models import ResourceKind, SourceName

from prairie_signal_ingestion.config import PublicBenchmark
from prairie_signal_ingestion.domain import SAFE_PROVENANCE_HEADERS, SourcePayload


class NWSIngestionNotConfigured(RuntimeError):
    """Raised when scheduled live ingestion lacks an identifying User-Agent."""


class NWSSettings(Protocol):
    nws_base_url: str
    nws_timeout_seconds: float

    @property
    def effective_nws_user_agent(self) -> str | None: ...


class NWSBenchmarkAdapter:
    """Fetch NWS resources reachable from a configured benchmark point.

    This adapter deliberately has no public method accepting latitude,
    longitude, search text, or an arbitrary URL.  Linked resources are accepted
    only when they remain on the configured NWS origin.
    """

    source_name = SourceName.NWS

    def __init__(
        self,
        *,
        base_url: str,
        user_agent: str | None,
        timeout_seconds: float = 12.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not user_agent:
            raise NWSIngestionNotConfigured(
                "Scheduled NWS ingestion requires an identifying User-Agent.",
            )
        self.base_url = base_url.rstrip("/") + "/"
        self.user_agent = user_agent
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
        )
        parsed_base = httpx.URL(self.base_url)
        self._allowed_origin = (
            parsed_base.scheme,
            parsed_base.host,
            parsed_base.port,
        )

    @classmethod
    def from_settings(
        cls,
        settings: NWSSettings,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> NWSBenchmarkAdapter:
        return cls(
            base_url=str(settings.nws_base_url),
            user_agent=settings.effective_nws_user_agent,
            timeout_seconds=float(settings.nws_timeout_seconds),
            client=client,
        )

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def fetch(
        self,
        benchmark: PublicBenchmark,
    ) -> tuple[SourcePayload, ...]:
        point_url = self._url(
            f"points/{benchmark.latitude:.4f},{benchmark.longitude:.4f}",
        )
        point = await self._get(point_url, ResourceKind.POINT)
        outputs: list[SourcePayload] = [point]

        properties = _properties(point.payload)
        linked_resources = (
            ("forecast", ResourceKind.FORECAST),
            ("forecastHourly", ResourceKind.HOURLY),
            ("observationStations", ResourceKind.STATIONS),
        )
        fetched_by_kind: dict[ResourceKind, SourcePayload] = {}
        for property_name, resource_kind in linked_resources:
            linked_url = properties.get(property_name)
            if not isinstance(linked_url, str):
                raise ValueError(f"NWS point response is missing {property_name}.")
            payload = await self._get(
                self._validated_link(linked_url),
                resource_kind,
            )
            outputs.append(payload)
            fetched_by_kind[resource_kind] = payload

        observation = await self._first_valid_observation(
            fetched_by_kind[ResourceKind.STATIONS],
        )
        if observation is not None:
            outputs.append(observation)

        alerts_url = self._url("alerts/active").copy_add_param(
            "point",
            f"{benchmark.latitude:.4f},{benchmark.longitude:.4f}",
        )
        outputs.append(await self._get(alerts_url, ResourceKind.ALERTS))
        return tuple(outputs)

    async def _first_valid_observation(
        self,
        station_collection: SourcePayload,
    ) -> SourcePayload | None:
        if not isinstance(station_collection.payload, dict):
            return None
        features = station_collection.payload.get("features")
        if not isinstance(features, list):
            return None
        for feature in features[:3]:
            if not isinstance(feature, dict):
                continue
            station_uri = feature.get("id")
            if not isinstance(station_uri, str):
                continue
            observation_uri = self._validated_link(
                station_uri.rstrip("/") + "/observations/latest",
            ).copy_add_param("require_qc", "true")
            try:
                observation = await self._get(
                    observation_uri,
                    ResourceKind.OBSERVATION,
                )
            except (httpx.HTTPError, ValueError):
                continue
            if _properties(observation.payload).get("timestamp"):
                return observation
        return None

    async def _get(
        self,
        url: httpx.URL,
        resource_kind: ResourceKind,
    ) -> SourcePayload:
        requested_at = datetime.now(UTC)
        started = time.monotonic()
        response = await self.client.get(
            url,
            headers={
                "Accept": "application/geo+json",
                "User-Agent": self.user_agent,
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, (dict, list)):
            raise ValueError("NWS returned a non-object JSON document.")
        fetched_at = datetime.now(UTC)
        duration_ms = max(0, round((time.monotonic() - started) * 1_000))
        headers = {
            key.lower(): value
            for key, value in response.headers.items()
            if key.lower() in SAFE_PROVENANCE_HEADERS
        }
        return SourcePayload(
            source_name=SourceName.NWS,
            resource_kind=resource_kind,
            resource_uri=str(response.request.url),
            payload=payload,
            requested_at=requested_at,
            fetched_at=fetched_at,
            duration_ms=duration_ms,
            status_code=response.status_code,
            headers=headers,
            source_time=_source_time(payload),
            content_type=headers.get("content-type", "application/geo+json"),
        )

    def _url(self, relative_path: str) -> httpx.URL:
        return self._validated_link(urljoin(self.base_url, relative_path))

    def _validated_link(self, value: str) -> httpx.URL:
        parsed = httpx.URL(value)
        origin = (parsed.scheme, parsed.host, parsed.port)
        if origin != self._allowed_origin:
            raise ValueError("NWS returned a resource outside its configured origin.")
        return parsed


def _properties(payload: dict[str, Any] | list[Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    properties = payload.get("properties")
    return properties if isinstance(properties, dict) else {}


def _source_time(payload: dict[str, Any] | list[Any]) -> datetime | None:
    properties = _properties(payload)
    for field in ("updated", "generatedAt", "timestamp", "sent"):
        value = properties.get(field)
        if not isinstance(value, str):
            continue
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    return None
