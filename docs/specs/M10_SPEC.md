# Milestone M10 Specification: 5-State Component Renderers, CLS=0 Skeletons & Degraded Heuristic Fallback Indicator

## 1. Objective
Implement `src/time_capsule/api/static/views.js` (`window.TimeCapsuleViews`) providing pure, XSS-safe DOM rendering functions for all 5 deterministic component states (`Empty`, `Loading` with `CLS = 0` skeletons, `Nominal`, `Degraded/Offline Fallback` distinguishing `nvidia/Qwen3.8-Flash-Next-FP4-Local` vs `heuristic-vader`, and `Error` with retry buttons) across all 4 workspaces and modals. Verify all 5 states and end-to-end UI asset serving in `tests/test_ui_states.py`.

## 2. Target Files
1. `src/time_capsule/api/static/views.js`
2. `tests/test_ui_states.py`

## 3. Exact Rendering Contract (`src/time_capsule/api/static/views.js`)
Expose `window.TimeCapsuleViews` (and CommonJS export guard if needed) with:
1. **Security & Formatting Utilities**:
   - `escapeHtml(value)`: Escapes `&`, `<`, `>`, `"`, `'` to prevent DOM XSS.
   - `formatSentimentScore(score)`: Returns signed 2-decimal string (`+0.42` or `-0.18`) with `.tabular-nums` and semantic class (`.score-positive` vs `.score-negative`).
   - `renderModelBadge(modelUsed)`:
     - When `modelUsed === "heuristic-vader"` (or includes `"heuristic"`): returns `<span class="badge badge-model-fallback" title="Synthesized via local VADER heuristic fallback">Heuristic VADER Fallback</span>`.
     - Otherwise: returns `<span class="badge badge-model-spark" title="Synthesized via DGX Spark vLLM">${escapeHtml(modelUsed)}</span>`.
   - `renderSourceBadge(sourceType)`: Maps `"hacker_news"` -> `.badge-hn`, `"reddit"` -> `.badge-reddit`, `"github"` -> `.badge-github`, others -> `.badge-github`.
2. **5-State Renderers Across All Containers**:
   - **Discussions (`#discussions-container`) & Analysis Modal (`#analysis-modal-body`)**:
     - `renderDiscussionsLoading(container)`: Sets `aria-busy="true"` and renders 2 geometry-matched `.skeleton-card` placeholders with `.skeleton-line` blocks (`CLS = 0`).
     - `renderDiscussionsEmpty(container)`: Sets `aria-busy="false"` and renders `.state-empty` with reload button calling `loadCapsuleDigest()`.
     - `renderDiscussionsError(container, errorMsg)`: Sets `aria-busy="false"` and renders `.state-error` (`role="alert"`) with `<button type="button" class="btn-secondary btn-retry" onclick="loadCapsuleDigest()">Retry Capsule Load</button>`.
     - `renderDiscussionCardHtml(d)`: Renders `.card.card-nested` with `.badge-score.tabular-nums` for `Sentiment` and `Controversy`, `renderModelBadge(d.model_used)`, `Core Thesis`, `Community Consensus`, `Contrarian Pushback`, `.spotlight-box` (when `d.anchor_comment_spotlight` is present with `#${d.anchor_comment_id}` in `.tabular-nums`), and `Actionable Takeaways`.
     - `renderAnalysisModalLoading(container)`, `renderAnalysisModalResult(container, d)`, `renderAnalysisModalError(container, errorMsg, itemId, itemTitle)`.
   - **Markdown Preview (`#markdown-preview`)**:
     - `renderMarkdownLoading(container)` (`.skeleton-well` with `.skeleton-line` bars), `renderMarkdownNominal(container, markdownText)`, `renderMarkdownEmpty(container)`, `renderMarkdownError(container, errorMsg)`.
   - **3-Epoch Reading Vault Table (`#vault-table-body`)**:
     - `renderVaultLoading(tbody, tableEl)`: Sets `aria-busy="true"` on `tableEl` and renders 6 `.skeleton-row` `<tr>` rows (`colspan="7"`).
     - `renderVaultEmpty(tbody, tableEl)`: Renders `.state-empty` inside `<td colspan="7">` with two action buttons: `<button type="button" class="btn-secondary" onclick="clearVaultFilters()">Clear Active Filters</button>` and `<button type="button" class="btn-primary" onclick="openImportModal()">Import Safari Notes</button>`.
     - `renderVaultError(tbody, tableEl, errorMsg)`: Renders `.state-error` with `<button type="button" class="btn-secondary btn-retry" onclick="loadVaultItems()">Retry Vault Query</button>`.
     - `renderVaultRows(tbody, tableEl, items)`: Renders rows with canonical link, `search_query` subtitle, monospace domain, `renderSourceBadge(item.source_type)`, `.badge-epoch.tabular-nums` for `epochs_present`, `.badge-canon` (`Evergreen Canon` when `item.is_evergreen_canon` is true) + `<span class="tabular-nums">${item.total_occurrences}x</span>` inside `<td class="num-col">`, `.badge-pillar`, and `<button type="button" class="btn-secondary" data-item-id="${escapeHtml(item.item_id)}" data-item-title="${escapeHtml(item.title)}" onclick="analyzeItem('${escapeHtml(item.item_id)}', '${encodeURIComponent(item.title || "")}', this)">Analyze via Spark</button>`.
   - **Personal Time Capsule (`#taste-profile-container`, `#vocab-table-body`, `#intents-table-body`)**:
     - Loading skeletons, Empty states (including `resetIntentCategory()` CTA on intents), Error states with Retry buttons (`loadTasteProfile()`, `loadVocab()`, `loadIntents()`), and Nominal renderers with `.tabular-nums` on counts and percentages.
   - **Macro Time Machine (`#weather-table-body`, `#stocks-table-body`)**:
     - Loading skeletons (5 `.skeleton-row` rows), Empty states, Error states with Retry (`loadMacro()`), and Nominal rows with `<td class="num-col tabular-nums">` on all numeric weather (`temp`, `humidity`, `pressure`) and equity OHLCV (`close`, `open`, `high`, `low`, `volume`) columns.

## 4. Verification Test Suite (`tests/test_ui_states.py`)
Write deterministic tests in `tests/test_ui_states.py` verifying:
1. `GET /static/views.js` and `GET /static/app.js` return `200 OK` with JavaScript MIME type via FastAPI `TestClient`.
2. `views.js` implements all 5-state rendering functions and includes explicit `.state-empty`, `.state-loading`, `.skeleton-card`, `.skeleton-row`, `.skeleton-line`, `.badge-model-spark`, `.badge-model-fallback`, `.state-error`, `.btn-retry`, `.num-col`, and `.tabular-nums` hooks.
3. End-to-end API + UI state verification against `TestClient`: verifying `/api/v1/capsule/2026-11-06` returns `model_used` fields (`heuristic-vader` when offline) that map cleanly to the degraded-mode contract, and `/api/v1/vault?is_evergreen_canon=true` returns the 14 Evergreen Canon items.
