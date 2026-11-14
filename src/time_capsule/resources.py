"""API resources and external service configurations for Dagster assets.

Pre-conditions:
    - Dagster environment initializes with configured or default resource values.

Post-conditions:
    - Exposes APIResource class with configurable service keys.
"""

from dagster import ConfigurableResource


class APIResource(ConfigurableResource):
    """Dagster configurable resource providing API keys for external services.

    Pre-conditions:
        - If provided, API keys must be strings or None.
        - Defaults are empty strings to permit offline instantiation.

    Post-conditions:
        - Exposes openweathermap_api_key and alphavantage_api_key fields.
    """

    openweathermap_api_key: str | None = ""
    alphavantage_api_key: str | None = ""
