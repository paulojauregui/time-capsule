"""Unit tests verifying HTML5 semantic landmarks and ARIA contracts for Digital Time Capsule.

Pre-conditions:
    - index.html must exist in src/time_capsule/api/templates/.
    - html.parser from standard library and pytest must be available.

Post-conditions:
    - Validates presence of semantic landmarks, skip link, live region, tablist wiring,
      inactive panel hidden attributes, form control labels, external asset links,
      zero inline styles, zero inline scripts, and backward compatibility strings.
"""

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest

from time_capsule.models import IntellectualPillar

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "src" / "time_capsule" / "api" / "templates"
INDEX_HTML_PATH = TEMPLATES_DIR / "index.html"


class TagRecord:
    """Record storing an HTML tag's name and dictionary of attributes.

    Pre-conditions:
        - tag must be a non-empty string.
        - attrs must be a dictionary of string attribute names and values.

    Post-conditions:
        - Stores tag and attrs for contract validation.
    """

    def __init__(self, tag: str, attrs: dict[str, str | None]) -> None:
        self.tag: str = tag
        self.attrs: dict[str, str | None] = attrs

    def get(self, attr_name: str, default: str | None = None) -> str | None:
        """Retrieve attribute value or default.

        Pre-conditions:
            - attr_name must be a valid attribute string.

        Post-conditions:
            - Returns attribute value if present, else default.
        """
        return self.attrs.get(attr_name, default)


class SemanticHTMLContractParser(HTMLParser):
    """HTML parser recording landmarks, form controls, and attributes for contract verification.

    Pre-conditions:
        - Standard HTML input.

    Post-conditions:
        - Collects structured records of tags, element IDs, labels, form controls,
          scripts, and styles for invariant assertions.
    """

    def __init__(self) -> None:
        super().__init__()
        self.elements: list[TagRecord] = []
        self.by_id: dict[str, TagRecord] = {}
        self.by_tag: dict[str, list[TagRecord]] = {}
        self.labels_for: set[str] = set()
        self.form_controls: list[TagRecord] = []
        self.style_tags_count: int = 0
        self.inline_style_attrs: list[str] = []
        self.inline_scripts: list[str] = []
        self.raw_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Handle opening tags and index attributes.

        Pre-conditions:
            - tag and attrs passed by HTMLParser.

        Post-conditions:
            - Indexes tag in by_tag and by_id; tracks form controls and style attributes.
        """
        attr_dict: dict[str, str | None] = dict(attrs)
        record = TagRecord(tag, attr_dict)
        self.elements.append(record)

        if tag not in self.by_tag:
            self.by_tag[tag] = []
        self.by_tag[tag].append(record)

        elem_id = attr_dict.get("id")
        if elem_id:
            self.by_id[elem_id] = record

        if "style" in attr_dict:
            self.inline_style_attrs.append(f"{tag}#{elem_id or 'anonymous'}")

        if tag == "style":
            self.style_tags_count += 1

        if tag == "label" and "for" in attr_dict and attr_dict["for"]:
            self.labels_for.add(attr_dict["for"])

        if tag in ("input", "select", "textarea"):
            self.form_controls.append(record)

    def handle_data(self, data: str) -> None:
        """Collect inner textual content.

        Pre-conditions:
            - Text segment passed by HTMLParser.

        Post-conditions:
            - Appends stripped text segment.
        """
        if data.strip():
            self.raw_text.append(data.strip())


@pytest.fixture(scope="module")
def html_content() -> str:
    """Fixture providing raw content of index.html.

    Pre-conditions:
        - index.html file exists in templates directory.

    Post-conditions:
        - Returns string content of index.html.
    """
    assert INDEX_HTML_PATH.is_file(), f"index.html missing at {INDEX_HTML_PATH}"
    return INDEX_HTML_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def parsed_html(html_content: str) -> SemanticHTMLContractParser:
    """Fixture parsing index.html and returning SemanticHTMLContractParser.

    Pre-conditions:
        - html_content loaded.

    Post-conditions:
        - Yields populated SemanticHTMLContractParser.
    """
    parser = SemanticHTMLContractParser()
    parser.feed(html_content)
    return parser


def test_html_file_exists_and_non_empty(html_content: str) -> None:
    """Verify index.html exists and is non-empty.

    Pre-conditions:
        - html_content loaded.

    Post-conditions:
        - Asserts file content length > 0.
    """
    assert len(html_content.strip()) > 0
    assert "<!DOCTYPE html>" in html_content


def test_zero_inline_styles_and_scripts(parsed_html: SemanticHTMLContractParser, html_content: str) -> None:
    """Verify zero inline style tags, zero style attributes, and zero inline scripts.

    Pre-conditions:
        - parsed_html fixture populated.

    Post-conditions:
        - Asserts zero style elements, zero style attributes, and scripts only reference external src.
    """
    assert parsed_html.style_tags_count == 0, "Forbidden <style> tags found in index.html"
    assert parsed_html.inline_style_attrs == [], (
        f"Forbidden inline style attributes found: {parsed_html.inline_style_attrs}"
    )

    # Ensure scripts only load external files
    scripts = parsed_html.by_tag.get("script", [])
    assert len(scripts) >= 2, "Expected at least 2 <script> tags for views.js and app.js"
    for script in scripts:
        src = script.get("src")
        assert src is not None, "Script tag missing external 'src' attribute"
        assert src in ("/static/views.js", "/static/app.js"), f"Unexpected script src: {src}"


def test_zero_emojis_in_html(html_content: str) -> None:
    """Verify index.html contains zero emojis or non-ASCII characters.

    Pre-conditions:
        - html_content loaded.

    Post-conditions:
        - Asserts all characters in index.html have ord(ch) <= 127.
    """
    for ch in html_content:
        assert ord(ch) <= 127, f"Forbidden non-ascii/emoji character {ch!r} (ord={ord(ch)}) found in index.html"


def test_backward_compatibility_strings_preserved(html_content: str) -> None:
    """Verify all 5 dashboard titles and tab names expected by existing test_api.py are present.

    Pre-conditions:
        - html_content loaded.

    Post-conditions:
        - Asserts presence of Digital Time Capsule, Daily Tech Digest, 3-Epoch Reading Vault,
          Personal Time Capsule, and Macro Time Machine.
    """
    required_strings = [
        "Digital Time Capsule",
        "Daily Tech Digest",
        "3-Epoch Reading Vault",
        "Personal Time Capsule",
        "Macro Time Machine",
    ]
    for required in required_strings:
        assert required in html_content, f"Required string '{required}' missing from index.html"


def test_semantic_landmarks_present(parsed_html: SemanticHTMLContractParser) -> None:
    """Verify presence of semantic landmarks: header, nav[role=tablist], main#main-workspace, and dialogs.

    Pre-conditions:
        - parsed_html fixture populated.

    Post-conditions:
        - Asserts header landmark, nav tablist, main workspace, and accessible dialogs exist.
    """
    # Header landmark
    assert "header" in parsed_html.by_tag, "Missing <header> landmark"
    header = parsed_html.by_tag["header"][0]
    assert header.get("role") == "banner"
    assert "site-header" in (header.get("class") or "")

    # Nav landmark with tablist
    assert "nav" in parsed_html.by_tag, "Missing <nav> landmark"
    nav = parsed_html.by_tag["nav"][0]
    assert nav.get("role") == "tablist"
    assert nav.get("aria-label") == "Time Capsule Workspaces"
    assert "tab-bar" in (nav.get("class") or "")

    # Main landmark
    assert "main" in parsed_html.by_tag, "Missing <main> landmark"
    main_el = parsed_html.by_id.get("main-workspace")
    assert main_el is not None, "Missing <main id='main-workspace'>"
    assert main_el.tag == "main"
    assert "workspace-main" in (main_el.get("class") or "")

    # Dialog modals
    import_modal = parsed_html.by_id.get("import-modal")
    assert import_modal is not None, "Missing #import-modal"
    assert import_modal.get("role") == "dialog"
    assert import_modal.get("aria-modal") == "true"
    assert "hidden" in import_modal.attrs

    analysis_modal = parsed_html.by_id.get("analysis-modal")
    assert analysis_modal is not None, "Missing #analysis-modal"
    assert analysis_modal.get("role") == "dialog"
    assert analysis_modal.get("aria-modal") == "true"
    assert "hidden" in analysis_modal.attrs


def test_accessibility_skip_link_and_live_regions(parsed_html: SemanticHTMLContractParser) -> None:
    """Verify skip link, polite live status region, and degraded mode banner.

    Pre-conditions:
        - parsed_html fixture populated.

    Post-conditions:
        - Asserts #skip-to-main points to #main-workspace, #live-status-region has polite ARIA live,
          and #degraded-mode-banner has role='status' and hidden.
    """
    skip_link = parsed_html.by_id.get("skip-to-main")
    assert skip_link is not None, "Missing #skip-to-main"
    assert skip_link.tag == "a"
    assert skip_link.get("href") == "#main-workspace"
    assert "skip-link" in (skip_link.get("class") or "")

    live_region = parsed_html.by_id.get("live-status-region")
    assert live_region is not None, "Missing #live-status-region"
    assert live_region.get("aria-live") == "polite"
    assert live_region.get("aria-atomic") == "true"
    assert "sr-only" in (live_region.get("class") or "")

    degraded_banner = parsed_html.by_id.get("degraded-mode-banner")
    assert degraded_banner is not None, "Missing #degraded-mode-banner"
    assert degraded_banner.get("role") == "status"
    assert "hidden" in degraded_banner.attrs
    assert "state-banner-degraded" in (degraded_banner.get("class") or "")


def test_header_telemetry_pills(parsed_html: SemanticHTMLContractParser) -> None:
    """Verify operational telemetry pills in the site header.

    Pre-conditions:
        - parsed_html fixture populated.

    Post-conditions:
        - Asserts #service-status, #vault-count-pill, #evergreen-count-pill, and #model-status-pill exist
          with .pill and .tabular-nums.
    """
    pill_ids = [
        "service-status",
        "vault-count-pill",
        "evergreen-count-pill",
        "model-status-pill",
    ]
    for pill_id in pill_ids:
        pill = parsed_html.by_id.get(pill_id)
        assert pill is not None, f"Missing telemetry pill #{pill_id}"
        classes = pill.get("class") or ""
        assert "pill" in classes, f"Pill #{pill_id} missing 'pill' class"
        assert "tabular-nums" in classes, f"Pill #{pill_id} missing 'tabular-nums' class"


def test_roving_tabindex_and_tabpanel_wiring(parsed_html: SemanticHTMLContractParser) -> None:
    """Verify ARIA wiring and roving tabindex contract between tabs and tabpanels.

    Pre-conditions:
        - parsed_html fixture populated.

    Post-conditions:
        - Asserts tab button IDs, role='tab', aria-selected, aria-controls, tabindex,
          and matching tabpanel IDs, role='tabpanel', aria-labelledby, and hidden attributes.
    """
    tab_configs: list[dict[str, Any]] = [
        {
            "btn_id": "tab-btn-digest",
            "panel_id": "tab-digest",
            "aria_selected": "true",
            "tabindex": "0",
            "panel_hidden": False,
            "data_tab": "digest",
        },
        {
            "btn_id": "tab-btn-vault",
            "panel_id": "tab-vault",
            "aria_selected": "false",
            "tabindex": "-1",
            "panel_hidden": True,
            "data_tab": "vault",
        },
        {
            "btn_id": "tab-btn-capsule",
            "panel_id": "tab-capsule",
            "aria_selected": "false",
            "tabindex": "-1",
            "panel_hidden": True,
            "data_tab": "capsule",
        },
        {
            "btn_id": "tab-btn-macro",
            "panel_id": "tab-macro",
            "aria_selected": "false",
            "tabindex": "-1",
            "panel_hidden": True,
            "data_tab": "macro",
        },
    ]

    for config in tab_configs:
        btn = parsed_html.by_id.get(config["btn_id"])
        assert btn is not None, f"Missing tab button #{config['btn_id']}"
        assert btn.get("role") == "tab"
        assert btn.get("aria-selected") == config["aria_selected"]
        assert btn.get("aria-controls") == config["panel_id"]
        assert btn.get("tabindex") == config["tabindex"]
        assert btn.get("data-tab") == config["data_tab"]

        panel = parsed_html.by_id.get(config["panel_id"])
        assert panel is not None, f"Missing tabpanel #{config['panel_id']}"
        assert panel.get("role") == "tabpanel"
        assert panel.get("aria-labelledby") == config["btn_id"]
        assert panel.get("tabindex") == "0"

        if config["panel_hidden"]:
            assert "hidden" in panel.attrs, f"Inactive panel #{config['panel_id']} must have 'hidden' attribute"
        else:
            assert "hidden" not in panel.attrs, f"Active panel #{config['panel_id']} must not have 'hidden' attribute"


def test_form_controls_have_accessible_labels(parsed_html: SemanticHTMLContractParser) -> None:
    """Verify every input, select, and textarea has an associated label for or aria-label.

    Pre-conditions:
        - parsed_html fixture populated.

    Post-conditions:
        - Asserts every form control has either an explicit <label for="id"> or aria-label.
    """
    assert len(parsed_html.form_controls) >= 9, (
        f"Expected at least 9 form controls, found {len(parsed_html.form_controls)}"
    )

    for ctrl in parsed_html.form_controls:
        ctrl_id = ctrl.get("id")
        aria_label = ctrl.get("aria-label")

        has_label_for = ctrl_id is not None and ctrl_id in parsed_html.labels_for
        has_aria_label = aria_label is not None and len(aria_label.strip()) > 0

        assert has_label_for or has_aria_label, (
            f"Form control <{ctrl.tag} id='{ctrl_id}'> lacks an associated <label for='...'> or aria-label."
        )


def test_numeric_table_headers_use_num_col_class(parsed_html: SemanticHTMLContractParser) -> None:
    """Verify numeric table headers in vault, weather, and stock tables use class num-col.

    Pre-conditions:
        - parsed_html fixture populated.

    Post-conditions:
        - Asserts presence of th elements with class='num-col' for tabular numeric alignment.
    """
    th_elements = parsed_html.by_tag.get("th", [])
    num_col_ths = [th for th in th_elements if "num-col" in (th.get("class") or "")]
    assert len(num_col_ths) >= 9, f"Expected at least 9 numeric table headers with class='num-col', found {len(num_col_ths)}"


def test_external_stylesheet_and_script_links(parsed_html: SemanticHTMLContractParser) -> None:
    """Verify tokens.css and components.css are linked in head, and views.js and app.js in body.

    Pre-conditions:
        - parsed_html fixture populated.

    Post-conditions:
        - Asserts link tags for /static/tokens.css and /static/components.css exist.
        - Asserts script tags for /static/views.js and /static/app.js exist.
    """
    links = parsed_html.by_tag.get("link", [])
    stylesheets = [link.get("href") for link in links if link.get("rel") == "stylesheet"]
    assert "/static/tokens.css" in stylesheets, "Missing stylesheet link for /static/tokens.css"
    assert "/static/components.css" in stylesheets, "Missing stylesheet link for /static/components.css"

    scripts = parsed_html.by_tag.get("script", [])
    script_srcs = [script.get("src") for script in scripts]
    assert "/static/views.js" in script_srcs, "Missing script src for /static/views.js"
    assert "/static/app.js" in script_srcs, "Missing script src for /static/app.js"


def test_vault_pillar_select_matches_model_enum(html_content: str) -> None:
    """Verify #vault-pillar-select option values match IntellectualPillar enum values.

    Pre-conditions:
        - html_content fixture loaded from src/time_capsule/api/templates/index.html.
        - time_capsule.models.IntellectualPillar defines the canonical pillar identifiers.

    Post-conditions:
        - Confirms every IntellectualPillar member value appears as an <option> value
          inside #vault-pillar-select.
    """
    match = re.search(
        r'<select[^>]*id="vault-pillar-select"[^>]*>(.*?)</select>',
        html_content,
        flags=re.DOTALL,
    )
    assert match is not None, "Missing #vault-pillar-select element"
    select_body = match.group(1)
    option_values = set(re.findall(r'<option\s+value="([^"]*)"', select_body))
    for member in IntellectualPillar:
        assert member.value in option_values, (
            f"Missing IntellectualPillar enum option value: {member.value}"
        )


def test_intents_count_badge_and_copy_status_live_region_fix(
    parsed_html: SemanticHTMLContractParser,
) -> None:
    """Verify Gate 3 HTML refinements for #intents-count-badge, #copy-status, and #markdown-preview.

    Pre-conditions:
        - parsed_html fixture populated.

    Post-conditions:
        - Confirms #intents-count-badge is present.
        - Confirms #copy-status does not declare redundant aria-live or role=status attributes.
        - Confirms #markdown-preview is a <div> container rather than <pre>.
        - Confirms #discussions-container uses .discussions-stack.
    """
    assert "intents-count-badge" in parsed_html.by_id

    copy_status = parsed_html.by_id.get("copy-status")
    assert copy_status is not None
    assert copy_status.get("aria-live") is None
    assert copy_status.get("role") is None

    markdown_preview = parsed_html.by_id.get("markdown-preview")
    assert markdown_preview is not None
    assert markdown_preview.tag == "div"

    discussions = parsed_html.by_id.get("discussions-container")
    assert discussions is not None
    assert "discussions-stack" in (discussions.get("class") or "")
