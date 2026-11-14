"""Unit tests for financial assets and equity observation ingestion.

Pre-conditions:
    - Pytest framework and time_capsule.financial_assets must be importable.

Post-conditions:
    - Validates mocked Alpha Vantage responses, fallback records, and rate limit error handling.
"""

from unittest.mock import MagicMock

import pandas as pd
import pytest

from time_capsule.financial_assets import (
    TICKERS,
    fetch_stock_records,
    get_fallback_stock_records,
    raw_stock_data,
)
from time_capsule.resources import APIResource


def test_raw_stock_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the raw_stock_data asset by mocking the Alpha Vantage API call.

    Pre-conditions:
        - requests.get monkeypatched to return synthetic time series data.

    Post-conditions:
        - Verifies that raw_stock_data returns a DataFrame with expected tickers and prices.
    """
    mock_api_data = {
        "Time Series (Daily)": {
            "2025-10-01": {
                "1. open": "150.00",
                "2. high": "155.00",
                "3. low": "149.00",
                "4. close": "154.50",
                "5. volume": "1234567",
            }
        }
    }

    def mock_get(url: str, timeout: float = 10.0) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = mock_api_data
        return mock_resp

    monkeypatch.setattr("time_capsule.financial_assets.requests.get", mock_get)

    mock_api_resource = APIResource(
        openweathermap_api_key="dummy_weather_key",
        alphavantage_api_key="dummy_stock_key",
    )

    result_df = raw_stock_data(api=mock_api_resource)

    assert isinstance(result_df, pd.DataFrame)
    assert len(result_df) == len(TICKERS)
    assert "ticker" in result_df.columns
    assert result_df.iloc[0]["close"] == 154.50


def test_fetch_stock_records_missing_key() -> None:
    """Test that fetch_stock_records raises ValueError when api_key is missing.

    Pre-conditions:
        - Empty string or None provided as api_key.

    Post-conditions:
        - Confirms ValueError is raised.
    """
    with pytest.raises(ValueError, match="ALPHAVANTAGE_API_KEY environment variable not set."):
        fetch_stock_records(api_key="")


def test_fetch_stock_records_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that fetch_stock_records raises ConnectionError when API rate limit note is returned.

    Pre-conditions:
        - Mocked API response returns a Note indicating limit reached.

    Post-conditions:
        - Asserts ConnectionError is raised.
    """
    def mock_get(url: str, timeout: float = 10.0) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"Note": "Thank you for using Alpha Vantage! Call frequency is 5 calls per minute."}
        return mock_resp

    monkeypatch.setattr("time_capsule.financial_assets.requests.get", mock_get)

    with pytest.raises(ConnectionError, match="Alpha Vantage API limit reached"):
        fetch_stock_records(api_key="valid_key")


def test_get_fallback_stock_records() -> None:
    """Test that get_fallback_stock_records returns deterministic records for all tickers.

    Pre-conditions:
        - Valid target_date string.

    Post-conditions:
        - Verifies length matches TICKERS and contains required OHLCV numeric fields.
    """
    records = get_fallback_stock_records("2026-11-06")
    assert len(records) == len(TICKERS)
    tickers_found = {r["ticker"] for r in records}
    assert tickers_found == set(TICKERS)
    for r in records:
        assert r["date"] == "2026-11-06"
        assert r["open"] > 0
        assert r["close"] > 0
        assert r["volume"] > 0
