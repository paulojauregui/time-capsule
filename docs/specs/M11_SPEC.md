# Milestone M11 Specification: Container/Package Asset Verification & Architecture Documentation

## 1. Objective
Ensure non-Python frontend assets (`src/time_capsule/api/templates/*.html` and `src/time_capsule/api/static/*`) are explicitly included in Poetry package builds (`pyproject.toml`), update `ROADMAP.md` and `README.md` to document the Iteration 2 (`v2-ux`) UI/UX & Design System architecture and Milestones M06-M11, and run full end-to-end regression verification.

## 2. Target Files
1. `pyproject.toml`
2. `ROADMAP.md`
3. `README.md`

## 3. Exact Modifications
1. **`pyproject.toml`**:
   - Ensure `[tool.poetry]` includes `include = [{path = "src/time_capsule/api/templates/**/*", format = ["sdist", "wheel"]}, {path = "src/time_capsule/api/static/**/*", format = ["sdist", "wheel"]}]` so built wheels and container installs always package HTML templates and static CSS/JS assets.
2. **`ROADMAP.md`**:
   - Add Iteration 2 (`v2-ux`) Milestones (`M06` through `M11`) to the Milestone Status Matrix table and update the Architectural Verification Summary with the new test count and Gate 1/Gate 3 UX & Design System deliverables (`docs/UX_SPEC.md`, `docs/DESIGN_SYSTEM.md`, `docs/specs/M06_SPEC.md`..`M11_SPEC.md`).
3. **`README.md`**:
   - Update the architecture diagram and Serving/Frontend section to document the modular `v2-ux` frontend architecture (`templates/index.html`, `static/tokens.css`, `static/components.css`, `static/app.js`, `static/views.js`, `api/ui.py`), WCAG 2.2 AA keyboard navigation (`ArrowLeft`/`ArrowRight` tabs, `/` quick search, `Escape` modal focus restore), 5-state determinism (`Empty`, `Loading` `CLS=0` skeletons, `Nominal`, `Degraded/Offline` `heuristic-vader` banner, `Error` retry), and Archival Observatory design tokens (`tabular-nums`, Evergreen Canon amber reservation).
   - Zero emojis anywhere in `README.md` or `ROADMAP.md`.

## 4. Verification Command
`poetry run ruff check . && poetry run mypy src tests && poetry run pytest -v && kubectl kustomize deploy/base >/dev/null`
