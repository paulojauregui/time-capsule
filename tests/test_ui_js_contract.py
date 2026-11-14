"""Contract tests for the client-side controller `src/time_capsule/api/static/app.js`.

Pre-conditions:
    - app.js must exist in src/time_capsule/api/static/ alongside tokens.css and
      components.css, and must be UTF-8 encoded plain JavaScript.
    - pytest must be available in the virtualenv.

Post-conditions:
    - Validates file existence and zero-emoji/ASCII-only content, the declared state
      store and TAB_ORDER, every required controller and loader function, the WAI-ARIA
      roving tabindex tablist keyboard contract (ArrowRight, ArrowLeft, Home, End,
      aria-selected, tabindex, hidden), the global `/`, Cmd/Ctrl+K and Escape shortcut
      handlers, the accessible modal focus-restoration contract, the
      window.TimeCapsuleViews delegation, and every REST endpoint binding.
"""

import re
from pathlib import Path

import pytest

STATIC_DIR: Path = (
    Path(__file__).resolve().parent.parent / "src" / "time_capsule" / "api" / "static"
)
APP_JS_PATH: Path = STATIC_DIR / "app.js"

REQUIRED_FUNCTIONS: tuple[str, ...] = (
    "initDashboard",
    "switchTab",
    "handleTabbarKeydown",
    "handleGlobalKeydown",
    "loadCapsuleDigest",
    "copyMarkdownDigest",
    "loadVaultItems",
    "clearVaultFilters",
    "openImportModal",
    "closeImportModal",
    "submitImport",
    "analyzeItem",
    "closeAnalysisModal",
    "loadTasteProfile",
    "loadVocab",
    "loadIntents",
    "resetIntentCategory",
    "loadMacro",
    "announceStatus",
    "updateModelStatus",
)

REQUIRED_ENDPOINTS: tuple[str, ...] = (
    "/healthz",
    "/ready",
    "/api/v1/capsule/",
    "/api/v1/vault",
    "/api/v1/vault/import",
    "/analyze",
    "/api/v1/epochs/summary",
    "/api/v1/vocabulary",
    "/api/v1/intents",
)

ROVING_TAB_INDEX_KEYS: tuple[str, ...] = ("ArrowRight", "ArrowLeft", "Home", "End")

TAB_ELEMENT_IDS: tuple[str, ...] = (
    "tab-btn-digest",
    "tab-btn-vault",
    "tab-btn-capsule",
    "tab-btn-macro",
)

PANEL_ELEMENT_IDS: tuple[str, ...] = ("tab-digest", "tab-vault", "tab-capsule", "tab-macro")


@pytest.fixture(scope="module")
def app_js_content() -> str:
    """Fixture providing the raw content of static/app.js.

    Pre-conditions:
        - app.js exists in the packaged static asset directory.

    Post-conditions:
        - Returns the full JavaScript source as a UTF-8 string.
    """
    assert APP_JS_PATH.is_file(), f"app.js missing at {APP_JS_PATH}"
    return APP_JS_PATH.read_text(encoding="utf-8")


def test_app_js_exists_and_is_non_empty(app_js_content: str) -> None:
    """Verify app.js exists on disk and carries substantive controller source.

    Pre-conditions:
        - app_js_content fixture loaded from disk.

    Post-conditions:
        - Asserts a non-trivial, non-empty source body.
    """
    assert len(app_js_content.strip()) > 500, "app.js must contain the application controller body"


def test_app_js_contains_zero_emojis_and_non_ascii(app_js_content: str) -> None:
    """Verify app.js contains zero emoji or non-ASCII characters.

    Pre-conditions:
        - app_js_content fixture loaded.

    Post-conditions:
        - Asserts every character satisfies ord(ch) <= 127.
    """
    for ch in app_js_content:
        assert ord(ch) <= 127, (
            f"Forbidden non-ascii/emoji character {ch!r} (ord={ord(ch)}) found in app.js"
        )


def test_app_js_declares_state_store_and_tab_order(app_js_content: str) -> None:
    """Verify the TAB_ORDER constant and appState state store contract.

    Pre-conditions:
        - app_js_content fixture loaded.

    Post-conditions:
        - Asserts TAB_ORDER lists the 4 workspaces in canonical order and appState
          exposes activeTab, currentDigestMarkdown, lastFocusedElement,
          isDegradedMode, and debounceTimer.
    """
    tab_order_match = re.search(
        r"TAB_ORDER\s*=\s*\[(?P<body>[^\]]*)\]",
        app_js_content,
    )
    assert tab_order_match is not None, "TAB_ORDER array declaration missing from app.js"
    tab_order_body = tab_order_match.group("body")
    for tab in ("digest", "vault", "capsule", "macro"):
        assert f'"{tab}"' in tab_order_body, f"TAB_ORDER missing workspace '{tab}'"

    for key, expected in (
        ("activeTab", '"digest"'),
        ("currentDigestMarkdown", '""'),
        ("lastFocusedElement", "null"),
        ("isDegradedMode", "false"),
        ("debounceTimer", "null"),
    ):
        assert re.search(rf"\b{key}\s*:\s*{re.escape(expected)}", app_js_content), (
            f"appState missing '{key}' initialized to {expected}"
        )


@pytest.mark.parametrize("function_name", REQUIRED_FUNCTIONS)
def test_app_js_defines_required_controller_function(
    app_js_content: str, function_name: str
) -> None:
    """Verify each required controller/loader function is declared.

    Pre-conditions:
        - app_js_content fixture loaded and function_name supplied by parametrize.

    Post-conditions:
        - Asserts a function declaration (or function-valued binding) exists for the
          name and that it is exported onto window.
    """
    declaration = re.search(
        rf"(function\s+{function_name}\s*\(|(?:const|let|var)\s+{function_name}\s*=\s*"
        rf"(?:async\s+)?function|{function_name}\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)",
        app_js_content,
    )
    assert declaration is not None, f"Function '{function_name}' is not defined in app.js"
    assert re.search(rf"window\.{function_name}\s*=", app_js_content), (
        f"Function '{function_name}' is not exposed on window for HTML handlers and views.js retries"
    )


@pytest.mark.parametrize("key_name", ROVING_TAB_INDEX_KEYS)
def test_app_js_handles_roving_tab_index_key(app_js_content: str, key_name: str) -> None:
    """Verify the tablist keydown controller handles each roving tabindex key.

    Pre-conditions:
        - app_js_content fixture loaded and key_name supplied by parametrize.

    Post-conditions:
        - Asserts handleTabbarKeydown branches on the key, calls preventDefault, and
          re-activates the workspace via switchTab with focus movement enabled.
    """
    assert f'event.key === "{key_name}"' in app_js_content, (
        f"handleTabbarKeydown missing branch for '{key_name}'"
    )
    handler_body = _extract_function_body(app_js_content, "handleTabbarKeydown")
    assert "event.preventDefault()" in handler_body, (
        "handleTabbarKeydown must call event.preventDefault() for roving tabindex keys"
    )
    assert "switchTab(" in handler_body, "handleTabbarKeydown must delegate to switchTab"


def test_app_js_switch_tab_implements_aria_tablist_contract(app_js_content: str) -> None:
    """Verify switchTab maintains aria-selected, tabindex, active class, and hidden.

    Pre-conditions:
        - app_js_content fixture loaded.

    Post-conditions:
        - Asserts switchTab toggles aria-selected true/false, tabindex 0/-1, the
          .active class, and the panel hidden boolean, and targets all 4 tab buttons
          and panels.
    """
    body = _extract_function_body(app_js_content, "switchTab")
    assert 'setAttribute("aria-selected"' in body, "switchTab must maintain aria-selected"
    assert '"true"' in body and '"false"' in body, (
        "switchTab must set aria-selected to both 'true' and 'false'"
    )
    assert 'setAttribute("tabindex"' in body, "switchTab must maintain roving tabindex"
    assert '"0"' in body and '"-1"' in body, "switchTab must set tabindex 0 and -1"
    assert 'classList.toggle("active"' in body or 'classList.add("active")' in body, (
        "switchTab must maintain the .active class"
    )
    assert re.search(r"\.hidden\s*=", body), "switchTab must toggle the panel hidden attribute"
    assert ".focus()" in body, "switchTab must move focus when moveFocus is requested"

    for btn_id in TAB_ELEMENT_IDS:
        assert btn_id in app_js_content, f"app.js never references tab button #{btn_id}"
    for panel_id in PANEL_ELEMENT_IDS:
        assert panel_id in app_js_content, f"app.js never references tabpanel #{panel_id}"


def test_app_js_switch_tab_triggers_workspace_loaders(app_js_content: str) -> None:
    """Verify switchTab lazily triggers the per-workspace data loaders.

    Pre-conditions:
        - app_js_content fixture loaded.

    Post-conditions:
        - Asserts vault loads vault items, capsule loads taste profile, vocab, and
          intents, and macro loads macro telemetry.
    """
    body = _extract_function_body(app_js_content, "switchTab")
    for loader in ("loadVaultItems(", "loadTasteProfile(", "loadVocab(", "loadIntents(", "loadMacro("):
        assert loader in body, f"switchTab must trigger {loader.rstrip('(')}"


def test_app_js_announce_status_targets_live_region(app_js_content: str) -> None:
    """Verify announceStatus writes to the aria-live polite status region.

    Pre-conditions:
        - app_js_content fixture loaded.

    Post-conditions:
        - Asserts #live-status-region is targeted and textContent is assigned.
    """
    assert "live-status-region" in app_js_content, "announceStatus must target #live-status-region"
    body = _extract_function_body(app_js_content, "announceStatus")
    assert "textContent" in body, "announceStatus must assign textContent"


def test_app_js_update_model_status_degraded_contract(app_js_content: str) -> None:
    """Verify updateModelStatus distinguishes heuristic fallback from DGX Spark nominal.

    Pre-conditions:
        - app_js_content fixture loaded.

    Post-conditions:
        - Asserts heuristic detection, both pill labels, both pill modifier classes,
          and the degraded-mode-banner hidden toggle are implemented.
    """
    body = _extract_function_body(app_js_content, "updateModelStatus")
    assert "heuristic" in body, "updateModelStatus must detect the heuristic-vader model"
    assert "model-status-pill" in body, "updateModelStatus must update #model-status-pill"
    assert "Model: Heuristic VADER Fallback" in app_js_content, "Degraded pill label missing"
    assert "Model: Qwen3.8-Flash-Next-FP4-Local" in app_js_content, "Nominal pill label missing"
    assert "pill-degraded" in body, "updateModelStatus must apply .pill-degraded"
    assert "pill-nominal" in body, "updateModelStatus must apply .pill-nominal"
    assert "degraded-mode-banner" in body, "updateModelStatus must toggle #degraded-mode-banner"
    assert re.search(r"hidden\s*=\s*!", body), "updateModelStatus must invert heuristic flag onto hidden"


def test_app_js_global_escape_shortcut(app_js_content: str) -> None:
    """Verify the Escape shortcut closes open modals or clears the vault search.

    Pre-conditions:
        - app_js_content fixture loaded.

    Post-conditions:
        - Asserts Escape handling checks modal hidden state, calls preventDefault,
          closes both modals, and clears #vault-search-input before reloading.
    """
    body = _extract_function_body(app_js_content, "handleGlobalKeydown")
    assert 'event.key === "Escape"' in body, "handleGlobalKeydown must handle Escape"
    assert "import-modal" in body and "analysis-modal" in body, (
        "Escape must consider both #import-modal and #analysis-modal"
    )
    assert re.search(r"\.hidden", body), "Escape handler must inspect modal hidden state"
    assert "closeImportModal()" in body, "Escape must call closeImportModal"
    assert "closeAnalysisModal()" in body, "Escape must call closeAnalysisModal"
    assert "vault-search-input" in body, "Escape must handle #vault-search-input clearing"
    assert 'value = ""' in body, "Escape must clear the vault search value"
    assert "loadVaultItems()" in body, "Escape clearing must reload vault items"
    assert "event.preventDefault()" in body, "Escape must call preventDefault"


def test_app_js_global_search_shortcuts(app_js_content: str) -> None:
    """Verify `/` and Cmd/Ctrl+K focus vault search outside editable contexts.

    Pre-conditions:
        - app_js_content fixture loaded.

    Post-conditions:
        - Asserts both shortcut forms are detected, editable elements are excluded,
          preventDefault is called, the vault tab is activated, and search gains focus.
    """
    body = _extract_function_body(app_js_content, "handleGlobalKeydown")
    assert '"/"' in body, "Global shortcut must handle the '/' key"
    assert "metaKey" in body and "ctrlKey" in body, "Global shortcut must handle Cmd and Ctrl"
    assert '"k"' in body, "Global shortcut must handle the Cmd/Ctrl+K key"
    for editable_tag in ("INPUT", "TEXTAREA", "SELECT"):
        assert editable_tag in app_js_content, (
            f"Shortcut guard must skip editable element {editable_tag}"
        )
    assert "isContentEditable" in app_js_content, "Shortcut guard must skip contenteditable hosts"
    assert "event.preventDefault()" in body, "Search shortcut must call preventDefault"
    assert 'switchTab("vault"' in body, "Search shortcut must activate the vault workspace"
    assert re.search(r"vault-search-input[\s\S]{0,200}\.focus\(\)", body), (
        "Search shortcut must focus #vault-search-input"
    )


@pytest.mark.parametrize(
    ("opener", "closer", "modal_id"),
    [
        ("openImportModal", "closeImportModal", "import-modal"),
        ("openAnalysisModalAlias", "closeAnalysisModal", "analysis-modal"),
    ],
)
def test_app_js_modals_manage_focus_and_visibility(
    app_js_content: str, opener: str, closer: str, modal_id: str
) -> None:
    """Verify modal open/close maintain lastFocusedElement and the hidden/active pair.

    Pre-conditions:
        - app_js_content fixture loaded and opener/closer/modal_id supplied.

    Post-conditions:
        - Asserts the analysis modal path stores lastFocusedElement, toggles hidden and
          .active, and restores focus on close. The import pair is asserted separately.
    """
    if opener == "openAnalysisModalAlias":
        opener = "analyzeItem"

    opener_body = _extract_function_body(app_js_content, opener)
    closer_body = _extract_function_body(app_js_content, closer)

    assert modal_id in opener_body, f"{opener} must target #{modal_id}"
    assert modal_id in closer_body, f"{closer} must target #{modal_id}"
    assert "lastFocusedElement" in opener_body, f"{opener} must store lastFocusedElement"
    assert re.search(r"\.hidden\s*=\s*false", opener_body), f"{opener} must unhide #{modal_id}"
    assert 'classList.add("active")' in opener_body, f"{opener} must add .active to #{modal_id}"
    assert ".focus()" in opener_body, f"{opener} must move focus into #{modal_id}"
    assert re.search(r"\.hidden\s*=\s*true", closer_body), f"{closer} must hide #{modal_id}"
    assert 'classList.remove("active")' in closer_body, f"{closer} must remove .active"
    assert "lastFocusedElement" in closer_body and ".focus()" in closer_body, (
        f"{closer} must restore focus from appState.lastFocusedElement"
    )


def test_app_js_import_modal_focuses_import_text(app_js_content: str) -> None:
    """Verify openImportModal moves focus into #import-text on open.

    Pre-conditions:
        - app_js_content fixture loaded.

    Post-conditions:
        - Asserts #import-text is focused when the import dialog opens.
    """
    body = _extract_function_body(app_js_content, "openImportModal")
    assert "import-text" in body, "openImportModal must focus #import-text"
    assert ".focus()" in body, "openImportModal must call focus()"


def test_app_js_backdrop_click_closes_modals(app_js_content: str) -> None:
    """Verify backdrop clicks on the .modal overlay dismiss the active dialog.

    Pre-conditions:
        - app_js_content fixture loaded.

    Post-conditions:
        - Asserts a click handler compares event.target against the modal element.
    """
    assert "event.target === modal" in app_js_content, (
        "Backdrop dismissal must compare event.target with the modal container"
    )


@pytest.mark.parametrize("endpoint", REQUIRED_ENDPOINTS)
def test_app_js_binds_required_api_endpoints(app_js_content: str, endpoint: str) -> None:
    """Verify every REST endpoint required by the UI contract is bound.

    Pre-conditions:
        - app_js_content fixture loaded and endpoint supplied by parametrize.

    Post-conditions:
        - Asserts the endpoint literal appears inside a fetch call in app.js.
    """
    assert endpoint in app_js_content, f"API endpoint '{endpoint}' is not bound in app.js"
    assert "fetch(" in app_js_content, "app.js must use fetch() for REST bindings"


def test_app_js_uses_correct_http_methods(app_js_content: str) -> None:
    """Verify mutating endpoints use POST while reads use implicit GET.

    Pre-conditions:
        - app_js_content fixture loaded.

    Post-conditions:
        - Asserts vault import and analysis requests declare method POST.
    """
    assert re.search(r'method:\s*"POST"', app_js_content), "Mutating calls must use method POST"
    assert app_js_content.count('"POST"') >= 2, (
        "Both /api/v1/vault/import and the analyze endpoint must POST"
    )


def test_app_js_delegates_rendering_to_time_capsule_views(app_js_content: str) -> None:
    """Verify data loaders delegate DOM rendering to window.TimeCapsuleViews.

    Pre-conditions:
        - app_js_content fixture loaded.

    Post-conditions:
        - Asserts views.js renderers are consulted for discussions, markdown, vault,
          taste profile, vocab, intents, and macro containers.
    """
    assert "window.TimeCapsuleViews" in app_js_content, "app.js must consume window.TimeCapsuleViews"
    for renderer in (
        "renderDiscussions",
        "renderMarkdownPreview",
        "renderVaultRows",
        "renderTasteProfile",
        "renderVocabRows",
        "renderIntentsRows",
        "renderWeatherRows",
        "renderStockRows",
    ):
        assert renderer in app_js_content, f"app.js never delegates to TimeCapsuleViews.{renderer}"


def test_app_js_targets_all_required_dom_hooks(app_js_content: str) -> None:
    """Verify every DOM id consumed from the index.html shell is referenced.

    Pre-conditions:
        - app_js_content fixture loaded.

    Post-conditions:
        - Asserts the status pills, banners, vault controls, capsule controls, and
          macro tables all appear in app.js.
    """
    required_ids = (
        "live-status-region",
        "model-status-pill",
        "degraded-mode-banner",
        "service-status",
        "vault-count-pill",
        "evergreen-count-pill",
        "vault-search-input",
        "vault-epoch-select",
        "vault-evergreen-select",
        "vault-pillar-select",
        "vault-source-select",
        "vault-results-count",
        "vault-table-body",
        "vault-table",
        "capsule-date-input",
        "discussions-container",
        "markdown-preview",
        "copy-status",
        "taste-profile-container",
        "vocab-table-body",
        "vocab-count-badge",
        "intents-table-body",
        "intent-category-select",
        "weather-table-body",
        "stocks-table-body",
        "import-text",
        "import-epoch-select",
        "import-feedback",
        "analysis-modal-body",
        "close-analysis-modal-btn",
    )
    for element_id in required_ids:
        assert element_id in app_js_content, f"DOM hook #{element_id} missing from app.js"


def test_app_js_wires_dom_content_loaded_and_keyboard_listeners(app_js_content: str) -> None:
    """Verify bootstrapping wires DOMContentLoaded plus tablist and global keydown.

    Pre-conditions:
        - app_js_content fixture loaded.

    Post-conditions:
        - Asserts a DOMContentLoaded listener boots the dashboard and both keydown
          handlers are registered.
    """
    assert "DOMContentLoaded" in app_js_content, "app.js must wire a DOMContentLoaded listener"
    assert 'addEventListener("keydown", handleTabbarKeydown)' in app_js_content, (
        "app.js must bind handleTabbarKeydown to the tablist"
    )
    assert 'addEventListener("keydown", handleGlobalKeydown)' in app_js_content, (
        "app.js must bind handleGlobalKeydown globally"
    )
    assert "tab-bar" in app_js_content, "app.js must resolve the .tab-bar role=tablist element"
    assert "initDashboard()" in app_js_content, "app.js must boot via initDashboard()"


def test_app_js_debounces_vault_search(app_js_content: str) -> None:
    """Verify vault search input is debounced through appState.debounceTimer.

    Pre-conditions:
        - app_js_content fixture loaded.

    Post-conditions:
        - Asserts setTimeout/clearTimeout are driven through appState.debounceTimer.
    """
    assert "setTimeout(" in app_js_content, "Vault search must be debounced via setTimeout"
    assert "clearTimeout(" in app_js_content, "Vault search must cancel pending timers"
    assert "debounceTimer" in app_js_content, "Debounce state must live on appState"


def test_app_js_uses_clipboard_api_for_digest_copy(app_js_content: str) -> None:
    """Verify copyMarkdownDigest writes currentDigestMarkdown via the clipboard API.

    Pre-conditions:
        - app_js_content fixture loaded.

    Post-conditions:
        - Asserts navigator.clipboard.writeText is used with the stored markdown and
          that #copy-status plus announceStatus report the outcome.
    """
    body = _extract_function_body(app_js_content, "copyMarkdownDigest")
    assert "navigator.clipboard.writeText" in body, "Copy must use navigator.clipboard.writeText"
    assert "currentDigestMarkdown" in body, "Copy must read appState.currentDigestMarkdown"
    assert "copy-status" in body, "Copy must update #copy-status"
    assert "announceStatus(" in body, "Copy must announce the result"


def _extract_function_body(source: str, function_name: str) -> str:
    """Extract a balanced-brace function body from the JavaScript source.

    Pre-conditions:
        - source must be the app.js text.
        - function_name must name a `function <name>(...)` declaration present in source.

    Post-conditions:
        - Returns the substring spanning the function's opening brace through its
          matching closing brace; returns an empty string when no declaration exists.
    """
    match = re.search(rf"function\s+{re.escape(function_name)}\s*\(", source)
    if match is None:
        return ""

    brace_start = source.find("{", match.end())
    if brace_start == -1:
        return ""

    depth = 0
    for index in range(brace_start, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[brace_start : index + 1]

    return source[brace_start:]
