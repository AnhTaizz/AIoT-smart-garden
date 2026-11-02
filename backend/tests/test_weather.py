"""Open-Meteo adapter tests with a mocked provider; no network, DB or MQTT."""

import asyncio
import json
import math
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient

from app import weather
from app.auth import Session, require_session
from app.config import Settings
from app.main import app

NOW = datetime(2026, 11, 1, 10, 30, tzinfo=timezone.utc)
START = int(datetime(2026, 11, 1, 10, tzinfo=timezone.utc).timestamp())


def provider_body(hours=12, **overrides):
    hourly = {
        "time": [START + 3600 * index for index in range(hours)],
        "precipitation_probability": [5 * index for index in range(hours)],
        "precipitation": [0.5] * hours,
        "temperature_2m": [25.0] * hours,
    }
    hourly.update(overrides)
    return {"latitude": 21.0, "longitude": 105.875, "hourly": hourly}


def enabled_settings(**changes):
    return replace(Settings.from_env(), weather_enabled=True, weather_latitude=21.03,
                   weather_longitude=105.85, **changes)


def fake_app(settings, handler=None):
    state = SimpleNamespace(settings=settings)
    if handler:
        state.weather_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return SimpleNamespace(state=state)


def refreshed(handler, settings=None):
    """Run one refresh against the mocked provider; returns (app, ok, requests)."""
    requests = []

    def record(request):
        requests.append(request)
        return handler(request)

    app_ = fake_app(settings or enabled_settings(), record)

    async def run():
        try:
            return await weather.refresh(app_)
        finally:
            await app_.state.weather_client.aclose()

    return app_, asyncio.run(run()), requests


def test_valid_forecast_is_parsed_in_utc_and_summarized():
    app_, ok, requests = refreshed(lambda _: httpx.Response(200, json=provider_body()))
    assert ok
    query = requests[0].url.params
    assert str(requests[0].url).startswith(weather.PROVIDER_URL)
    assert query["latitude"] == "21.03" and query["longitude"] == "105.85"
    assert query["hourly"] == "precipitation_probability,precipitation,temperature_2m"
    assert query["forecast_hours"] == "12" and query["timeformat"] == "unixtime"

    # Pin "now" inside the fixed forecast window; the wall clock moves past START.
    app_.state.weather_cache.fetched_at = NOW
    out = weather.current_weather(app_, NOW + timedelta(minutes=1))
    assert out.status == "fresh" and out.reason is None and out.message is None
    assert out.kind == "forecast" and out.provider == "open-meteo"
    assert out.hours[0].time.tzinfo is not None and out.hours[0].time.utcoffset() == timedelta(0)
    assert out.valid_until == out.fetched_at + timedelta(seconds=7200)


def test_summary_uses_hourly_maximum_and_keeps_missing_hours_unknown():
    hours = weather.parse_forecast(provider_body(
        precipitation_probability=[20, None, 70, 10, 0, 5, 5, 90, 0, 0, 0, 0],
        precipitation=[0.2, 1.0, None, 0.0, 0.0, 0.3, 0.0, 9.9, 0, 0, 0, 0],
    ))
    assert hours[1].precipitation_probability_pct is None  # null stays null, never 0
    summary = weather.summarize(hours, NOW)
    # 10:30..16:30 overlaps the 10:00..16:00 slots; the 17:00 slot (90%) is outside.
    assert summary.hours_in_window == 7
    assert summary.hours_with_data == 5
    assert summary.max_precipitation_probability_pct == 70
    assert summary.total_precipitation_mm == 1.5


def test_summary_without_any_rain_data_is_unknown_not_zero():
    hours = weather.parse_forecast(provider_body(
        precipitation_probability=[None] * 12, precipitation=[None] * 12))
    summary = weather.summarize(hours, NOW)
    assert summary.max_precipitation_probability_pct is None
    assert summary.total_precipitation_mm is None
    assert summary.hours_with_data == 0


@pytest.mark.parametrize("body", [
    provider_body(precipitation=[0.5] * 11),
    provider_body(precipitation_probability=[101] + [0] * 11),
    provider_body(precipitation=[-1.0] + [0.0] * 11),
    provider_body(temperature_2m=[99.0] + [25.0] * 11),
    provider_body(time=[START] * 12),
    provider_body(time=[str(START)] + [START + 3600 * i for i in range(1, 12)]),
    provider_body(precipitation_probability=["10"] + [0] * 11),
    {"hourly": {}},
    {"error": True, "reason": "Latitude must be in range"},
    [],
])
def test_invalid_provider_bodies_are_rejected(body):
    with pytest.raises(ValueError):
        weather.parse_forecast(body)


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
def test_nan_and_infinity_are_rejected(token):
    raw = json.dumps(provider_body()).replace('"temperature_2m": [25.0', f'"temperature_2m": [{token}')
    _, ok, _ = refreshed(lambda _: httpx.Response(200, content=raw, headers={"content-type": "application/json"}))
    assert not ok


@pytest.mark.parametrize("handler,error", [
    (lambda _: httpx.Response(429, json={"reason": "limit"}), "provider_rate_limited"),
    (lambda _: httpx.Response(503, text="down"), "provider_error"),
    (lambda _: httpx.Response(200, text="<html>not json</html>"), "provider_invalid_response"),
    (lambda _: httpx.Response(200, json=provider_body(precipitation=[1.0])), "provider_invalid_response"),
])
def test_provider_failures_keep_previous_forecast(handler, error):
    app_, ok, _ = refreshed(lambda _: httpx.Response(200, json=provider_body()))
    assert ok
    previous = app_.state.weather_cache.hours
    fetched_at = app_.state.weather_cache.fetched_at
    app_.state.weather_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    assert not asyncio.run(weather.refresh(app_))
    cache = app_.state.weather_cache
    assert cache.hours is previous and cache.fetched_at == fetched_at
    assert cache.last_error == error
    # Within max age the kept forecast is still fresh; afterwards it is stale.
    assert weather.current_weather(app_, fetched_at + timedelta(minutes=5)).status == "fresh"
    stale = weather.current_weather(app_, fetched_at + timedelta(hours=3))
    assert stale.status == "stale" and stale.reason == error and stale.message


@pytest.mark.parametrize("error,code", [
    (httpx.ConnectTimeout("slow"), "provider_timeout"),
    (httpx.ConnectError("offline"), "provider_unreachable"),
])
def test_transport_errors_do_not_raise(error, code):
    def handler(request):
        raise error
    app_, ok, _ = refreshed(handler)
    assert not ok
    out = weather.current_weather(app_)
    assert out.status == "unavailable" and out.reason == code and out.hours == []


def test_disabled_and_unconfigured_never_call_provider():
    disabled = fake_app(Settings.from_env())
    assert weather.current_weather(disabled).status == "disabled"
    assert weather.current_weather(disabled).reason == "weather_disabled"
    missing = fake_app(replace(enabled_settings(), weather_longitude=None))
    assert weather.current_weather(missing).reason == "weather_not_configured"
    # run() returns at once instead of polling a provider it cannot use.
    asyncio.run(asyncio.wait_for(weather.run(missing), timeout=1))


def test_not_fetched_yet_is_unavailable():
    out = weather.current_weather(fake_app(enabled_settings()))
    assert out.status == "unavailable" and out.reason == "weather_not_fetched"


def test_past_hours_are_dropped_and_advisory_is_rain_only():
    app_, ok, _ = refreshed(lambda _: httpx.Response(200, json=provider_body()))
    assert ok
    # Pin "now" inside the forecast so the result does not depend on the wall clock.
    app_.state.weather_cache.fetched_at = NOW
    out = weather.current_weather(app_, NOW + timedelta(hours=2))
    assert out.hours[0].time == datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
    advisory = weather.advisory(app_, NOW + timedelta(minutes=10))
    assert advisory["status"] == "fresh" and advisory["kind"] == "forecast"
    assert "temperature_c" not in json.dumps(advisory, default=str)
    assert set(advisory) >= {"max_precipitation_probability_pct", "total_precipitation_mm", "window_start"}
    stale = weather.advisory(app_, NOW + timedelta(hours=3))
    assert stale == {"status": "stale", "reason": "weather_expired"}


@pytest.mark.parametrize("env,value", [
    ("WEATHER_ENABLED", "maybe"),
    ("WEATHER_LATITUDE", "91"),
    ("WEATHER_LONGITUDE", "nan"),
    ("WEATHER_REFRESH_SECONDS", "60"),
    ("WEATHER_MAX_AGE_SECONDS", "1000"),
])
def test_invalid_weather_configuration_fails_fast(monkeypatch, env, value):
    monkeypatch.setenv(env, value)
    with pytest.raises(ValueError):
        Settings.from_env()


def test_weather_configuration_defaults_off(monkeypatch):
    for name in ("WEATHER_ENABLED", "WEATHER_LATITUDE", "WEATHER_LONGITUDE"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings.from_env()
    assert not settings.weather_enabled
    assert settings.weather_latitude is None and settings.weather_longitude is None
    monkeypatch.setenv("WEATHER_ENABLED", "true")
    monkeypatch.setenv("WEATHER_LATITUDE", "21.03")
    monkeypatch.setenv("WEATHER_LONGITUDE", "105.85")
    settings = Settings.from_env()
    assert settings.weather_enabled and math.isclose(settings.weather_longitude, 105.85)


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setattr(app.state, "settings", enabled_settings(), raising=False)
    monkeypatch.setattr(app.state, "weather_cache", weather.WeatherCache(), raising=False)
    monkeypatch.setattr(app.state, "bridge", MagicMock(), raising=False)
    client = TestClient(app)  # No lifespan: the provider and DB stay isolated.
    yield client
    app.dependency_overrides.clear()
    client.close()


def test_weather_endpoint_requires_login(api):
    response = api.get("/weather")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "auth_required"


def test_weather_endpoint_serves_cache_to_any_session(api):
    app.dependency_overrides[require_session] = lambda: Session(
        "viewer1", "viewer", datetime.now(timezone.utc) + timedelta(hours=1), b"t" * 32
    )
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    hours = weather.parse_forecast(provider_body(time=[int(now.timestamp()) + 3600 * i for i in range(12)]))
    app.state.weather_cache.hours = hours
    app.state.weather_cache.fetched_at = datetime.now(timezone.utc)
    data = api.get("/weather").json()
    assert data["status"] == "fresh" and data["kind"] == "forecast"
    assert data["hours"][0]["time"].endswith("Z")
    assert data["summary"]["hours_in_window"] >= 6
    assert data["attribution"].startswith("Weather data by Open-Meteo.com")
