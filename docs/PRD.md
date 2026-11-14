# Product Requirements Document (PRD): Digital Time Capsule & Multi-Epoch Tech Discussion Digest (`time-capsule`)

**Status**: Approved  
**Owner**: Principal Product Manager (`tron-agent-mainframe[bot]`)  
**Target Platform**: `mainframe` K3s Homelab (`time-capsule.paulojauregui.com`) + Local DGX Spark (`happy.tail749110.ts.net:8000`)  
**Version**: 2.0.0  

---

## 1. Executive Summary & Product Vision

`time-capsule` evolves from a static Phase 1 macro-indicator pipeline into a longitudinal **Personal Intellectual Time Capsule & Daily Tech Discussion Digest**. By combining automated daily macro snapshots (global weather across key cities, major market indices/equities, and front-page engineering discussions) with a curated **Multi-Epoch Safari Reading Vault** spanning three distinct snapshots of Paulo Jauregui's browser tabs and bookmarks (`2023_2024`, `2026_08_16`, `2026_11_06`), `time-capsule` preserves both the external state of the world and the internal trajectory of a software and AI infrastructure engineer's intellectual curiosity over time.

Instead of treating bookmarks and open tabs as a graveyard of unread URLs, `time-capsule` treats browser exports as a high-signal longitudinal dataset:
1. **Cross-Epoch Survival & Evergreen Canon**: Links that survive tab purges across all three epochs (`cross_epoch_count == 3`) are automatically elevated to the **Evergreen Canon** (14 foundational works on SRE, distributed systems, neural networks, calm technology, and life stages).
2. **Deep Comment-Tree & Anchor Spotlight**: Hacker News links—especially those bookmarked with specific `#comment_id` fragments (`#50014121`, `#46143525`, `#47473516`, `#49593756`, `#50140985`) or saved as untitled `[Hacker News]` tabs—are hydrated via the Algolia HN API (`https://hn.algolia.com/api/v1/items/{id}`) to extract the story metadata, nested comment tree, community consensus, contrarian pushback, and the exact anchored sub-thread.
3. **Personal Vocabulary Lexicon & Active Learning Intents**: Google Search `?q=` tabs and dictionary lookups (`de rigueur`, `temerity`, `posit`, `ennui`, `malingerers`, `obstinance`, `vis a vis`, `backbiting`, `demonym`, `urdu kismat meaning`) are separated from technical deep-dive queries (`linear algebra rank reduction`, `how to get started with linux kernel programming`, `how do i back up cephfs data`, `erlang beam`) and personal life queries (`2006 gx470 headlights`, California tenant/landlord law).
4. **Zero-Quota Local LLM Synthesis on DGX Spark (`happy`)**: Deep discussion synthesis, sentiment scoring, controversy estimation, and classification into the **6 Intellectual Pillars** execute locally on `nvidia/Qwen3.8-Flash-Next-FP4-Local` (`happy.tail749110.ts.net:8000`) with a deterministic VADER + keyword heuristic fallback when offline.

---

## 2. User Personas & Core Use Cases

| Persona | Primary Goal | Key Workflows |
| :--- | :--- | :--- |
| **Senior AI Infrastructure Engineer (Author / Operator)** | Track intellectual evolution across years, synthesize dense Hacker News/Reddit/article discussions, and publish curated daily digests to `paulojauregui.com`. | 1. Browse the 3-Epoch Safari Vault filtered by Epoch, Intellectual Pillar, or Evergreen Canon.<br/>2. Trigger on-demand HN/Article synthesis via DGX Spark.<br/>3. Export daily digest snapshots as Markdown for personal blog publishing.<br/>4. Paste new Safari tab exports to incrementally grow the vault. |
| **Autonomous Nightly Digest Pipeline (Temporal Worker)** | Reliably ingest daily weather, market, and tech discussion data without manual intervention. | 1. Execute `DailyDigestCapsuleWorkflow` on schedule.<br/>2. Execute `BackfillSafariVaultWorkflow` to hydrate untitled tabs and persist to DuckDB/Parquet. |

---

## 3. The Six Intellectual Pillars (Taxonomy)

Every ingested link, discussion thread, and technical search intent is mapped to one or more of the six core intellectual pillars observed across the 2023–2026 dataset:

| Pillar ID | Pillar Name | Core Domains & Representative Topics |
| :--- | :--- | :--- |
| `PILLAR_1_AI_LLM_AGENTS` | **Local AI, LLM Harnesses & Autonomous Agents** | vLLM, speculative decoding, LoRA/GRPO, DGX Spark, OpenCode/Pi/Claude Code harnesses, MCP, RAG, agent systems scaling. |
| `PILLAR_2_SYSTEMS_KERNEL` | **Low-Level Systems, Kernel, GPU & Languages** | Linux kernel (LFD103, Landlock), C/C++, Rust, Zig, Go concurrency, Erlang/Elixir BEAM, CUDA/ROCm/CDNA, SIMD, OSTEP. |
| `PILLAR_3_INFRA_K8S_HOMELAB` | **Cloud-Native Infra, Kubernetes, Storage & Homelab** | K3s/Kubernetes operators, Kueue, CephFS/ZFS, DuckDB/SQLite/Postgres, MikroTik/IPv6 routers, KVM-over-IP (JetKVM, NanoKVM), $5 VPS. |
| `PILLAR_4_MATH_ML_THEORY` | **Mathematics, Deep Learning Foundations & Statistics** | Linear algebra rank reduction, Dummit & Foote abstract algebra, t-test/frequentism, Bishop/Karpathy Zero-to-Hero, binary vector search. |
| `PILLAR_5_SWE_CRAFT_CAREER` | **Software Engineering Craft, Architecture & Career** | SRE lessons, shipping at big tech, system design, avoiding wrong abstractions, AI job market dynamics, OMSCS, coding by hand. |
| `PILLAR_6_HUMANITIES_LIFE` | **Philosophy, Literature, Calm Tech, Health & Life** | Calm technology, Public Books, Kafka, Iliad, procrastination, exercise/creatine/coffee biology, audio/turntables, photography, California real estate. |

---

## 4. Functional Requirements

### 4.1 Multi-Epoch Safari Reading Vault (`safari_parser.py` & `models.py`)
- **FR-1.1 (Multi-Epoch Seed Ingestion)**: Parse Apple Notes / Safari markdown exports from `data/seeds/safari_open_tabs_2023_2024.txt` (`2023_2024`), `data/seeds/safari_bookmarks_2026_08_16.txt` (`2026_08_16`), and `data/seeds/safari_tabs_2026_11_06.txt` (`2026_11_06`), stripping Apple Notes CSS preamble headers (`p.p1 {margin: ...}`) and extracting every `[Title](URL)` entry.
- **FR-1.2 (Canonical URL Deduplication & Survival Metrics)**: Normalize URLs (stripping tracking query parameters like `utm_*`, `fbclid`, `gclid`, `_gl`, `sca_esv`, `sxsrf`, `ved`, `biw`, `bih`, `fbs`, `mstk` while preserving identity parameters like HN `id`, Google Search `q`, YouTube `v`, Reddit thread path) and compute:
  - `epochs_present: list[str]`
  - `cross_epoch_count: int` (`1`, `2`, or `3`)
  - `is_evergreen_canon: bool` (`True` iff `cross_epoch_count == 3`, yielding the 14 Evergreen Canon items)
  - `total_occurrences: int` (`interest_weight`, counting duplicate tabs within and across epochs)
- **FR-1.3 (Hacker News Metadata & Anchor Extraction)**: Detect `news.ycombinator.com` URLs, extract `hn_item_id: str | None` and `anchor_comment_id: str | None` (e.g., `50014121`, `46143525`, `47473516`, `49593756`, `50140985`), and set `needs_title_hydration = True` when the raw title is generic (`Hacker News`, `[Hacker News]`, `Start Page`, `Can’t Open Page`, `Can't Open Page`).
- **FR-1.4 (Search Query & Lexicon Classification)**: Extract Google Search `?q=` queries and dictionary URLs (`merriam-webster.com`, `dictionary.cambridge.org`, `en.m.wikipedia.org/wiki/Demonym`) and classify them into:
  - `VocabularyEntry` (words/idioms: `de rigueur`, `temerity`, `posit`, `ennui`, `malingerers`, `obstinance`, `obstinate`, `vis a vis`, `backbiting`, `demonym`, `urdu kismat meaning`, `vas deferens`)
  - `TechnicalLearningIntent` (systems, ML, math, infra queries)
  - `PersonalLifeQuery` (automotive, landlord/tenant deposit, health insurance, entertainment, local parks)

### 4.2 HN Discussion Hydration, Reddit/Article Scraping & Macro Assets (`news_assets.py`, `cultural_assets.py`, `weather_assets.py`, `financial_assets.py`)
- **FR-2.1 (HN Algolia Client)**: Fetch item trees from `https://hn.algolia.com/api/v1/items/{id}` and front-page/search stories from `https://hn.algolia.com/api/v1/search`. Hydrate untitled HN tabs with their true story title, points, author, external URL, and top comments. Isolate the specific `#anchor_comment_id` comment and its child replies when present.
- **FR-2.2 (Reddit & Article Extractor)**: Fetch structured metadata for Reddit discussion URLs (`r/MachineLearning`, `r/LocalLLaMA`, `r/devops`, `r/kernel`, `r/elixir`, `r/webdev`) and web articles/PDFs with deterministic offline-safe fallbacks.
- **FR-2.3 (Macro Weather & Financial Assets)**: Maintain backward compatibility with existing `raw_weather_data` and `raw_stock_data` tests while adding strict Design-by-Contract docstrings, static typing, and clean helper functions callable without Dagster context when needed.

### 4.3 Local DGX Spark LLM Discussion Analyzer & Sentiment Engine (`enrichment.py`)
- **FR-3.1 (Hybrid VADER + Local Qwen3.8 Analyzer)**: Compute fast deterministic sentiment polarity (`-1.0` to `1.0`) and controversy index (`0.0` to `1.0`) using `vaderSentiment`, augmented by structured JSON synthesis from `nvidia/Qwen3.8-Flash-Next-FP4-Local` at `SPARK_LLM_BASE_URL` (`http://happy.tail749110.ts.net:8000/v1`).
- **FR-3.2 (Fail-Open Heuristic Fallback)**: When DGX Spark is unreachable or offline during unit tests or degraded network states, automatically synthesize a deterministic `DiscussionAnalysis` (`core_thesis`, `community_consensus`, `contrarian_pushback`, `anchor_comment_spotlight`, `pillar_tags`, `actionable_takeaways`) without raising unhandled exceptions.

### 4.4 DuckDB Lakehouse Repository & Temporal Workflows (`repository.py`, `workflows.py`)
- **FR-4.1 (DuckDB + Parquet Persistence)**: Persist `vault_items`, `discussion_analyses`, `vocabulary_entries`, `search_intents`, and `daily_capsules` in DuckDB (`data/time_capsule.duckdb` or `:memory:` for unit tests), with one-call Parquet export for S3/SeaweedFS archival.
- **FR-4.2 (Temporal Workflows & Auto-Seeder)**: Provide `BackfillSafariVaultWorkflow` and `DailyDigestCapsuleWorkflow` using `temporalio`, plus an idempotent startup/CLI seeder that ingests all three seed files in `data/seeds/` automatically.

### 4.5 FastAPI Service, Web UI & GitOps Delivery (`api/main.py`, `deploy/base/`, `Dockerfile`)
- **FR-5.1 (REST API & Kubernetes Probes)**: Expose `/healthz`, `/ready`, `/api/v1/vault`, `/api/v1/epochs/summary`, `/api/v1/vault/import`, `/api/v1/vault/{item_id}/analyze`, `/api/v1/intents`, `/api/v1/vocabulary`, `/api/v1/digests`, and `/api/v1/capsule/{date}`.
- **FR-5.2 (Interactive Time Capsule Dashboard)**: Serve a responsive single-page application at `/` featuring the **Daily Tech Digest**, **3-Epoch Reading Vault & Evergreen Canon**, **Personal Time Capsule (Vocabulary Lexicon, Learning Intents & Longitudinal Shift)**, and **Macro Time Machine**.

---

## 5. Non-Functional & Quality Requirements

- **Performance**: Unit test suite must execute in `< 1.0s` with zero external network I/O. Full multi-epoch seed parsing of all 3 files (828 raw link lines -> deduplicated vault) must complete in `< 100ms`.
- **Reliability**: Zero-retry circuit breaker on LLM calls (`< 2.0s` connect probe) with deterministic fallback.
- **Security**: Container image runs as non-privileged `USER 10001:10001`. Zero hard-coded credentials.
- **Code Quality**: 100% compliance with `ruff check .` (including `ban-relative-imports = "all"`), `mypy src tests`, and Design-by-Contract (`Pre-conditions:` / `Post-conditions:`) on every public symbol.
