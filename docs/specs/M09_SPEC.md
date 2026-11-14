# Milestone M09 Specification: Client-Side State Store, WAI-ARIA Roving Tabindex, Keyboard Shortcuts & Modal Accessibility Controller

## 1. Objective
Implement `src/time_capsule/api/static/app.js` providing the application state controller, WAI-ARIA roving tabindex tab navigation (`ArrowLeft`, `ArrowRight`, `Home`, `End`), global keyboard shortcuts (`/` and `Cmd/Ctrl+K` for Vault search, `Escape` for modal dismissal and search clearing), modal focus restoration, `aria-live="polite"` announcements, and REST API data loaders across all 4 workspaces. Verify the contract in `tests/test_ui_js_contract.py`.

## 2. Target Files
1. `src/time_capsule/api/static/app.js`
2. `tests/test_ui_js_contract.py`

## 3. Exact Behavioral & Architectural Contract (`src/time_capsule/api/static/app.js`)
1. **State & Focus Management**:
   - Maintain `appState`: `activeTab` (`"digest"`, `"vault"`, `"capsule"`, `"macro"`), `currentDigestMarkdown`, `lastFocusedElement` (for restoring focus when closing `#import-modal` or `#analysis-modal`), `isDegradedMode` (`boolean`), and `debounceTimer`.
   - `announceStatus(message)`: Sets `document.getElementById("live-status-region").textContent = message`.
   - `updateModelStatus(modelUsed)`:
     - Checks if `modelUsed === "heuristic-vader"` (or contains `"heuristic"`).
     - Updates `#model-status-pill` text (`"Model: Heuristic VADER Fallback"` with `.pill-degraded` vs `"Model: Qwen3.8-Flash-Next-FP4-Local"` with `.pill-nominal`).
     - Toggles `document.getElementById("degraded-mode-banner").hidden = !isHeuristic`.
2. **WAI-ARIA Tablist & Roving Tabindex Controller**:
   - `TAB_ORDER = ["digest", "vault", "capsule", "macro"]`.
   - `switchTab(tabName, moveFocus = false)`:
     - Updates all 4 `[role="tab"]` buttons (`#tab-btn-digest`, `#tab-btn-vault`, `#tab-btn-capsule`, `#tab-btn-macro`):
       - Active tab: `aria-selected="true"`, `tabindex="0"`, `.classList.add("active")`; if `moveFocus` is true, calls `.focus()`.
       - Inactive tabs: `aria-selected="false"`, `tabindex="-1"`, `.classList.remove("active")`.
     - Updates all 4 `[role="tabpanel"]` sections (`#tab-digest`, `#tab-vault`, `#tab-capsule`, `#tab-macro`):
       - Active panel: `panel.hidden = false`, `.classList.add("active")`.
       - Inactive panels: `panel.hidden = true`, `.classList.remove("active")`.
     - Triggers workspace data loader (`loadVaultItems()` for `"vault"`, `loadTasteProfile()`, `loadVocab()`, `loadIntents()` for `"capsule"`, `loadMacro()` for `"macro"`).
   - `handleTabbarKeydown(event)`:
     - Handles `ArrowRight`, `ArrowLeft`, `Home`, `End` inside `.tab-bar` (`role="tablist"`), calling `event.preventDefault()` and `switchTab(nextTab, true)`.
3. **Global Keyboard Shortcut Controller (`handleGlobalKeydown`)**:
   - `Escape`:
     - If `#import-modal` is open (`!modal.hidden`), calls `event.preventDefault()` and `closeImportModal()`.
     - Else if `#analysis-modal` is open (`!modal.hidden`), calls `event.preventDefault()` and `closeAnalysisModal()`.
     - Else if `document.activeElement.id === "vault-search-input"` and `document.activeElement.value !== ""`, clears `#vault-search-input`, triggers `loadVaultItems()`, and announces `"Cleared vault search filter."`.
   - `/` or `(event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k"`:
     - When `document.activeElement` is NOT an `INPUT`, `TEXTAREA`, `SELECT`, or `isContentEditable`:
       - Calls `event.preventDefault()`, switches to `"vault"` tab (`switchTab("vault", false)`), and focuses `#vault-search-input`.
4. **Accessible Modals (`openImportModal`, `closeImportModal`, `analyzeItem`, `closeAnalysisModal`)**:
   - Stores `appState.lastFocusedElement = document.activeElement` before opening.
   - Removes `hidden` and adds `.active` on open; moves focus into modal (`#import-text` for `#import-modal`, `#close-analysis-modal-btn` for `#analysis-modal`).
   - On close, sets `modal.hidden = true`, removes `.active`, and calls `appState.lastFocusedElement.focus()` if available.
   - Backdrop click on `.modal` (`event.target === modal`) closes the modal.
5. **Data Loaders & Action Handlers Delegating Rendering to `window.TimeCapsuleViews` (`views.js`)**:
   - `initDashboard()`: Fetches `/healthz` and `/ready`, updates `#service-status`, `#vault-count-pill`, `#evergreen-count-pill`, and calls `loadCapsuleDigest()`.
   - `loadCapsuleDigest()`: Calls `TimeCapsuleViews.renderDiscussionsLoading()`, fetches `/api/v1/capsule/{date}`, updates `currentDigestMarkdown`, calls `TimeCapsuleViews.renderDiscussions(...)` and `TimeCapsuleViews.renderMarkdownPreview(...)`, and updates `#degraded-mode-banner` if any discussion has `model_used === "heuristic-vader"`.
   - `copyMarkdownDigest()`: Copies `currentDigestMarkdown` via `navigator.clipboard.writeText`, updates `#copy-status`, and calls `announceStatus("Copied Markdown digest to clipboard.")`.
   - `loadVaultItems()`, `clearVaultFilters()`, `submitImport()`, `analyzeItem(itemId, itemTitle, triggerEl)`, `loadTasteProfile()`, `loadVocab()`, `loadIntents()`, `resetIntentCategory()`, `loadMacro()`.

## 4. Verification Test Suite (`tests/test_ui_js_contract.py`)
Write deterministic unit tests in `tests/test_ui_js_contract.py` verifying:
1. `src/time_capsule/api/static/app.js` exists, contains zero emojis, and defines all required controller functions (`initDashboard`, `switchTab`, `handleTabbarKeydown`, `handleGlobalKeydown`, `loadCapsuleDigest`, `copyMarkdownDigest`, `loadVaultItems`, `clearVaultFilters`, `openImportModal`, `closeImportModal`, `submitImport`, `analyzeItem`, `closeAnalysisModal`, `loadTasteProfile`, `loadVocab`, `loadIntents`, `resetIntentCategory`, `loadMacro`, `announceStatus`, `updateModelStatus`).
2. `app.js` implements WAI-ARIA roving tabindex (`aria-selected`, `tabindex`, `hidden`) and keyboard handlers (`ArrowRight`, `ArrowLeft`, `Home`, `End`, `Escape`, `/`).
3. `app.js` binds all required API endpoints (`/healthz`, `/ready`, `/api/v1/capsule/`, `/api/v1/vault`, `/api/v1/vault/import`, `/analyze`, `/api/v1/epochs/summary`, `/api/v1/vocabulary`, `/api/v1/intents`).
