import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

import requests

from cache import get_ttl_cache, set_ttl_cache

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_TIMEOUT_SECONDS = 10
WEATHER_CACHE_TTL_SECONDS = 900


def _parse_hourly_entries(hourly_payload: dict[str, list[Any]]) -> list[dict[str, Any]]:
    times = hourly_payload.get("time", [])
    temperatures = hourly_payload.get("temperature_2m", [])
    wind_speeds = hourly_payload.get("wind_speed_10m", [])
    wind_gusts = hourly_payload.get("wind_gusts_10m", [])
    wind_directions = hourly_payload.get("wind_direction_10m", [])
    precipitation_probabilities = hourly_payload.get("precipitation_probability", [])
    humidities = hourly_payload.get("relative_humidity_2m", [])

    entries: list[dict[str, Any]] = []
    for index, time_value in enumerate(times):
        entries.append(
            {
                "time": time_value,
                "temperature_f": temperatures[index]
                if index < len(temperatures)
                else None,
                "wind_speed_mph": wind_speeds[index]
                if index < len(wind_speeds)
                else None,
                "wind_gust_mph": wind_gusts[index] if index < len(wind_gusts) else None,
                "wind_direction_degrees": wind_directions[index]
                if index < len(wind_directions)
                else None,
                "precipitation_probability_pct": (
                    precipitation_probabilities[index]
                    if index < len(precipitation_probabilities)
                    else None
                ),
                "humidity_pct": humidities[index] if index < len(humidities) else None,
            }
        )
    return entries


def _parse_daily_entries(
    daily_payload: dict[str, list[Any]],
) -> dict[str, dict[str, Any]]:
    times = daily_payload.get("time", [])
    max_temps = daily_payload.get("temperature_2m_max", [])
    min_temps = daily_payload.get("temperature_2m_min", [])

    entries: dict[str, dict[str, Any]] = {}
    for index, time_value in enumerate(times):
        entries[time_value] = {
            "temp_max_f": max_temps[index] if index < len(max_temps) else None,
            "temp_min_f": min_temps[index] if index < len(min_temps) else None,
        }
    return entries


def get_forecast_for_park(
    lat: float,
    lon: float,
    target_date: Optional[datetime.date] = None,
) -> dict[str, Any]:
    effective_date = target_date or datetime.date.today()
    cache_key = f"weather:{lat}:{lon}:{effective_date.isoformat()}"
    cached_forecast = get_ttl_cache(cache_key)
    if cached_forecast is not None:
        return cached_forecast

    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,wind_speed_10m,wind_gusts_10m,wind_direction_10m,precipitation_probability,relative_humidity_2m",
        "daily": "temperature_2m_max,temperature_2m_min",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "auto",
        "start_date": effective_date.isoformat(),
        "end_date": effective_date.isoformat(),
    }
    response = requests.get(
        OPEN_METEO_FORECAST_URL, params=params, timeout=OPEN_METEO_TIMEOUT_SECONDS
    )
    response.raise_for_status()

    payload = response.json()
    timezone_name = payload.get("timezone", "UTC")
    try:
        ZoneInfo(timezone_name)
    except Exception:
        timezone_name = "UTC"

    normalized_payload = {
        "timezone": timezone_name,
        "hourly": _parse_hourly_entries(payload.get("hourly", {})),
        "daily": _parse_daily_entries(payload.get("daily", {})),
    }
    return set_ttl_cache(cache_key, normalized_payload, WEATHER_CACHE_TTL_SECONDS)
