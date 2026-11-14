"""Unit tests for VADER sentiment analysis, DGX Spark vLLM inference, and taste profiling.

Pre-conditions:
    - pytest and pytest-asyncio must be configured.
    - time_capsule.enrichment and domain models must be importable.

Post-conditions:
    - Validates lexical sentiment bounds, zero-retry circuit breaker, deterministic fallback,
      and longitudinal intellectual taste profiling.
"""

from typing import Any
from unittest.mock import MagicMock

import pytest

from time_capsule.cultural_assets import CulturalContentSummary
from time_capsule.enrichment import (
    SparkDiscussionAnalyzer,
    compute_taste_profile_summary,
    compute_vader_sentiment,
)
from time_capsule.models import (
    EpochId,
    IntellectualPillar,
    SafariLinkItem,
    SourceType,
)
from time_capsule.news_assets import HNCommentNode, HNStoryThread


def test_compute_vader_sentiment_positive_negative_mixed() -> None:
    """Test VADER sentiment analysis on positive, negative, mixed, and empty text corpuses.

    Pre-conditions:
        - Lists of positive, negative, polarized, and empty comment bodies.

    Post-conditions:
        - Verifies compound polarity directions, score bounds, and controversy indices.
    """
    empty_metrics = compute_vader_sentiment([])
    assert empty_metrics.compound_score == 0.0
    assert empty_metrics.neutral_ratio == 1.0
    assert empty_metrics.controversy_score == 0.0

    pos_texts = [
        "This tool is fantastic, elegant, and exceptionally well designed.",
        "Great performance improvements and outstanding documentation!",
    ]
    pos_metrics = compute_vader_sentiment(pos_texts)
    assert pos_metrics.compound_score > 0.3
    assert pos_metrics.positive_ratio > 0.0
    assert -1.0 <= pos_metrics.compound_score <= 1.0

    neg_texts = [
        "This update broke everything and caused terrible regressions.",
        "Horrible architecture, extremely buggy and unmaintainable garbage.",
    ]
    neg_metrics = compute_vader_sentiment(neg_texts)
    assert neg_metrics.compound_score < -0.3
    assert neg_metrics.negative_ratio > 0.0
    assert -1.0 <= neg_metrics.compound_score <= 1.0

    mixed_texts = [
        "I absolutely love this new architecture, it is pure brilliance!",
        "This is disastrous, completely broken, and utterly useless.",
    ]
    mixed_metrics = compute_vader_sentiment(mixed_texts)
    assert 0.0 <= mixed_metrics.controversy_score <= 1.0
    assert mixed_metrics.controversy_score > 0.1


def test_build_heuristic_analysis_with_anchor() -> None:
    """Test deterministic heuristic analysis generation with isolated anchor comment spotlight.

    Pre-conditions:
        - SafariLinkItem with anchor_comment_id='50014121' and corresponding HNStoryThread.

    Post-conditions:
        - Verifies that anchor comment text is highlighted and scores adhere to bounds.
    """
    item = SafariLinkItem(
        item_id="vps123456789",
        title="Ask HN: What do you run on a $5 VPS that's worth keeping online 24/7?",
        url="https://news.ycombinator.com/item?id=49985548#50014121",
        canonical_url="https://news.ycombinator.com/item?id=49985548",
        domain="news.ycombinator.com",
        source_type=SourceType.HACKER_NEWS,
        hn_item_id="49985548",
        anchor_comment_id="50014121",
        primary_pillar=IntellectualPillar.INFRA_K8S_HOMELAB.value,
        pillar_tags=[IntellectualPillar.INFRA_K8S_HOMELAB.value],
    )

    anchor_node = HNCommentNode(
        comment_id="50014121",
        author="homelab_veteran",
        text="I host lightweight WireGuard, Unbound DNS, and a self-contained monitoring agent.",
    )
    thread = HNStoryThread(
        hn_item_id="49985548",
        title="Ask HN: What do you run on a $5 VPS that's worth keeping online 24/7?",
        author="curious_dev",
        points=420,
        num_comments=180,
        anchor_comment_id="50014121",
        anchor_subthread=anchor_node,
    )

    analyzer = SparkDiscussionAnalyzer()
    analysis = analyzer.build_heuristic_analysis(item, thread=thread)

    assert analysis.item_id == "vps123456789"
    assert analysis.hn_item_id == "49985548"
    assert analysis.anchor_comment_id == "50014121"
    assert analysis.model_used == "heuristic-vader"
    assert -1.0 <= analysis.sentiment_score <= 1.0
    assert 0.0 <= analysis.controversy_score <= 1.0
    assert analysis.anchor_comment_spotlight is not None
    assert "50014121" in analysis.anchor_comment_spotlight
    assert "WireGuard" in analysis.anchor_comment_spotlight
    assert len(analysis.actionable_takeaways) >= 2


def test_build_heuristic_analysis_cultural() -> None:
    """Test heuristic analysis on cultural Reddit and article inputs.

    Pre-conditions:
        - CulturalContentSummary with community excerpt and top replies.

    Post-conditions:
        - Asserts thesis reflects community excerpt and sentiment is properly calculated.
    """
    item = SafariLinkItem(
        item_id="reddit123456",
        title="Which skill should I go for now?: webdev",
        url="https://www.reddit.com/r/webdev/comments/16gtcma/which_skill_should_i_go_for_now/",
        canonical_url="https://www.reddit.com/r/webdev/comments/16gtcma/which_skill_should_i_go_for_now",
        domain="reddit.com",
        source_type=SourceType.REDDIT,
        primary_pillar=IntellectualPillar.SWE_CRAFT_CAREER.value,
        pillar_tags=[IntellectualPillar.SWE_CRAFT_CAREER.value],
    )
    cultural = CulturalContentSummary(
        url=item.url,
        source_type="reddit",
        title=item.title,
        subreddit="webdev",
        author="coder",
        score=95,
        excerpt="Exploring systems programming and container infrastructure.",
        top_replies=["Focus on foundational low-level concepts."],
    )

    analyzer = SparkDiscussionAnalyzer()
    analysis = analyzer.build_heuristic_analysis(item, cultural=cultural)
    assert "systems programming" in analysis.core_thesis
    assert len(analysis.actionable_takeaways) >= 2


@pytest.mark.asyncio
async def test_analyze_item_async_healthy_llm_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test asynchronous discussion analysis when DGX Spark responds with valid structured JSON.

    Pre-conditions:
        - httpx.AsyncClient mocked to simulate healthy /models and /chat/completions endpoints.

    Post-conditions:
        - Verifies that DiscussionAnalysis uses the target model name and parses synthesis fields.
    """
    mock_models_resp = MagicMock()
    mock_models_resp.status_code = 200
    mock_models_resp.json.return_value = {
        "data": [{"id": "nvidia/Qwen3.8-Flash-Next-FP4-Local"}]
    }

    mock_chat_resp = MagicMock()
    mock_chat_resp.status_code = 200
    mock_chat_resp.raise_for_status.return_value = None
    mock_chat_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": (
                        "{\"core_thesis\": \"Architectural evaluation of local agent loop resilience.\", "
                        "\"community_consensus\": \"Strong support for zero-retry circuit breakers.\", "
                        "\"contrarian_pushback\": \"Minor concerns regarding fallback overhead.\", "
                        "\"anchor_comment_spotlight\": \"Spotlight on anchor #50014121.\", "
                        "\"actionable_takeaways\": [\"Establish strict 2.0s circuit breaker boundaries.\", "
                        "\"Maintain deterministic offline heuristic fallbacks.\"]}"
                    )
                }
            }
        ]
    }

    class MockAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "MockAsyncClient":
            return self

        async def __aexit__(self, *args: Any) -> None:
            pass

        async def get(self, url: str) -> MagicMock:
            return mock_models_resp

        async def post(self, url: str, json: dict[str, Any] | None = None) -> MagicMock:
            return mock_chat_resp

    monkeypatch.setattr("time_capsule.enrichment.httpx.AsyncClient", MockAsyncClient)

    item = SafariLinkItem(
        item_id="item12345678",
        title="Building reliable systems out of unreliable agents",
        url="https://news.ycombinator.com/item?id=39984209",
        canonical_url="https://news.ycombinator.com/item?id=39984209",
        domain="news.ycombinator.com",
        source_type=SourceType.HACKER_NEWS,
        hn_item_id="39984209",
        primary_pillar=IntellectualPillar.AI_LLM_AGENTS.value,
    )

    analyzer = SparkDiscussionAnalyzer()
    analysis = await analyzer.analyze_item_async(item, allow_llm=True)

    assert analysis.model_used == "nvidia/Qwen3.8-Flash-Next-FP4-Local"
    assert "agent loop resilience" in analysis.core_thesis
    assert "zero-retry circuit breakers" in analysis.community_consensus
    assert len(analysis.actionable_takeaways) == 2


@pytest.mark.asyncio
async def test_analyze_item_async_circuit_breaker_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test zero-retry circuit breaker fallback when DGX Spark is unreachable or times out.

    Pre-conditions:
        - httpx.AsyncClient probe throws TimeoutError or connection exception.

    Post-conditions:
        - Verifies that analysis seamlessly falls back to heuristic-vader without crashing.
    """
    class MockFailingAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "MockFailingAsyncClient":
            return self

        async def __aexit__(self, *args: Any) -> None:
            pass

        async def get(self, url: str) -> MagicMock:
            raise TimeoutError("Probe timed out after 1.8s")

    monkeypatch.setattr("time_capsule.enrichment.httpx.AsyncClient", MockFailingAsyncClient)

    item = SafariLinkItem(
        item_id="offline12345",
        title="Linux Kernel Programming Guide",
        url="https://kernel.org/guide",
        canonical_url="https://kernel.org/guide",
        domain="kernel.org",
        source_type=SourceType.ARTICLE,
        primary_pillar=IntellectualPillar.SYSTEMS_KERNEL.value,
    )

    analyzer = SparkDiscussionAnalyzer()
    assert await analyzer.check_spark_available() is False

    analysis = await analyzer.analyze_item_async(item, allow_llm=True)
    assert analysis.model_used == "heuristic-vader"
    assert "Linux Kernel Programming Guide" in analysis.title


def test_compute_taste_profile_summary() -> None:
    """Test longitudinal intellectual taste profile distribution and rising pillar detection.

    Pre-conditions:
        - List of SafariLinkItems distributed across historical epochs with distinct pillar tags.

    Post-conditions:
        - Confirms total item counts, percentages, and detection of expanding pillars.
    """
    item1 = SafariLinkItem(
        item_id="item1",
        title="Resume and Interview Tips",
        url="https://example.com/careers",
        canonical_url="https://example.com/careers",
        domain="example.com",
        source_type=SourceType.ARTICLE,
        epochs_present=[EpochId.EPOCH_2023_2024.value],
        primary_pillar=IntellectualPillar.SWE_CRAFT_CAREER.value,
        pillar_tags=[IntellectualPillar.SWE_CRAFT_CAREER.value],
    )
    item2 = SafariLinkItem(
        item_id="item2",
        title="Local LLM Harness Engineering",
        url="https://example.com/llm",
        canonical_url="https://example.com/llm",
        domain="example.com",
        source_type=SourceType.ARTICLE,
        epochs_present=[EpochId.EPOCH_2026_08_16.value, EpochId.EPOCH_2026_11_06.value],
        primary_pillar=IntellectualPillar.AI_LLM_AGENTS.value,
        pillar_tags=[IntellectualPillar.AI_LLM_AGENTS.value],
    )
    item3 = SafariLinkItem(
        item_id="item3",
        title="Kubernetes Operators and eBPF",
        url="https://example.com/k8s",
        canonical_url="https://example.com/k8s",
        domain="example.com",
        source_type=SourceType.ARTICLE,
        epochs_present=[EpochId.EPOCH_2026_11_06.value],
        primary_pillar=IntellectualPillar.INFRA_K8S_HOMELAB.value,
        pillar_tags=[IntellectualPillar.INFRA_K8S_HOMELAB.value, IntellectualPillar.SYSTEMS_KERNEL.value],
    )

    summary = compute_taste_profile_summary([item1, item2, item3])

    assert summary["total_items"] == 3
    assert summary["pillar_counts"][IntellectualPillar.AI_LLM_AGENTS.value] >= 1
    assert summary["pillar_counts"][IntellectualPillar.SWE_CRAFT_CAREER.value] >= 1
    assert summary["top_pillar_overall"] in summary["pillar_counts"]

    # AI and Infra/Kernel grew from epoch 1 to epoch 3
    assert IntellectualPillar.AI_LLM_AGENTS.value in summary["rising_pillars"]
