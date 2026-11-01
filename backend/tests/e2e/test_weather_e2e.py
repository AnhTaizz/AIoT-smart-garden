"""GET /weather against the real stack: PostgreSQL sessions, FastAPI and Nginx.

The live provider is not a dependency: any of the four statuses passes, so a
stack without Internet or with weather disabled still checks auth and schema.
"""

import math
import os

import pytest

from helpers import API, auth_headers, raw_request

pytestmark = pytest.mark.skipif(not API, reason="E2E_API_BASE_URL not set")
PROXY = os.getenv("E2E_PROXY_URL", "").rstrip("/")
STATUSES = {"fresh", "stale", "unavailable", "disabled"}


def bases():
    return [API] + ([PROXY] if PROXY else [])


def in_range(value, low, high):
    return value is None or (isinstance(value, (int, float)) and math.isfinite(value) and low <= value <= high)


@pytest.mark.parametrize("base", bases())
def test_weather_requires_a_session(base):
    for headers in ({}, {"Authorization": "Bearer forged-token"}):
        status, body = raw_request("GET", f"{base}/weather", headers=headers)
        assert status == 401, body
        assert body["detail"]["code"] in ("auth_required", "invalid_session")


@pytest.mark.parametrize("base", bases())
def test_weather_schema_is_a_labelled_forecast(base):
    status, body = raw_request("GET", f"{base}/weather", headers=auth_headers())
    assert status == 200, body
    assert body["status"] in STATUSES
    assert body["kind"] == "forecast" and body["provider"] == "open-meteo"
    assert body["attribution"].startswith("Weather data by Open-Meteo.com")
    assert (body["reason"] is None) == (body["status"] == "fresh")
    if body["status"] in ("unavailable", "disabled"):
        assert body["hours"] == [] and body["summary"] is None
        return
    assert body["fetched_at"].endswith("Z") and body["valid_until"].endswith("Z")
    assert len(body["hours"]) <= 12
    for hour in body["hours"]:
        assert hour["time"].endswith("Z")
        assert in_range(hour["precipitation_probability_pct"], 0, 100)
        assert in_range(hour["precipitation_mm"], 0, 500)
        assert in_range(hour["temperature_c"], -60, 60)
    summary = body["summary"]
    assert summary["hours_with_data"] <= summary["hours_in_window"]
    assert in_range(summary["max_precipitation_probability_pct"], 0, 100)
