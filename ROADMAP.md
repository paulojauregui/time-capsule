# Project Roadmap: Digital Time Capsule & Daily Tech Discussion Digest (`time-capsule`)

This roadmap tracks the end-to-end engineering progression of `time-capsule` from its legacy Phase 1 prototype to a production-grade autonomous reading vault lakehouse and discussion synthesis service on `mainframe`.

---

## Milestone Status Matrix

| Milestone | Scope & Key Deliverables | Target Modules | Verification Gate | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 1 (Legacy)** | Initial prototype for weather and equity tickers. | `weather_assets.py`, `financial_assets.py`, `resources.py` | Initial `pytest` suite | Completed |
| **Milestone 1** | **PM, Architecture ADR & Multi-Epoch Safari Vault Parser**<br/>- Author `docs/PRD.md`, `docs/adr/0001-*.md`, `ROADMAP.md`<br/>- Pydantic domain schemas (`models.py`) + 6 Intellectual Pillars<br/>- Multi-epoch Safari parser (`safari_parser.py`) across `2023_2024`, `2026_08_16`, `2026_11_06`<br/>- Canonical URL deduplication, 14 Evergreen Canon items, HN `#anchor_comment_id` extraction, Vocabulary vs. Learning Intent classification | `src/time_capsule/models.py`<br/>`src/time_capsule/safari_parser.py`<br/>`tests/test_safari_parser.py` | `pytest`, `ruff`, `mypy` | Completed |
| **Milestone 2** | **HN Discussion Tree Hydration, Reddit/Article Scraper & Macro Assets**<br/>- Refactor `weather_assets.py` & `financial_assets.py` to strict DbC & `mypy`<br/>- Implement `HNClient` (`news_assets.py`) for Algolia item hydration, comment trees, and recursive `#anchor_comment_id` sub-thread isolation<br/>- Implement `cultural_assets.py` for Reddit `.json` & clean article metadata extraction | `src/time_capsule/weather_assets.py`<br/>`src/time_capsule/financial_assets.py`<br/>`src/time_capsule/news_assets.py`<br/>`src/time_capsule/cultural_assets.py`<br/>`tests/test_assets.py` | `pytest`, `ruff`, `mypy` | Completed |
| **Milestone 3** | **DGX Spark LLM Discussion Analyzer, Sentiment Engine & Taste Profile**<br/>- Hybrid VADER (`vaderSentiment`) + async client targeting DGX Spark vLLM (`happy.tail749110.ts.net:8000`, `nvidia/Qwen3.8-Flash-Next-FP4-Local`)<br/>- Zero-retry circuit breaker probe (< 2.0s) with deterministic heuristic fallback<br/>- Structured `DiscussionAnalysis` & 6-Pillar longitudinal taste profile distribution | `src/time_capsule/enrichment.py`<br/>`tests/test_enrichment.py` | `pytest`, `ruff`, `mypy` | Completed |
| **Milestone 4** | **DuckDB / Lakehouse Repository & Temporal Workflows**<br/>- DuckDB Lakehouse repository (`repository.py`) with Parquet export and multi-parameter filtering<br/>- Temporal workflows (`workflows.py`): `BackfillSafariVaultWorkflow` & `DailyDigestCapsuleWorkflow`<br/>- Standalone in-process CLI execution pipeline and auto-seeding | `src/time_capsule/repository.py`<br/>`src/time_capsule/workflows.py`<br/>`tests/test_repository_workflows.py` | `pytest`, `ruff`, `mypy` | Completed |
| **Milestone 5** | **FastAPI Service, Interactive Multi-Epoch UI & GitOps Delivery**<br/>- FastAPI REST API (`api/main.py`) with `/healthz`, `/ready`, `/api/v1/vault`, `/api/v1/epochs/summary`, `/api/v1/capsule/{date}`, and Markdown export<br/>- Interactive single-page web UI at `/` (Daily Tech Digest, 3-Epoch Reading Vault, Personal Time Capsule, Macro Time Machine)<br/>- Hardened multi-stage `Dockerfile` (`USER 10001:10001`), `deploy/base/` Kustomize manifests, `.github/workflows/ci.yml` | `src/time_capsule/api/main.py`<br/>`Dockerfile`<br/>`deploy/base/*`<br/>`.github/workflows/ci.yml`<br/>`tests/test_api.py` | Full E2E `pytest`, `ruff`, `mypy`, `kubectl kustomize` | Completed |

---

## Architectural Verification Summary

All 5 milestones have passed strict verification gates:
- Unit and integration test suite: 45 passed in < 4.0s (`pytest -v`).
- Static lint checks: 0 errors (`ruff check .`).
- Static type analysis: 0 errors across 20 source files (`mypy src tests`).
- GitOps Kustomize build: Clean rendering with Gateway API `HTTPRoute` (`kubectl kustomize deploy/base`).
