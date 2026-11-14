# Milestone 2 Specification: HN Discussion Tree Hydration, Reddit/Article Scraper & Macro Assets

## 1. Objective & Scope

Refactor the Phase 1 macro assets (`src/time_capsule/weather_assets.py`, `src/time_capsule/financial_assets.py`, `tests/test_weather_assets.py`, `tests/test_financial_assets.py`) to full Design-by-Contract (DbC), `ruff`, and `mypy` compliance, and implement the Hacker News Algolia hydration engine (`src/time_capsule/news_assets.py`), the Reddit/Article cultural scraper (`src/time_capsule/cultural_assets.py`), and comprehensive unit tests (`tests/test_assets.py`).

## 2. Non-Negotiable Engineering Invariants

1. **Absolute Imports Only**: Use `from time_capsule...` exclusively. Zero relative imports (`from .`).
2. **Design by Contract (DbC)**: Every public class, method, and function (including test functions) MUST include `Pre-conditions:` and `Post-conditions:` in its docstring.
3. **Static Typing**: Full type annotations passing `poetry run mypy src tests`.
4. **Zero External Network Calls in Unit Tests**: All HTTP calls in `tests/` must be mocked (`monkeypatch` / `unittest.mock`) and execute in `< 1s`.
5. **Backward Compatibility**: Existing `raw_weather_data(api=...)` and `raw_stock_data(api=...)` signatures and `requests.get` usage in `weather_assets.py` and `financial_assets.py` MUST remain compatible with `tests/test_weather_assets.py` and `tests/test_financial_assets.py`.

---

## 3. File-by-File Contracts

### 3.1 `src/time_capsule/weather_assets.py`

- Use absolute import `from time_capsule.resources import APIResource`.
- Keep `CITIES: dict[str, tuple[float, float]]` with Tokyo, New York, London, Beijing, Sydney.
- Implement helper `fetch_weather_records(api_key: str | None = None, timeout: float = 10.0) -> list[dict[str, Any]]`:
  - `Pre-conditions`: `timeout > 0`.
  - `Post-conditions`: If `api_key` is provided, queries OpenWeatherMap via `requests.get` for each city in `CITIES` and returns normalized dicts; if `api_key` is empty/None, raises `ValueError("OPENWEATHERMAP_API_KEY environment variable not set.")`.
- Implement `get_fallback_weather_records() -> list[dict[str, Any]]`:
  - `Pre-conditions`: None.
  - `Post-conditions`: Returns deterministic baseline weather records for all 5 cities in `CITIES` when offline or when no API key is configured in local/preview environments.
- Keep `@asset def raw_weather_data(api: APIResource) -> pd.DataFrame:` with explicit DbC docstring (`Pre-conditions:` and `Post-conditions:`), calling `requests.get(url)` directly (or via `fetch_weather_records`) so `monkeypatch.setattr("time_capsule.weather_assets.requests.get", mock_get)` in `tests/test_weather_assets.py` works identically.

### 3.2 `src/time_capsule/financial_assets.py`

- Use absolute import `from time_capsule.resources import APIResource`.
- Keep `TICKERS: list[str] = ["AAPL", "MSFT", "GOOG", "AMZN", "NVDA"]`.
- Implement helper `get_fallback_stock_records(target_date: str = "2026-11-06") -> list[dict[str, Any]]`:
  - `Pre-conditions`: `target_date` is a non-empty YYYY-MM-DD date string.
  - `Post-conditions`: Returns deterministic baseline OHLCV records for all tickers in `TICKERS`.
- Keep `@asset def raw_stock_data(api: APIResource) -> pd.DataFrame:` with explicit DbC docstring (`Pre-conditions:` and `Post-conditions:`), calling `requests.get(url)` so `monkeypatch.setattr("time_capsule.financial_assets.requests.get", mock_get)` in `tests/test_financial_assets.py` continues to pass.

### 3.3 `src/time_capsule/news_assets.py`

Implement Pydantic models and `HNClient` for Algolia Hacker News API (`https://hn.algolia.com/api/v1`):

- `HNCommentNode(BaseModel)`:
  - `comment_id: str`
  - `author: str = "anonymous"`
  - `text: str = ""`
  - `created_at: str = ""`
  - `points: int | None = None`
  - `children: list[HNCommentNode] = Field(default_factory=list)`
- `HNStoryThread(BaseModel)`:
  - `hn_item_id: str`
  - `title: str`
  - `url: str | None = None`
  - `author: str = "anonymous"`
  - `points: int = 0`
  - `num_comments: int = 0`
  - `created_at: str = ""`
  - `top_comments: list[HNCommentNode] = Field(default_factory=list)`
  - `anchor_comment_id: str | None = None`
  - `anchor_subthread: HNCommentNode | None = None`
  - `was_hydrated_from_untitled: bool = False`
- `HNClient`:
  - `__init__(self, base_url: str = "https://hn.algolia.com/api/v1", timeout: float = 5.0) -> None`
  - `clean_hn_html(raw_html: str | None) -> str` (static/method helper that strips HTML tags like `<p>`, `<i>`, `<a>`, `<pre><code>` and unescapes HTML entities via `html.unescape`).
  - `find_comment_by_id(node_or_children: list[ dict[str, Any] ] | dict[str, Any], target_id: str) -> HNCommentNode | None`:
    - Recursively traverses Algolia `children` trees to locate the comment where `str(child.get("id")) == str(target_id).lstrip("#")` and converts that comment plus its nested replies into an `HNCommentNode`.
  - `fetch_item_thread(self, hn_item_id: str, anchor_comment_id: str | None = None, was_untitled: bool = False) -> HNStoryThread`:
    - Queries `GET {self.base_url}/items/{hn_item_id}` via `requests.get`.
    - Parses story `title`, `url`, `author`, `points`, `children`.
    - If the Algolia item itself has `type == "comment"` (when an item ID was actually a comment ID), uses `story_id` or synthesizes the title from the comment.
    - Extracts up to 10 top-level comments (`top_comments`) and, if `anchor_comment_id` is provided, recursively isolates `anchor_subthread` via `find_comment_by_id`.
    - On `requests.RequestException` or offline state, returns a deterministic fallback `HNStoryThread` so pipelines never crash when offline.
  - `hydrate_safari_item(self, item: SafariLinkItem) -> tuple[SafariLinkItem, HNStoryThread | None]`:
    - If `item.hn_item_id` is present, calls `fetch_item_thread(item.hn_item_id, anchor_comment_id=item.anchor_comment_id, was_untitled=item.needs_title_hydration)`.
    - If `item.needs_title_hydration` is True and `thread.title` is non-empty, returns an updated copy of `item` with `title=f"{thread.title} | Hacker News"` and `needs_title_hydration=False`.
  - `fetch_front_page_stories(self, limit: int = 10) -> list[HNStoryThread]`:
    - Queries `GET {self.base_url}/search?tags=front_page&hitsPerPage={limit}` via `requests.get`, returning `list[HNStoryThread]` (with deterministic fallback on error).
- Dagster Asset:
  - `@asset def top_hn_discussions() -> pd.DataFrame:` wraps `HNClient().fetch_front_page_stories(limit=10)` and returns a DataFrame of top stories.

### 3.4 `src/time_capsule/cultural_assets.py`

Implement Reddit `.json` discussion fetcher and clean article metadata extractor:

- `CulturalContentSummary(BaseModel)`:
  - `url: str`
  - `source_type: str`
  - `title: str`
  - `subreddit: str | None = None`
  - `author: str = ""`
  - `score: int = 0`
  - `excerpt: str = ""`
  - `top_replies: list[str] = Field(default_factory=list)`
- `CulturalExtractor`:
  - `__init__(self, timeout: float = 5.0, user_agent: str = "TimeCapsuleBot/2.0") -> None`
  - `fetch_reddit_summary(self, reddit_url: str) -> CulturalContentSummary`:
    - Appends `.json` to the Reddit post path, queries `requests.get(json_url, headers={"User-Agent": self.user_agent}, timeout=self.timeout)`.
    - Extracts post `title`, `subreddit`, `selftext`, `score`, and top comment bodies from listing `[1]["data"]["children"]`.
    - Falls back deterministically to URL-slug synthesis on network error.
  - `fetch_article_summary(self, url: str, fallback_title: str = "") -> CulturalContentSummary`:
    - Queries `requests.get(url, headers={"User-Agent": self.user_agent}, timeout=self.timeout)`.
    - Extracts `<title>`, `<meta name="description">`, or first `<p>` paragraph text using regex/standard library HTML parsing.
    - Falls back deterministically using `fallback_title` and domain metadata if offline or PDF.
- Dagster Asset:
  - `@asset def cultural_discussions_snapshot() -> pd.DataFrame:` returns a DataFrame summarizing curated Reddit/article items.

### 3.5 `tests/test_weather_assets.py`, `tests/test_financial_assets.py`, `tests/test_assets.py`

- Ensure all test functions in `tests/test_weather_assets.py` and `tests/test_financial_assets.py` have full type annotations (`monkeypatch: pytest.MonkeyPatch`) and DbC docstrings (`Pre-conditions:` / `Post-conditions:`).
- In `tests/test_assets.py`, write comprehensive unit tests (mocking `requests.get` with `monkeypatch`) for:
  - `HNClient.fetch_item_thread` including nested comment trees and `#anchor_comment_id` (`50014121`, `46143525`, `47473516`, `49593756`, `50140985`) isolation.
  - `HNClient.hydrate_safari_item` resolving an untitled `"Hacker News"` tab (`item_id="49803892"`) to its hydrated story title.
  - `HNClient.fetch_front_page_stories` and offline fallback behavior.
  - `CulturalExtractor.fetch_reddit_summary` and `CulturalExtractor.fetch_article_summary` with mocked responses and offline fallback.
