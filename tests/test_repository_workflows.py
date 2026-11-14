"""Unit and integration tests for DuckDB Lakehouse repository and workflow execution.

Pre-conditions:
    - DuckDB, Temporalio, and time_capsule modules must be importable.
    - Canonical seed data in data/seeds must be present.

Post-conditions:
    - Validates relational schema operations, multi-epoch queries, Parquet export,
      markdown digest rendering, and standalone pipeline execution.
"""

from pathlib import Path

from time_capsule.financial_assets import get_fallback_stock_records
from time_capsule.models import (
    DailyCapsuleSnapshot,
    DiscussionAnalysis,
    EpochId,
    IntellectualPillar,
    QueryIntentCategory,
    SafariLinkItem,
    SourceType,
)
from time_capsule.repository import TimeCapsuleRepository
from time_capsule.safari_parser import parse_seed_directory
from time_capsule.weather_assets import get_fallback_weather_records
from time_capsule.workflows import (
    render_capsule_markdown,
    run_standalone_pipeline,
    seed_database_from_seeds,
)


def test_repository_schema_init_memory() -> None:
    """Test repository initialization using in-memory DuckDB database.

    Pre-conditions:
        - None.

    Post-conditions:
        - Verifies that tables are created and querying an empty repository returns empty lists.
    """
    repo = TimeCapsuleRepository(":memory:")
    items = repo.query_vault_items()
    assert items == []
    assert repo.list_discussion_analyses() == []
    assert repo.list_vocabulary_entries() == []
    assert repo.list_search_intents() == []


def test_repository_vault_upsert_and_query() -> None:
    """Test upserting multi-epoch vault parse results and executing multi-dimensional queries.

    Pre-conditions:
        - Seeds under data/seeds parsed into VaultParseResult.

    Post-conditions:
        - Confirms upsert item count, query by evergreen status, epoch, pillar, source, and search.
    """
    repo = TimeCapsuleRepository(":memory:")
    parse_result = parse_seed_directory("data/seeds")

    items_stored = repo.upsert_vault_parse_result(parse_result)
    assert items_stored == len(parse_result.items)

    # 1. Evergreen canon query
    evergreen = repo.query_vault_items(is_evergreen_canon=True)
    assert len(evergreen) == 14
    for item in evergreen:
        assert item.is_evergreen_canon is True
        assert len(item.epochs_present) == 3

    # 2. Epoch filter query
    e1_items = repo.query_vault_items(epoch=EpochId.EPOCH_2023_2024.value)
    assert len(e1_items) > 0
    for item in e1_items:
        assert EpochId.EPOCH_2023_2024.value in item.epochs_present

    # 3. Pillar filter query
    ai_items = repo.query_vault_items(pillar=IntellectualPillar.AI_LLM_AGENTS.value)
    assert len(ai_items) > 0
    for item in ai_items:
        assert IntellectualPillar.AI_LLM_AGENTS.value in item.pillar_tags or item.primary_pillar == IntellectualPillar.AI_LLM_AGENTS.value

    # 4. Source type query
    hn_items = repo.query_vault_items(source_type="hacker_news")
    assert len(hn_items) > 0
    for item in hn_items:
        assert item.source_type == SourceType.HACKER_NEWS

    # 5. Full text search query
    search_results = repo.query_vault_items(search="VPS")
    assert len(search_results) >= 1
    assert any("VPS" in i.title for i in search_results)

    # 6. Item lookup by ID and HN story ID
    vps_item = next(i for i in hn_items if i.hn_item_id == "49985548")
    fetched = repo.get_vault_item(vps_item.item_id)
    assert fetched is not None
    assert fetched.title == vps_item.title

    fetched_by_hn = repo.get_vault_item("49985548")
    assert fetched_by_hn is not None
    assert fetched_by_hn.item_id == vps_item.item_id


def test_repository_discussion_analysis_and_sentiment_filter() -> None:
    """Test persisting DiscussionAnalysis records and querying vault items by minimum sentiment.

    Pre-conditions:
        - In-memory repository with upserted items and associated discussion analyses.

    Post-conditions:
        - Asserts analysis retrieval and sentiment-joined vault queries.
    """
    repo = TimeCapsuleRepository(":memory:")
    item = SafariLinkItem(
        item_id="item_sentiment_1",
        title="High Sentiment Architecture Discussion",
        url="https://example.com/discussion",
        canonical_url="https://example.com/discussion",
        domain="example.com",
        source_type=SourceType.ARTICLE,
    )
    from time_capsule.models import VaultParseResult

    repo.upsert_vault_parse_result(VaultParseResult(items=[item]))

    analysis = DiscussionAnalysis(
        item_id="item_sentiment_1",
        title=item.title,
        core_thesis="Core thesis for sentiment test.",
        community_consensus="Universal community praise.",
        contrarian_pushback="Minimal pushback.",
        sentiment_score=0.85,
        controversy_score=0.1,
        pillar_tags=[IntellectualPillar.AI_LLM_AGENTS.value],
        actionable_takeaways=["Adopt verified patterns."],
        model_used="heuristic-vader",
        analyzed_at="2026-11-06T12:00:00Z",
    )
    repo.upsert_discussion_analysis(analysis)

    retrieved = repo.get_discussion_analysis("item_sentiment_1")
    assert retrieved is not None
    assert retrieved.sentiment_score == 0.85

    all_analyses = repo.list_discussion_analyses()
    assert len(all_analyses) == 1

    high_sentiment_items = repo.query_vault_items(min_sentiment=0.5)
    assert len(high_sentiment_items) == 1
    assert high_sentiment_items[0].item_id == "item_sentiment_1"

    no_items = repo.query_vault_items(min_sentiment=0.95)
    assert len(no_items) == 0


def test_repository_vocabulary_and_search_intents() -> None:
    """Test listing vocabulary entries and search query intents from repository.

    Pre-conditions:
        - Repository seeded with VaultParseResult.

    Post-conditions:
        - Confirms vocabulary entries and search intents are retrieved and filterable.
    """
    repo = TimeCapsuleRepository(":memory:")
    parse_result = parse_seed_directory("data/seeds")
    repo.upsert_vault_parse_result(parse_result)

    vocab = repo.list_vocabulary_entries()
    assert len(vocab) > 0
    terms = {v.term for v in vocab}
    assert "de rigueur" in terms
    assert "temerity" in terms
    assert "demonym" in terms

    intents = repo.list_search_intents()
    assert len(intents) > 0

    personal_intents = repo.list_search_intents(category=QueryIntentCategory.PERSONAL_LIFE.value)
    assert len(personal_intents) > 0
    for pi in personal_intents:
        assert pi.category == QueryIntentCategory.PERSONAL_LIFE


def test_repository_daily_capsule() -> None:
    """Test storing, retrieving, and listing DailyCapsuleSnapshot records.

    Pre-conditions:
        - Complete DailyCapsuleSnapshot with weather, stocks, discussions, and spotlight.

    Post-conditions:
        - Asserts that get_daily_capsule and list_daily_capsules preserve all nested models.
    """
    repo = TimeCapsuleRepository(":memory:")
    snapshot = DailyCapsuleSnapshot(
        capsule_date="2026-11-06",
        weather_records=get_fallback_weather_records(),
        stock_records=get_fallback_stock_records("2026-11-06"),
        top_discussions=[],
        evergreen_spotlight=[],
        markdown_digest="# Digest for 2026-11-06",
    )
    repo.upsert_daily_capsule(snapshot)

    fetched = repo.get_daily_capsule("2026-11-06")
    assert fetched is not None
    assert fetched.capsule_date == "2026-11-06"
    assert len(fetched.weather_records) == 5
    assert len(fetched.stock_records) == 5
    assert fetched.markdown_digest == "# Digest for 2026-11-06"

    capsules = repo.list_daily_capsules()
    assert len(capsules) == 1


def test_repository_get_epochs_summary() -> None:
    """Test computation of longitudinal statistics across epochs.

    Pre-conditions:
        - Repository seeded with all 3 canonical seed files.

    Post-conditions:
        - Asserts summary contains 14 evergreen items, 5 anchored HN items, and taste profiles.
    """
    repo = TimeCapsuleRepository(":memory:")
    parse_result = parse_seed_directory("data/seeds")
    repo.upsert_vault_parse_result(parse_result)

    summary = repo.get_epochs_summary()
    assert summary["total_vault_items"] > 0
    assert summary["evergreen_canon_count"] == 14
    assert len(summary["evergreen_canon_items"]) == 14
    assert summary["anchored_hn_count"] == 5
    assert summary["untitled_hn_count"] > 0
    assert summary["hydration_needed_count"] > 0
    assert "taste_profile" in summary


def test_repository_export_to_parquet(tmp_path: Path) -> None:
    """Test exporting all Lakehouse tables to native Parquet files.

    Pre-conditions:
        - Seeded repository and writable tmp_path directory.

    Post-conditions:
        - Verifies that parquet files are created for all 5 tables and are non-empty.
    """
    repo = TimeCapsuleRepository(":memory:")
    parse_result = parse_seed_directory("data/seeds")
    repo.upsert_vault_parse_result(parse_result)

    exported_files = repo.export_to_parquet(tmp_path)
    expected_tables = {
        "vault_items",
        "discussion_analyses",
        "vocabulary_entries",
        "search_intents",
        "daily_capsules",
    }
    assert set(exported_files.keys()) == expected_tables

    for _table, filepath in exported_files.items():
        p = Path(filepath)
        assert p.exists()
        assert p.stat().st_size > 0


def test_workflows_render_capsule_markdown() -> None:
    """Test publication Markdown rendering for daily technical discussion digests.

    Pre-conditions:
        - DailyCapsuleSnapshot with discussions, evergreen items, and telemetry.

    Post-conditions:
        - Verifies generation of executive digest, evergreen section, and markdown tables.
    """
    analysis = DiscussionAnalysis(
        item_id="vps_test",
        title="Ask HN: What do you run on a $5 VPS?",
        core_thesis="Self-hosted infrastructure on low-cost compute.",
        community_consensus="Broad support for wireguard and static servers.",
        contrarian_pushback="Concerns regarding data durability without backups.",
        anchor_comment_spotlight="Spotlight on comment #50014121.",
        sentiment_score=0.45,
        controversy_score=0.2,
        actionable_takeaways=["Automate backups off-node."],
        model_used="heuristic-vader",
    )
    evergreen_item = SafariLinkItem(
        item_id="calmtech123",
        title="Calm Technology",
        url="https://calmtech.com",
        canonical_url="https://calmtech.com",
        domain="calmtech.com",
        source_type=SourceType.ARTICLE,
        is_evergreen_canon=True,
        total_occurrences=3,
        primary_pillar=IntellectualPillar.INFRA_K8S_HOMELAB.value,
    )
    snapshot = DailyCapsuleSnapshot(
        capsule_date="2026-11-06",
        weather_records=get_fallback_weather_records(),
        stock_records=get_fallback_stock_records("2026-11-06"),
        top_discussions=[analysis],
        evergreen_spotlight=[evergreen_item],
    )

    md = render_capsule_markdown(snapshot)
    assert "# Digital Time Capsule & Tech Discussion Digest: 2026-11-06" in md
    assert "Ask HN: What do you run on a $5 VPS?" in md
    assert "Calm Technology" in md
    assert "| Tokyo |" in md
    assert "| AAPL |" in md


def test_workflows_seed_database_and_standalone_pipeline(tmp_path: Path) -> None:
    """Test end-to-end database seeding and standalone pipeline execution.

    Pre-conditions:
        - Target directory data/seeds containing export files.

    Post-conditions:
        - Confirms population of vault items, 14 evergreen items, and daily digest snapshots.
    """
    repo = TimeCapsuleRepository(":memory:")
    result = seed_database_from_seeds(repo, seed_dir="data/seeds", capsule_date="2026-11-06")

    assert result["status"] == "ok"
    assert result["vault_items_stored"] > 0
    assert result["evergreen_canon_count"] == 14

    snapshot = repo.get_daily_capsule("2026-11-06")
    assert snapshot is not None
    assert len(snapshot.evergreen_spotlight) == 14
    assert len(snapshot.markdown_digest) > 0

    # Test standalone pipeline writing to a physical DuckDB file
    db_file = tmp_path / "standalone.duckdb"
    standalone_res = run_standalone_pipeline(
        db_path=str(db_file), seed_dir="data/seeds", capsule_date="2026-11-06"
    )
    assert standalone_res["status"] == "ok"
    assert db_file.exists()
