"""Modular UI asset loader and static file mounting for the Digital Time Capsule dashboard.

Pre-conditions:
    - FastAPI must be installed and importable.
    - The templates/ and static/ asset directories must ship beside this module
      inside the time_capsule.api package.

Post-conditions:
    - Exposes resolved asset directory paths, a template loader for the dashboard
      shell, and a helper that mounts static assets on a FastAPI service.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

__all__ = [
    "API_DIR",
    "STATIC_DIR",
    "TEMPLATES_DIR",
    "get_static_dir",
    "get_templates_dir",
    "load_index_html",
    "mount_ui_assets",
]

API_DIR: Path = Path(__file__).resolve().parent
TEMPLATES_DIR: Path = API_DIR / "templates"
STATIC_DIR: Path = API_DIR / "static"

INDEX_HTML_FILENAME: str = "index.html"
STATIC_MOUNT_PATH: str = "/static"
STATIC_MOUNT_NAME: str = "static"


def get_templates_dir() -> Path:
    """Return the directory holding server-rendered HTML templates.

    Pre-conditions:
        - None.

    Post-conditions:
        - Returns the absolute templates directory path resolved relative to
          this module (never None, never a relative path).
    """
    return TEMPLATES_DIR


def get_static_dir() -> Path:
    """Return the directory holding static client assets (CSS, JavaScript).

    Pre-conditions:
        - None.

    Post-conditions:
        - Returns the absolute static assets directory path resolved relative
          to this module (never None, never a relative path).
    """
    return STATIC_DIR


def load_index_html() -> str:
    """Read and return the dashboard shell template as UTF-8 text.

    Pre-conditions:
        - templates/index.html must exist and be valid UTF-8 encoded text.

    Post-conditions:
        - Returns the full HTML document string for the single-page dashboard.
        - Raises OSError if the template is missing or unreadable.
    """
    index_path: Path = TEMPLATES_DIR / INDEX_HTML_FILENAME
    return index_path.read_text(encoding="utf-8")


def mount_ui_assets(service: FastAPI) -> None:
    """Mount the static asset directory on a FastAPI service at /static.

    Pre-conditions:
        - service must be an instantiated FastAPI application.
        - static/ must exist beside this module as a readable directory.

    Post-conditions:
        - The service serves files from STATIC_DIR under the /static route
          with the mount name "static"; no other routes are modified.
    """
    service.mount(
        STATIC_MOUNT_PATH,
        StaticFiles(directory=str(STATIC_DIR)),
        name=STATIC_MOUNT_NAME,
    )
