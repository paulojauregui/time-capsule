"""Unit tests for weather assets and meteorological telemetry ingestion.

Pre-conditions:
    - Pytest framework and time_capsule.weather_assets must be importable.

Post-conditions:
    - Validates mocked OpenWeatherMap ingestion, fallback records, and missing key error handling.
"""

from unittest.mock import MagicMock

import pandas as pd
import pytest

from time_capsule.resources import APIResource
from time_capsule.weather_assets import (
    CITIES,
    fetch_weather_records,
    get_fallback_weather_records,
    raw_weather_data,
)


def test_raw_weather_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the raw_weather_data asset by mocking the requests.get call.

    Pre-conditions:
        - requests.get is monkeypatched to return synthetic OpenWeatherMap payloads.

    Post-conditions:
        - Verifies that raw_weather_data produces a DataFrame with 5 city rows and expected temperatures.
    """
    mock_api_data: dict[str, dict[str, object]] = {
        "Tokyo": {"main": {"temp": 15.0}, "city": "Tokyo"},
        "New York": {"main": {"temp": 12.0}, "city": "New York"},
    }

    def mock_get(url: str, timeout: float = 10.0) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None

        if "lat=35.68" in url:
            mock_resp.json.return_value = mock_api_data["Tokyo"]
        elif "lat=40.71" in url:
            mock_resp.json.return_value = mock_api_data["New York"]
        else:
            mock_resp.json.return_value = {"main": {"temp": 10.0}}

        return mock_resp

    monkeypatch.setattr("time_capsule.weather_assets.requests.get", mock_get)

    mock_api_resource = APIResource(
        openweathermap_api_key="dummy_weather_key",
        alphavantage_api_key="dummy_stock_key",
    )

    result_df = raw_weather_data(api=mock_api_resource)

    assert isinstance(result_df, pd.DataFrame)
    assert len(result_df) == len(CITIES)
    assert "city" in result_df.columns
    assert result_df.loc[result_df["city"] == "Tokyo"]["temp"].iloc[0] == 15.0


def test_fetch_weather_records_missing_key() -> None:
    """Test that fetch_weather_records raises ValueError when api_key is empty or None.

    Pre-conditions:
        - None or empty string provided as api_key.

    Post-conditions:
        - Confirms ValueError is raised.
    """
    with pytest.raises(ValueError, match="OPENWEATHERMAP_API_KEY environment variable not set."):
        fetch_weather_records(api_key="")

    with pytest.raises(ValueError, match="OPENWEATHERMAP_API_KEY environment variable not set."):
        fetch_weather_records(api_key=None)


def test_get_fallback_weather_records() -> None:
    """Test that get_fallback_weather_records returns valid baseline records for all benchmark cities.

    Pre-conditions:
        - None.

    Post-conditions:
        - Verifies records list has length matching CITIES and contains required metric keys.
    """
    records = get_fallback_weather_records()
    assert len(records) == len(CITIES)
    city_names = {r["city"] for r in records}
    assert "Tokyo" in city_names
    assert "New York" in city_names
    assert "London" in city_names
    assert "Beijing" in city_names
    assert "Sydney" in city_names
    for r in records:
        assert "temp" in r
        assert "humidity" in r
        assert "pressure" in r
