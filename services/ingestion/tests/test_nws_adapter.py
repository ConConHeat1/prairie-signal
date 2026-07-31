from __future__ import annotations

import json

import httpx
import pytest
from prairie_signal_api.models import ResourceKind

from prairie_signal_ingestion.adapters.nws import NWSBenchmarkAdapter
from prairie_signal_ingestion.config import PublicBenchmark


@pytest.mark.asyncio
async def test_adapter_collects_only_links_for_the_public_benchmark() -> None:
    base = "https://api.weather.test"

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.startswith("/points/"):
            body = {
                "properties": {
                    "forecast": f"{base}/grid/forecast",
                    "forecastHourly": f"{base}/grid/hourly",
                    "observationStations": f"{base}/stations",
                    "updated": "2026-07-30T12:00:00Z",
                },
            }
        elif path == "/stations":
            body = {"features": [{"id": f"{base}/stations/KLNK"}]}
        elif path == "/stations/KLNK/observations/latest":
            body = {"properties": {"timestamp": "2026-07-30T12:05:00Z"}}
        elif path == "/alerts/active":
            body = {"features": []}
        else:
            body = {"properties": {"updated": "2026-07-30T12:00:00Z"}}
        return httpx.Response(
            200,
            content=json.dumps(body),
            headers={"Content-Type": "application/geo+json", "ETag": '"fixture"'},
            request=request,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = NWSBenchmarkAdapter(
        base_url=base,
        user_agent="PrairieSignal/test (weather@example.test)",
        client=client,
    )
    benchmark = PublicBenchmark(
        slug="lincoln-ne",
        latitude=40.8136,
        longitude=-96.7026,
        name="Lincoln",
        state_code="NE",
    )

    payloads = await adapter.fetch(benchmark)
    assert {payload.resource_kind for payload in payloads} == {
        ResourceKind.POINT,
        ResourceKind.FORECAST,
        ResourceKind.HOURLY,
        ResourceKind.STATIONS,
        ResourceKind.OBSERVATION,
        ResourceKind.ALERTS,
    }
    assert all(payload.resource_uri.startswith(base) for payload in payloads)
    assert all(payload.safe_headers.get("etag") == '"fixture"' for payload in payloads)
    await client.aclose()
