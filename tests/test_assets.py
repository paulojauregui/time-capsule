"""Comprehensive tests for Hacker News Algolia client, cultural assets, and Dagster pipelines.

Pre-conditions:
    - Package time_capsule must be installed and importable.
    - requests calls must be mocked to eliminate external network dependencies.

Post-conditions:
    - Verifies Algolia item hydration, comment tree parsing, anchor isolation across all 5 IDs,
      Reddit .json scraping, web article extraction, and Dagster asset execution.
"""

from typing import Any
from unittest.mock import MagicMock

import pandas as pd
import pytest
import requests

from time_capsule.cultural_assets import (
    CulturalContentSummary,
    CulturalExtractor,
    cultural_discussions_snapshot,
)
from time_capsule.models import SafariLinkItem, SourceType
from time_capsule.news_assets import (
    HNClient,
    top_hn_discussions,
)


def test_hn_clean_html() -> None:
    """Test HTML cleaning and entity unescaping on raw Hacker News comment text.

    Pre-conditions:
        - Input string contains HTML markup (<p>, <i>, <pre>, <code>) and encoded HTML entities.

    Post-conditions:
        - Confirms returned text is stripped of tags and entities are properly unescaped.
    """
    raw_html = "<p>Here is an <i>important</i> point &amp; quote: &#x27;Hello World&#x27;</p>"
    cleaned = HNClient.clean_hn_html(raw_html)
    assert cleaned == "Here is an important point & quote: 'Hello World'"

    assert HNClient.clean_hn_html(None) == ""
    assert HNClient.clean_hn_html("") == ""


def test_hn_client_fetch_item_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test fetching and parsing a Hacker News story item with nested comments from Algolia.

    Pre-conditions:
        - requests.get is monkeypatched to return structured Algolia item JSON.

    Post-conditions:
        - Verifies thread attributes, top comments count, and comment node properties.
    """
    mock_payload: dict[str, Any] = {
        "id": 46138952,
        "title": "Everyone in Seattle hates AI",
        "url": "https://example.com/seattle-ai",
        "author": "tech_writer",
        "points": 342,
        "created_at": "2026-08-16T10:00:00Z",
        "children": [
            {
                "id": 46140001,
                "author": "commenter_1",
                "text": "<p>First top-level comment.</p>",
                "created_at": "2026-08-16T10:15:00Z",
                "points": 15,
                "children": [
                    {
                        "id": 46140002,
                        "author": "commenter_2",
                        "text": "<p>A nested reply.</p>",
                        "created_at": "2026-08-16T10:30:00Z",
                        "points": 5,
                        "children": [],
                    }
                ],
            }
        ],
    }

    def mock_get(url: str, timeout: float = 5.0) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = mock_payload
        return mock_resp

    monkeypatch.setattr("time_capsule.news_assets.requests.get", mock_get)

    client = HNClient()
    thread = client.fetch_item_thread("46138952")

    assert thread.hn_item_id == "46138952"
    assert thread.title == "Everyone in Seattle hates AI"
    assert thread.points == 342
    assert len(thread.top_comments) == 1
    assert thread.top_comments[0].comment_id == "46140001"
    assert thread.top_comments[0].text == "First top-level comment."
    assert len(thread.top_comments[0].children) == 1
    assert thread.top_comments[0].children[0].comment_id == "46140002"


def test_hn_client_anchor_subthread_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test recursive isolation of anchor comments across all five canonical anchor IDs.

    Pre-conditions:
        - Target anchor comments placed at various nested depths within the Algolia item tree.

    Post-conditions:
        - Verifies that find_comment_by_id correctly locates and extracts each anchor node.
    """
    mock_payload: dict[str, Any] = {
        "id": 1000,
        "title": "Multi-anchor Test Story",
        "url": "https://example.com/multi-anchor",
        "author": "curator",
        "points": 500,
        "created_at": "2026-11-06T00:00:00Z",
        "children": [
            {
                "id": 50014121,
                "author": "vps_guru",
                "text": "<p>The $5 VPS anchor comment.</p>",
                "children": [],
            },
            {
                "id": 2000,
                "author": "nested_parent",
                "text": "<p>Parent node.</p>",
                "children": [
                    {
                        "id": 46143525,
                        "author": "seattle_local",
                        "text": "<p>Seattle anchor comment.</p>",
                        "children": [],
                    },
                    {
                        "id": 3000,
                        "author": "deep_parent",
                        "text": "<p>Deep parent.</p>",
                        "children": [
                            {
                                "id": 47473516,
                                "author": "floci_dev",
                                "text": "<p>Floci AWS emulator anchor comment.</p>",
                                "children": [],
                            },
                            {
                                "id": 49593756,
                                "author": "skills_manager",
                                "text": "<p>Skills file anchor comment.</p>",
                                "children": [],
                            },
                            {
                                "id": 50140985,
                                "author": "deepseek_bench",
                                "text": "<p>DeepSeek search anchor comment.</p>",
                                "children": [],
                            },
                        ],
                    },
                ],
            },
        ],
    }

    def mock_get(url: str, timeout: float = 5.0) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = mock_payload
        return mock_resp

    monkeypatch.setattr("time_capsule.news_assets.requests.get", mock_get)

    client = HNClient()
    canonical_anchors = ["50014121", "46143525", "47473516", "49593756", "50140985"]

    for anchor in canonical_anchors:
        thread = client.fetch_item_thread("1000", anchor_comment_id=f"#{anchor}")
        assert thread.anchor_subthread is not None, f"Anchor #{anchor} must be resolved."
        assert thread.anchor_subthread.comment_id == anchor


def test_hn_client_hydrate_safari_item(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test hydrating an untitled Hacker News SafariLinkItem using Algolia metadata.

    Pre-conditions:
        - SafariLinkItem with title='Hacker News' and needs_title_hydration=True.

    Post-conditions:
        - Confirms title is updated to '{hydrated_title} | Hacker News' and flag is cleared.
    """
    mock_payload = {
        "id": 49803892,
        "title": "Reflections on 10 Years of Distributed Systems",
        "url": "https://example.com/dist-sys-10y",
        "author": "dist_eng",
        "points": 450,
        "children": [],
    }

    def mock_get(url: str, timeout: float = 5.0) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = mock_payload
        return mock_resp

    monkeypatch.setattr("time_capsule.news_assets.requests.get", mock_get)

    client = HNClient()
    untitled_item = SafariLinkItem(
        item_id="abc123def456",
        title="Hacker News",
        url="https://news.ycombinator.com/item?id=49803892",
        canonical_url="https://news.ycombinator.com/item?id=49803892",
        domain="news.ycombinator.com",
        source_type=SourceType.HACKER_NEWS,
        hn_item_id="49803892",
        needs_title_hydration=True,
        was_untitled_tab=True,
    )

    hydrated_item, thread = client.hydrate_safari_item(untitled_item)
    assert thread is not None
    assert hydrated_item.title == "Reflections on 10 Years of Distributed Systems | Hacker News"
    assert hydrated_item.needs_title_hydration is False
    assert hydrated_item.was_untitled_tab is True


def test_hn_client_front_page_and_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test fetch_front_page_stories and error handling on network failure.

    Pre-conditions:
        - Normal requests.get execution returning hits, followed by RequestException.

    Post-conditions:
        - Asserts proper story parsing on success and deterministic fallback on error.
    """
    mock_search_payload = {
        "hits": [
            {
                "objectID": "50000001",
                "title": "Front Page Headline",
                "url": "https://news.ycombinator.com/item?id=50000001",
                "author": "author_1",
                "points": 180,
                "num_comments": 45,
                "created_at": "2026-11-06T08:00:00Z",
            }
        ]
    }

    def mock_get_success(url: str, timeout: float = 5.0) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = mock_search_payload
        return mock_resp

    monkeypatch.setattr("time_capsule.news_assets.requests.get", mock_get_success)

    client = HNClient()
    stories = client.fetch_front_page_stories(limit=5)
    assert len(stories) == 1
    assert stories[0].hn_item_id == "50000001"
    assert stories[0].title == "Front Page Headline"

    def mock_get_failure(url: str, timeout: float = 5.0) -> MagicMock:
        raise requests.RequestException("Connection refused")

    monkeypatch.setattr("time_capsule.news_assets.requests.get", mock_get_failure)

    fallback_stories = client.fetch_front_page_stories(limit=5)
    assert len(fallback_stories) > 0
    fallback_thread = client.fetch_item_thread("99999999")
    assert fallback_thread.hn_item_id == "99999999"


def test_cultural_extractor_reddit_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test Reddit .json discussion fetching and offline fallback synthesis.

    Pre-conditions:
        - requests.get mocked to return standard Reddit 2-element listing JSON.

    Post-conditions:
        - Verifies extraction of title, subreddit, selftext excerpt, and top comments.
    """
    mock_reddit_json = [
        {
            "data": {
                "children": [
                    {
                        "data": {
                            "title": "Which skill should I go for now?",
                            "subreddit": "webdev",
                            "author": "coder_jane",
                            "score": 128,
                            "selftext": "I feel like I have stopped learning. What next?",
                        }
                    }
                ]
            }
        },
        {
            "data": {
                "children": [
                    {
                        "kind": "t1",
                        "data": {"body": "Learn distributed systems and low-level kernel concepts."},
                    }
                ]
            }
        },
    ]

    def mock_get(url: str, headers: dict[str, str] | None = None, timeout: float = 5.0) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = mock_reddit_json
        return mock_resp

    monkeypatch.setattr("time_capsule.cultural_assets.requests.get", mock_get)

    extractor = CulturalExtractor()
    summary: CulturalContentSummary = extractor.fetch_reddit_summary(
        "https://www.reddit.com/r/webdev/comments/16gtcma/which_skill_should_i_go_for_now/"
    )

    assert summary.source_type == "reddit"
    assert summary.subreddit == "webdev"
    assert summary.title == "Which skill should I go for now?"
    assert summary.score == 128
    assert "stopped learning" in summary.excerpt
    assert len(summary.top_replies) == 1
    assert "distributed systems" in summary.top_replies[0]

    def mock_get_error(url: str, headers: dict[str, str] | None = None, timeout: float = 5.0) -> MagicMock:
        raise requests.RequestException("Rate limited")

    monkeypatch.setattr("time_capsule.cultural_assets.requests.get", mock_get_error)

    fallback_summary = extractor.fetch_reddit_summary(
        "https://www.reddit.com/r/webdev/comments/16gtcma/which_skill_should_i_go_for_now/"
    )
    assert fallback_summary.subreddit == "webdev"
    assert fallback_summary.source_type == "reddit"


def test_cultural_extractor_article_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test web article summary extraction, PDF handling, and fallback behavior.

    Pre-conditions:
        - HTML article containing title and meta description, and PDF URLs.

    Post-conditions:
        - Verifies title and excerpt extraction for HTML and appropriate classification of PDFs.
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Calm Technology - Designing for Simplicity</title>
        <meta name="description" content="Principles of calm technology for unobtrusive interfaces.">
    </head>
    <body>
        <p>Technology should require the smallest possible amount of attention.</p>
    </body>
    </html>
    """

    def mock_get(url: str, headers: dict[str, str] | None = None, timeout: float = 5.0) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.text = html_content
        return mock_resp

    monkeypatch.setattr("time_capsule.cultural_assets.requests.get", mock_get)

    extractor = CulturalExtractor()
    summary = extractor.fetch_article_summary("https://calmtech.com")
    assert summary.source_type == "article"
    assert "Calm Technology" in summary.title
    assert "Principles of calm technology" in summary.excerpt

    pdf_summary = extractor.fetch_article_summary(
        "https://cs-people.bu.edu/mathan/publications/fnt23-athanassoulis.pdf"
    )
    assert pdf_summary.source_type == "pdf_paper"


def test_dagster_assets_top_hn_and_cultural(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test execution of top_hn_discussions and cultural_discussions_snapshot Dagster assets.

    Pre-conditions:
        - Underlying HTTP requests mocked to return valid data structures.

    Post-conditions:
        - Confirms both asset functions return populated pandas DataFrames with expected schemas.
    """
    def mock_get(url: str, *args: Any, **kwargs: Any) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        if "algolia" in url or "search" in url:
            mock_resp.json = MagicMock(
                return_value={
                    "hits": [
                        {
                            "objectID": "123",
                            "title": "Dagster Ingestion Test",
                            "url": "https://example.com/test",
                            "author": "tester",
                            "points": 50,
                            "num_comments": 10,
                            "created_at": "2026-11-06T00:00:00Z",
                        }
                    ]
                }
            )
        else:
            mock_resp.text = (
                "<html><head><title>Mocked Article</title></head>"
                "<body><p>Mocked paragraph.</p></body></html>"
            )
        return mock_resp

    monkeypatch.setattr("time_capsule.news_assets.requests.get", mock_get)
    monkeypatch.setattr("time_capsule.cultural_assets.requests.get", mock_get)

    hn_df = top_hn_discussions()
    assert isinstance(hn_df, pd.DataFrame)
    assert len(hn_df) == 1
    assert "hn_item_id" in hn_df.columns
    assert hn_df.iloc[0]["hn_item_id"] == "123"

    cultural_df = cultural_discussions_snapshot()
    assert isinstance(cultural_df, pd.DataFrame)
    assert len(cultural_df) == 3
    assert "url" in cultural_df.columns
    assert "title" in cultural_df.columns
