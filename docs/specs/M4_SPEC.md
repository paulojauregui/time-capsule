# Milestone 4 Specification: DuckDB / S3 Lakehouse Repository & Temporal Workflows

## 1. Objective & Scope

Implement `src/time_capsule/repository.py` (DuckDB persistence layer with S3/Parquet export capability for SeaweedFS) and `src/time_capsule/workflows.py` (`temporalio` workflows and activities for `BackfillSafariVaultWorkflow` and `DailyDigestCapsuleWorkflow`, plus an idempotent CLI/startup seeder that populates the database from the 3 seed files in `data/seeds/`). Validate with `tests/test_repository_workflows.py`.

## 2. Non-Negotiable Engineering Invariants

1. **Absolute Imports Only**: Use `from time_capsule...` exclusively.
2. **Design by Contract (DbC)**: Every public class, method, and function MUST include `Pre-conditions:` and `Post-conditions:` in its docstring.
3. **Static Typing**: Full type annotations passing `poetry run mypy src tests`.
4. **Zero External Network Calls in Unit Tests**: Tests use `:memory:` or `tmp_path` DuckDB databases and run in `< 1s`.

---

## 3. File-by-File Contracts

### 3.1 `src/time_capsule/repository.py`

Implement `TimeCapsuleRepository`:

- `__init__(self, db_path: str | Path = "data/time_capsule.duckdb") -> None`:
  - Initializes schema tables in DuckDB (`vault_items`, `discussion_analyses`, `vocabulary_entries`, `search_intents`, `daily_capsules`).
  - Supports `:memory:` (keeping a persistent in-memory connection) or file-backed DuckDB paths (creating parent directory if needed).
- `init_schema(self) -> None`:
  - Creates tables if not exists.
- `upsert_vault_parse_result(self, parse_result: VaultParseResult) -> int`:
  - Upserts all `SafariLinkItem` records, `VocabularyEntry` records, and `SearchQueryIntent` records into DuckDB. Returns number of vault items stored.
- `query_vault_items(self, epoch: str | None = None, is_evergreen_canon: bool | None = None, pillar: str | None = None, source_type: str | None = None, min_sentiment: float | None = None, search: str | None = None, limit: int = 1000) -> list[SafariLinkItem]`:
  - Filters vault items (optionally joining `discussion_analyses` when `min_sentiment` is specified) and returns `list[SafariLinkItem]` ordered by `is_evergreen_canon DESC, total_occurrences DESC, title ASC`.
- `get_vault_item(self, item_id: str) -> SafariLinkItem | None`:
  - Looks up a single `SafariLinkItem` by `item_id` or `hn_item_id`.
- `upsert_discussion_analysis(self, analysis: DiscussionAnalysis) -> None`:
  - Persists a `DiscussionAnalysis` record keyed by `item_id`.
- `get_discussion_analysis(self, item_id: str) -> DiscussionAnalysis | None`:
  - Retrieves a stored `DiscussionAnalysis` by `item_id`.
- `list_discussion_analyses(self, limit: int = 100) -> list[DiscussionAnalysis]`:
  - Lists stored `DiscussionAnalysis` records.
- `list_vocabulary_entries(self, epoch: str | None = None) -> list[VocabularyEntry]`:
  - Returns stored `VocabularyEntry` records ordered by `term ASC`.
- `list_search_intents(self, category: str | None = None, epoch: str | None = None) -> list[SearchQueryIntent]`:
  - Returns stored `SearchQueryIntent` records.
- `upsert_daily_capsule(self, snapshot: DailyCapsuleSnapshot) -> None`:
  - Stores a `DailyCapsuleSnapshot` keyed by `capsule_date`.
- `get_daily_capsule(self, capsule_date: str) -> DailyCapsuleSnapshot | None`:
  - Retrieves a `DailyCapsuleSnapshot` by date.
- `list_daily_capsules(self, limit: int = 30) -> list[DailyCapsuleSnapshot]`:
  - Returns stored `DailyCapsuleSnapshot` records ordered by `capsule_date DESC`.
- `get_epochs_summary(self) -> dict[str, Any]`:
  - Computes longitudinal statistics across `2023_2024`, `2026_08_16`, and `2026_11_06`, including per-epoch counts, pillar distributions per epoch, the 14 Evergreen Canon items (`is_evergreen_canon == True`), anchored HN items, and untitled HN tab counts.
- `export_to_parquet(self, export_dir: str | Path) -> dict[str, str]`:
  - Exports `vault_items`, `discussion_analyses`, `vocabulary_entries`, `search_intents`, and `daily_capsules` to Parquet files in `export_dir` (compatible with local filesystem or S3/SeaweedFS staging) and returns a mapping of table name to Parquet file path.

### 3.2 `src/time_capsule/workflows.py`

Implement Temporal workflows, activities, markdown digest formatter, and standalone seeder/runner:

- `render_capsule_markdown(snapshot: DailyCapsuleSnapshot) -> str`:
  - Produces a clean, publication-ready Markdown document for `paulojauregui.com` containing the date, Executive Tech Discussion Digest (thesis, consensus, contrarian pushback, anchor comment spotlight), Evergreen Canon spotlight, and Macro Weather & Equity Snapshot tables.
- `seed_database_from_seeds(repo: TimeCapsuleRepository, seed_dir: str | Path = "data/seeds", capsule_date: str = "2026-11-06") -> dict[str, Any]`:
  - Parses all 3 seed files via `parse_seed_directory(seed_dir)`, upserts the `VaultParseResult` into `repo`, generates baseline `DiscussionAnalysis` records for the 5 anchored HN items (`49985548`, `46138952`, `47471801`, `49589914`, `50138531`) and the 14 Evergreen Canon items using deterministic heuristic analysis, and creates a default `DailyCapsuleSnapshot` for `capsule_date` (plus today's date if different) so the API and UI are immediately populated out-of-the-box.
- Temporal Activities (`@activity.defn`):
  - `ingest_safari_seeds_activity(db_path: str = "data/time_capsule.duckdb", seed_dir: str = "data/seeds") -> dict[str, Any]`
  - `build_daily_digest_activity(db_path: str = "data/time_capsule.duckdb", capsule_date: str = "2026-11-06", allow_external: bool = False) -> dict[str, Any]`
- Temporal Workflows (`@workflow.defn`):
  - `BackfillSafariVaultWorkflow`: executes `ingest_safari_seeds_activity` with retry policy and timeout.
  - `DailyDigestCapsuleWorkflow`: executes `build_daily_digest_activity` with retry policy and timeout.
- `run_standalone_pipeline(db_path: str = "data/time_capsule.duckdb", seed_dir: str = "data/seeds", capsule_date: str = "2026-11-06") -> dict[str, Any]`:
  - Runs the full backfill and daily digest pipeline in-process when Temporal server (`TEMPORAL_HOST=temporal-frontend.temporal-system.svc.cluster.local:7233`) is not enabled.
- `cli_main() -> None`:
  - CLI entrypoint supporting `--seed`, `--digest`, or `--worker` (connecting to `TEMPORAL_HOST` when `--worker` is passed).

### 3.3 `tests/test_repository_workflows.py`

Write fast unit/integration tests verifying:
- `TimeCapsuleRepository` CRUD for vault items, filtering by epoch (`2023_2024`, `2026_08_16`, `2026_11_06`), `is_evergreen_canon=True` (14 items), pillar, source_type, and sentiment.
- `export_to_parquet` writes valid Parquet files to `tmp_path`.
- `seed_database_from_seeds` populates all 3 epochs, 14 Evergreen Canon items, vocabulary lexicon, learning intents, discussion analyses, and daily capsule snapshot with Markdown export.
