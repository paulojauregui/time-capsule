"""Integration tests for the modular UI asset loader and FastAPI static serving contracts.

Pre-conditions:
    - pytest and fastapi.testclient must be available.
    - templates/index.html and static/tokens.css plus static/components.css must ship
      inside the time_capsule.api package.
    - Seed files must exist in data/seeds for the in-memory repository fixture.

Post-conditions:
    - Validates asset directory accessors, dashboard HTML serving at GET /,
      CSS asset serving at GET /static, static mount registration, and that
      src/time_capsule/api/main.py no longer embeds inline markup or styles.
"""

from pathlib import Path
from typing import Any

import pytest
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from starlette.routing import Mount

from time_capsule.api.main import create_app
from time_capsule.api.ui import (
    API_DIR,
    STATIC_DIR,
    TEMPLATES_DIR,
    get_static_dir,
    get_templates_dir,
    load_index_html,
)

MAIN_PY_PATH: Path = API_DIR / "main.py"
MAIN_PY_MAX_LINES: int = 460
EXPECTED_PACKAGE_LAYOUT: tuple[str, ...] = ("src", "time_capsule", "api")


@pytest.fixture(scope="module")
def ui_client() -> Any:
    """Fixture initializing a TestClient backed by an in-memory seeded repository.

    Pre-conditions:
        - Seed files exist in data/seeds.

    Post-conditions:
        - Yields a TestClient whose app has UI assets mounted at /static.
    """
    app = create_app(db_path=":memory:", seed_dir="data/seeds")
    with TestClient(app) as client:
        yield client


def test_get_templates_dir_resolves_to_package_templates() -> None:
    """Verify get_templates_dir exposes the packaged templates directory.

    Pre-conditions:
        - time_capsule.api package is importable.

    Post-conditions:
        - Returns the same path as TEMPLATES_DIR, is a directory named
          'templates', and lives beside main.py in the api package.
    """
    templates_dir: Path = get_templates_dir()

    assert templates_dir == TEMPLATES_DIR
    assert templates_dir.is_dir(), f"templates directory missing at {templates_dir}"
    assert templates_dir.name == "templates"
    assert templates_dir.parent == API_DIR
    assert tuple(templates_dir.parent.parts[-3:]) == EXPECTED_PACKAGE_LAYOUT


def test_get_static_dir_resolves_to_package_static() -> None:
    """Verify get_static_dir exposes the packaged static assets directory.

    Pre-conditions:
        - time_capsule.api package is importable.

    Post-conditions:
        - Returns the same path as STATIC_DIR, is a directory named 'static',
          and lives beside main.py in the api package.
    """
    static_dir: Path = get_static_dir()

    assert static_dir == STATIC_DIR
    assert static_dir.is_dir(), f"static directory missing at {static_dir}"
    assert static_dir.name == "static"
    assert static_dir.parent == API_DIR
    assert tuple(static_dir.parent.parts[-3:]) == EXPECTED_PACKAGE_LAYOUT


def test_load_index_html_returns_externalized_template() -> None:
    """Verify load_index_html reads the externalized templates/index.html document.

    Pre-conditions:
        - templates/index.html exists on disk.

    Post-conditions:
        - Returned text matches the on-disk file and contains the dashboard
          shell markers used by the 4 primary application tabs.
    """
    expected_text: str = (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")
    html_text: str = load_index_html()

    assert html_text == expected_text
    assert "<!DOCTYPE html>" in html_text
    assert 'href="/static/tokens.css"' in html_text
    assert 'href="/static/components.css"' in html_text


def test_render_dashboard_serves_html_200(ui_client: TestClient) -> None:
    """Verify GET / returns the externalized dashboard shell as HTML.

    Pre-conditions:
        - ui_client is available with assets mounted.

    Post-conditions:
        - Responds 200 OK with a text/html content type and body identical to
          templates/index.html including all 4 primary application tabs.
    """
    res = ui_client.get("/")

    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert res.text == load_index_html()
    for label in (
        "Daily Tech Digest",
        "3-Epoch Reading Vault",
        "Personal Time Capsule",
        "Macro Time Machine",
    ):
        assert label in res.text


def test_serves_tokens_css(ui_client: TestClient) -> None:
    """Verify GET /static/tokens.css serves the design token stylesheet.

    Pre-conditions:
        - ui_client is available with assets mounted.

    Post-conditions:
        - Responds 200 OK with a text/css content type and body matching
          static/tokens.css on disk.
    """
    res = ui_client.get("/static/tokens.css")

    assert res.status_code == 200
    assert "text/css" in res.headers["content-type"]
    assert res.text == (STATIC_DIR / "tokens.css").read_text(encoding="utf-8")


def test_serves_components_css(ui_client: TestClient) -> None:
    """Verify GET /static/components.css serves the component layout stylesheet.

    Pre-conditions:
        - ui_client is available with assets mounted.

    Post-conditions:
        - Responds 200 OK with a text/css content type and body matching
          static/components.css on disk.
    """
    res = ui_client.get("/static/components.css")

    assert res.status_code == 200
    assert "text/css" in res.headers["content-type"]
    assert res.text == (STATIC_DIR / "components.css").read_text(encoding="utf-8")


def test_static_mount_registered_on_service() -> None:
    """Verify create_app registers the /static StaticFiles mount.

    Pre-conditions:
        - Seed files exist in data/seeds.

    Post-conditions:
        - A Mount route named 'static' is present on the application router.
    """
    app = create_app(db_path=":memory:", seed_dir="data/seeds")
    mounts = [route for route in app.routes if isinstance(route, Mount)]

    static_mounts = [
        route
        for route in mounts
        if route.path == "/static" and route.name == "static" and isinstance(route.app, StaticFiles)
    ]
    assert len(static_mounts) == 1


def test_missing_static_asset_returns_404(ui_client: TestClient) -> None:
    """Verify unknown static paths are rejected rather than serving the shell.

    Pre-conditions:
        - ui_client is available with assets mounted.

    Post-conditions:
        - GET /static/does-not-exist.css responds 404.
    """
    res = ui_client.get("/static/does-not-exist.css")

    assert res.status_code == 404


def test_main_module_is_under_line_budget() -> None:
    """Verify main.py stayed lean after extracting the inline dashboard markup.

    Pre-conditions:
        - src/time_capsule/api/main.py exists.

    Post-conditions:
        - File contains fewer than 460 lines.
    """
    assert MAIN_PY_PATH.is_file(), f"main.py missing at {MAIN_PY_PATH}"
    line_count: int = len(MAIN_PY_PATH.read_text(encoding="utf-8").splitlines())

    assert line_count < MAIN_PY_MAX_LINES, f"main.py has {line_count} lines"


def test_main_module_embeds_no_inline_style_or_script() -> None:
    """Verify main.py no longer embeds raw style or script blocks.

    Pre-conditions:
        - src/time_capsule/api/main.py exists.

    Post-conditions:
        - Source contains no inline <style> or <script> markup and no INDEX_HTML
          string literal, proving the shell lives only in templates/index.html.
    """
    source: str = MAIN_PY_PATH.read_text(encoding="utf-8")

    assert "<style" not in source
    assert "</style>" not in source
    assert "<script" not in source
    assert "</script>" not in source
    assert "INDEX_HTML" not in source
