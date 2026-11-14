"""Domain models and data schemas for Digital Time Capsule and Reading Vault.

Pre-conditions:
    - Pydantic v2 and Python standard typing modules must be available.

Post-conditions:
    - Exports domain enums, link items, search query intents, vocabulary entries,
      discussion analyses, daily snapshots, and vault parse results.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EpochId(StrEnum):
    """Identifier for longitudinal reading vault ingestion epochs.

    Pre-conditions:
        - None.

    Post-conditions:
        - String enum member matching known historical snapshots.
    """

    EPOCH_2023_2024 = "2023_2024"
    EPOCH_2026_08_16 = "2026_08_16"
    EPOCH_2026_11_06 = "2026_11_06"


class IntellectualPillar(StrEnum):
    """The six intellectual pillar taxonomies of technical taste and curiosity.

    Pre-conditions:
        - None.

    Post-conditions:
        - Categorical pillar identifier string.
    """

    AI_LLM_AGENTS = "PILLAR_1_AI_LLM_AGENTS"
    SYSTEMS_KERNEL = "PILLAR_2_SYSTEMS_KERNEL"
    INFRA_K8S_HOMELAB = "PILLAR_3_INFRA_K8S_HOMELAB"
    MATH_ML_THEORY = "PILLAR_4_MATH_ML_THEORY"
    SWE_CRAFT_CAREER = "PILLAR_5_SWE_CRAFT_CAREER"
    HUMANITIES_LIFE = "PILLAR_6_HUMANITIES_LIFE"


PILLAR_LABELS: dict[str, str] = {
    IntellectualPillar.AI_LLM_AGENTS.value: "AI, LLMs & Autonomous Agents",
    IntellectualPillar.SYSTEMS_KERNEL.value: "Systems, Kernel & Low-Level Engineering",
    IntellectualPillar.INFRA_K8S_HOMELAB.value: "Infrastructure, Kubernetes & Homelab",
    IntellectualPillar.MATH_ML_THEORY.value: "Mathematics, ML & Foundations",
    IntellectualPillar.SWE_CRAFT_CAREER.value: "Software Craftsmanship & Career",
    IntellectualPillar.HUMANITIES_LIFE.value: "Humanities, Life & Culture",
}


class SourceType(StrEnum):
    """Classification of content origin and hosting medium.

    Pre-conditions:
        - None.

    Post-conditions:
        - String enum representation of origin platform.
    """

    HACKER_NEWS = "hacker_news"
    REDDIT = "reddit"
    GITHUB = "github"
    GOOGLE_SEARCH = "google_search"
    DICTIONARY = "dictionary"
    PDF_PAPER = "pdf_paper"
    VIDEO = "video"
    ARTICLE = "article"


class QueryIntentCategory(StrEnum):
    """Categorical classification of search query intent.

    Pre-conditions:
        - None.

    Post-conditions:
        - String enum denoting vocabulary lookup, technical learning, or personal life query.
    """

    VOCABULARY = "vocabulary"
    TECHNICAL_LEARNING = "technical_learning"
    PERSONAL_LIFE = "personal_life"


class SafariLinkItem(BaseModel):
    """Canonical reading vault link item deduplicated across browser snapshot epochs.

    Pre-conditions:
        - item_id must be a deterministic hex string.
        - canonical_url must be normalized according to vault canonicalization rules.

    Post-conditions:
        - Represents an ingested or merged reading item with cross-epoch survival metrics.
    """

    item_id: str
    title: str
    url: str
    canonical_url: str
    domain: str
    source_type: SourceType
    epochs_present: list[str] = Field(default_factory=list)
    cross_epoch_count: int = 1
    is_evergreen_canon: bool = False
    total_occurrences: int = 1
    interest_weight: int = 1
    hn_item_id: str | None = None
    anchor_comment_id: str | None = None
    needs_title_hydration: bool = False
    was_untitled_tab: bool = False
    search_query: str | None = None
    query_intent_category: QueryIntentCategory | None = None
    pillar_tags: list[str] = Field(default_factory=list)
    primary_pillar: str = IntellectualPillar.SWE_CRAFT_CAREER.value


class VocabularyEntry(BaseModel):
    """Lexicon entry tracked from dictionary lookups and idiom searches.

    Pre-conditions:
        - term must be a non-empty string.

    Post-conditions:
        - Stores vocabulary item with longitudinal first-seen epoch and definition hint.
    """

    term: str
    source_url: str
    source_type: str
    epoch_first_seen: str
    epochs_present: list[str] = Field(default_factory=list)
    definition_hint: str = ""


class SearchQueryIntent(BaseModel):
    """Longitudinal search intent indicating active inquiry and knowledge exploration.

    Pre-conditions:
        - query_text must be non-empty.

    Post-conditions:
        - Categorized search query with epoch tracking and intellectual pillar associations.
    """

    query_text: str
    category: QueryIntentCategory
    source_url: str
    epoch_first_seen: str
    epochs_present: list[str] = Field(default_factory=list)
    pillar_tags: list[str] = Field(default_factory=list)


class DiscussionAnalysis(BaseModel):
    """Synthesized architectural and community perspective on a technical discussion.

    Pre-conditions:
        - sentiment_score bounded within [-1.0, 1.0].
        - controversy_score bounded within [0.0, 1.0].

    Post-conditions:
        - Captures consensus, pushback, anchor spotlight, and actionable takeaways.
    """

    item_id: str
    hn_item_id: str | None = None
    anchor_comment_id: str | None = None
    title: str
    core_thesis: str
    community_consensus: str
    contrarian_pushback: str
    anchor_comment_spotlight: str | None = None
    sentiment_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    controversy_score: float = Field(default=0.0, ge=0.0, le=1.0)
    pillar_tags: list[str] = Field(default_factory=list)
    actionable_takeaways: list[str] = Field(default_factory=list)
    model_used: str = "heuristic-vader"
    analyzed_at: str = ""


class DailyCapsuleSnapshot(BaseModel):
    """Consolidated snapshot combining macro indicators, discussions, and vault spotlights.

    Pre-conditions:
        - capsule_date formatted as YYYY-MM-DD.

    Post-conditions:
        - Bundles weather, financial, discussion, and reading vault highlights.
    """

    capsule_date: str
    weather_records: list[dict[str, Any]] = Field(default_factory=list)
    stock_records: list[dict[str, Any]] = Field(default_factory=list)
    top_discussions: list[DiscussionAnalysis] = Field(default_factory=list)
    evergreen_spotlight: list[SafariLinkItem] = Field(default_factory=list)
    markdown_digest: str = ""


class VaultParseResult(BaseModel):
    """Aggregate result from parsing and merging multi-epoch Safari reading vaults.

    Pre-conditions:
        - raw_link_count >= 0.

    Post-conditions:
        - Contains deduplicated items, evergreen canon subset, vocabulary, and intents.
    """

    items: list[SafariLinkItem] = Field(default_factory=list)
    evergreen_canon: list[SafariLinkItem] = Field(default_factory=list)
    vocabulary_entries: list[VocabularyEntry] = Field(default_factory=list)
    search_intents: list[SearchQueryIntent] = Field(default_factory=list)
    raw_link_count: int = 0
    epoch_counts: dict[str, int] = Field(default_factory=dict)
