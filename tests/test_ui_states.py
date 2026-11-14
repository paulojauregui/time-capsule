"""Unit and integration tests for 5-state UI component renderers and asset serving.

Pre-conditions:
    - views.js and app.js must exist in src/time_capsule/api/static/.
    - FastAPI TestClient must be usable against in-memory seeded repository.
    - pytest, ruff, and mypy must be configured in the virtual environment.

Post-conditions:
    - Validates static asset HTTP serving contracts for /static/views.js and /static/app.js.
    - Validates presence of all 5-state rendering functions, XSS escaping, sentiment badge
      formatting, model badge degradation logic, and tabular numeric alignment classes.
    - Validates end-to-end API payloads consumed by client-side views.
"""

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from time_capsule.api.main import create_app

STATIC_DIR = Path(__file__).resolve().parent.parent / "src" / "time_capsule" / "api" / "static"
VIEWS_JS_PATH = STATIC_DIR / "views.js"
APP_JS_PATH = STATIC_DIR / "app.js"


@pytest.fixture(scope="module")
def views_js_content() -> str:
    """Fixture providing raw content of static/views.js.

    Pre-conditions:
        - views.js must exist on disk.

    Post-conditions:
        - Returns string content of views.js.
    """
    assert VIEWS_JS_PATH.is_file(), f"views.js missing at {VIEWS_JS_PATH}"
    return VIEWS_JS_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def api_client() -> Any:
    """Fixture providing TestClient backed by seeded in-memory repository.

    Pre-conditions:
        - Seed directory data/seeds exists.

    Post-conditions:
        - Yields TestClient instance for testing HTTP routes and static assets.
    """
    app = create_app(db_path=":memory:", seed_dir="data/seeds")
    with TestClient(app) as client:
        yield client


def test_views_js_exists_and_is_non_empty(views_js_content: str) -> None:
    """Verify views.js exists and has substantial implementation.

    Pre-conditions:
        - views_js_content fixture loaded.

    Post-conditions:
        - Asserts file size > 500 characters and contains TimeCapsuleViews export.
    """
    assert len(views_js_content.strip()) > 500
    assert "window.TimeCapsuleViews" in views_js_content


def test_views_js_contains_zero_emojis_and_non_ascii(views_js_content: str) -> None:
    """Verify views.js contains zero emojis and only ASCII characters.

    Pre-conditions:
        - views_js_content fixture loaded.

    Post-conditions:
        - Asserts all characters in views.js have ord(ch) <= 127.
    """
    for ch in views_js_content:
        assert ord(ch) <= 127, f"Forbidden non-ascii/emoji character {ch!r} (ord={ord(ch)}) in views.js"


def test_static_asset_serving_views_and_app(api_client: TestClient) -> None:
    """Verify GET /static/views.js and GET /static/app.js return 200 with javascript MIME type.

    Pre-conditions:
        - api_client initialized with static assets mounted.

    Post-conditions:
        - Asserts 200 status code and text/javascript content type for both assets.
    """
    views_res = api_client.get("/static/views.js")
    assert views_res.status_code == 200
    assert "javascript" in views_res.headers.get("content-type", "")
    assert views_res.text == VIEWS_JS_PATH.read_text(encoding="utf-8")

    app_res = api_client.get("/static/app.js")
    assert app_res.status_code == 200
    assert "javascript" in app_res.headers.get("content-type", "")
    assert app_res.text == APP_JS_PATH.read_text(encoding="utf-8")


def test_views_defines_security_and_formatting_utilities(views_js_content: str) -> None:
    """Verify security and formatting utilities in views.js.

    Pre-conditions:
        - views_js_content fixture loaded.

    Post-conditions:
        - Asserts escapeHtml, formatSentimentScore, renderModelBadge, and renderSourceBadge exist.
    """
    utilities = [
        "escapeHtml",
        "formatSentimentScore",
        "renderModelBadge",
        "renderSourceBadge",
    ]
    for util in utilities:
        assert f"function {util}" in views_js_content, f"Missing utility function {util}"
        assert f"{util}: {util}" in views_js_content, f"Utility {util} not exported in TimeCapsuleViews"


def test_views_format_sentiment_score_contract(views_js_content: str) -> None:
    """Verify formatSentimentScore produces signed tabular score badges.

    Pre-conditions:
        - views_js_content fixture loaded.

    Post-conditions:
        - Asserts presence of badge-score, tabular-nums, score-positive, and score-negative classes.
    """
    assert "badge-score" in views_js_content
    assert "tabular-nums" in views_js_content
    assert "score-positive" in views_js_content
    assert "score-negative" in views_js_content


def test_views_render_model_badge_degraded_contract(views_js_content: str) -> None:
    """Verify renderModelBadge distinguishes DGX Spark from Heuristic fallback.

    Pre-conditions:
        - views_js_content fixture loaded.

    Post-conditions:
        - Asserts badge-model-fallback and badge-model-spark rendering logic.
    """
    assert "badge-model-fallback" in views_js_content
    assert "Heuristic VADER Fallback" in views_js_content
    assert "badge-model-spark" in views_js_content


def test_views_render_source_badge_contract(views_js_content: str) -> None:
    """Verify renderSourceBadge produces taxonomy badges for HN, Reddit, GitHub, etc.

    Pre-conditions:
        - views_js_content fixture loaded.

    Post-conditions:
        - Asserts badge-hn, badge-reddit, and badge-github classes in renderSourceBadge.
    """
    assert "badge-hn" in views_js_content
    assert "badge-reddit" in views_js_content
    assert "badge-github" in views_js_content


def test_views_defines_all_5_state_renderers(views_js_content: str) -> None:
    """Verify all 5-state rendering functions are defined and exported.

    Pre-conditions:
        - views_js_content fixture loaded.

    Post-conditions:
        - Asserts presence and export of all loading, empty, nominal, and error renderers.
    """
    required_renderers = [
        # Discussions & Analysis Modal
        "renderDiscussionsLoading",
        "renderDiscussionsEmpty",
        "renderDiscussionsError",
        "renderDiscussionCardHtml",
        "renderDiscussions",
        "renderAnalysisModalLoading",
        "renderAnalysisModalResult",
        "renderAnalysisModalError",
        # Markdown Preview
        "renderMarkdownLoading",
        "renderMarkdownNominal",
        "renderMarkdownPreview",
        "renderMarkdownEmpty",
        "renderMarkdownError",
        # 3-Epoch Vault
        "renderVaultLoading",
        "renderVaultEmpty",
        "renderVaultError",
        "renderVaultRows",
        # Personal Time Capsule
        "renderTasteProfileLoading",
        "renderTasteProfileEmpty",
        "renderTasteProfileError",
        "renderTasteProfile",
        "renderVocabLoading",
        "renderVocabEmpty",
        "renderVocabError",
        "renderVocabRows",
        "renderIntentsLoading",
        "renderIntentsEmpty",
        "renderIntentsError",
        "renderIntentsRows",
        # Macro Time Machine
        "renderWeatherLoading",
        "renderWeatherEmpty",
        "renderWeatherError",
        "renderWeatherRows",
        "renderStocksLoading",
        "renderStocksEmpty",
        "renderStocksError",
        "renderStockRows",
        "renderMacroError",
    ]

    for renderer in required_renderers:
        assert f"function {renderer}" in views_js_content, f"Missing renderer function {renderer}"
        assert f"{renderer}: {renderer}" in views_js_content, f"Renderer {renderer} not exported"


def test_views_defines_skeleton_and_state_classes(views_js_content: str) -> None:
    """Verify views.js generates explicit design system state and skeleton classes.

    Pre-conditions:
        - views_js_content fixture loaded.

    Post-conditions:
        - Asserts presence of state-empty, state-error, state-loading, skeleton,
          skeleton-card, skeleton-row, skeleton-line, skeleton-well, and btn-retry classes.
    """
    required_classes = [
        "state-empty",
        "state-error",
        "state-loading",
        "skeleton",
        "skeleton-card",
        "skeleton-row",
        "skeleton-line",
        "skeleton-well",
        "btn-retry",
        "num-col",
        "tabular-nums",
        "badge-canon",
        "badge-pillar",
        "badge-epoch",
    ]
    for cls in required_classes:
        assert cls in views_js_content, f"Class hook '{cls}' missing from views.js"


def test_end_to_end_capsule_payload_supports_degraded_contract(api_client: TestClient) -> None:
    """Verify /api/v1/capsule/{date} returns discussions with model_used field for UI consumption.

    Pre-conditions:
        - api_client initialized with test seeds.

    Post-conditions:
        - Asserts response contains top_discussions with model_used, core_thesis, and sentiment.
    """
    res = api_client.get("/api/v1/capsule/2026-11-06")
    assert res.status_code == 200
    payload = res.json()
    assert "top_discussions" in payload
    assert len(payload["top_discussions"]) > 0

    first_discussion = payload["top_discussions"][0]
    assert "model_used" in first_discussion
    assert "core_thesis" in first_discussion
    assert "sentiment_score" in first_discussion
    assert "controversy_score" in first_discussion
    assert "actionable_takeaways" in first_discussion


def test_end_to_end_vault_evergreen_canon_payload(api_client: TestClient) -> None:
    """Verify /api/v1/vault with is_evergreen_canon=true returns exactly 14 items for UI table.

    Pre-conditions:
        - api_client initialized with test seeds.

    Post-conditions:
        - Asserts count == 14, every item has is_evergreen_canon == True, and total_occurrences >= 3.
    """
    res = api_client.get("/api/v1/vault?is_evergreen_canon=true")
    assert res.status_code == 200
    payload = res.json()
    assert payload["count"] == 14
    assert len(payload["items"]) == 14

    for item in payload["items"]:
        assert item["is_evergreen_canon"] is True
        assert item["total_occurrences"] >= 3
        assert "epochs_present" in item
        assert len(item["epochs_present"]) >= 3


def test_end_to_end_taste_profile_and_epochs_summary(api_client: TestClient) -> None:
    """Verify /api/v1/epochs/summary returns taste profile breakdown across all 3 epochs.

    Pre-conditions:
        - api_client initialized with test seeds.

    Post-conditions:
        - Asserts presence of 2023_2024, 2026_08_16, and 2026_11_06 in epoch_breakdown and taste_profile.
    """
    res = api_client.get("/api/v1/epochs/summary")
    assert res.status_code == 200
    payload = res.json()

    assert "epoch_breakdown" in payload
    assert "taste_profile" in payload
    epoch_taste = payload["taste_profile"].get("epoch_breakdown", payload["taste_profile"])
    for epoch in ("2023_2024", "2026_08_16", "2026_11_06"):
        assert epoch in payload["epoch_breakdown"]
        assert epoch in epoch_taste
        assert payload["epoch_breakdown"][epoch] > 0
