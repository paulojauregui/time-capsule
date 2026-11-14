# Milestone 3 Specification: DGX Spark LLM Discussion Analyzer, Sentiment Engine & Taste Profile

## 1. Objective & Scope

Implement `src/time_capsule/enrichment.py` and `tests/test_enrichment.py` to combine fast baseline VADER lexical sentiment analysis (`vaderSentiment`) with an asynchronous OpenAI-compatible client targeting `SPARK_LLM_BASE_URL` (`http://happy.tail749110.ts.net:8000/v1`, model `nvidia/Qwen3.8-Flash-Next-FP4-Local`), guarded by a `< 2.0s` health probe and deterministic heuristic fallback when offline.

## 2. Non-Negotiable Engineering Invariants

1. **Absolute Imports Only**: Use `from time_capsule...` exclusively.
2. **Design by Contract (DbC)**: Every public class, method, and function MUST include `Pre-conditions:` and `Post-conditions:` in its docstring.
3. **Static Typing**: Full type annotations passing `poetry run mypy src tests`.
4. **Zero External Network Calls in Unit Tests**: All HTTP calls in `tests/test_enrichment.py` must be mocked (`httpx.AsyncClient` / `monkeypatch`) and run in `< 1s`.

---

## 3. File-by-File Contracts

### 3.1 `src/time_capsule/enrichment.py`

Implement the following classes and functions with strict DbC docstrings:

1. `SentimentMetrics(BaseModel)`:
   - `compound_score: float = Field(ge=-1.0, le=1.0)`
   - `positive_ratio: float = Field(ge=0.0, le=1.0)`
   - `negative_ratio: float = Field(ge=0.0, le=1.0)`
   - `neutral_ratio: float = Field(ge=0.0, le=1.0)`
   - `controversy_score: float = Field(ge=0.0, le=1.0)`

2. `compute_vader_sentiment(texts: list[str]) -> SentimentMetrics`:
   - Uses `vaderSentiment.vaderSentiment.SentimentIntensityAnalyzer` to score a list of text segments (e.g., story title + comment texts).
   - Computes mean `compound_score` clamped to `[-1.0, 1.0]`.
   - Computes `controversy_score` in `[0.0, 1.0]` based on polarization/variance across comments (or balance of strong positive and negative lexicon hits when both `pos` and `neg` are active).

3. `SparkDiscussionAnalyzer`:
   - `__init__(self, base_url: str | None = None, model: str | None = None, probe_timeout: float = 1.8, request_timeout: float = 20.0) -> None`:
     - Defaults `base_url` to `os.getenv("SPARK_LLM_BASE_URL", "http://happy.tail749110.ts.net:8000/v1")` and `model` to `os.getenv("SPARK_LLM_MODEL", "nvidia/Qwen3.8-Flash-Next-FP4-Local")`.
   - `async def check_spark_available(self) -> bool`:
     - Performs a fast `< 2.0s` (`self.probe_timeout`) HTTP GET to `{self.base_url}/models` using `httpx.AsyncClient`. Returns `True` if status 200, `False` on any exception or non-200 status (Zero-Retry Circuit Breaker).
   - `def build_heuristic_analysis(self, item: SafariLinkItem, thread: HNStoryThread | None = None, cultural: CulturalContentSummary | None = None) -> DiscussionAnalysis`:
     - Deterministic synthesis fallback when DGX Spark is offline or `use_llm=False`.
     - Extracts texts from `item.title`, `thread.top_comments`, `thread.anchor_subthread`, or `cultural.excerpt` / `cultural.top_replies`.
     - Calls `compute_vader_sentiment(texts)` for `sentiment_score` and `controversy_score`.
     - Generates high-signal structured fields:
       - `core_thesis`
       - `community_consensus`
       - `contrarian_pushback`
       - `anchor_comment_spotlight` (specifically highlighting `thread.anchor_subthread` or `item.anchor_comment_id` when present!)
       - `pillar_tags` (from `item.pillar_tags` or `classify_pillars`)
       - `actionable_takeaways` (2–3 concrete engineering takeaways mapped to the item's primary pillar)
       - `model_used = "heuristic-vader"`
   - `async def analyze_item_async(self, item: SafariLinkItem, thread: HNStoryThread | None = None, cultural: CulturalContentSummary | None = None, allow_llm: bool = True) -> DiscussionAnalysis`:
     - If `allow_llm` is True and `await self.check_spark_available()` is True:
       - Sends a chat completion request to `{self.base_url}/chat/completions` (`model=self.model`, `temperature=0.2`, `max_tokens=600`) requesting a JSON object with `core_thesis`, `community_consensus`, `contrarian_pushback`, `anchor_comment_spotlight`, `actionable_takeaways`, and optional `pillar_tags`.
       - Combines LLM synthesis with VADER `sentiment_score` and `controversy_score`, setting `model_used=self.model`.
       - On any timeout, HTTP error, or JSON parse failure, falls back immediately without retry to `build_heuristic_analysis(...)`.
     - Otherwise returns `build_heuristic_analysis(item, thread=thread, cultural=cultural)`.
   - `def analyze_item(self, item: SafariLinkItem, thread: HNStoryThread | None = None, cultural: CulturalContentSummary | None = None, allow_llm: bool = False) -> DiscussionAnalysis`:
     - Synchronous wrapper supporting both deterministic heuristic mode (`allow_llm=False`) and event-loop execution when `allow_llm=True`.

4. `compute_taste_profile_summary(items: list[SafariLinkItem]) -> dict[str, Any]`:
   - Computes longitudinal intellectual taste distribution across the 6 Intellectual Pillars (`PILLAR_1`..`PILLAR_6`) overall and per epoch (`2023_2024`, `2026_08_16`, `2026_11_06`), identifying top rising pillars (e.g. shift from job-search/webdev in `2023_2024` toward local LLM harnesses, Linux kernel, and homelab infrastructure in `2026_08_16` and `2026_11_06`).

### 3.2 `tests/test_enrichment.py`

Write fast unit tests covering:
- `compute_vader_sentiment` polarity and controversy scoring on positive, negative, and mixed comment sets.
- `build_heuristic_analysis` with an anchored HN thread (`anchor_comment_id="50014121"`), verifying `anchor_comment_spotlight` is populated and scores are within valid bounds (`[-1.0, 1.0]` and `[0.0, 1.0]`).
- `analyze_item_async` with mocked `httpx.AsyncClient` simulating (a) healthy `nvidia/Qwen3.8-Flash-Next-FP4-Local` JSON response and (b) circuit-breaker fallback when `check_spark_available` returns `False` or times out.
- `compute_taste_profile_summary` across multi-epoch `SafariLinkItem` fixtures.
