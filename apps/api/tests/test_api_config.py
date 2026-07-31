from pathlib import Path

import pytest

from prairie_signal_api.config import Settings


def test_alert_freshness_environment_names_are_backward_compatible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALERTS_FRESH_MINUTES", "3")
    monkeypatch.setenv("ALERTS_DELAYED_MINUTES", "12")

    settings = Settings()

    assert settings.alerts_fresh_minutes == 3
    assert settings.alerts_delayed_minutes == 12

    monkeypatch.delenv("ALERTS_FRESH_MINUTES")
    monkeypatch.delenv("ALERTS_DELAYED_MINUTES")
    monkeypatch.setenv("ALERT_FRESH_MINUTES", "4")
    monkeypatch.setenv("ALERT_DELAYED_MINUTES", "14")

    legacy_settings = Settings()

    assert legacy_settings.alerts_fresh_minutes == 4
    assert legacy_settings.alerts_delayed_minutes == 14


def test_compose_environment_aliases_are_supported(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("REDIS_URL", "redis://cache:6379/0")
    monkeypatch.setenv("RAW_ARCHIVE_PATH", "/data/raw")

    settings = Settings()

    assert settings.environment == "staging"
    assert settings.cache_url == "redis://cache:6379/0"
    assert settings.archive_directory == Path("/data/raw")
    assert settings.region_radius_km == 256


def test_alias_fields_still_accept_direct_construction() -> None:
    settings = Settings(
        environment="test",
        cache_url="redis://localhost:6379/1",
        archive_directory=Path("/tmp/prairie-test"),
    )

    assert settings.environment == "test"
    assert settings.cache_url == "redis://localhost:6379/1"
    assert settings.archive_directory == Path("/tmp/prairie-test")


def test_placeholder_nws_contact_is_never_used_for_live_requests() -> None:
    settings = Settings(
        nws_user_agent="PrairieSignal/0.1",
        nws_contact="https://example.invalid/weather-contact",
    )

    assert settings.effective_nws_user_agent is None
