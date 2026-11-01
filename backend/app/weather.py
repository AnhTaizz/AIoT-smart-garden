"""Read-only Open-Meteo forecast for the garden (W3; GET /weather agreed 2026-11-01).

- Advisory data only: this module never publishes MQTT, creates commands or
  changes the irrigation guards. A forecast is never a garden measurement.
- The provider URL is fixed here (no client- or env-supplied URL, no SSRF).
- One background task refreshes an in-memory cache; requests only read it, so
  the provider is never called per request or per telemetry message.
- A failed refresh keeps the previous forecast; its age alone decides
  fresh/stale. Stale/unavailable forecasts must not justify delaying watering.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Literal

import httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .auth import SessionDep
from .config import Settings

logger = logging.getLogger(__name__)
router = APIRouter()

PROVIDER = "open-meteo"
PROVIDER_URL = "https://api.open-meteo.com/v1/forecast"
ATTRIBUTION = "Weather data by Open-Meteo.com (CC BY 4.0)"
ATTRIBUTION_URL = "https://open-meteo.com/"
FORECAST_HOURS = 12
SUMMARY_HOURS = 6
RETRY_SECONDS = 300
HOUR = timedelta(hours=1)

WEATHER_ERRORS = {
    "weather_disabled": "Dự báo thời tiết đang tắt (WEATHER_ENABLED=false).",
    "weather_not_configured": "Chưa cấu hình tọa độ vườn (WEATHER_LATITUDE/WEATHER_LONGITUDE).",
    "weather_not_fetched": "Backend chưa lấy được dự báo thời tiết lần nào kể từ khi khởi động.",
    "weather_expired": "Dự báo đã quá hạn và chưa cập nhật được bản mới.",
    "provider_timeout": "Máy chủ thời tiết phản hồi quá lâu.",
    "provider_unreachable": "Không kết nối được máy chủ thời tiết.",
    "provider_rate_limited": "Máy chủ thời tiết đang giới hạn số lượt gọi.",
    "provider_error": "Máy chủ thời tiết trả lỗi.",
    "provider_invalid_response": "Dữ liệu thời tiết nhận về không hợp lệ.",
}

Probability = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]
Precipitation = Annotated[float, Field(ge=0, le=500, allow_inf_nan=False)]
Temperature = Annotated[float, Field(ge=-60, le=60, allow_inf_nan=False)]


class _ProviderHourly(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    time: list[int] = Field(min_length=1, max_length=48)
    precipitation_probability: list[Probability | None]
    precipitation: list[Precipitation | None]
    temperature_2m: list[Temperature | None]

    @model_validator(mode="after")
    def aligned(self) -> "_ProviderHourly":
        count = len(self.time)
        if any(len(values) != count for values in (
            self.precipitation_probability, self.precipitation, self.temperature_2m
        )):
            raise ValueError("hourly arrays must have the same length as time")
        if any(later <= earlier for earlier, later in zip(self.time, self.time[1:])):
            raise ValueError("hourly time must be strictly increasing")
        return self


class _ProviderForecast(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    hourly: _ProviderHourly


class WeatherHour(BaseModel):
    time: datetime
    precipitation_probability_pct: float | None
    precipitation_mm: float | None
    temperature_c: float | None


class WeatherSummary(BaseModel):
    window_start: datetime
    window_end: datetime
    hours_in_window: int
    # Hours with both rain probability and amount; missing hours stay unknown.
    hours_with_data: int
    # Highest hourly probability, NOT the chance of rain over the whole window.
    max_precipitation_probability_pct: float | None
    total_precipitation_mm: float | None


class WeatherOut(BaseModel):
    status: Literal["fresh", "stale", "unavailable", "disabled"]
    reason: str | None = None
    message: str | None = None
    provider: Literal["open-meteo"] = PROVIDER
    kind: Literal["forecast"] = "forecast"
    latitude: float | None = None
    longitude: float | None = None
    fetched_at: datetime | None = None
    valid_until: datetime | None = None
    summary: WeatherSummary | None = None
    hours: list[WeatherHour] = Field(default_factory=list)
    attribution: str = ATTRIBUTION
    attribution_url: str = ATTRIBUTION_URL


@dataclass
class WeatherCache:
    hours: list[WeatherHour] = field(default_factory=list)
    fetched_at: datetime | None = None
    last_error: str | None = None


def parse_forecast(data: Any) -> list[WeatherHour]:
    """Validate the provider body; raises ValueError/ValidationError if unusable."""
    hourly = _ProviderForecast.model_validate(data).hourly
    return [
        WeatherHour(
            time=datetime.fromtimestamp(stamp, timezone.utc),
            precipitation_probability_pct=probability,
            precipitation_mm=amount,
            temperature_c=temperature,
        )
        for stamp, probability, amount, temperature in zip(
            hourly.time, hourly.precipitation_probability, hourly.precipitation, hourly.temperature_2m
        )
    ]


def configured(settings: Settings) -> bool:
    return (
        settings.weather_enabled
        and settings.weather_latitude is not None
        and settings.weather_longitude is not None
    )


def weather_cache(app: Any) -> WeatherCache:
    cache = getattr(app.state, "weather_cache", None)
    if cache is None:
        cache = WeatherCache()
        app.state.weather_cache = cache
    return cache


def summarize(hours: list[WeatherHour], now: datetime) -> WeatherSummary:
    start, end = now, now + timedelta(hours=SUMMARY_HOURS)
    # An hourly value covers [time, time + 1h); count every hour that overlaps.
    window = [hour for hour in hours if hour.time < end and hour.time + HOUR > start]
    probabilities = [h.precipitation_probability_pct for h in window if h.precipitation_probability_pct is not None]
    amounts = [h.precipitation_mm for h in window if h.precipitation_mm is not None]
    return WeatherSummary(
        window_start=start,
        window_end=end,
        hours_in_window=len(window),
        hours_with_data=sum(
            1 for h in window if h.precipitation_probability_pct is not None and h.precipitation_mm is not None
        ),
        max_precipitation_probability_pct=max(probabilities) if probabilities else None,
        total_precipitation_mm=round(sum(amounts), 2) if amounts else None,
    )


def current_weather(app: Any, now: datetime | None = None) -> WeatherOut:
    weather = _current_weather(app, now or datetime.now(timezone.utc))
    weather.message = WEATHER_ERRORS.get(weather.reason) if weather.reason else None
    return weather


def _current_weather(app: Any, now: datetime) -> WeatherOut:
    settings: Settings = app.state.settings
    if not settings.weather_enabled:
        return WeatherOut(status="disabled", reason="weather_disabled")
    if not configured(settings):
        return WeatherOut(status="disabled", reason="weather_not_configured")
    cache = weather_cache(app)
    out = WeatherOut(
        status="unavailable",
        reason=cache.last_error or "weather_not_fetched",
        latitude=settings.weather_latitude,
        longitude=settings.weather_longitude,
    )
    if cache.fetched_at is None:
        return out
    out.fetched_at = cache.fetched_at
    out.valid_until = cache.fetched_at + timedelta(seconds=settings.weather_max_age_seconds)
    out.hours = [hour for hour in cache.hours if hour.time + HOUR > now]
    out.summary = summarize(out.hours, now)
    if now >= out.valid_until:
        out.status, out.reason = "stale", cache.last_error or "weather_expired"
    else:
        # A failed refresh does not hide a forecast that is still within max age.
        out.status, out.reason = "fresh", None
    return out


def advisory(app: Any, now: datetime | None = None) -> dict[str, Any]:
    """Compact forecast for AI prompts: rain fields only, and only when fresh."""
    weather = current_weather(app, now)
    if weather.status != "fresh" or weather.summary is None:
        return {"status": weather.status, "reason": weather.reason}
    return {
        "status": "fresh",
        "kind": "forecast",
        "provider": PROVIDER,
        "fetched_at": weather.fetched_at,
        **weather.summary.model_dump(),
    }


async def refresh(app: Any) -> bool:
    settings: Settings = app.state.settings
    cache = weather_cache(app)
    params = {
        "latitude": settings.weather_latitude,
        "longitude": settings.weather_longitude,
        "hourly": "precipitation_probability,precipitation,temperature_2m",
        "forecast_hours": FORECAST_HOURS,
        "timeformat": "unixtime",
    }
    try:
        response = await app.state.weather_client.get(
            PROVIDER_URL, params=params, timeout=settings.weather_timeout_seconds
        )
        if response.status_code == 429:
            error = "provider_rate_limited"
        elif not response.is_success:
            error = "provider_error"
        else:
            cache.hours = parse_forecast(response.json())
            cache.fetched_at = datetime.now(timezone.utc)
            cache.last_error = None
            return True
    except httpx.TimeoutException:
        error = "provider_timeout"
    except httpx.RequestError:
        error = "provider_unreachable"
    except (ValueError, ValidationError):
        # Malformed JSON, NaN/Infinity, out-of-range or misaligned arrays.
        error = "provider_invalid_response"
    cache.last_error = error
    logger.warning("Weather refresh failed: %s; keeping the previous forecast", error)
    return False


async def run(app: Any) -> None:
    settings: Settings = app.state.settings
    if not configured(settings):
        logger.info("Weather forecast disabled or not configured")
        return
    while True:
        delay = settings.weather_refresh_seconds
        try:
            if not await refresh(app):
                delay = min(delay, RETRY_SECONDS)
        except Exception as error:
            logger.warning("Weather refresh crashed: %s", type(error).__name__)
            delay = min(delay, RETRY_SECONDS)
        await asyncio.sleep(delay)


@router.get("/weather", response_model=WeatherOut)
async def get_weather(request: Request, _session: SessionDep) -> WeatherOut:
    return current_weather(request.app)
