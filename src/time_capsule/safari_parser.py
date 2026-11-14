"""Multi-Epoch Safari Reading Vault parser, canonicalizer, and classifier.

Pre-conditions:
    - Target seed files or raw export text must follow standard Apple Notes / Safari markdown format.

Post-conditions:
    - Provides deterministic URL canonicalization, metadata extraction, pillar tagging,
      and cross-epoch vault merging.
"""

import hashlib
import re
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from time_capsule.models import (
    EpochId,
    IntellectualPillar,
    QueryIntentCategory,
    SafariLinkItem,
    SearchQueryIntent,
    SourceType,
    VaultParseResult,
    VocabularyEntry,
)

GENERIC_HN_TITLES: set[str] = {
    "Hacker News",
    "[Hacker News]",
    "Start Page",
    "Can’t Open Page",
    "Can't Open Page",
}

TRACKING_PARAMS: set[str] = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_id",
    "term",
    "_kx",
    "tag",
    "type",
    "subtype",
    "fbclid",
    "gclid",
    "_gl",
    "_ga",
    "aff",
    "irclickid",
    "irgwc",
    "afsrc",
    "ref",
    "loc",
    "acampid",
    "mpid",
    "affgroup",
    "ncid",
    "_bt",
    "_bk",
    "_bm",
    "_bn",
    "_bg",
    "gad_source",
    "force-legacy-sct",
    "chainedposts",
    "ra",
    "pp",
    "sca_esv",
    "sxsrf",
    "ved",
    "biw",
    "bih",
    "fbs",
    "mstk",
    "sei",
    "ei",
    "oq",
    "gs_lp",
    "ie",
    "oe",
    "hl",
    "client",
    "udm",
    "sa",
    "spell",
    "dpr",
    "stick",
}

VOCABULARY_TERMS: dict[str, str] = {
    "de rigueur": "Required by etiquette or current fashion",
    "temerity": "Excessive confidence or boldness; audacity",
    "posit": "To assume or put forward as fact or basis of argument",
    "ennui": "A feeling of listlessness and dissatisfaction from lack of occupation or excitement; boredom",
    "malingerers": "Those who pretend illness or incapacity to shirk duty or work",
    "obstinance": "Stubbornness; the trait of being unyielding or obstinate",
    "obstinate": "Stubbornly refusing to change one's opinion or chosen course of action",
    "vis a vis": "In relation to; with regard to; face-to-face",
    "backbiting": "Malicious talk about someone who is not present",
    "demonym": "A noun or adjective identifying a native or inhabitant of a particular place",
    "urdu kismat meaning": "Fate, destiny, or fortune in Urdu",
    "vas deferens": "The duct that conveys sperm from the testicle to the urethra",
    "ptolemy": "Alexandrian mathematician, astronomer, and geographer",
    "franz.kafka": "German-speaking Bohemian novelist and short-story writer",
    "das kapital": "Foundational 1867 theoretical treatise in economics by Karl Marx",
    "stavridis": "Retired US Navy admiral and former Supreme Allied Commander Europe",
    "loewhaley": "Comedic creator portraying corporate workplace archetypes",
}

PERSONAL_QUERY_PATTERNS: list[str] = [
    "2006 gx470 headlights",
    "how long do yoy have to teturn tennants deposit",
    "reasonable cleaning fee for small apartment in california after 5 years",
    "how to find my aetna member id",
    "castle peak state park",
    "dim sum",
    "russell peters hbo",
    "jo koy",
    "the ugly truth",
    "how soccer explains the world",
    "how top play power point as looping video",
    "google fitbit air vs whoop reddit",
    "masterplan cast",
    "experience beyond plan",
    "industries with highest employment rate",
    "headlight",
    "deposit",
    "tennant",
    "cleaning fee",
    "apartment",
    "aetna",
    "state park",
    "dim sum",
    "russell peters",
    "jo koy",
    "ugly truth",
    "soccer",
    "looping video",
    "fitbit",
    "whoop",
    "masterplan",
    "experience beyond",
    "employment rate",
]


def clean_search_query(raw_query: str) -> str:
    """Clean and normalize raw Google search queries.

    Pre-conditions:
        - raw_query must be a string.

    Post-conditions:
        - Returns unescaped and formatted query string.
    """
    cleaned = raw_query.replace("\\(audio streaming server\\", "(audio streaming server)")
    cleaned = cleaned.replace(r"\(audio streaming server\)", "(audio streaming server)")
    cleaned = cleaned.replace(r"\(", "(").replace(r"\)", ")")
    if cleaned.endswith("\\"):
        cleaned = cleaned[:-1] + ")"
    return cleaned.strip()


def canonicalize_url(raw_url: str) -> str:
    """Normalize raw URL by stripping tracking parameters, fragments, and host variances.

    Pre-conditions:
        - raw_url is a non-empty string URL or web address.

    Post-conditions:
        - Returns deterministic canonical URL string without tracking tokens or fragments.
    """
    url = raw_url.strip()
    parsed = urlparse(url)
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()

    if netloc.startswith("www."):
        netloc = netloc[4:]
    if netloc == "m.youtube.com":
        netloc = "youtube.com"
    elif netloc == "en.m.wikipedia.org":
        netloc = "en.wikipedia.org"

    path = parsed.path.rstrip("/")

    if "news.ycombinator.com" in netloc:
        qs = parse_qs(parsed.query)
        if path == "/item" and "id" in qs:
            return f"https://news.ycombinator.com/item?id={qs['id'][0]}"
        elif path == "/user" and "id" in qs:
            return f"https://news.ycombinator.com/user?id={qs['id'][0]}"
        else:
            clean_path = path if path else ""
            return f"https://news.ycombinator.com{clean_path}"

    if (netloc == "google.com" or netloc.endswith(".google.com")) and path == "/search":
        qs = parse_qs(parsed.query)
        q = qs.get("q", [""])[0].strip()
        q = clean_search_query(q).lower()
        return f"https://google.com/search?q={q}"

    qs = parse_qs(parsed.query, keep_blank_values=True)
    kept_query: list[tuple[str, str]] = []
    for k, vals in qs.items():
        if k.lower() not in TRACKING_PARAMS:
            for v in vals:
                kept_query.append((k, v))
    kept_query.sort()
    query_str = urlencode(kept_query)

    clean_path = path if path else ""
    canonical = f"{scheme}://{netloc}{clean_path}"
    if query_str:
        canonical += f"?{query_str}"
    return canonical


def extract_hn_metadata(
    title: str, raw_url: str
) -> tuple[str | None, str | None, bool]:
    """Extract Hacker News story ID, anchor comment ID, and untitled status from URL.

    Pre-conditions:
        - title and raw_url must be strings.

    Post-conditions:
        - Returns (hn_item_id, anchor_comment_id, is_untitled) triple.
    """
    parsed = urlparse(raw_url)
    netloc = parsed.netloc.lower()
    if "news.ycombinator.com" not in netloc:
        return None, None, False

    qs = parse_qs(parsed.query)
    hn_item_id: str | None = None
    if parsed.path == "/item" and "id" in qs:
        hn_item_id = qs["id"][0]

    frag = parsed.fragment.lstrip("#")
    anchor_comment_id: str | None = frag if frag.isdigit() else None

    is_untitled = title.strip() in GENERIC_HN_TITLES
    return hn_item_id, anchor_comment_id, is_untitled


def classify_search_or_dictionary(
    title: str, raw_url: str
) -> tuple[str | None, QueryIntentCategory | None, str | None]:
    """Classify URLs and titles into search queries, dictionary lookups, or standard links.

    Pre-conditions:
        - title and raw_url must be strings.

    Post-conditions:
        - Returns (term_or_query, category, definition_hint) triple, or (None, None, None).
    """
    parsed = urlparse(raw_url)
    netloc = parsed.netloc.lower()
    path = parsed.path

    if "dictionary.cambridge.org" in netloc:
        term = path.rstrip("/").split("/")[-1].lower()
        hint = VOCABULARY_TERMS.get(term, "Dictionary definition")
        return term, QueryIntentCategory.VOCABULARY, hint

    if "merriam-webster.com" in netloc and "/dictionary/" in path:
        term = path.rstrip("/").split("/")[-1].lower()
        hint = VOCABULARY_TERMS.get(term, "Dictionary definition")
        return term, QueryIntentCategory.VOCABULARY, hint

    if "wikipedia.org" in netloc and "/wiki/Demonym" in path:
        return "demonym", QueryIntentCategory.VOCABULARY, VOCABULARY_TERMS["demonym"]

    if ("google.com" in netloc or netloc.endswith(".google.com")) and "/search" in path:
        qs = parse_qs(parsed.query)
        q = qs.get("q", [""])[0]
        q_cleaned = clean_search_query(q)
        ql = q_cleaned.lower().strip()

        if ql in VOCABULARY_TERMS:
            return ql, QueryIntentCategory.VOCABULARY, VOCABULARY_TERMS[ql]

        if any(pat in ql for pat in PERSONAL_QUERY_PATTERNS):
            return q_cleaned, QueryIntentCategory.PERSONAL_LIFE, None

        return q_cleaned, QueryIntentCategory.TECHNICAL_LEARNING, None

    return None, None, None


def classify_pillars(
    title: str, raw_url: str, search_query: str | None = None
) -> list[str]:
    """Deterministically classify a link into 1 to 3 intellectual pillar taxonomies.

    Pre-conditions:
        - title and raw_url must be strings.

    Post-conditions:
        - Returns a non-empty list of 1 to 3 IntellectualPillar string values.
    """
    text = f"{title} {raw_url} {search_query or ''}".lower()
    matched: list[str] = []

    if any(
        kw in text
        for kw in [
            "ai ",
            " ai",
            "/ai",
            "-ai",
            "llm",
            "agent",
            "deepseek",
            "openai",
            "gpt",
            "anthropic",
            "claude",
            "transformer",
            "vllm",
            "gemini",
            "langchain",
            "rag",
            "localllama",
            "qwen",
            "vibe code",
        ]
    ):
        matched.append(IntellectualPillar.AI_LLM_AGENTS.value)

    if any(
        kw in text
        for kw in [
            "kernel",
            "ebpf",
            "operating system",
            "systemctl",
            "systemd",
            "io_uring",
            "nvme",
            "ext4",
            "xfs",
            "posix",
            "linux",
            "zig lang",
            "erlang",
            "beam",
            "c++",
            "rust",
            "cs-people.bu.edu",
            "high performance computing",
            "graphical programming opengl",
            "opengl",
        ]
    ):
        matched.append(IntellectualPillar.SYSTEMS_KERNEL.value)

    if any(
        kw in text
        for kw in [
            "kubernetes",
            "k8s",
            "k3s",
            "homelab",
            "docker",
            "container",
            "wireguard",
            "nixos",
            "gateway",
            "cilium",
            "argocd",
            "gitops",
            "ceph",
            "cephfs",
            "seaweedfs",
            "duckdb",
            "s3",
            "vps",
            "server",
            "aws",
            "terraform",
            "ansible",
            "twingate",
            "searxng",
            "graylog",
            "siem",
            "calibre",
            "broker",
            "rabbitmq",
            "bullmq",
            "prometheus",
            "grafana",
            "metrics exporter",
            "operator",
            "floci",
            "calmtech",
            "yaml",
            "site reliability engineering",
            "sre",
        ]
    ):
        matched.append(IntellectualPillar.INFRA_K8S_HOMELAB.value)

    if any(
        kw in text
        for kw in [
            "linear algebra",
            "platonic solids",
            "rank reduction",
            "math",
            "geometry",
            "calculus",
            "probability",
            "statistics",
            "neural network",
            "neural networks",
            "how do neural networks learn",
            "ml in the age of ai",
            "fnt23-athanassoulis",
        ]
    ):
        matched.append(IntellectualPillar.MATH_ML_THEORY.value)

    if any(
        kw in text
        for kw in [
            "brain on books",
            "stages of life",
            "books",
            "philosophy",
            "psychology",
            "social graph",
            "headlight",
            "deposit",
            "tennant",
            "cleaning fee",
            "apartment",
            "aetna",
            "state park",
            "dim sum",
            "russell peters",
            "jo koy",
            "ugly truth",
            "soccer",
            "looping video",
            "fitbit",
            "whoop",
            "masterplan",
            "experience beyond",
            "employment rate",
            "dictionary",
            "merriam-webster",
            "vocabulary",
            "kafka",
            "das kapital",
            "ptolemy",
            "vis a vis",
            "ennui",
            "temerity",
            "posit",
            "malingerers",
            "obstinance",
            "obstinate",
            "backbiting",
            "demonym",
            "urdu kismat",
            "vas deferens",
            "loewhaley",
            "stavridis",
            "thomas mason",
        ]
    ):
        matched.append(IntellectualPillar.HUMANITIES_LIFE.value)

    if any(
        kw in text
        for kw in [
            "software engineer",
            "software engineering",
            "career",
            "hiring",
            "interview",
            "resume",
            "laid off",
            "job",
            "freelancing",
            "webdev",
            "frontend",
            "backend",
            "craftsmanship",
            "quality software",
            "side projects",
            "product manager",
            "authentic positions",
            "roadmap.sh",
            "web design",
            "elixir vs rust job market",
            "sr. ai infra engineer duties",
        ]
    ):
        matched.append(IntellectualPillar.SWE_CRAFT_CAREER.value)

    deduped: list[str] = []
    for p in matched:
        if p not in deduped:
            deduped.append(p)

    if not deduped:
        deduped = [IntellectualPillar.SWE_CRAFT_CAREER.value]

    return deduped[:3]


def parse_safari_export_text(text: str, epoch_id: str) -> list[SafariLinkItem]:
    """Parse raw Safari/Notes markdown export text into unmerged link items.

    Pre-conditions:
        - text contains export lines.
        - epoch_id represents an EpochId identifier string.

    Post-conditions:
        - Returns list of SafariLinkItem models extracted from markdown links.
    """
    lines = text.splitlines()
    link_pattern = re.compile(r"\[(.*?)\]\((.*?)\)")
    items: list[SafariLinkItem] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("p.p"):
            continue

        matches = link_pattern.findall(stripped)
        for raw_title, raw_url in matches:
            canonical_url = canonicalize_url(raw_url)
            item_id = hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()[:12]
            domain = urlparse(canonical_url).netloc

            hn_item_id, anchor_comment_id, is_untitled = extract_hn_metadata(
                raw_title, raw_url
            )
            term_or_query, query_cat, _ = classify_search_or_dictionary(
                raw_title, raw_url
            )

            lower_url = raw_url.lower()
            if term_or_query and query_cat == QueryIntentCategory.VOCABULARY and (
                "dictionary" in lower_url or "demonym" in lower_url
            ):
                source_type = SourceType.DICTIONARY
            elif "google.com" in lower_url and "/search" in lower_url:
                source_type = SourceType.GOOGLE_SEARCH
            elif "news.ycombinator.com" in lower_url:
                source_type = SourceType.HACKER_NEWS
            elif "reddit.com" in lower_url:
                source_type = SourceType.REDDIT
            elif "github.com" in lower_url:
                source_type = SourceType.GITHUB
            elif lower_url.endswith(".pdf") or "arxiv.org" in lower_url:
                source_type = SourceType.PDF_PAPER
            elif any(v in lower_url for v in ["youtube.com", "youtu.be", "vimeo.com"]):
                source_type = SourceType.VIDEO
            else:
                source_type = SourceType.ARTICLE

            pillars = classify_pillars(raw_title, raw_url, search_query=term_or_query)

            item = SafariLinkItem(
                item_id=item_id,
                title=raw_title,
                url=raw_url,
                canonical_url=canonical_url,
                domain=domain,
                source_type=source_type,
                epochs_present=[epoch_id],
                cross_epoch_count=1,
                is_evergreen_canon=False,
                total_occurrences=1,
                interest_weight=1,
                hn_item_id=hn_item_id,
                anchor_comment_id=anchor_comment_id,
                needs_title_hydration=is_untitled,
                was_untitled_tab=is_untitled,
                search_query=term_or_query,
                query_intent_category=query_cat,
                pillar_tags=pillars,
                primary_pillar=pillars[0] if pillars else IntellectualPillar.SWE_CRAFT_CAREER.value,
            )
            items.append(item)

    return items


def merge_vault_items(
    raw_items: list[SafariLinkItem], epoch_counts: dict[str, int] | None = None
) -> VaultParseResult:
    """Group and merge raw items by canonical URL, computing cross-epoch metrics.

    Pre-conditions:
        - raw_items is a list of SafariLinkItem models.

    Post-conditions:
        - Returns VaultParseResult with deduplicated items, evergreen canon,
          vocabulary entries, and search intents.
    """
    groups: dict[str, list[SafariLinkItem]] = {}
    for item in raw_items:
        groups.setdefault(item.canonical_url, []).append(item)

    merged_items: list[SafariLinkItem] = []
    evergreen_canon: list[SafariLinkItem] = []

    for _, group in groups.items():
        epochs: list[str] = sorted(
            list({epoch for item in group for epoch in item.epochs_present})
        )
        cross_epoch_count = len(epochs)
        is_evergreen = cross_epoch_count == 3
        total_occurrences = len(group)
        interest_weight = total_occurrences

        anchor_comment_id: str | None = None
        for item in group:
            if item.anchor_comment_id is not None:
                anchor_comment_id = item.anchor_comment_id
                break

        was_untitled = any(item.was_untitled_tab for item in group)
        descriptive_titles = [
            item.title for item in group if item.title.strip() not in GENERIC_HN_TITLES
        ]
        if descriptive_titles:
            final_title = descriptive_titles[0]
            needs_hydration = False
        else:
            final_title = group[0].title
            needs_hydration = final_title.strip() in GENERIC_HN_TITLES

        search_query: str | None = None
        query_cat: QueryIntentCategory | None = None
        for item in group:
            if item.search_query is not None:
                search_query = item.search_query
                query_cat = item.query_intent_category
                break

        all_pillars: list[str] = []
        for item in group:
            for p in item.pillar_tags:
                if p not in all_pillars:
                    all_pillars.append(p)
        if not all_pillars:
            all_pillars = [IntellectualPillar.SWE_CRAFT_CAREER.value]

        base = group[0]
        merged_item = SafariLinkItem(
            item_id=base.item_id,
            title=final_title,
            url=base.url,
            canonical_url=base.canonical_url,
            domain=base.domain,
            source_type=base.source_type,
            epochs_present=epochs,
            cross_epoch_count=cross_epoch_count,
            is_evergreen_canon=is_evergreen,
            total_occurrences=total_occurrences,
            interest_weight=interest_weight,
            hn_item_id=base.hn_item_id,
            anchor_comment_id=anchor_comment_id,
            needs_title_hydration=needs_hydration,
            was_untitled_tab=was_untitled,
            search_query=search_query,
            query_intent_category=query_cat,
            pillar_tags=all_pillars,
            primary_pillar=all_pillars[0],
        )
        merged_items.append(merged_item)
        if is_evergreen:
            evergreen_canon.append(merged_item)

    vocab_entries_map: dict[str, VocabularyEntry] = {}
    for item in merged_items:
        if (
            item.query_intent_category == QueryIntentCategory.VOCABULARY
            or item.source_type == SourceType.DICTIONARY
        ):
            term: str | None = None
            if item.search_query:
                term = item.search_query.strip().lower()
            elif "dictionary" in item.canonical_url or "demonym" in item.canonical_url:
                term = item.canonical_url.rstrip("/").split("/")[-1].lower()

            if term and term not in vocab_entries_map:
                vocab_entries_map[term] = VocabularyEntry(
                    term=term,
                    source_url=item.canonical_url,
                    source_type=item.source_type.value,
                    epoch_first_seen=item.epochs_present[0] if item.epochs_present else "",
                    epochs_present=item.epochs_present,
                    definition_hint=VOCABULARY_TERMS.get(term, "Vocabulary definition"),
                )

    intents_map: dict[str, SearchQueryIntent] = {}
    for item in merged_items:
        if item.search_query:
            key = item.search_query.strip().lower()
            if key not in intents_map:
                intents_map[key] = SearchQueryIntent(
                    query_text=item.search_query,
                    category=item.query_intent_category or QueryIntentCategory.TECHNICAL_LEARNING,
                    source_url=item.canonical_url,
                    epoch_first_seen=item.epochs_present[0] if item.epochs_present else "",
                    epochs_present=item.epochs_present,
                    pillar_tags=item.pillar_tags,
                )

    return VaultParseResult(
        items=merged_items,
        evergreen_canon=evergreen_canon,
        vocabulary_entries=list(vocab_entries_map.values()),
        search_intents=list(intents_map.values()),
        raw_link_count=len(raw_items),
        epoch_counts=epoch_counts or {},
    )


def parse_seed_directory(seed_dir: str | Path = "data/seeds") -> VaultParseResult:
    """Read the 3 canonical seed files and return aggregate VaultParseResult.

    Pre-conditions:
        - seed_dir must contain the three canonical Safari export files.

    Post-conditions:
        - Returns fully parsed and merged VaultParseResult with longitudinal cross-epoch metrics.
    """
    path = Path(seed_dir)
    file_epochs = [
        ("safari_open_tabs_2023_2024.txt", EpochId.EPOCH_2023_2024.value),
        ("safari_bookmarks_2026_08_16.txt", EpochId.EPOCH_2026_08_16.value),
        ("safari_tabs_2026_11_06.txt", EpochId.EPOCH_2026_11_06.value),
    ]

    all_raw_items: list[SafariLinkItem] = []
    epoch_counts: dict[str, int] = {}

    for filename, epoch_id in file_epochs:
        target = path / filename
        content = target.read_text(encoding="utf-8")
        items = parse_safari_export_text(content, epoch_id)
        epoch_counts[epoch_id] = len(items)
        all_raw_items.extend(items)

    return merge_vault_items(all_raw_items, epoch_counts)
