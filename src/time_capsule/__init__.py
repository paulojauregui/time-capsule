"""Digital Time Capsule Dagster definitions and asset package.

Pre-conditions:
    - Ingest modules cultural_assets, financial_assets, news_assets, and weather_assets must be importable.

Post-conditions:
    - Exposes dagster Definitions instance 'defs' configured with DuckDB and API resources.
"""

import os

from dagster import Definitions, load_assets_from_modules
from dagster_duckdb_pandas import DuckDBPandasIOManager

from time_capsule import cultural_assets, financial_assets, news_assets, weather_assets
from time_capsule.resources import APIResource

all_assets = load_assets_from_modules(
    [cultural_assets, financial_assets, news_assets, weather_assets]
)

defs = Definitions(
    assets=all_assets,
    resources={
        "io_manager": DuckDBPandasIOManager(
            database="data/time_capsule.duckdb",
            schema="main",
        ),
        "api": APIResource(
            openweathermap_api_key=os.getenv("OPENWEATHERMAP_API_KEY", ""),
            alphavantage_api_key=os.getenv("ALPHAVANTAGE_API_KEY", ""),
        ),
    },
)
