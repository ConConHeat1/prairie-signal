from __future__ import annotations

from fastapi.testclient import TestClient

from prairie_signal_api.config import Settings
from prairie_signal_api.main import create_app


def test_health_and_openapi_contract_are_available() -> None:
    app = create_app(
        Settings(
            _env_file=None,
            cache_url=None,
            nws_user_agent="PrairieSignal-Test/1.0",
            nws_contact="tests@localhost",
        )
    )
    with TestClient(app) as client:
        health = client.get("/api/v1/health")
        schema = client.get("/api/openapi.json")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert schema.status_code == 200
    paths = schema.json()["paths"]
    assert "/api/v1/weather/current" in paths
    assert "/api/v1/alerts/active" in paths


def test_location_search_supports_city_zip_and_coordinates() -> None:
    app = create_app(Settings(_env_file=None, cache_url=None))
    with TestClient(app) as client:
        city = client.get("/api/v1/location/search", params={"q": "Lincoln"})
        zipcode = client.get("/api/v1/location/search", params={"q": "68508"})
        coordinates = client.get(
            "/api/v1/location/search",
            params={"q": "40.8136,-96.7026"},
        )

    assert city.json()["results"][0]["label"] == "Lincoln, NE"
    assert city.json()["region_limit_km"] == 512
    assert zipcode.json()["query_kind"] == "zip"
    assert coordinates.json()["query_kind"] == "coordinate"


def test_outside_service_region_has_stable_error_contract() -> None:
    app = create_app(Settings(_env_file=None, cache_url=None))
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/weather/current",
            params={"latitude": 34.0522, "longitude": -118.2437},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "outside_service_region"


def test_missing_nws_identity_is_explicit() -> None:
    app = create_app(
        Settings(_env_file=None, cache_url=None, nws_user_agent=None, nws_contact=None)
    )
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/weather/hourly",
            params={"latitude": 40.8136, "longitude": -96.7026},
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "nws_not_configured"


def test_ready_requires_identifying_nws_configuration() -> None:
    app = create_app(
        Settings(_env_file=None, cache_url=None, nws_user_agent=None, nws_contact=None)
    )
    with TestClient(app) as client:
        response = client.get("/api/v1/ready")

    assert response.status_code == 503
    assert response.json()["checks"]["nws_configured"] is False
