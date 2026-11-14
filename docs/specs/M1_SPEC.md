# Milestone 1 Specification: Domain Models & Multi-Epoch Safari Reading Vault Parser

## 1. Objective & Scope

Implement the core Pydantic domain models (`src/time_capsule/models.py`), the multi-epoch Safari Reading Vault parser (`src/time_capsule/safari_parser.py`), the fix for import-time `APIResource` defaults (`src/time_capsule/resources.py` and `src/time_capsule/__init__.py`), and the comprehensive unit/integration test suite (`tests/test_safari_parser.py`).

## 2. Non-Negotiable Engineering Invariants

1. **Absolute Imports Only**: Every import from the package MUST use `from time_capsule...` (zero relative imports `from .` or `from ..`). Ruff rule `TID252` (`ban-relative-imports = "all"`) is enforced.
2. **Design by Contract (DbC)**: Every public class, method, and function MUST have a docstring containing explicit `Pre-conditions:` and `Post-conditions:` sections.
3. **Static Typing**: Every function and method signature MUST have full type annotations and pass `poetry run mypy src tests` with zero errors.
4. **Zero Emojis**: Do not use any emojis in code comments, docstrings, or string literals (except when stripping emojis from external seed titles if desired).

---

## 3. File-by-File Contracts

### 3.1 `src/time_capsule/resources.py` & `src/time_capsule/__init__.py`

- In `src/time_capsule/resources.py`:
  - `APIResource(ConfigurableResource)`:
    - Fields: `openweathermap_api_key: str | None = ""` and `alphavantage_api_key: str | None = ""`
    - Add DbC docstring (`Pre-conditions:` and `Post-conditions:`).
- In `src/time_capsule/__init__.py`:
  - Replace relative imports (`from . import ...`, `from .resources import APIResource`) with absolute imports (`from time_capsule import cultural_assets, financial_assets, news_assets, weather_assets` and `from time_capsule.resources import APIResource`).
  - Pass `openweathermap_api_key=os.getenv("OPENWEATHERMAP_API_KEY", "")` and `alphavantage_api_key=os.getenv("ALPHAVANTAGE_API_KEY", "")` so importing `time_capsule` when environment variables are unset does not raise a Pydantic `ValidationError`.

### 3.2 `src/time_capsule/models.py`

Define the following public enums, constants, and Pydantic `BaseModel` classes (each with DbC docstrings):

- `EpochId(StrEnum)`:
  - `EPOCH_2023_2024 = "2023_2024"`
  - `EPOCH_2026_08_16 = "2026_08_16"`
  - `EPOCH_2026_11_06 = "2026_11_06"`
- `IntellectualPillar(StrEnum)`:
  - `AI_LLM_AGENTS = "PILLAR_1_AI_LLM_AGENTS"`
  - `SYSTEMS_KERNEL = "PILLAR_2_SYSTEMS_KERNEL"`
  - `INFRA_K8S_HOMELAB = "PILLAR_3_INFRA_K8S_HOMELAB"`
  - `MATH_ML_THEORY = "PILLAR_4_MATH_ML_THEORY"`
  - `SWE_CRAFT_CAREER = "PILLAR_5_SWE_CRAFT_CAREER"`
  - `HUMANITIES_LIFE = "PILLAR_6_HUMANITIES_LIFE"`
- `PILLAR_LABELS: dict[str, str]` mapping each `IntellectualPillar` string value to its display title.
- `SourceType(StrEnum)`:
  - `HACKER_NEWS = "hacker_news"`
  - `REDDIT = "reddit"`
  - `GITHUB = "github"`
  - `GOOGLE_SEARCH = "google_search"`
  - `DICTIONARY = "dictionary"`
  - `PDF_PAPER = "pdf_paper"`
  - `VIDEO = "video"`
  - `ARTICLE = "article"`
- `QueryIntentCategory(StrEnum)`:
  - `VOCABULARY = "vocabulary"`
  - `TECHNICAL_LEARNING = "technical_learning"`
  - `PERSONAL_LIFE = "personal_life"`
- `SafariLinkItem(BaseModel)`:
  - `item_id: str` (deterministic 12-char hex SHA-256 prefix of `canonical_url`)
  - `title: str`
  - `url: str`
  - `canonical_url: str`
  - `domain: str`
  - `source_type: SourceType`
  - `epochs_present: list[str] = Field(default_factory=list)`
  - `cross_epoch_count: int = 1`
  - `is_evergreen_canon: bool = False`
  - `total_occurrences: int = 1`
  - `interest_weight: int = 1`
  - `hn_item_id: str | None = None`
  - `anchor_comment_id: str | None = None`
  - `needs_title_hydration: bool = False`
  - `was_untitled_tab: bool = False`
  - `search_query: str | None = None`
  - `query_intent_category: QueryIntentCategory | None = None`
  - `pillar_tags: list[str] = Field(default_factory=list)`
  - `primary_pillar: str = IntellectualPillar.SWE_CRAFT_CAREER.value`
- `VocabularyEntry(BaseModel)`:
  - `term: str`
  - `source_url: str`
  - `source_type: str`
  - `epoch_first_seen: str`
  - `epochs_present: list[str] = Field(default_factory=list)`
  - `definition_hint: str = ""`
- `SearchQueryIntent(BaseModel)`:
  - `query_text: str`
  - `category: QueryIntentCategory`
  - `source_url: str`
  - `epoch_first_seen: str`
  - `epochs_present: list[str] = Field(default_factory=list)`
  - `pillar_tags: list[str] = Field(default_factory=list)`
- `DiscussionAnalysis(BaseModel)`:
  - `item_id: str`
  - `hn_item_id: str | None = None`
  - `anchor_comment_id: str | None = None`
  - `title: str`
  - `core_thesis: str`
  - `community_consensus: str`
  - `contrarian_pushback: str`
  - `anchor_comment_spotlight: str | None = None`
  - `sentiment_score: float = Field(default=0.0, ge=-1.0, le=1.0)`
  - `controversy_score: float = Field(default=0.0, ge=0.0, le=1.0)`
  - `pillar_tags: list[str] = Field(default_factory=list)`
  - `actionable_takeaways: list[str] = Field(default_factory=list)`
  - `model_used: str = "heuristic-vader"`
  - `analyzed_at: str = ""`
- `DailyCapsuleSnapshot(BaseModel)`:
  - `capsule_date: str`
  - `weather_records: list[dict[str, Any]] = Field(default_factory=list)`
  - `stock_records: list[dict[str, Any]] = Field(default_factory=list)`
  - `top_discussions: list[DiscussionAnalysis] = Field(default_factory=list)`
  - `evergreen_spotlight: list[SafariLinkItem] = Field(default_factory=list)`
  - `markdown_digest: str = ""`
- `VaultParseResult(BaseModel)`:
  - `items: list[SafariLinkItem] = Field(default_factory=list)`
  - `evergreen_canon: list[SafariLinkItem] = Field(default_factory=list)`
  - `vocabulary_entries: list[VocabularyEntry] = Field(default_factory=list)`
  - `search_intents: list[SearchQueryIntent] = Field(default_factory=list)`
  - `raw_link_count: int = 0`
  - `epoch_counts: dict[str, int] = Field(default_factory=dict)`

### 3.3 `src/time_capsule/safari_parser.py`

Implement the following public functions with strict DbC docstrings:

1. `canonicalize_url(raw_url: str) -> str`:
   - Parses `raw_url`. Normalizes `netloc` to lowercase, strips leading `www.`, maps `m.youtube.com` -> `youtube.com` and `en.m.wikipedia.org` -> `en.wikipedia.org`.
   - For `news.ycombinator.com`:
     - If `id` is in query string and path is `/item`, returns `f"https://news.ycombinator.com/item?id={qs['id'][0]}"` (stripping `#fragment` so `#50014121` merges with the parent item while preserving `anchor_comment_id` on the item).
     - If `id` is in query string and path is `/user`, returns `f"https://news.ycombinator.com/user?id={qs['id'][0]}"`.
     - Otherwise returns `f"https://news.ycombinator.com{path.rstrip('/')}"`.
   - For `google.com/search`:
     - Extracts `q` query parameter, strips and lowercases it, and returns `f"https://google.com/search?q={q}"`.
   - For all other URLs:
     - Strips tracking parameters (`utm_source`, `utm_medium`, `utm_campaign`, `utm_id`, `term`, `_kx`, `tag`, `type`, `subtype`, `fbclid`, `gclid`, `_gl`, `_ga`, `aff`, `irclickid`, `irgwc`, `afsrc`, `ref`, `loc`, `acampID`, `mpid`, `affgroup`, `ncid`, `_bt`, `_bk`, `_bm`, `_bn`, `_bg`, `gad_source`, `force-legacy-sct`, `chainedPosts`, `ra`, `pp`) while keeping meaningful query parameters (`v`, `tab`, `gh_jid`, `view`, `category`, `page`, `hashed`, `listFilterMode`).
     - Strips trailing `/` from path and drops URL fragments.

2. `extract_hn_metadata(title: str, raw_url: str) -> tuple[str | None, str | None, bool]`:
   - Returns `(hn_item_id, anchor_comment_id, is_untitled)`.
   - If `news.ycombinator.com` in URL:
     - Extracts `hn_item_id` from `?id=...` when path is `/item`.
     - Extracts `anchor_comment_id` from URL fragment (`#50014121`, `#46143525`, `#47473516`, `#49593756`, `#50140985`) when fragment is numeric (or strips leading `#`). Note: also recognize `46138952` as the story ID for `#46143525`.
     - Marks `is_untitled = True` if `title.strip()` is in `{"Hacker News", "[Hacker News]", "Start Page", "Can’t Open Page", "Can't Open Page"}`.

3. `classify_search_or_dictionary(title: str, raw_url: str) -> tuple[str | None, QueryIntentCategory | None, str | None]`:
   - Returns `(term_or_query, category, definition_hint)`.
   - Detects dictionary/lexicon links:
     - `dictionary.cambridge.org` (e.g. `temerity`)
     - `merriam-webster.com/dictionary/` (e.g. `posit`, `obstinate`)
     - `wikipedia.org/wiki/Demonym` (`demonym`)
   - Detects Google Search `?q=` URLs, extracts decoded query string `q` (cleaning `\(audio streaming server\)` -> `(audio streaming server)`).
   - Classifies into:
     - `QueryIntentCategory.VOCABULARY` when it is a dictionary/Demonym link OR the search query matches known vocabulary/idiom lookups (`de rigueur`, `temerity`, `posit`, `ennui`, `malingerers`, `obstinance`, `obstinate`, `vis a vis`, `backbiting`, `demonym`, `urdu kismat meaning`, `vas deferens`, `ptolemy`, `franz.kafka`, `das kapital`, `stavridis`, `loewhaley`). Specifically, ensure `extract_vocabulary_entries` includes the core vocabulary lexicon (`de rigueur`, `temerity`, `posit`, `ennui`, `malingerers`, `obstinance`, `obstinate`, `vis a vis`, `backbiting`, `demonym`, `urdu kismat meaning`, `vas deferens`) with concise human-readable `definition_hint` strings.
     - `QueryIntentCategory.PERSONAL_LIFE` when the query is about cars/home/health/entertainment/local life (`2006 gx470 headlights`, `how long do yoy have to teturn tennants deposit`, `reasonable cleaning fee for small apartment in california after 5 years`, `how to find my aetna member id`, `castle peak state park`, `dim sum`, `russell peters hbo`, `jo koy`, `The Ugly Truth`, `how soccer explains the world`, `how top play power point as looping video`, `Google fitbit air vs whoop reddit`, `masterplan cast`, `Experience Beyond plan`, `industries with highest employment rate`).
     - `QueryIntentCategory.TECHNICAL_LEARNING` for all technical/engineering/math/AI/systems search queries (`linear algebra rank reduction`, `platonic solids`, `multi tenant`, `twingate`, `reduced sinplified or eliminated your homelab`, `systemctl list-unit-files`, `how to get started with linux kernel programming`, `bigquery`, `searxng`, `can open code be used as an agent harness`, `zig lang`, `ISC 2026`, `data cleaning for a good cause`, `cool examples of graphical programming opengl`, `sr. ai infra engineer duties`, `XMPP`, `calibre ebook linux desktop client`, `graylog siem`, `leaening ml in the age of ai make sense`, `erlang beam`, `AI compute extensions`, `Gemini Flash Lite 2.5`, `Messaging queues and brokers. RabbitMQ, BullMQ`, `gonic (audio streaming server)`, `how do i back up cephfs data`, `metrics exporter`, `kubernetes operator`, `elixir vs rust job market`).

4. `classify_pillars(title: str, raw_url: str, search_query: str | None = None) -> list[str]`:
   - Deterministically maps an item to 1–3 `IntellectualPillar` values based on keyword/domain rules, always returning at least 1 pillar.

5. `parse_safari_export_text(text: str, epoch_id: str) -> list[SafariLinkItem]`:
   - Parses raw Apple Notes / Safari export text, ignoring the CSS header line (`p.p1 {margin: ...}`), extracting every `[Title](URL)` markdown link in order.

6. `merge_vault_items(raw_items: list[SafariLinkItem], epoch_counts: dict[str, int] | None = None) -> VaultParseResult`:
   - Groups `raw_items` by `canonical_url`.
   - Computes `epochs_present` (sorted unique epoch IDs), `cross_epoch_count = len(epochs_present)`, `is_evergreen_canon = (cross_epoch_count == 3)`, `total_occurrences = len(group)`, `interest_weight = len(group)`.
   - Preserves any non-None `anchor_comment_id` from any occurrence in the group.
   - If one occurrence had a generic title (`Hacker News`, `Start Page`, etc.) and another occurrence had a real descriptive title, uses the descriptive title for `title`, sets `was_untitled_tab = True`, and sets `needs_title_hydration = True` if the final merged `title` is still generic (`Hacker News`, `[Hacker News]`, `Start Page`, `Can’t Open Page`, `Can't Open Page`).
   - Builds deduplicated `vocabulary_entries: list[VocabularyEntry]` and `search_intents: list[SearchQueryIntent]`.

7. `parse_seed_directory(seed_dir: str | Path = "data/seeds") -> VaultParseResult`:
   - Reads the 3 canonical seed files:
     - `safari_open_tabs_2023_2024.txt` -> `EpochId.EPOCH_2023_2024.value` (`"2023_2024"`)
     - `safari_bookmarks_2026_08_16.txt` -> `EpochId.EPOCH_2026_08_16.value` (`"2026_08_16"`)
     - `safari_tabs_2026_11_06.txt` -> `EpochId.EPOCH_2026_11_06.value` (`"2026_11_06"`)
   - Returns the merged `VaultParseResult`.

### 3.4 `tests/test_safari_parser.py`

Write fast, deterministic tests verifying:
- `canonicalize_url` strips tracking params and normalizes HN / Google Search URLs.
- `extract_hn_metadata` extracts `hn_item_id`, `anchor_comment_id`, and `is_untitled`.
- `parse_seed_directory("data/seeds")` parses all 3 files (`raw_link_count == 828`), yields exactly `14` items in `evergreen_canon` (`cross_epoch_count == 3` and `is_evergreen_canon is True`), extracts all 5 HN anchor comment IDs (`50014121`, `46143525`, `47473516`, `49593756`, `50140985`) across stories (`49985548`, `46138952`, `47471801`, `49589914`, `50138531`), flags untitled HN tabs (`was_untitled_tab` / `needs_title_hydration`), and populates `vocabulary_entries` (containing `de rigueur`, `temerity`, `posit`, `ennui`, `malingerers`, `obstinance`, `vis a vis`, `backbiting`, `demonym`, `urdu kismat meaning`) and `search_intents`.
