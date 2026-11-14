# Milestone M07 Specification: Modular Semantic HTML5 Shell

## 1. Objective
Extract and overhaul the single-page application HTML structure into `src/time_capsule/api/templates/index.html` adhering to WCAG 2.2 AA, WAI-ARIA 1.2 tablist/tabpanel/dialog patterns, and `docs/UX_SPEC.md`, verified by `tests/test_ui_html_contract.py`.

## 2. Target Files
1. `src/time_capsule/api/templates/index.html`
2. `tests/test_ui_html_contract.py`

## 3. Non-Negotiable Invariants
- **Zero Emojis & Zero Inline Styles**:
  - `src/time_capsule/api/templates/index.html` must NOT contain any `<style>` tags, inline `style="..."` attributes, or `<script>` blocks containing inline JS code (it must link `/static/tokens.css`, `/static/components.css`, `/static/views.js`, and `/static/app.js`).
  - Zero emojis anywhere in HTML or test files (use `&times;` or clean text `"Close"` for close buttons).
- **Backward Compatibility with `tests/test_api.py`**:
  - `index.html` MUST contain the exact strings verified by `test_render_dashboard`:
    - `"Digital Time Capsule"`
    - `"Daily Tech Digest"`
    - `"3-Epoch Reading Vault"`
    - `"Personal Time Capsule"`
    - `"Macro Time Machine"`
- **Semantic Landmarks & WAI-ARIA Contract (`docs/UX_SPEC.md`)**:
  - `<a href="#main-workspace" class="skip-link" id="skip-to-main">Skip to main workspace</a>`
  - `<div id="live-status-region" class="sr-only" aria-live="polite" aria-atomic="true"></div>`
  - `<header class="site-header" role="banner">` containing:
    - `<h1>Digital Time Capsule &amp; Autonomous Reading Vault</h1>`
    - `<div class="status-pills">` with `#service-status`, `#vault-count-pill`, `#evergreen-count-pill`, `#model-status-pill` (all with `.pill` and `.tabular-nums`).
  - `<div id="degraded-mode-banner" class="state-banner state-banner-degraded" role="status" hidden>` explaining fallback to `heuristic-vader` when DGX Spark is offline.
  - `<nav class="tab-bar" role="tablist" aria-label="Time Capsule Workspaces">` with 4 `<button type="button" class="tab-btn" role="tab">`:
    - `#tab-btn-digest` (`aria-selected="true"`, `aria-controls="tab-digest"`, `tabindex="0"`, `data-tab="digest"`) -> `Daily Tech Digest`
    - `#tab-btn-vault` (`aria-selected="false"`, `aria-controls="tab-vault"`, `tabindex="-1"`, `data-tab="vault"`) -> `3-Epoch Reading Vault &amp; Evergreen Canon`
    - `#tab-btn-capsule` (`aria-selected="false"`, `aria-controls="tab-capsule"`, `tabindex="-1"`, `data-tab="capsule"`) -> `Personal Time Capsule`
    - `#tab-btn-macro` (`aria-selected="false"`, `aria-controls="tab-macro"`, `tabindex="-1"`, `data-tab="macro"`) -> `Macro Time Machine`
  - `<main id="main-workspace" class="workspace-main">` containing 4 `<section role="tabpanel" tabindex="0">`:
    1. `<section id="tab-digest" class="tab-content active" role="tabpanel" aria-labelledby="tab-btn-digest" tabindex="0">`:
       - `<label for="capsule-date-input">` + `<input type="text" id="capsule-date-input" class="tabular-nums" value="2026-11-06">`
       - `#load-capsule-btn`, `#copy-digest-btn`, `<span id="copy-status" role="status" aria-live="polite"></span>`
       - `#discussions-container` (`aria-busy="false"`)
       - `#copy-digest-secondary-btn`, `#markdown-preview` (`aria-busy="false"`)
    2. `<section id="tab-vault" class="tab-content" role="tabpanel" aria-labelledby="tab-btn-vault" tabindex="0" hidden>`:
       - Explicit `<label>` or `aria-label` on `#vault-epoch-select`, `#vault-evergreen-select`, `#vault-pillar-select`, `#vault-source-select`, `#vault-search-input` (with `<kbd class="kbd-hint">/</kbd>` shortcut hint)
       - `#clear-vault-filters-btn` (`Clear Filters`), `#open-import-modal-btn` (`Import Safari Notes`)
       - `#vault-results-count` (`class="results-meta tabular-nums"`, `aria-live="polite"`)
       - `.table-scroll-container` wrapping `<table class="data-table" id="vault-table">` with `<th class="num-col">Cross-Epoch / Occurrences</th>` and `<tbody id="vault-table-body">`
    3. `<section id="tab-capsule" class="tab-content" role="tabpanel" aria-labelledby="tab-btn-capsule" tabindex="0" hidden>`:
       - `#taste-profile-container`
       - `#vocab-count-badge` (`class="badge badge-epoch tabular-nums"`), `#vocab-table`, `#vocab-table-body`
       - `<label for="intent-category-select">` + `#intent-category-select`, `#intents-table`, `#intents-table-body`
    4. `<section id="tab-macro" class="tab-content" role="tabpanel" aria-labelledby="tab-btn-macro" tabindex="0" hidden>`:
       - `#weather-table` with `<th class="num-col">Temperature (C)</th>`, `<th class="num-col">Humidity (%)</th>`, `<th class="num-col">Pressure (hPa)</th>`, and `#weather-table-body`
       - `#stocks-table` with `<th class="num-col">Close ($)</th>`, `<th class="num-col">Open ($)</th>`, `<th class="num-col">High ($)</th>`, `<th class="num-col">Low ($)</th>`, `<th class="num-col">Volume</th>`, and `#stocks-table-body`
  - Accessible Modals:
    - `<div class="modal" id="import-modal" role="dialog" aria-modal="true" aria-labelledby="import-modal-title" aria-describedby="import-modal-desc" hidden>` containing `#import-modal-title`, `#close-import-modal-btn` (`aria-label="Close import modal"`), `#import-modal-desc`, `<label for="import-epoch-select">`, `#import-epoch-select`, `<label for="import-text">`, `#import-text`, `#import-feedback` (`role="status" aria-live="polite"`), `#cancel-import-btn`, `#submit-import-btn`.
    - `<div class="modal" id="analysis-modal" role="dialog" aria-modal="true" aria-labelledby="analysis-modal-title" hidden>` containing `#analysis-modal-title`, `#close-analysis-modal-btn` (`aria-label="Close analysis modal"`), `#analysis-modal-body` (`aria-live="polite"`).

## 4. Verification Test Suite (`tests/test_ui_html_contract.py`)
Write deterministic unit tests in `tests/test_ui_html_contract.py` (with full type hints and DbC docstrings) using `html.parser.HTMLParser` to parse `src/time_capsule/api/templates/index.html` and assert:
1. Presence of semantic landmarks (`header`, `nav[role="tablist"]`, `main#main-workspace`, 4 `section[role="tabpanel"]`, 2 `div[role="dialog"][aria-modal="true"]`).
2. Presence of `#skip-to-main`, `#live-status-region[aria-live="polite"]`, `#degraded-mode-banner[role="status"]`.
3. Roving tabindex and ARIA wiring on `#tab-btn-digest`, `#tab-btn-vault`, `#tab-btn-capsule`, `#tab-btn-macro` and `hidden` attribute on inactive tabpanels.
4. Zero inline `style="..."` attributes or `<style>` blocks, and presence of `<link rel="stylesheet" href="/static/tokens.css">`, `<link rel="stylesheet" href="/static/components.css">`, `<script src="/static/views.js"></script>`, `<script src="/static/app.js"></script>`.
5. Every `<input>`, `<select>`, and `<textarea>` has either an associated `<label for="...">` or `aria-label`.
