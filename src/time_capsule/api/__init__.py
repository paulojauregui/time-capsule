"""FastAPI web service application package for Digital Time Capsule.

Pre-conditions:
    - FastAPI and dependencies installed.

Post-conditions:
    - Exports create_app factory and default app instance.
"""

from time_capsule.api.main import app, create_app

__all__ = ["app", "create_app"]
