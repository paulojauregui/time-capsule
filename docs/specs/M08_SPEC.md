# Milestone M08 Specification: Modular UI Asset Loader, Static Mount & FastAPI Integration

## 1. Objective
Create the typed UI asset loader and static file mounting module `src/time_capsule/api/ui.py`, refactor `src/time_capsule/api/main.py` to remove the monolithic ~840-line inline `INDEX_HTML` constant while preserving 100% of existing REST endpoints and response schemas, and verify serving contracts in `tests/test_ui_serving.py`.

## 2. Target Files
1. `src/time_capsule/api/ui.py`
2. `src/time_capsule/api/main.py`
3. `tests/test_ui_serving.py`

## 3. Non-Negotiable Invariants
- **Preserve All Existing Endpoints & Tests**:
  - Every endpoint in `src/time_capsule/api/main.py` (`/healthz`, `/ready`, `/api/v1/vault`, `/api/v1/epochs/summary`, `/api/v1/vault/import`, `/api/v1/vault/{item_id}/analyze`, `/api/v1/intents`, `/api/v1/vocabulary`, `/api/v1/digests`, `/api/v1/capsule/{capsule_date}`, and `GET /`) must keep its exact route, query/body schema, and response payload structure.
  - All 8 existing API tests in `tests/test_api.py` must pass unmodified.
- **Modular UI Helper (`src/time_capsule/api/ui.py`)**:
  - Resolve asset paths strictly relative to `Path(__file__).resolve().parent`:
    - `API_DIR: Path = Path(__file__).resolve().parent`
    - `TEMPLATES_DIR: Path = API_DIR / "templates"`
    - `STATIC_DIR: Path = API_DIR / "static"`
  - Provide typed functions with Design-by-Contract docstrings (`Pre-conditions:` and `Post-conditions:`):
    - `get_templates_dir() -> Path`
    - `get_static_dir() -> Path`
    - `load_index_html() -> str`: Reads and returns `(TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")`.
    - `mount_ui_assets(service: FastAPI) -> None`: Mounts `STATIC_DIR` at `/static` using `fastapi.staticfiles.StaticFiles(directory=str(STATIC_DIR))` with `name="static"`.
- **Clean `src/time_capsule/api/main.py`**:
  - Remove the ~840-line inline `INDEX_HTML` string literal.
  - Import `load_index_html` and `mount_ui_assets` from `time_capsule.api.ui` (absolute import).
  - Call `mount_ui_assets(service)` inside `create_app(...)`.
  - In `render_dashboard()`, return `HTMLResponse(content=load_index_html(), status_code=status.HTTP_200_OK)`.
- **Python Standards**:
  - Absolute imports only (`from time_capsule...`).
  - Full type annotations (`mypy src tests` clean).
  - Zero emojis anywhere.

## 4. Verification Test Suite (`tests/test_ui_serving.py`)
Write deterministic tests in `tests/test_ui_serving.py` verifying:
1. `get_templates_dir()` and `get_static_dir()` point to existing directories under `src/time_capsule/api/`.
2. `GET /` returns `200 OK` with `text/html` content-type and serves the externalized `templates/index.html` template.
3. `GET /static/tokens.css` and `GET /static/components.css` return `200 OK` with `text/css` content-type.
4. `src/time_capsule/api/main.py` is under 460 lines and no longer embeds raw `<style>` or `<script>` blocks inline.
