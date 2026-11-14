"""Unit and integration tests for Digital Time Capsule FastAPI service.

Pre-conditions:
    - FastAPI and pytest must be configured.
    - TestClient must be usable against in-memory DuckDB repository.

Post-conditions:
    - Validates healthz, ready, dashboard HTML, vault queries, epochs summary,
      import, analyze, intents, vocabulary, and daily capsule endpoints.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from time_capsule.api.main import create_app


@pytest.fixture(scope="module")
def api_client() -> Any:
    """Fixture initializing a TestClient backed by an in-memory seeded repository.

    Pre-conditions:
        - Seed files exist in data/seeds.

    Post-conditions:
        - Yields TestClient instance populated with 3-epoch reading vault data.
    """
    app = create_app(db_path=":memory:", seed_dir="data/seeds")
    with TestClient(app) as client:
        yield client


def test_healthz_and_ready(api_client: TestClient) -> None:
    """Verify healthz and readiness endpoints return standard operational payloads.

    Pre-conditions:
        - api_client initialized with populated repository.

    Post-conditions:
        - /healthz returns 200 with ok status.
        - /ready returns 200 with ready status, vault count > 0, and evergreen_count == 14.
    """
    health_res = api_client.get("/healthz")
    assert health_res.status_code == 200
    health_json = health_res.json()
    assert health_json["status"] == "ok"
    assert health_json["service"] == "time-capsule"

    ready_res = api_client.get("/ready")
    assert ready_res.status_code == 200
    ready_json = ready_res.json()
    assert ready_json["status"] == "ready"
    assert ready_json["vault_count"] > 500
    assert ready_json["evergreen_count"] == 14


def test_render_dashboard(api_client: TestClient) -> None:
    """Verify root endpoint renders the interactive single-page HTML dashboard.

    Pre-conditions:
        - api_client is available.

    Post-conditions:
        - Returns HTTP 200 with HTML content containing all 4 primary application tabs.
    """
    res = api_client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    html_text = res.text
    assert "Digital Time Capsule" in html_text
    assert "Daily Tech Digest" in html_text
    assert "3-Epoch Reading Vault" in html_text
    assert "Personal Time Capsule" in html_text
    assert "Macro Time Machine" in html_text


def test_get_vault_items_and_filtering(api_client: TestClient) -> None:
    """Verify multi-parameter querying and search over vault items.

    Pre-conditions:
        - In-memory vault contains multi-epoch ingested items.

    Post-conditions:
        - Confirms filtering by epoch, evergreen canon (14 items), pillar, source, and search string.
    """
    all_res = api_client.get("/api/v1/vault")
    assert all_res.status_code == 200
    all_json = all_res.json()
    assert all_json["count"] > 500

    # Filter by Evergreen Canon
    canon_res = api_client.get("/api/v1/vault?is_evergreen_canon=true")
    assert canon_res.status_code == 200
    canon_json = canon_res.json()
    assert canon_json["count"] == 14
    for item in canon_json["items"]:
        assert item["is_evergreen_canon"] is True
        assert item["cross_epoch_count"] == 3

    # Filter by Epoch
    epoch_res = api_client.get("/api/v1/vault?epoch=2023_2024")
    assert epoch_res.status_code == 200
    epoch_json = epoch_res.json()
    assert epoch_json["count"] > 0
    for item in epoch_json["items"]:
        assert "2023_2024" in item["epochs_present"]

    # Filter by Primary Pillar
    pillar_res = api_client.get("/api/v1/vault?pillar=PILLAR_1_AI_LLM_AGENTS")
    assert pillar_res.status_code == 200
    pillar_json = pillar_res.json()
    assert pillar_json["count"] > 0
    for item in pillar_json["items"]:
        assert item["primary_pillar"] == "PILLAR_1_AI_LLM_AGENTS"

    # Filter by Source Type
    hn_res = api_client.get("/api/v1/vault?source_type=hacker_news")
    assert hn_res.status_code == 200
    hn_json = hn_res.json()
    assert hn_json["count"] > 0
    for item in hn_json["items"]:
        assert item["source_type"] == "hacker_news"

    # Text Search
    search_res = api_client.get("/api/v1/vault?search=sqlite")
    assert search_res.status_code == 200
    search_json = search_res.json()
    assert search_json["count"] > 0
    for item in search_json["items"]:
        match_found = (
            "sqlite" in item["title"].lower()
            or "sqlite" in item["canonical_url"].lower()
            or (item.get("search_query") and "sqlite" in item["search_query"].lower())
        )
        assert match_found


def test_get_epochs_summary(api_client: TestClient) -> None:
    """Verify longitudinal epochs summary endpoint.

    Pre-conditions:
        - In-memory vault populated with multi-epoch seed data.

    Post-conditions:
        - Returns longitudinal taste profile, 14 evergreen canon items, and anchored items.
    """
    res = api_client.get("/api/v1/epochs/summary")
    assert res.status_code == 200
    summary = res.json()

    assert "total_unique_items" in summary
    assert "epoch_breakdown" in summary
    assert summary["evergreen_canon_count"] == 14
    assert len(summary["evergreen_canon"]) == 14
    assert len(summary["anchored_hn_items"]) == 5
    assert "taste_profile" in summary


def test_import_vault_text(api_client: TestClient) -> None:
    """Verify incremental Safari reading list snippet ingestion.

    Pre-conditions:
        - api_client is available.

    Post-conditions:
        - Ingests new link lines, updates item count, and makes new item queryable.
    """
    sample_text = (
        "[Autonomous Agent Systems in Production](https://example.com/autonomous-agents)\n"
        "[Distributed Consensus Mechanics](https://example.com/consensus-mechanics)\n"
    )

    res = api_client.post(
        "/api/v1/vault/import",
        json={"text": sample_text, "epoch_id": "2026_11_06"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["imported_raw_count"] == 2
    assert data["total_vault_items"] > 500

    search_res = api_client.get("/api/v1/vault?search=autonomous-agents")
    assert search_res.status_code == 200
    search_json = search_res.json()
    assert search_json["count"] >= 1
    assert "autonomous-agents" in search_json["items"][0]["canonical_url"]


def test_analyze_vault_item(api_client: TestClient) -> None:
    """Verify on-demand discussion synthesis endpoint.

    Pre-conditions:
        - Items exist in vault.

    Post-conditions:
        - Returns generated DiscussionAnalysis and persists into database.
        - Returns 404 for unknown item identifier.
    """
    vault_res = api_client.get("/api/v1/vault?limit=1")
    items = vault_res.json()["items"]
    assert len(items) == 1
    target_id = items[0]["item_id"]

    analyze_res = api_client.post(
        f"/api/v1/vault/{target_id}/analyze",
        json={"allow_llm": False, "allow_external_hydration": False},
    )
    assert analyze_res.status_code == 200
    analysis = analyze_res.json()
    assert analysis["item_id"] == target_id
    assert len(analysis["core_thesis"]) > 0
    assert -1.0 <= analysis["sentiment_score"] <= 1.0
    assert 0.0 <= analysis["controversy_score"] <= 1.0
    assert isinstance(analysis["pillar_tags"], list)

    missing_res = api_client.post(
        "/api/v1/vault/non_existent_item_id_12345/analyze",
        json={"allow_llm": False},
    )
    assert missing_res.status_code == 404


def test_get_intents_and_vocabulary(api_client: TestClient) -> None:
    """Verify search intents and vocabulary lexicon endpoints.

    Pre-conditions:
        - Seeded repository contains intents and vocabulary terms.

    Post-conditions:
        - /api/v1/intents and /api/v1/vocabulary return structured data and respect category filters.
    """
    intents_res = api_client.get("/api/v1/intents")
    assert intents_res.status_code == 200
    intents_data = intents_res.json()
    assert intents_data["count"] > 0
    assert len(intents_data["intents"]) == intents_data["count"]

    filtered_res = api_client.get("/api/v1/intents?category=technical_learning")
    assert filtered_res.status_code == 200
    filtered_data = filtered_res.json()
    for item in filtered_data["intents"]:
        assert item["category"] == "technical_learning"

    vocab_res = api_client.get("/api/v1/vocabulary")
    assert vocab_res.status_code == 200
    vocab_data = vocab_res.json()
    assert vocab_data["count"] > 0
    assert len(vocab_data["vocabulary"]) == vocab_data["count"]


def test_get_digests_and_capsule_by_date(api_client: TestClient) -> None:
    """Verify digests list and daily capsule snapshot retrieval and synthesis.

    Pre-conditions:
        - api_client is available.

    Post-conditions:
        - /api/v1/digests returns capsule summaries.
        - /api/v1/capsule/{capsule_date} returns or generates DailyCapsuleSnapshot with markdown_digest.
    """
    digests_res = api_client.get("/api/v1/digests")
    assert digests_res.status_code == 200
    digests_data = digests_res.json()
    assert "digests" in digests_data
    assert "top_analyses" in digests_data

    # Existing seeded capsule
    capsule_res = api_client.get("/api/v1/capsule/2026-11-06")
    assert capsule_res.status_code == 200
    capsule = capsule_res.json()
    assert capsule["capsule_date"] == "2026-11-06"
    assert "Digital Time Capsule" in capsule["markdown_digest"]
    assert len(capsule["weather_records"]) > 0
    assert len(capsule["stock_records"]) > 0

    # Synthetic on-the-fly future date
    future_res = api_client.get("/api/v1/capsule/2026-12-01")
    assert future_res.status_code == 200
    future_capsule = future_res.json()
    assert future_capsule["capsule_date"] == "2026-12-01"
    assert "Digital Time Capsule" in future_capsule["markdown_digest"]
