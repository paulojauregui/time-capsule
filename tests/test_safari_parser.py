"""Unit and integration tests for multi-epoch Safari Reading Vault parser.

Pre-conditions:
    - Test runner pytest and package time_capsule must be installed and importable.
    - Seed files must be present under data/seeds directory.

Post-conditions:
    - Validates URL canonicalization, HN metadata extraction, search intent classification,
      pillar tagging, and cross-epoch deduplication across all three historical snapshots.
"""

from pathlib import Path

from time_capsule.models import (
    IntellectualPillar,
    QueryIntentCategory,
    VaultParseResult,
)
from time_capsule.safari_parser import (
    canonicalize_url,
    classify_pillars,
    classify_search_or_dictionary,
    extract_hn_metadata,
    merge_vault_items,
    parse_safari_export_text,
    parse_seed_directory,
)


def test_canonicalize_url_tracking_and_normalization() -> None:
    """Test that canonicalize_url strips tracking parameters, fragments, and www prefix.

    Pre-conditions:
        - Input URLs contain various tracking query parameters and fragments.

    Post-conditions:
        - Confirms returned URL preserves essential parameters while discarding tracking tags.
    """
    raw_url = "https://www.example.com/blog/post/?utm_source=twitter&utm_medium=social&v=42#intro"
    canon = canonicalize_url(raw_url)
    assert canon == "https://example.com/blog/post?v=42"

    raw_yt = "https://m.youtube.com/watch?v=dQw4w9WgXcQ&fbclid=12345"
    assert canonicalize_url(raw_yt) == "https://youtube.com/watch?v=dQw4w9WgXcQ"

    raw_wiki = "https://en.m.wikipedia.org/wiki/Demonym#Etymology"
    assert canonicalize_url(raw_wiki) == "https://en.wikipedia.org/wiki/Demonym"


def test_canonicalize_url_hacker_news_and_google_search() -> None:
    """Test URL canonicalization for Hacker News items and Google Search queries.

    Pre-conditions:
        - Hacker News URLs with comment anchors and Google Search URLs with tracking parameters.

    Post-conditions:
        - Asserts comment fragments are stripped from HN item URLs and Google queries are normalized.
    """
    hn_item = "https://news.ycombinator.com/item?id=46138952#46143525"
    assert canonicalize_url(hn_item) == "https://news.ycombinator.com/item?id=46138952"

    hn_user = "https://news.ycombinator.com/user?id=pg"
    assert canonicalize_url(hn_user) == "https://news.ycombinator.com/user?id=pg"

    hn_root = "https://news.ycombinator.com/"
    assert canonicalize_url(hn_root) == "https://news.ycombinator.com"

    google_search = "https://www.google.com/search?q=de+rigueur&client=safari&hl=en-us"
    assert canonicalize_url(google_search) == "https://google.com/search?q=de rigueur"

    escaped_google = "https://www.google.com/search?q=gonic+\\(audio+streaming+server\\"
    assert canonicalize_url(escaped_google) == "https://google.com/search?q=gonic (audio streaming server)"


def test_extract_hn_metadata() -> None:
    """Test extraction of Hacker News story IDs, anchor comment IDs, and untitled indicators.

    Pre-conditions:
        - Hacker News URLs with and without fragments, generic titles, and non-HN URLs.

    Post-conditions:
        - Verifies exact identification of story ID, anchor comment ID, and untitled status.
    """
    hn_id, anchor_id, is_untitled = extract_hn_metadata(
        "Hacker News", "https://news.ycombinator.com/item?id=49985548#50014121"
    )
    assert hn_id == "49985548"
    assert anchor_id == "50014121"
    assert is_untitled is True

    hn_id, anchor_id, is_untitled = extract_hn_metadata(
        "Everyone in Seattle hates AI | Hacker News",
        "https://news.ycombinator.com/item?id=46138952#46143525",
    )
    assert hn_id == "46138952"
    assert anchor_id == "46143525"
    assert is_untitled is False

    hn_id, anchor_id, is_untitled = extract_hn_metadata(
        "Start Page", "https://news.ycombinator.com/item?id=48914646"
    )
    assert hn_id == "48914646"
    assert anchor_id is None
    assert is_untitled is True

    hn_id, anchor_id, is_untitled = extract_hn_metadata(
        "Calm Tech", "https://calmtech.com"
    )
    assert hn_id is None
    assert anchor_id is None
    assert is_untitled is False


def test_classify_search_or_dictionary() -> None:
    """Test detection and classification of dictionary references and Google search intents.

    Pre-conditions:
        - Diverse URLs including Cambridge dictionary, Merriam-Webster, Wikipedia, and Google Search.

    Post-conditions:
        - Asserts appropriate QueryIntentCategory classification and term extraction.
    """
    term, cat, hint = classify_search_or_dictionary(
        "TEMERITY | definition",
        "https://dictionary.cambridge.org/us/dictionary/english/temerity",
    )
    assert term == "temerity"
    assert cat == QueryIntentCategory.VOCABULARY
    assert hint is not None and "audacity" in hint

    term, cat, hint = classify_search_or_dictionary(
        "Posit Definition", "https://www.merriam-webster.com/dictionary/posit"
    )
    assert term == "posit"
    assert cat == QueryIntentCategory.VOCABULARY
    assert hint is not None and "assume" in hint

    term, cat, _ = classify_search_or_dictionary(
        "2006 gx470 headlights - Google Search",
        "https://www.google.com/search?q=2006+gx470+headlights",
    )
    assert term == "2006 gx470 headlights"
    assert cat == QueryIntentCategory.PERSONAL_LIFE

    term, cat, _ = classify_search_or_dictionary(
        "kubernetes operator - Google Search",
        "https://www.google.com/search?q=kubernetes+operator",
    )
    assert term == "kubernetes operator"
    assert cat == QueryIntentCategory.TECHNICAL_LEARNING

    term, cat, _ = classify_search_or_dictionary("Normal Page", "https://example.com/docs")
    assert term is None
    assert cat is None


def test_classify_pillars() -> None:
    """Test deterministic mapping of content items to 1-3 intellectual pillar taxonomies.

    Pre-conditions:
        - Titles and URLs spanning AI, low-level systems, Kubernetes infrastructure, and career topics.

    Post-conditions:
        - Confirms returned list contains between 1 and 3 valid pillar identifiers.
    """
    ai_pillars = classify_pillars(
        "Building reliable systems out of unreliable agents",
        "https://news.ycombinator.com/item?id=39984209",
    )
    assert IntellectualPillar.AI_LLM_AGENTS.value in ai_pillars
    assert 1 <= len(ai_pillars) <= 3

    sys_pillars = classify_pillars(
        "Linux kernel programming guide",
        "https://www.google.com/search?q=how+to+get+started+with+linux+kernel+programming",
        search_query="how to get started with linux kernel programming",
    )
    assert IntellectualPillar.SYSTEMS_KERNEL.value in sys_pillars

    infra_pillars = classify_pillars(
        "Kubernetes the hard way",
        "https://github.com/kelseyhightower/kubernetes-the-hard-way",
    )
    assert IntellectualPillar.INFRA_K8S_HOMELAB.value in infra_pillars


def test_parse_safari_export_text_and_merge() -> None:
    """Test single-epoch text parsing and subsequent multi-epoch merging logic.

    Pre-conditions:
        - Synthetic export texts containing duplicate tabs and untitled tab states.

    Post-conditions:
        - Asserts correct occurrence counting, title resolution, and interest weight computation.
    """
    raw_text = """
    p.p1 {margin: 0.0px 0.0px 0.0px 0.0px; font: 20.0px 'Helvetica Neue'}
    [Hacker News](https://news.ycombinator.com/item?id=49985548#50014121)
    [Calm Technology](https://calmtech.com/)
    """
    items = parse_safari_export_text(raw_text, "epoch_1")
    assert len(items) == 2
    assert items[0].was_untitled_tab is True
    assert items[0].anchor_comment_id == "50014121"

    second_text = """
    p.p1 {margin: 0.0px 0.0px 0.0px 0.0px; font: 20.0px 'Helvetica Neue'}
    [Ask HN: What do you run on a $5 VPS?](https://news.ycombinator.com/item?id=49985548)
    [Calm Technology](https://calmtech.com/)
    """
    second_items = parse_safari_export_text(second_text, "epoch_2")
    merged_res: VaultParseResult = merge_vault_items(items + second_items)

    assert len(merged_res.items) == 2
    hn_merged = next(i for i in merged_res.items if i.hn_item_id == "49985548")
    assert hn_merged.title == "Ask HN: What do you run on a $5 VPS?"
    assert hn_merged.was_untitled_tab is True
    assert hn_merged.needs_title_hydration is False
    assert hn_merged.anchor_comment_id == "50014121"
    assert hn_merged.cross_epoch_count == 2
    assert hn_merged.total_occurrences == 2
    assert hn_merged.interest_weight == 2


def test_parse_seed_directory_comprehensive() -> None:
    """Test full multi-epoch parsing and cross-epoch survival algebra on the canonical seed vault.

    Pre-conditions:
        - Seeds under data/seeds containing all 828 historical links across 3 epochs.

    Post-conditions:
        - Asserts raw_link_count is 828.
        - Asserts exactly 14 items in evergreen_canon with cross_epoch_count == 3.
        - Verifies extraction of all 5 HN anchor comments on their respective stories.
        - Verifies untitled HN tab detection and title hydration flagging.
        - Validates inclusion of all core vocabulary lexicon entries and search intents.
    """
    seeds_dir = Path("data/seeds")
    assert seeds_dir.exists(), "Seeds directory data/seeds must exist."

    result: VaultParseResult = parse_seed_directory(seeds_dir)

    assert result.raw_link_count == 828
    assert result.epoch_counts == {
        "2023_2024": 229,
        "2026_08_16": 279,
        "2026_11_06": 320,
    }

    assert len(result.evergreen_canon) == 14
    for item in result.evergreen_canon:
        assert item.cross_epoch_count == 3
        assert item.is_evergreen_canon is True
        assert len(item.epochs_present) == 3

    evergreen_urls = {item.canonical_url for item in result.evergreen_canon}
    assert "https://calmtech.com" in evergreen_urls
    assert "https://publicbooks.org/this-is-your-brain-on-books" in evergreen_urls
    assert "https://dariusforoux.com/stages-of-life" in evergreen_urls
    assert "https://news.ycombinator.com/item?id=38037141" in evergreen_urls

    expected_anchors: dict[str, str] = {
        "49985548": "50014121",
        "46138952": "46143525",
        "47471801": "47473516",
        "49589914": "49593756",
        "50138531": "50140985",
    }
    for story_id, expected_anchor in expected_anchors.items():
        matched = [i for i in result.items if i.hn_item_id == story_id]
        assert len(matched) == 1, f"Story {story_id} must exist in parsed vault items."
        assert (
            matched[0].anchor_comment_id == expected_anchor
        ), f"Story {story_id} must have anchor comment {expected_anchor}"

    untitled_items = [i for i in result.items if i.was_untitled_tab]
    assert len(untitled_items) > 0, "Must identify untitled tabs."
    hydration_needed = [i for i in result.items if i.needs_title_hydration]
    assert len(hydration_needed) > 0, "Must flag generic tabs needing hydration."

    vocab_terms = {v.term for v in result.vocabulary_entries}
    required_vocab = {
        "de rigueur",
        "temerity",
        "posit",
        "ennui",
        "malingerers",
        "obstinance",
        "vis a vis",
        "backbiting",
        "demonym",
        "urdu kismat meaning",
    }
    for term in required_vocab:
        assert term in vocab_terms, f"Vocabulary term '{term}' must be extracted."

    for v in result.vocabulary_entries:
        assert len(v.definition_hint) > 0, f"Vocabulary term '{v.term}' must have definition hint."

    assert len(result.search_intents) > 0
    intent_categories = {si.category for si in result.search_intents}
    assert QueryIntentCategory.VOCABULARY in intent_categories
    assert QueryIntentCategory.PERSONAL_LIFE in intent_categories
    assert QueryIntentCategory.TECHNICAL_LEARNING in intent_categories
