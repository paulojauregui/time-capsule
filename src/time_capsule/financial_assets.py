"""Financial market assets and equity telemetry ingestion via Alpha Vantage.

Pre-conditions:
    - APIResource configured with valid Alpha Vantage API key or fallback mock data.

Post-conditions:
    - Provides financial ingestion assets and normalized daily OHLCV equity records.
"""

from typing import Any

import pandas as pd
import requests
from dagster import asset

from time_capsule.resources import APIResource

__all__ = [
    "APIResource",
    "TICKERS",
    "fetch_stock_records",
    "get_fallback_stock_records",
    "raw_stock_data",
]

TICKERS: list[str] = ["AAPL", "MSFT", "GOOG", "AMZN", "NVDA"]


def get_fallback_stock_records(target_date: str = "2026-11-06") -> list[dict[str, Any]]:
    """Return deterministic baseline OHLCV equity market records across target tickers.

    Pre-conditions:
        - target_date must be a valid non-empty date string.

    Post-conditions:
        - Returns a list of standardized equity observation dictionaries.
    """
    baseline_quotes: dict[str, dict[str, float]] = {
        "AAPL": {"open": 225.0, "high": 228.5, "low": 224.1, "close": 227.6, "volume": 45000000},
        "MSFT": {"open": 415.0, "high": 420.2, "low": 413.5, "close": 418.0, "volume": 21000000},
        "GOOG": {"open": 175.0, "high": 178.0, "low": 174.2, "close": 176.8, "volume": 18000000},
        "AMZN": {"open": 188.0, "high": 191.5, "low": 186.9, "close": 190.2, "volume": 32000000},
        "NVDA": {"open": 140.0, "high": 144.5, "low": 139.2, "close": 143.1, "volume": 55000000},
    }

    records: list[dict[str, Any]] = []
    for ticker in TICKERS:
        quote = baseline_quotes.get(
            ticker,
            {"open": 100.0, "high": 105.0, "low": 99.0, "close": 102.5, "volume": 1000000},
        )
        records.append(
            {
                "ticker": ticker,
                "date": target_date,
                "open": quote["open"],
                "high": quote["high"],
                "low": quote["low"],
                "close": quote["close"],
                "volume": int(quote["volume"]),
            }
        )

    return records


def fetch_stock_records(
    api_key: str | None = None, timeout: float = 10.0
) -> list[dict[str, Any]]:
    """Fetch daily time series equity observations via Alpha Vantage API.

    Pre-conditions:
        - timeout must be strictly greater than zero.

    Post-conditions:
        - Returns list of processed OHLCV dictionaries if api_key is valid.
        - Raises ValueError if api_key is missing or empty.
        - Raises ConnectionError if Alpha Vantage API rate limit message is received.
    """
    if not api_key:
        raise ValueError("ALPHAVANTAGE_API_KEY environment variable not set.")

    all_stock_data: list[dict[str, Any]] = []

    for ticker in TICKERS:
        url = (
            f"https://www.alphavantage.co/query?"
            f"function=TIME_SERIES_DAILY&symbol={ticker}&apikey={api_key}"
        )

        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        if "Note" in data:
            raise ConnectionError(f"Alpha Vantage API limit reached: {data['Note']}")

        time_series = data.get("Time Series (Daily)", {})
        latest_day = next(iter(time_series.keys()), None)
        if latest_day:
            daily_data = time_series[latest_day]
            processed_data = {
                "ticker": ticker,
                "date": latest_day,
                "open": float(daily_data.get("1. open", 0.0)),
                "high": float(daily_data.get("2. high", 0.0)),
                "low": float(daily_data.get("3. low", 0.0)),
                "close": float(daily_data.get("4. close", 0.0)),
                "volume": int(daily_data.get("5. volume", 0)),
            }
            all_stock_data.append(processed_data)

    return all_stock_data


@asset
def raw_stock_data(api: APIResource) -> pd.DataFrame:
    """Dagster asset retrieving daily stock indicators into a Pandas DataFrame.

    Pre-conditions:
        - api resource must provide alphavantage_api_key.

    Post-conditions:
        - Returns pandas DataFrame containing daily financial metrics for configured tickers.
    """
    records = fetch_stock_records(api.alphavantage_api_key)
    return pd.DataFrame(records)
