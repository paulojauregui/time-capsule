"""Unit tests verifying design tokens and component CSS stylesheets for Digital Time Capsule.

Pre-conditions:
    - tokens.css and components.css must exist in src/time_capsule/api/static/.
    - pytest, ruff, and mypy must be configured and available in the virtualenv.

Post-conditions:
    - Validates token definitions, zero raw hex in components.css, zero emojis,
      tabular-nums enforcement, 5-state class definitions, accessibility utilities,
      modal classes, and responsive media queries.
"""

import re
from pathlib import Path

import pytest

STATIC_DIR = Path(__file__).resolve().parent.parent / "src" / "time_capsule" / "api" / "static"
TOKENS_CSS_PATH = STATIC_DIR / "tokens.css"
COMPONENTS_CSS_PATH = STATIC_DIR / "components.css"


@pytest.fixture(scope="module")
def tokens_content() -> str:
    """Fixture providing raw content of tokens.css.

    Pre-conditions:
        - tokens.css file exists in static asset directory.

    Post-conditions:
        - Returns string content of tokens.css.
    """
    assert TOKENS_CSS_PATH.is_file(), f"tokens.css missing at {TOKENS_CSS_PATH}"
    return TOKENS_CSS_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def components_content() -> str:
    """Fixture providing raw content of components.css.

    Pre-conditions:
        - components.css file exists in static asset directory.

    Post-conditions:
        - Returns string content of components.css.
    """
    assert COMPONENTS_CSS_PATH.is_file(), f"components.css missing at {COMPONENTS_CSS_PATH}"
    return COMPONENTS_CSS_PATH.read_text(encoding="utf-8")


def test_tokens_file_existence_and_non_empty(tokens_content: str) -> None:
    """Verify tokens.css exists and contains valid CSS tokens.

    Pre-conditions:
        - tokens_content fixture loaded.

    Post-conditions:
        - Confirms tokens.css is non-empty and declares :root block.
    """
    assert len(tokens_content.strip()) > 0
    assert ":root" in tokens_content


def test_tokens_defines_all_required_custom_properties(tokens_content: str) -> None:
    """Verify tokens.css defines all required Design System custom properties.

    Pre-conditions:
        - tokens_content fixture loaded.

    Post-conditions:
        - Confirms all 4 elevation tiers, borders, text, status, source badges,
          typography, spatial grid, radii, and motion tokens exist.
    """
    required_tokens = [
        # 1. 4-Tier Dark Surface Elevation Hierarchy
        "--bg-canvas",
        "--bg-surface-1",
        "--bg-surface-2",
        "--bg-elevated",
        "--bg-backdrop",
        # 2. Structural Hairline Borders & Focus Ring
        "--border-subtle",
        "--border-default",
        "--border-strong",
        "--focus-ring",
        # 3. Primary Text Hierarchy
        "--text-primary",
        "--text-secondary",
        "--text-muted",
        # 4. Interactive & Link Accents
        "--accent-primary",
        "--accent-primary-hover",
        "--accent-text",
        # 5. Archival Canon Tokens
        "--canon-amber-text",
        "--canon-amber-bg",
        "--canon-amber-border",
        # 6. Source Platform & Taxonomy Badges
        "--source-hn-text",
        "--source-hn-bg",
        "--source-hn-border",
        "--source-reddit-text",
        "--source-reddit-bg",
        "--source-reddit-border",
        "--source-github-text",
        "--source-github-bg",
        "--source-github-border",
        "--pillar-text",
        "--pillar-bg",
        "--pillar-border",
        "--epoch-text",
        "--epoch-bg",
        "--epoch-border",
        # 7. Status Tokens
        "--status-nominal-text",
        "--status-nominal-bg",
        "--status-nominal-border",
        "--status-degraded-text",
        "--status-degraded-bg",
        "--status-degraded-border",
        "--status-error-text",
        "--status-error-bg",
        "--status-error-border",
        # 8. Typography Stacks & Modular Scale
        "--font-sans",
        "--font-mono",
        "--text-xs",
        "--text-sm",
        "--text-base",
        "--text-md",
        "--text-lg",
        "--text-xl",
        # 9. Spatial Grid & Radii
        "--space-1",
        "--space-2",
        "--space-3",
        "--space-4",
        "--space-5",
        "--space-6",
        "--space-8",
        "--radius-sm",
        "--radius-md",
        "--radius-lg",
        "--radius-pill",
        # 10. Motion
        "--ease-out",
        "--duration-fast",
    ]

    for token in required_tokens:
        assert f"{token}:" in tokens_content, f"Required token '{token}' missing from tokens.css"


def test_components_contains_zero_raw_hex_color_literals(components_content: str) -> None:
    """Verify components.css contains zero raw hex color literals.

    Pre-conditions:
        - components_content fixture loaded.

    Post-conditions:
        - Confirms regex findall for hex color literals returns an empty list.
    """
    hex_pattern = re.compile(r"#[0-9a-fA-F]{3,8}\b")
    matches = hex_pattern.findall(components_content)
    assert matches == [], f"Found forbidden raw hex color literals in components.css: {matches}"


def test_css_files_contain_zero_emojis(tokens_content: str, components_content: str) -> None:
    """Verify neither tokens.css nor components.css contain any emoji characters.

    Pre-conditions:
        - tokens_content and components_content fixtures loaded.

    Post-conditions:
        - Confirms zero unicode characters outside standard printable ASCII range.
    """
    for name, content in [("tokens.css", tokens_content), ("components.css", components_content)]:
        for ch in content:
            assert ord(ch) <= 127, f"Forbidden non-ascii/emoji character {ch!r} (ord={ord(ch)}) in {name}"


def test_components_consumes_tokens_via_var(components_content: str) -> None:
    """Verify components.css consumes custom properties via var(--*).

    Pre-conditions:
        - components_content fixture loaded.

    Post-conditions:
        - Confirms pervasive usage of var(--*) references throughout components.css.
    """
    var_matches = re.findall(r"var\(--[a-zA-Z0-9_-]+\)", components_content)
    assert len(var_matches) >= 30, f"Expected extensive var(--*) usage, found {len(var_matches)}"
    assert "var(--bg-canvas)" in components_content
    assert "var(--bg-surface-1)" in components_content
    assert "var(--border-default)" in components_content
    assert "var(--focus-ring)" in components_content


def test_components_tabular_nums_and_num_col_discipline(components_content: str) -> None:
    """Verify components.css defines tabular-nums and num-col alignment rules.

    Pre-conditions:
        - components_content fixture loaded.

    Post-conditions:
        - Confirms .tabular-nums, .num-col, th.num-col, and td.num-col are defined
          with font-family var(--font-mono) and font-variant-numeric: tabular-nums.
    """
    assert ".tabular-nums" in components_content
    assert ".num-col" in components_content
    assert "th.num-col" in components_content
    assert "td.num-col" in components_content
    assert "tabular-nums" in components_content
    assert "var(--font-mono)" in components_content


def test_components_accessibility_utilities(components_content: str) -> None:
    """Verify components.css defines focus-visible, skip-link, sr-only, and hidden rules.

    Pre-conditions:
        - components_content fixture loaded.

    Post-conditions:
        - Confirms :focus-visible, .skip-link, .sr-only, and [hidden] rules exist.
    """
    assert ":focus-visible" in components_content
    assert ".skip-link" in components_content
    assert ".sr-only" in components_content
    assert "[hidden]" in components_content
    assert "display: none !important" in components_content


def test_components_defines_header_and_pills(components_content: str) -> None:
    """Verify components.css defines site header and status pills.

    Pre-conditions:
        - components_content fixture loaded.

    Post-conditions:
        - Confirms .site-header, .status-pills, .pill, and all status pill variants exist.
    """
    required_classes = [
        ".site-header",
        ".header-titles",
        ".header-subtitle",
        ".status-pills",
        ".pill",
        ".pill-nominal",
        ".pill-green",
        ".pill-degraded",
        ".pill-amber",
        ".pill-error",
        ".pill-red",
        ".pill-canon",
        ".pill-info",
        ".pill-blue",
    ]
    for cls in required_classes:
        assert cls in components_content, f"Class {cls} missing from components.css"


def test_components_defines_tabs_and_controls(components_content: str) -> None:
    """Verify components.css defines tab bar navigation and control panel elements.

    Pre-conditions:
        - components_content fixture loaded.

    Post-conditions:
        - Confirms tab bar, tab buttons, workspace, control panel, and button classes exist.
    """
    required_elements = [
        ".tab-bar",
        ".tab-btn",
        ".workspace-main",
        ".tab-content",
        ".control-panel",
        ".filter-group",
        ".control-label",
        ".kbd-hint",
        ".btn-primary",
        ".btn-secondary",
        ".btn-ghost",
        ".btn-retry",
    ]
    for el in required_elements:
        assert el in components_content, f"Element {el} missing from components.css"


def test_components_defines_cards_and_synthesis(components_content: str) -> None:
    """Verify components.css defines grid layouts, cards, and synthesis blocks.

    Pre-conditions:
        - components_content fixture loaded.

    Post-conditions:
        - Confirms .card, .card-header, .analysis-box, .spotlight-box, and taste rows exist.
    """
    required_classes = [
        ".grid-2",
        ".grid-3",
        ".card",
        ".card-nested",
        ".card-header",
        ".card-title",
        ".card-subtitle",
        ".card-meta",
        ".analysis-section",
        ".analysis-label",
        ".analysis-box",
        ".spotlight-label",
        ".spotlight-box",
        ".takeaways-list",
        ".markdown-preview",
        ".taste-row",
        ".taste-row-header",
        ".taste-bar-track",
        ".taste-bar-fill",
    ]
    for cls in required_classes:
        assert cls in components_content, f"Class {cls} missing from components.css"


def test_components_defines_badges(components_content: str) -> None:
    """Verify components.css defines taxonomy badges and score indicators.

    Pre-conditions:
        - components_content fixture loaded.

    Post-conditions:
        - Confirms .badge and all badge variants exist.
    """
    badge_classes = [
        ".badge",
        ".badge-canon",
        ".badge-hn",
        ".badge-reddit",
        ".badge-github",
        ".badge-pillar",
        ".badge-epoch",
        ".badge-model-spark",
        ".badge-model-fallback",
        ".badge-score",
        ".score-positive",
        ".score-negative",
    ]
    for badge in badge_classes:
        assert badge in components_content, f"Badge class {badge} missing from components.css"


def test_components_defines_tables_and_scroll_containers(components_content: str) -> None:
    """Verify components.css defines data table styles and scroll containers.

    Pre-conditions:
        - components_content fixture loaded.

    Post-conditions:
        - Confirms table scroll containers, table.data-table, and results meta exist.
    """
    assert ".table-scroll-container" in components_content
    assert ".table-scroll-bounded" in components_content
    assert "table.data-table" in components_content
    assert ".results-meta" in components_content


def test_components_defines_5_state_classes(components_content: str) -> None:
    """Verify components.css defines all 5-state component classes and loading skeletons.

    Pre-conditions:
        - components_content fixture loaded.

    Post-conditions:
        - Confirms empty, loading, skeleton, degraded, and error states exist.
    """
    state_classes = [
        ".state-banner",
        ".state-banner-degraded",
        ".state-empty",
        ".state-actions",
        ".state-error",
        ".state-loading",
        ".skeleton",
        ".skeleton-card",
        ".skeleton-row",
        ".skeleton-line",
        ".skeleton-well",
        "skeleton-pulse",
    ]
    for sc in state_classes:
        assert sc in components_content, f"State class {sc} missing from components.css"


def test_components_defines_modals(components_content: str) -> None:
    """Verify components.css defines accessible modal dialog styles.

    Pre-conditions:
        - components_content fixture loaded.

    Post-conditions:
        - Confirms modal dialog classes exist.
    """
    modal_classes = [
        ".modal",
        ".modal.active",
        ".modal-card",
        ".modal-header",
        ".modal-close",
        ".modal-body",
        ".modal-footer",
        ".import-feedback",
    ]
    for mc in modal_classes:
        assert mc in components_content, f"Modal class {mc} missing from components.css"


def test_components_defines_responsive_and_motion_media_queries(components_content: str) -> None:
    """Verify components.css defines responsive breakpoints and reduced-motion queries.

    Pre-conditions:
        - components_content fixture loaded.

    Post-conditions:
        - Confirms @media max-width 767px, tablet, desktop, and prefers-reduced-motion queries exist.
    """
    assert "@media (max-width: 767px)" in components_content
    assert "@media (min-width: 768px) and (max-width: 1279px)" in components_content
    assert "@media (min-width: 1280px)" in components_content
    assert "@media (prefers-reduced-motion: reduce)" in components_content


def test_components_defines_base_link_code_and_discussions_stack(
    components_content: str,
) -> None:
    """Verify Gate 3 typographic, layout, and error-feedback CSS rules exist.

    Pre-conditions:
        - components_content fixture loaded from src/time_capsule/api/static/components.css.

    Post-conditions:
        - Confirms base a, a:hover, and code rules are defined using tokens.
        - Confirms .discussions-stack, .skeleton-row-vault, .import-feedback.state-error,
          and explicit .btn-retry:hover rules exist without raw hex colors.
    """
    assert re.search(r"(?:^|\n)a\s*\{", components_content) is not None
    assert "a:hover" in components_content
    assert re.search(r"(?:^|\n)code\s*\{", components_content) is not None
    assert ".discussions-stack" in components_content
    assert ".skeleton-row-vault" in components_content
    assert ".import-feedback.state-error" in components_content
    assert ".btn-retry:hover" in components_content
