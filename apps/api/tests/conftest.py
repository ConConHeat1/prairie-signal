from __future__ import annotations

from datetime import UTC, datetime

import pytest

from prairie_signal_api.config import Settings


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 7, 30, 18, 0, tzinfo=UTC)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        nws_user_agent="PrairieSignal-Test/1.0",
        nws_contact="tests@localhost",
        nws_max_retries=3,
        cache_default_ttl_seconds=60,
        cache_min_ttl_seconds=1,
        cache_max_ttl_seconds=900,
        stale_retention_seconds=86400,
    )
