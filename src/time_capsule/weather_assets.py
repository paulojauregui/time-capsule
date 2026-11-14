"""Weather assets and OpenWeatherMap telemetry ingestion.

Pre-conditions:
    - Configured APIResource containing valid OpenWeatherMap credentials or fallback mode.

Post-conditions:
    - Provides raw weather ingestion assets and normalized global city observations.
"""

from typing import Any

import pandas as pd
import requests
from dagster import asset

from time_capsule.resources import APIResource

# Re-export APIResource for backwards compatibility with tests
__all__ = [
    "APIResource",
    "CITIES",
    "fetch_weather_records",
    "get_fallback_weather_records",
    "raw_weather_data",
]

# A list of major world cities with their lat/lon coordinates
CITIES: dict[str, tuple[float, float]] = {
    "Tokyo": (35.68, 139.69),
    "New York": (40.71, -74.00),
    "London": (51.50, -0.12),
    "Beijing": (39.90, 116.40),
    "Sydney": (-33.86, 151.20),
}


def get_fallback_weather_records() -> list[dict[str, Any]]:
    """Return deterministic baseline weather records across canonical benchmark cities.

    Pre-conditions:
        - None.

    Post-conditions:
        - Returns a list of 5 standardized city weather telemetry dictionaries.
    """
    baseline_telemetry: dict[str, dict[str, Any]] = {
        "Tokyo": {"temp": 16.5, "humidity": 55, "pressure": 1014, "weather_main": "Clear"},
        "New York": {"temp": 12.0, "humidity": 60, "pressure": 1018, "weather_main": "Clouds"},
        "London": {"temp": 10.2, "humidity": 78, "pressure": 1011, "weather_main": "Drizzle"},
        "Beijing": {"temp": 8.5, "humidity": 40, "pressure": 1022, "weather_main": "Haze"},
        "Sydney": {"temp": 22.0, "humidity": 65, "pressure": 1016, "weather_main": "Clear"},
    }

    now = pd.Timestamp.now(tz="UTC")
    records: list[dict[str, Any]] = []

    for city, (lat, lon) in CITIES.items():
        base = baseline_telemetry.get(
            city, {"temp": 15.0, "humidity": 50, "pressure": 1013, "weather_main": "Clear"}
        )
        records.append(
            {
                "city": city,
                "lat": lat,
                "lon": lon,
                "timestamp": now,
                "temp": base["temp"],
                "feels_like": base["temp"] - 1.0,
                "temp_min": base["temp"] - 2.0,
                "temp_max": base["temp"] + 2.0,
                "pressure": base["pressure"],
                "humidity": base["humidity"],
                "wind_speed": 4.5,
                "wind_deg": 180,
                "weather_main": base["weather_main"],
                "weather_description": f"{base['weather_main'].lower()} sky",
                "country": "FALLBACK",
            }
        )

    return records


def fetch_weather_records(
    api_key: str | None = None, timeout: float = 10.0
) -> list[dict[str, Any]]:
    """Fetch live meteorological telemetry for canonical benchmark cities via OpenWeatherMap.

    Pre-conditions:
        - timeout must be greater than zero.

    Post-conditions:
        - Returns list of dictionary records if api_key is valid.
        - Raises ValueError if api_key is None or empty.
    """
    if not api_key:
        raise ValueError("OPENWEATHERMAP_API_KEY environment variable not set.")

    processed_data: list[dict[str, Any]] = []

    for city, (lat, lon) in CITIES.items():
        url = (
            f"https://api.openweathermap.org/data/2.5/weather?"
            f"lat={lat}&lon={lon}&appid={api_key}&units=metric"
        )
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()

        data = response.json()
        coord = data.get("coord") if isinstance(data.get("coord"), dict) else {}
        main = data.get("main") if isinstance(data.get("main"), dict) else {}
        wind = data.get("wind") if isinstance(data.get("wind"), dict) else {}
        weather_list = data.get("weather") if isinstance(data.get("weather"), list) else [{}]
        weather_first = weather_list[0] if weather_list else {}
        sys_info = data.get("sys") if isinstance(data.get("sys"), dict) else {}

        raw_dt = data.get("dt")
        timestamp = (
            pd.to_datetime(raw_dt, unit="s")
            if raw_dt is not None
            else pd.Timestamp.now(tz="UTC")
        )

        processed_data.append(
            {
                "city": city,
                "lat": coord.get("lat", lat),
                "lon": coord.get("lon", lon),
                "timestamp": timestamp,
                "temp": main.get("temp"),
                "feels_like": main.get("feels_like"),
                "temp_min": main.get("temp_min"),
                "temp_max": main.get("temp_max"),
                "pressure": main.get("pressure"),
                "humidity": main.get("humidity"),
                "wind_speed": wind.get("speed"),
                "wind_deg": wind.get("deg"),
                "weather_main": weather_first.get("main"),
                "weather_description": weather_first.get("description"),
                "country": sys_info.get("country"),
            }
        )

    return processed_data


@asset
def raw_weather_data(api: APIResource) -> pd.DataFrame:
    """Dagster asset fetching world city weather telemetry into a Pandas DataFrame.

    Pre-conditions:
        - api resource must provide openweathermap_api_key.

    Post-conditions:
        - Returns pandas DataFrame containing observations for all benchmark cities.
    """
    records = fetch_weather_records(api.openweathermap_api_key)
    return pd.DataFrame(records)
