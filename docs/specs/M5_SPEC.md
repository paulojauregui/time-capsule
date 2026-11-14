# Milestone 5 Specification: FastAPI Service, Interactive Multi-Epoch UI & GitOps Delivery

## 1. Objective & Scope

Implement the FastAPI service and interactive web UI (`src/time_capsule/api/__init__.py`, `src/time_capsule/api/main.py`), comprehensive API integration tests (`tests/test_api.py`), multi-stage non-root `Dockerfile` (`USER 10001:10001`), base Kustomize manifests (`deploy/base/01-deployment.yaml`, `deploy/base/02-service.yaml`, `deploy/base/03-httproute.yaml`, `deploy/base/kustomizeconfig.yaml`, `deploy/base/kustomization.yaml`), and GitHub Actions CI/CD workflow (`.github/workflows/ci.yml`).

## 2. Non-Negotiable Engineering Invariants

1. **Absolute Imports Only**: Use `from time_capsule...` exclusively.
2. **Design by Contract (DbC)**: Every public class, method, route handler, and test function MUST include `Pre-conditions:` and `Post-conditions:` in its docstring.
3. **Static Typing**: Full type annotations passing `poetry run mypy src tests`.
4. **Zero Emojis**: Do not use any emojis in code, HTML UI, commit messages, or `.github/workflows/ci.yml`.
5. **Startup Auto-Seeding**: When the FastAPI app initializes (or lazily on first repository access if the DB is empty), it automatically seeds from `data/seeds/` so all 3 epochs (828 raw link lines, 14 Evergreen Canon items, 5 anchored HN discussions, vocabulary lexicon, and learning intents) are immediately available.

---

## 3. File-by-File Contracts

### 3.1 `src/time_capsule/api/main.py`

Implement `create_app(db_path: str | None = None, seed_dir: str | None = None) -> FastAPI` and module-level `app = create_app()`:

- Request/Response Pydantic schemas (with DbC docstrings):
  - `VaultImportRequest(BaseModel)`: `text: str`, `epoch_id: str = "2026_11_06"`
  - `AnalyzeRequest(BaseModel)`: `allow_llm: bool = True`, `allow_external_hydration: bool = False`
- Endpoints:
  1. `GET /healthz`: returns `{"status": "ok", "service": "time-capsule"}` (HTTP 200).
  2. `GET /ready`: verifies DuckDB connectivity and seed state, returning `{"status": "ready", "vault_count": count, "evergreen_count": 14}` (HTTP 200).
  3. `GET /api/v1/vault`: query params `epoch: str | None = None`, `is_evergreen_canon: bool | None = None`, `pillar: str | None = None`, `source_type: str | None = None`, `min_sentiment: float | None = None`, `search: str | None = None`, `limit: int = 1000`. Returns `{"count": len(items), "items": items}`.
  4. `GET /api/v1/epochs/summary`: returns longitudinal summary across `2023_2024`, `2026_08_16`, `2026_11_06`, pillar shifts, `evergreen_canon` (the 14 Evergreen Canon items), `anchored_hn_items`, and `taste_profile`.
  5. `POST /api/v1/vault/import`: accepts `VaultImportRequest`, parses the pasted Safari note text, merges with existing vault items in DuckDB, and returns `{"imported_raw_count": ..., "total_vault_items": ..., "evergreen_count": ...}`.
  6. `POST /api/v1/vault/{item_id}/analyze`: looks up `item_id` in DuckDB (returns 404 if not found), optionally hydrates HN/cultural metadata, runs `SparkDiscussionAnalyzer.analyze_item_async(..., allow_llm=req.allow_llm)`, persists the `DiscussionAnalysis` in DuckDB, and returns the `DiscussionAnalysis`.
  7. `GET /api/v1/intents`: query params `category: str | None = None`, `epoch: str | None = None`. Returns `{"count": ..., "intents": ...}`.
  8. `GET /api/v1/vocabulary`: query params `epoch: str | None = None`. Returns `{"count": ..., "vocabulary": ...}`.
  9. `GET /api/v1/digests`: returns list of stored `DailyCapsuleSnapshot` summaries and top `DiscussionAnalysis` items.
  10. `GET /api/v1/capsule/{capsule_date}`: returns the `DailyCapsuleSnapshot` for `capsule_date` (generating a deterministic snapshot on the fly if that date is not yet stored), including `markdown_digest` for publishing on `paulojauregui.com`.
  11. `GET /`: returns `HTMLResponse` rendering the interactive single-page web application with 4 tabs:
      - **Daily Tech Digest** (executive theses, community consensus, contrarian pushback, `#anchor_comment_id` spotlights, and 1-click Markdown copy/export for `paulojauregui.com`)
      - **3-Epoch Reading Vault & Evergreen Canon** (interactive filters by Epoch `2023_2024` / `2026_08_16` / `2026_11_06`, `Evergreen Canon (14)`, Intellectual Pillar 1–6, Source Type, Search box, Safari Note Import modal, and On-Demand `Analyze via DGX Spark` button)
      - **Personal Time Capsule** (Personal Vocabulary Lexicon with definitions, Active Technical Learning Intents vs. Personal Queries, and Longitudinal 3-Epoch Taste Shift visualization)
      - **Macro Time Machine** (Daily Weather Snapshot across Tokyo/NY/London/Beijing/Sydney + Market Equity OHLCV table)

### 3.2 `tests/test_api.py`

Write comprehensive `TestClient` tests verifying:
- `GET /healthz` and `GET /ready`
- `GET /` serves the HTML dashboard containing the 4 views
- `GET /api/v1/vault` (all items, filtered by `epoch=2023_2024`, `is_evergreen_canon=true` returning 14 items, `pillar=PILLAR_1_AI_LLM_AGENTS`, `source_type=hacker_news`)
- `GET /api/v1/epochs/summary` returns all 3 epochs and 14 Evergreen Canon items
- `POST /api/v1/vault/import` ingests a new Safari markdown snippet and updates counts
- `POST /api/v1/vault/{item_id}/analyze` synthesizes and persists a `DiscussionAnalysis`
- `GET /api/v1/intents` and `GET /api/v1/vocabulary`
- `GET /api/v1/digests` and `GET /api/v1/capsule/2026-11-06` (including `markdown_digest`)

### 3.3 `Dockerfile`, `deploy/base/*`, `.github/workflows/ci.yml`

- `Dockerfile`: multi-stage `python:3.13-slim-bookworm` image, installs via Poetry (`virtualenvs.in-project true`), copies `src` and `data/seeds`, creates `/app/data` owned by `10001:10001`, runs as `USER 10001:10001`, exposes port `8000`, healthcheck against `http://127.0.0.1:8000/healthz`, entrypoint `["python3", "-m", "time_capsule.api.main"]`.
- `deploy/base/`:
  - `01-deployment.yaml` (`time-capsule`, `runAsNonRoot: true`, `runAsUser: 10001`, `/healthz` and `/ready` probes, `TEMPORAL_HOST=temporal-frontend.temporal-system.svc.cluster.local:7233`, `SPARK_LLM_BASE_URL=http://happy.tail749110.ts.net:8000/v1`)
  - `02-service.yaml` (`app-service` port 80 -> `http` 8000)
  - `03-httproute.yaml` (`homelab-gateway` in namespace `argocd`, hostname `time-capsule.paulojauregui.com`)
  - `kustomizeconfig.yaml` and `kustomization.yaml`
- `.github/workflows/ci.yml`: matches `/home/tron/workspace/mainframe-app-template/.github/workflows/ci.yml` (zero emojis).
