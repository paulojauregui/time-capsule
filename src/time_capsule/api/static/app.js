/**
 * Digital Time Capsule - Client-Side State Store, Keyboard Shortcuts & Modal Accessibility Controller.
 *
 * Pre-conditions:
 *   - templates/index.html must be loaded and must expose the documented element IDs
 *     (#live-status-region, #model-status-pill, #degraded-mode-banner, #tab-btn-*, #tab-*,
 *     #vault-search-input, #import-modal, #analysis-modal, etc.).
 *   - views.js must have registered window.TimeCapsuleViews renderers before load.
 *
 * Post-conditions:
 *   - Exposes appState, TAB_ORDER, the tablist roving tabindex controller, the global
 *     keyboard shortcut controller, the accessible modal controllers, and the REST API
 *     data loaders on the global window object.
 */
(function () {
  "use strict";

  /**
   * Ordered workspace identifiers matching the WAI-ARIA tablist in index.html.
   * @type {string[]}
   */
  var TAB_ORDER = ["digest", "vault", "capsule", "macro"];

  /**
   * Single source of truth for client-side application state.
   * @type {{activeTab: string, currentDigestMarkdown: string, lastFocusedElement: Element|null,
   *         isDegradedMode: boolean, debounceTimer: number|null}}
   */
  var appState = {
    activeTab: "digest",
    currentDigestMarkdown: "",
    lastFocusedElement: null,
    isDegradedMode: false,
    debounceTimer: null
  };

  var HEURISTIC_MODEL = "heuristic-vader";
  var NOMINAL_MODEL_LABEL = "Model: Qwen3.8-Flash-Next-FP4-Local";
  var DEGRADED_MODEL_LABEL = "Model: Heuristic VADER Fallback";
  var VAULT_SEARCH_DEBOUNCE_MS = 250;

  /**
   * Safely resolve a DOM element by id.
   * @param {string} elementId - The DOM id to resolve.
   * @returns {HTMLElement|null} The element, or null when absent.
   */
  function el(elementId) {
    if (typeof document === "undefined") {
      return null;
    }
    return document.getElementById(elementId);
  }

  /**
   * Announce a polite status message to assistive technologies.
   * @param {string} message - Announcement text.
   * @returns {void}
   */
  function announceStatus(message) {
    var region = el("live-status-region");
    if (region) {
      region.textContent = String(message);
    }
  }

  /**
   * Reflect the active synthesis model in the header pill and degraded banner.
   * @param {string} modelUsed - Model identifier returned by the API.
   * @returns {void}
   */
  function updateModelStatus(modelUsed) {
    var raw = String(modelUsed || "");
    var isHeuristic = raw === HEURISTIC_MODEL || raw.indexOf("heuristic") !== -1;
    appState.isDegradedMode = isHeuristic;

    var pill = el("model-status-pill");
    if (pill) {
      pill.textContent = isHeuristic ? DEGRADED_MODEL_LABEL : NOMINAL_MODEL_LABEL;
      pill.classList.toggle("pill-degraded", isHeuristic);
      pill.classList.toggle("pill-nominal", !isHeuristic);
    }

    var banner = el("degraded-mode-banner");
    if (banner) {
      banner.hidden = !isHeuristic;
    }
  }

  var TAB_BUTTON_IDS = {
    digest: "tab-btn-digest",
    vault: "tab-btn-vault",
    capsule: "tab-btn-capsule",
    macro: "tab-btn-macro"
  };

  var TAB_PANEL_IDS = {
    digest: "tab-digest",
    vault: "tab-vault",
    capsule: "tab-capsule",
    macro: "tab-macro"
  };

  /**
   * Activate one of the four workspaces using the WAI-ARIA tablist contract.
   * @param {string} tabName - One of TAB_ORDER.
   * @param {boolean} [moveFocus=false] - Whether to move DOM focus to the tab button.
   * @returns {void}
   */
  function switchTab(tabName, moveFocus) {
    if (TAB_ORDER.indexOf(tabName) === -1) {
      return;
    }
    appState.activeTab = tabName;

    TAB_ORDER.forEach(function (name) {
      var isActive = name === tabName;
      var btn = el(TAB_BUTTON_IDS[name]);
      if (btn) {
        btn.setAttribute("aria-selected", isActive ? "true" : "false");
        btn.setAttribute("tabindex", isActive ? "0" : "-1");
        btn.classList.toggle("active", isActive);
        if (isActive && moveFocus) {
          btn.focus();
        }
      }

      var panel = el(TAB_PANEL_IDS[name]);
      if (panel) {
        panel.hidden = !isActive;
        panel.classList.toggle("active", isActive);
      }
    });

    if (tabName === "vault") {
      loadVaultItems();
    } else if (tabName === "capsule") {
      loadTasteProfile();
      loadVocab();
      loadIntents();
    } else if (tabName === "macro") {
      loadMacro();
    }
  }

  /**
   * Roving tabindex keyboard controller for the .tab-bar [role="tablist"].
   * @param {KeyboardEvent} event - Keydown event originating inside the tab bar.
   * @returns {void}
   */
  function handleTabbarKeydown(event) {
    var currentIndex = TAB_ORDER.indexOf(appState.activeTab);
    if (currentIndex === -1) {
      currentIndex = 0;
    }

    var nextIndex = null;
    if (event.key === "ArrowRight") {
      nextIndex = (currentIndex + 1) % TAB_ORDER.length;
    } else if (event.key === "ArrowLeft") {
      nextIndex = (currentIndex - 1 + TAB_ORDER.length) % TAB_ORDER.length;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = TAB_ORDER.length - 1;
    } else {
      return;
    }

    event.preventDefault();
    switchTab(TAB_ORDER[nextIndex], true);
  }

  /**
   * Determine whether the focused element should be treated as a text entry surface.
   * @param {Element|null} element - The currently focused element.
   * @returns {boolean} True when typing should not be intercepted by global shortcuts.
   */
  function isTypingTarget(element) {
    if (!element) {
      return false;
    }
    var tag = String(element.tagName || "").toUpperCase();
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {
      return true;
    }
    return Boolean(element.isContentEditable);
  }

  /**
   * Trap Tab keyboard navigation inside an active modal dialog.
   * @param {Element|null} modalEl - Visible modal dialog element.
   * @param {KeyboardEvent} event - Keydown event for Tab.
   * @returns {void}
   */
  function trapModalFocus(modalEl, event) {
    if (!modalEl || typeof modalEl.querySelectorAll !== "function") {
      return;
    }
    var selector = [
      "a[href]",
      "button:not([disabled])",
      "input:not([disabled])",
      "select:not([disabled])",
      "textarea:not([disabled])",
      "[tabindex]:not([tabindex='-1'])"
    ].join(", ");
    var nodes = modalEl.querySelectorAll(selector);
    var focusable = [];
    for (var i = 0; i < nodes.length; i += 1) {
      var node = nodes[i];
      if (!node.hidden && (typeof node.closest !== "function" || !node.closest("[hidden]"))) {
        focusable.push(node);
      }
    }
    if (focusable.length === 0) {
      event.preventDefault();
      if (typeof modalEl.focus === "function") {
        modalEl.focus();
      }
      return;
    }
    var first = focusable[0];
    var last = focusable[focusable.length - 1];
    var active = typeof document !== "undefined" ? document.activeElement : null;
    var insideModal = typeof modalEl.contains === "function" && modalEl.contains(active);

    if (event.shiftKey) {
      if (active === first || !insideModal) {
        event.preventDefault();
        last.focus();
      }
    } else if (active === last || !insideModal) {
      event.preventDefault();
      first.focus();
    }
  }

  /**
   * Global keyboard shortcut controller (/, Cmd/Ctrl+K, Escape, Tab trap).
   * @param {KeyboardEvent} event - Window-level keydown event.
   * @returns {void}
   */
  function handleGlobalKeydown(event) {
    var active = typeof document !== "undefined" ? document.activeElement : null;
    var importModal = el("import-modal");
    var analysisModal = el("analysis-modal");
    var openModal = null;

    if (importModal && !importModal.hidden) {
      openModal = importModal;
    } else if (analysisModal && !analysisModal.hidden) {
      openModal = analysisModal;
    }

    if (openModal) {
      if (event.key === "Escape") {
        event.preventDefault();
        if (openModal === importModal) {
          closeImportModal();
        } else {
          closeAnalysisModal();
        }
        return;
      }
      if (event.key === "Tab") {
        trapModalFocus(openModal, event);
      }
      return;
    }

    if (event.key === "Escape") {
      var searchInput = el("vault-search-input");
      if (active && active.id === "vault-search-input" && searchInput && searchInput.value !== "") {
        event.preventDefault();
        searchInput.value = "";
        loadVaultItems();
        announceStatus("Cleared vault search filter.");
      }
      return;
    }

    var isSearchShortcut = event.key === "/" ||
      ((event.metaKey || event.ctrlKey) && String(event.key).toLowerCase() === "k");

    if (isSearchShortcut && !isTypingTarget(active)) {
      event.preventDefault();
      switchTab("vault", false);
      var vaultSearch = el("vault-search-input");
      if (vaultSearch) {
        vaultSearch.focus();
        if (typeof vaultSearch.select === "function") {
          vaultSearch.select();
        }
      }
      announceStatus("Vault search focused.");
    }
  }

  /**
   * Open the Safari import modal and move focus into the dialog.
   * @returns {void}
   */
  function openImportModal() {
    var modal = el("import-modal");
    if (!modal) {
      return;
    }
    appState.lastFocusedElement = document.activeElement;
    modal.hidden = false;
    modal.classList.add("active");

    var feedback = el("import-feedback");
    if (feedback) {
      feedback.hidden = true;
      feedback.textContent = "";
      feedback.classList.remove("state-error");
    }
    var submitBtn = el("submit-import-btn");
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.removeAttribute("aria-busy");
      submitBtn.textContent = "Ingest into Vault";
    }

    var target = el("import-text") || el("import-epoch-select");
    if (target) {
      target.focus();
    }
    announceStatus("Import Safari Reading List dialog opened.");
  }

  /**
   * Close the Safari import modal and restore the previously focused control.
   * @param {boolean} [silent] - Suppress generic close announcement when followed by a specific announcement.
   * @returns {void}
   */
  function closeImportModal(silent) {
    var modal = el("import-modal");
    if (!modal) {
      return;
    }
    modal.hidden = true;
    modal.classList.remove("active");

    if (appState.lastFocusedElement && typeof appState.lastFocusedElement.focus === "function" &&
      (typeof document === "undefined" || !document.contains || document.contains(appState.lastFocusedElement))) {
      appState.lastFocusedElement.focus();
    } else {
      var fallbackTrigger = el("open-import-btn");
      if (fallbackTrigger && typeof fallbackTrigger.focus === "function") {
        fallbackTrigger.focus();
      }
    }
    appState.lastFocusedElement = null;
    if (!silent) {
      announceStatus("Import dialog closed.");
    }
  }

  /**
   * Submit the Safari Reading List text payload to the lakehouse import endpoint.
   * @returns {Promise<void>}
   */
  async function submitImport() {
    var textarea = el("import-text");
    var epochSelect = el("import-epoch-select");
    var feedback = el("import-feedback");
    var submitBtn = el("submit-import-btn");

    var text = textarea ? textarea.value : "";
    var epoch = epochSelect ? epochSelect.value : "2026_11_06";

    if (!text || text.trim() === "") {
      if (feedback) {
        feedback.hidden = false;
        feedback.classList.add("state-error");
        feedback.textContent = "Please paste at least one URL or Markdown link to import.";
      }
      announceStatus("Import rejected: no URLs provided.");
      return;
    }

    if (feedback) {
      feedback.hidden = false;
      feedback.classList.remove("state-error");
      feedback.textContent = "Importing...";
    }
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = "Importing...";
      submitBtn.setAttribute("aria-busy", "true");
    }

    try {
      var response = await fetch("/api/v1/vault/import", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text, epoch_id: epoch })
      });
      if (!response.ok) {
        throw new Error("Import failed with HTTP " + String(response.status));
      }
      var data = await response.json();
      var imported = String(data.imported_raw_count || 0);

      if (feedback) {
        feedback.classList.remove("state-error");
        feedback.textContent = "Imported " + imported + " raw links into epoch " + epoch + ".";
      }
      if (textarea) {
        textarea.value = "";
      }
      closeImportModal(true);
      await loadVaultItems();
      await refreshHeaderPills();
      if (typeof document !== "undefined" && (!document.activeElement || document.activeElement === document.body)) {
        var vaultTrigger = el("open-import-btn");
        if (vaultTrigger && typeof vaultTrigger.focus === "function") {
          vaultTrigger.focus();
        }
      }
      announceStatus("Imported " + imported + " Safari reading list links into the vault.");
    } catch (error) {
      var message = error && error.message ? error.message : "Unknown import error";
      if (feedback) {
        feedback.hidden = false;
        feedback.classList.add("state-error");
        feedback.textContent = "Import error: " + message;
      }
      announceStatus("Vault import failed: " + message);
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = "Ingest into Vault";
        submitBtn.removeAttribute("aria-busy");
      }
    }
  }

  /**
   * Synthesize a discussion analysis for a vault item inside the analysis modal.
   * @param {string} itemId - Vault item identifier.
   * @param {string} itemTitle - Human readable item title.
   * @param {Element|null} triggerEl - The row button that triggered synthesis.
   * @returns {Promise<void>}
   */
  async function analyzeItem(itemId, itemTitle, triggerEl) {
    var modal = el("analysis-modal");
    if (!modal) {
      return;
    }
    if (modal.hidden) {
      var candidate = triggerEl || (typeof document !== "undefined" ? document.activeElement : null);
      if (candidate && (typeof modal.contains !== "function" || !modal.contains(candidate))) {
        appState.lastFocusedElement = candidate;
      }
    }

    modal.hidden = false;
    modal.classList.add("active");

    var titleEl = el("analysis-modal-title");
    if (titleEl) {
      titleEl.textContent = "Discussion Synthesis: " + String(itemTitle || itemId);
    }

    var closeBtn = el("close-analysis-modal-btn");
    if (closeBtn) {
      closeBtn.focus();
    }
    announceStatus("Synthesizing discussion analysis via DGX Spark.");

    var container = el("analysis-modal-body");
    var views = window.TimeCapsuleViews;
    if (views && typeof views.renderAnalysisModalLoading === "function") {
      views.renderAnalysisModalLoading(container);
    } else if (container) {
      container.textContent = "Loading analysis...";
    }

    try {
      var response = await fetch("/api/v1/vault/" + encodeURIComponent(itemId) + "/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ allow_llm: true, allow_external_hydration: false })
      });
      if (!response.ok) {
        throw new Error("Analysis failed with HTTP " + String(response.status));
      }
      var analysis = await response.json();
      if (analysis && analysis.model_used) {
        updateModelStatus(analysis.model_used);
      }
      if (views && typeof views.renderAnalysisModalResult === "function") {
        views.renderAnalysisModalResult(container, analysis);
      } else if (container) {
        container.textContent = String(analysis.core_thesis || "Analysis complete.");
      }
      announceStatus("Discussion analysis ready.");
    } catch (error) {
      var message = error && error.message ? error.message : "Unknown analysis error";
      if (views && typeof views.renderAnalysisModalError === "function") {
        views.renderAnalysisModalError(container, message, itemId, itemTitle);
      } else if (container) {
        container.textContent = "Analysis error: " + message;
      }
      announceStatus("Discussion analysis failed: " + message);
    }
  }

  /**
   * Close the analysis modal and restore focus to the triggering row button.
   * @returns {void}
   */
  function closeAnalysisModal() {
    var modal = el("analysis-modal");
    if (!modal) {
      return;
    }
    modal.hidden = true;
    modal.classList.remove("active");

    if (appState.lastFocusedElement && typeof appState.lastFocusedElement.focus === "function") {
      appState.lastFocusedElement.focus();
    }
    appState.lastFocusedElement = null;
    announceStatus("Analysis dialog closed.");
  }

  /**
   * Apply a semantic pill state class while clearing any previous status class.
   * @param {Element|null} pillEl - Header telemetry pill element.
   * @param {string} stateClass - Target CSS pill modifier class.
   * @returns {void}
   */
  function setPillState(pillEl, stateClass) {
    if (!pillEl || !pillEl.classList) {
      return;
    }
    pillEl.classList.remove(
      "pill-nominal",
      "pill-green",
      "pill-degraded",
      "pill-amber",
      "pill-error",
      "pill-red"
    );
    if (stateClass) {
      pillEl.classList.add(stateClass);
    }
  }

  /**
   * Fetch /ready and update the header telemetry pills.
   * @param {boolean} [healthOk=true] - Whether the /healthz probe succeeded during init.
   * @returns {Promise<void>}
   */
  async function refreshHeaderPills(healthOk) {
    try {
      var response = await fetch("/ready");
      if (!response.ok) {
        throw new Error("Readiness probe responded HTTP " + String(response.status));
      }
      var data = await response.json();
      var service = el("service-status");
      if (service) {
        if (healthOk === false) {
          service.textContent = "Service: Degraded";
          setPillState(service, "pill-degraded");
        } else {
          service.textContent = "Service: Nominal";
          setPillState(service, "pill-nominal");
        }
      }
      var vaultPill = el("vault-count-pill");
      if (vaultPill) {
        vaultPill.textContent = "Vault: " + String(data.vault_count) + " items";
      }
      var canonPill = el("evergreen-count-pill");
      if (canonPill) {
        canonPill.textContent = "Evergreen Canon: " + String(data.evergreen_count) + " items";
      }
    } catch (error) {
      var serviceErr = el("service-status");
      if (serviceErr) {
        serviceErr.textContent = "Service: Degraded";
        setPillState(serviceErr, "pill-degraded");
      }
    }
  }

  /**
   * Bootstrap the dashboard: health probes, header pills, and the default capsule digest.
   * @returns {Promise<void>}
   */
  async function initDashboard() {
    var healthOk = false;
    var service = el("service-status");
    try {
      var healthResponse = await fetch("/healthz");
      if (!healthResponse.ok) {
        throw new Error("Health probe responded HTTP " + String(healthResponse.status));
      }
      var health = await healthResponse.json();
      healthOk = Boolean(health && health.status === "ok");
      if (service) {
        service.textContent = healthOk ? "Service: Nominal" : "Service: Degraded";
        setPillState(service, healthOk ? "pill-nominal" : "pill-degraded");
      }
    } catch (error) {
      healthOk = false;
      if (service) {
        service.textContent = "Service: Degraded";
        setPillState(service, "pill-degraded");
      }
    }

    await refreshHeaderPills(healthOk);
    switchTab("digest", false);
    await loadCapsuleDigest();
    announceStatus("Dashboard initialized.");
  }

  /**
   * Load and render the daily capsule digest for #capsule-date-input.
   * @returns {Promise<void>}
   */
  async function loadCapsuleDigest() {
    var views = window.TimeCapsuleViews;
    var discussionContainer = el("discussions-container");
    var markdownContainer = el("markdown-preview");
    var copyStatus = el("copy-status");
    var dateInput = el("capsule-date-input");
    var capsuleDate = dateInput && dateInput.value ? dateInput.value : "2026-11-06";

    if (copyStatus) {
      copyStatus.textContent = "";
    }
    if (views && typeof views.renderDiscussionsLoading === "function") {
      views.renderDiscussionsLoading(discussionContainer);
    }
    if (views && typeof views.renderMarkdownLoading === "function") {
      views.renderMarkdownLoading(markdownContainer);
    }

    try {
      var response = await fetch("/api/v1/capsule/" + encodeURIComponent(capsuleDate));
      if (!response.ok) {
        throw new Error("Capsule request responded HTTP " + String(response.status));
      }
      var snapshot = await response.json();
      var discussions = snapshot.top_discussions || [];

      appState.currentDigestMarkdown = snapshot.markdown_digest || "";

      if (views && typeof views.renderDiscussions === "function") {
        views.renderDiscussions(discussionContainer, discussions);
      } else if (discussionContainer) {
        discussionContainer.textContent = String(discussions.length) + " discussions loaded.";
      }

      if (views && typeof views.renderMarkdownPreview === "function") {
        views.renderMarkdownPreview(markdownContainer, appState.currentDigestMarkdown);
      } else if (markdownContainer) {
        markdownContainer.textContent = appState.currentDigestMarkdown;
      }

      var degraded = discussions.some(function (d) {
        return d && d.model_used && String(d.model_used).indexOf("heuristic") !== -1;
      });
      if (degraded) {
        updateModelStatus(HEURISTIC_MODEL);
        var banner = el("degraded-mode-banner");
        if (banner) {
          banner.hidden = false;
        }
      } else if (discussions.length > 0 && discussions[0].model_used) {
        updateModelStatus(discussions[0].model_used);
      } else {
        updateModelStatus(NOMINAL_MODEL_LABEL);
      }

      announceStatus("Loaded " + String(discussions.length) + " discussion highlights for " + capsuleDate + ".");
    } catch (error) {
      var message = error && error.message ? error.message : "Unknown capsule error";
      if (views && typeof views.renderDiscussionsError === "function") {
        views.renderDiscussionsError(discussionContainer, message);
      } else if (discussionContainer) {
        discussionContainer.textContent = "Capsule error: " + message;
      }
      if (views && typeof views.renderMarkdownError === "function") {
        views.renderMarkdownError(markdownContainer, message);
      }
      announceStatus("Capsule digest failed to load: " + message);
    }
  }

  /**
   * Copy the active Markdown digest to the system clipboard.
   * @returns {Promise<void>}
   */
  async function copyMarkdownDigest() {
    var statusEl = el("copy-status");
    try {
      if (!navigator || !navigator.clipboard || typeof navigator.clipboard.writeText !== "function") {
        throw new Error("Clipboard API unavailable in this browser context");
      }
      await navigator.clipboard.writeText(appState.currentDigestMarkdown);
      if (statusEl) {
        statusEl.textContent = "Copied Markdown digest to clipboard.";
      }
      announceStatus("Copied Markdown digest to clipboard.");
    } catch (error) {
      var message = error && error.message ? error.message : "Clipboard write failed";
      if (statusEl) {
        statusEl.textContent = "Copy failed: " + message;
      }
      announceStatus("Copy failed: " + message);
    }
  }

  /**
   * Query the vault endpoint using the current control panel filters.
   * @returns {Promise<void>}
   */
  async function loadVaultItems() {
    var tbody = el("vault-table-body");
    var tableEl = el("vault-table");
    var views = window.TimeCapsuleViews;

    if (appState.debounceTimer !== null) {
      clearTimeout(appState.debounceTimer);
      appState.debounceTimer = null;
    }

    if (views && typeof views.renderVaultLoading === "function") {
      views.renderVaultLoading(tbody, tableEl);
    }

    var epoch = valueOf("vault-epoch-select");
    var evergreen = valueOf("vault-evergreen-select");
    var pillar = valueOf("vault-pillar-select");
    var source = valueOf("vault-source-select");
    var search = valueOf("vault-search-input");

    var params = new URLSearchParams();
    if (epoch) params.set("epoch", epoch);
    if (evergreen) params.set("is_evergreen_canon", evergreen);
    if (pillar) params.set("pillar", pillar);
    if (source) params.set("source_type", source);
    if (search) params.set("search", search);

    try {
      var response = await fetch("/api/v1/vault?" + params.toString());
      if (!response.ok) {
        throw new Error("Vault query responded HTTP " + String(response.status));
      }
      var payload = await response.json();
      var items = payload.items || [];

      var resultsMeta = el("vault-results-count");
      if (resultsMeta) {
        resultsMeta.textContent = "Displaying " + String(payload.count) + " items";
      }

      if (items.length === 0) {
        if (views && typeof views.renderVaultEmpty === "function") {
          views.renderVaultEmpty(tbody, tableEl);
        }
      } else if (views && typeof views.renderVaultRows === "function") {
        views.renderVaultRows(tbody, tableEl, items);
      }
      announceStatus("Vault shows " + String(payload.count) + " items.");
    } catch (error) {
      var message = error && error.message ? error.message : "Unknown vault error";
      if (views && typeof views.renderVaultError === "function") {
        views.renderVaultError(tbody, tableEl, message);
      }
      announceStatus("Vault query failed: " + message);
    }
  }

  /**
   * Read the .value of a control by id.
   * @param {string} elementId - The form control id.
   * @returns {string} The trimmed value, or "" when the control is missing.
   */
  function valueOf(elementId) {
    var node = el(elementId);
    return node && node.value ? String(node.value).trim() : "";
  }

  /**
   * Reset every vault filter control and reload the table.
   * @returns {void}
   */
  function clearVaultFilters() {
    ["vault-epoch-select", "vault-evergreen-select", "vault-pillar-select",
      "vault-source-select", "vault-search-input"].forEach(function (id) {
        var node = el(id);
        if (node) {
          node.value = "";
        }
      });
    loadVaultItems();
    announceStatus("Vault filters cleared.");
  }

  /**
   * Load the longitudinal taste profile summary.
   * @returns {Promise<void>}
   */
  /**
   * Resolve the enclosing table element for a table body when available.
   * @param {Element|null} tbody - Table body element.
   * @returns {Element|null} The ancestor table element or null.
   */
  function tableOf(tbody) {
    if (!tbody || typeof tbody.closest !== "function") {
      return null;
    }
    return tbody.closest("table");
  }

  async function loadTasteProfile() {
    var container = el("taste-profile-container");
    var views = window.TimeCapsuleViews;
    if (views && typeof views.renderTasteProfileLoading === "function") {
      views.renderTasteProfileLoading(container);
    }
    try {
      var response = await fetch("/api/v1/epochs/summary");
      if (!response.ok) {
        throw new Error("Epoch summary responded HTTP " + String(response.status));
      }
      var summary = await response.json();
      if (views && typeof views.renderTasteProfile === "function") {
        views.renderTasteProfile(container, summary);
      } else if (container) {
        container.textContent = "Taste profile loaded.";
      }
      announceStatus("Longitudinal taste profile loaded.");
    } catch (error) {
      var message = error && error.message ? error.message : "Unknown epochs error";
      if (views && typeof views.renderTasteProfileError === "function") {
        views.renderTasteProfileError(container, message);
      }
      announceStatus("Taste profile failed: " + message);
    }
  }

  /**
   * Load the personal technical vocabulary lexicon.
   * @returns {Promise<void>}
   */
  async function loadVocab() {
    var tbody = el("vocab-table-body");
    var vocabTable = tableOf(tbody);
    var views = window.TimeCapsuleViews;
    if (views && typeof views.renderVocabLoading === "function") {
      views.renderVocabLoading(tbody, vocabTable);
    }
    try {
      var response = await fetch("/api/v1/vocabulary");
      if (!response.ok) {
        throw new Error("Vocabulary request responded HTTP " + String(response.status));
      }
      var payload = await response.json();
      var entries = payload.vocabulary || [];
      var badge = el("vocab-count-badge");
      if (badge) {
        badge.textContent = String(payload.count) + " terms";
      }
      if (views && typeof views.renderVocabRows === "function") {
        views.renderVocabRows(tbody, entries, vocabTable);
      }
      announceStatus("Vocabulary lexicon loaded with " + String(payload.count) + " terms.");
    } catch (error) {
      var message = error && error.message ? error.message : "Unknown vocabulary error";
      if (views && typeof views.renderVocabError === "function") {
        views.renderVocabError(tbody, message, vocabTable);
      }
      announceStatus("Vocabulary load failed: " + message);
    }
  }

  /**
   * Load categorized search query intents.
   * @returns {Promise<void>}
   */
  async function loadIntents() {
    var tbody = el("intents-table-body");
    var intentsTable = tableOf(tbody);
    var views = window.TimeCapsuleViews;
    if (views && typeof views.renderIntentsLoading === "function") {
      views.renderIntentsLoading(tbody, intentsTable);
    }
    var category = valueOf("intent-category-select");
    var query = category ? "?category=" + encodeURIComponent(category) : "";
    try {
      var response = await fetch("/api/v1/intents" + query);
      if (!response.ok) {
        throw new Error("Intents request responded HTTP " + String(response.status));
      }
      var payload = await response.json();
      var intents = payload.intents || [];
      var badge = el("intents-count-badge");
      if (badge) {
        badge.textContent = String(payload.count) + " intents";
      }
      if (views && typeof views.renderIntentsRows === "function") {
        views.renderIntentsRows(tbody, intents, intentsTable);
      }
      announceStatus("Search intents loaded with " + String(payload.count) + " entries.");
    } catch (error) {
      var message = error && error.message ? error.message : "Unknown intents error";
      if (views && typeof views.renderIntentsError === "function") {
        views.renderIntentsError(tbody, message, intentsTable);
      }
      announceStatus("Search intents failed: " + message);
    }
  }

  /**
   * Reset the intent category filter and reload the intent table.
   * @returns {void}
   */
  function resetIntentCategory() {
    var select = el("intent-category-select");
    if (select) {
      select.value = "";
    }
    loadIntents();
    announceStatus("Intent category filter reset.");
  }

  /**
   * Load Macro Time Machine telemetry tables.
   * @returns {Promise<void>}
   */
  async function loadMacro() {
    var weatherBody = el("weather-table-body");
    var stocksBody = el("stocks-table-body");
    var weatherTable = tableOf(weatherBody);
    var stocksTable = tableOf(stocksBody);
    var views = window.TimeCapsuleViews;

    if (views && typeof views.renderWeatherLoading === "function") {
      views.renderWeatherLoading(weatherBody, weatherTable);
    }
    if (views && typeof views.renderStocksLoading === "function") {
      views.renderStocksLoading(stocksBody, stocksTable);
    }

    try {
      var response = await fetch("/api/v1/capsule/" + encodeURIComponent(valueOf("capsule-date-input") || "2026-11-06"));
      if (!response.ok) {
        throw new Error("Macro request responded HTTP " + String(response.status));
      }
      var snapshot = await response.json();
      var weather = snapshot.weather_records || [];
      var stocks = snapshot.stock_records || [];

      if (views && typeof views.renderWeatherRows === "function") {
        views.renderWeatherRows(weatherBody, weather, weatherTable);
      }
      if (views && typeof views.renderStockRows === "function") {
        views.renderStockRows(stocksBody, stocks, stocksTable);
      }
      announceStatus("Macro telemetry loaded: " + String(weather.length) + " cities, " +
        String(stocks.length) + " tickers.");
    } catch (error) {
      var message = error && error.message ? error.message : "Unknown macro error";
      if (views && typeof views.renderMacroError === "function") {
        views.renderMacroError(weatherBody, stocksBody, message, weatherTable, stocksTable);
      }
      announceStatus("Macro telemetry failed: " + message);
    }
  }

  /**
   * Wire debounced vault filtering and one-time DOM event bindings.
   * @returns {void}
   */
  function wireVaultFilterBindings() {
    ["vault-epoch-select", "vault-evergreen-select", "vault-pillar-select", "vault-source-select"]
      .forEach(function (id) {
        var node = el(id);
        if (node) {
          node.addEventListener("change", function () {
            loadVaultItems();
          });
        }
      });

    var search = el("vault-search-input");
    if (search) {
      search.addEventListener("input", function () {
        if (appState.debounceTimer !== null) {
          clearTimeout(appState.debounceTimer);
        }
        appState.debounceTimer = setTimeout(function () {
          appState.debounceTimer = null;
          loadVaultItems();
        }, VAULT_SEARCH_DEBOUNCE_MS);
      });
    }

    var intentSelect = el("intent-category-select");
    if (intentSelect) {
      intentSelect.addEventListener("change", function () {
        loadIntents();
      });
    }
  }

  /**
   * Wire tab bar keyboard navigation, modal buttons, and header actions.
   * @returns {void}
   */
  function wireEventListeners() {
    var tabbar = document.querySelector(".tab-bar[role='tablist']");
    if (tabbar) {
      tabbar.addEventListener("keydown", handleTabbarKeydown);
      tabbar.querySelectorAll("[role='tab']").forEach(function (btn) {
        btn.addEventListener("click", function () {
          var name = btn.getAttribute("data-tab");
          if (name) {
            switchTab(name, true);
          }
        });
      });
    }

    var bindings = [
      ["load-capsule-btn", function () { loadCapsuleDigest(); }],
      ["copy-digest-btn", function () { copyMarkdownDigest(); }],
      ["copy-digest-secondary-btn", function () { copyMarkdownDigest(); }],
      ["clear-vault-filters-btn", function () { clearVaultFilters(); }],
      ["open-import-modal-btn", function () { openImportModal(); }],
      ["close-import-modal-btn", function () { closeImportModal(); }],
      ["cancel-import-btn", function () { closeImportModal(); }],
      ["submit-import-btn", function () { submitImport(); }],
      ["close-analysis-modal-btn", function () { closeAnalysisModal(); }]
    ];

    bindings.forEach(function (pair) {
      var node = el(pair[0]);
      if (node) {
        node.addEventListener("click", pair[1]);
      }
    });

    var capsuleDate = el("capsule-date-input");
    if (capsuleDate) {
      capsuleDate.addEventListener("keydown", function (event) {
        if (event.key === "Enter") {
          event.preventDefault();
          loadCapsuleDigest();
        }
      });
    }

    [["import-modal", closeImportModal], ["analysis-modal", closeAnalysisModal]]
      .forEach(function (pair) {
        var modal = el(pair[0]);
        if (modal) {
          modal.addEventListener("click", function (event) {
            if (event.target === modal) {
              pair[1]();
            }
          });
        }
      });

    wireVaultFilterBindings();
    document.addEventListener("keydown", handleGlobalKeydown);
  }

  /**
   * Boot the dashboard once the DOM is parsed.
   * @returns {void}
   */
  function onDomContentLoaded() {
    wireEventListeners();
    initDashboard();
  }

  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", onDomContentLoaded);
    } else {
      onDomContentLoaded();
    }
  }

  window.TAB_ORDER = TAB_ORDER;
  window.appState = appState;
  window.announceStatus = announceStatus;
  window.updateModelStatus = updateModelStatus;
  window.switchTab = switchTab;
  window.handleTabbarKeydown = handleTabbarKeydown;
  window.handleGlobalKeydown = handleGlobalKeydown;
  window.openImportModal = openImportModal;
  window.closeImportModal = closeImportModal;
  window.analyzeItem = analyzeItem;
  window.closeAnalysisModal = closeAnalysisModal;
  window.initDashboard = initDashboard;
  window.loadCapsuleDigest = loadCapsuleDigest;
  window.copyMarkdownDigest = copyMarkdownDigest;
  window.loadVaultItems = loadVaultItems;
  window.clearVaultFilters = clearVaultFilters;
  window.submitImport = submitImport;
  window.loadTasteProfile = loadTasteProfile;
  window.loadVocab = loadVocab;
  window.loadIntents = loadIntents;
  window.resetIntentCategory = resetIntentCategory;
  window.loadMacro = loadMacro;
})();
