/**
 * Digital Time Capsule - 5-State Component Renderers & DOM Views.
 *
 * Pre-conditions:
 *   - DOM containers must exist in templates/index.html.
 *   - Window object must be present in the browser execution environment.
 *
 * Post-conditions:
 *   - Exposes window.TimeCapsuleViews containing pure, XSS-safe DOM rendering
 *     functions for all 5 deterministic component states (Empty, Loading, Nominal,
 *     Degraded/Offline Fallback, Error) across all 4 workspaces and modals.
 *   - Strictly enforces tabular numerics (.tabular-nums, .num-col) and zero emojis.
 */
(function () {
  "use strict";

  /**
   * Escape special HTML characters to prevent XSS injection.
   * @param {*} value - The input value to escape.
   * @returns {string} The HTML-safe string.
   */
  function escapeHtml(value) {
    if (value === null || value === undefined) {
      return "";
    }
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  /**
   * Format a signed 2-decimal sentiment score with tabular-nums and semantic classes.
   * @param {number|string} score - Sentiment polarity score (-1.0 to +1.0).
   * @returns {string} HTML snippet containing formatted sentiment badge.
   */
  function formatSentimentScore(score) {
    var num = typeof score === "number" ? score : parseFloat(score);
    if (isNaN(num)) {
      num = 0.0;
    }
    var sign = num > 0 ? "+" : "";
    var formatted = sign + num.toFixed(2);
    var cls = num >= 0 ? "score-positive" : "score-negative";
    return '<span class="badge badge-score tabular-nums ' + cls + '">Sentiment: ' + formatted + '</span>';
  }

  /**
   * Render the inference model badge distinguishing DGX Spark vs Heuristic fallback.
   * @param {string} modelUsed - Model identifier returned by the backend.
   * @returns {string} HTML badge snippet.
   */
  function renderModelBadge(modelUsed) {
    var raw = String(modelUsed || "");
    if (raw === "heuristic-vader" || raw.indexOf("heuristic") !== -1) {
      return '<span class="badge badge-model-fallback" title="Synthesized via local VADER heuristic fallback">Heuristic VADER Fallback</span>';
    }
    return '<span class="badge badge-model-spark" title="Synthesized via DGX Spark vLLM">' + escapeHtml(raw || "Qwen3.8-Flash-Next-FP4-Local") + '</span>';
  }

  /**
   * Render a taxonomy badge for the source platform.
   * @param {string} sourceType - Platform source type.
   * @returns {string} HTML badge snippet.
   */
  function renderSourceBadge(sourceType) {
    var st = String(sourceType || "").toLowerCase();
    if (st === "hacker_news" || st === "hn") {
      return '<span class="badge badge-hn">Hacker News</span>';
    } else if (st === "reddit") {
      return '<span class="badge badge-reddit">Reddit</span>';
    } else if (st === "github") {
      return '<span class="badge badge-github">GitHub</span>';
    } else if (st === "google_search") {
      return '<span class="badge badge-github">Search</span>';
    } else if (st === "dictionary") {
      return '<span class="badge badge-github">Dictionary</span>';
    } else if (st === "pdf_paper") {
      return '<span class="badge badge-github">PDF Paper</span>';
    } else if (st === "video") {
      return '<span class="badge badge-github">Video</span>';
    }
    return '<span class="badge badge-github">' + escapeHtml(sourceType || "Article") + '</span>';
  }

  /* -------------------------------------------------------------------------
   * Tab 1: Discussions & Analysis Modal
   * ------------------------------------------------------------------------- */

  /**
   * Render loading skeleton placeholders for the discussions container.
   * @param {HTMLElement|null} container - Target container element.
   * @returns {void}
   */
  function renderDiscussionsLoading(container) {
    if (!container) return;
    container.setAttribute("aria-busy", "true");
    container.innerHTML =
      '<div class="skeleton-card">' +
        '<div class="skeleton skeleton-line skeleton-w-60"></div>' +
        '<div class="skeleton skeleton-line skeleton-w-40"></div>' +
        '<div class="skeleton skeleton-line skeleton-w-85"></div>' +
      '</div>' +
      '<div class="skeleton-card">' +
        '<div class="skeleton skeleton-line skeleton-w-50"></div>' +
        '<div class="skeleton skeleton-line skeleton-w-45"></div>' +
        '<div class="skeleton skeleton-line skeleton-w-80"></div>' +
      '</div>';
  }

  /**
   * Render empty state for the discussions container.
   * @param {HTMLElement|null} container - Target container element.
   * @returns {void}
   */
  function renderDiscussionsEmpty(container) {
    if (!container) return;
    container.setAttribute("aria-busy", "false");
    container.innerHTML =
      '<div class="state-empty">' +
        '<p>No discussion highlights found for this date.</p>' +
        '<div class="state-actions">' +
          '<button type="button" class="btn-secondary" onclick="loadCapsuleDigest()">Reload Capsule</button>' +
        '</div>' +
      '</div>';
  }

  /**
   * Render error state for the discussions container.
   * @param {HTMLElement|null} container - Target container element.
   * @param {string} errorMsg - Descriptive error message.
   * @returns {void}
   */
  function renderDiscussionsError(container, errorMsg) {
    if (!container) return;
    container.setAttribute("aria-busy", "false");
    container.innerHTML =
      '<div class="state-error" role="alert">' +
        '<p>Failed to load discussion highlights: ' + escapeHtml(errorMsg) + '</p>' +
        '<div class="state-actions">' +
          '<button type="button" class="btn-secondary btn-retry" onclick="loadCapsuleDigest()">Retry Capsule Load</button>' +
        '</div>' +
      '</div>';
  }

  /**
   * Render HTML card for a single discussion analysis.
   * @param {Object} d - DiscussionAnalysis payload object.
   * @returns {string} HTML markup string.
   */
  function renderDiscussionCardHtml(d) {
    if (!d) return "";
    var titleHtml = escapeHtml(d.title || "Untitled Discussion");
    if (d.url) {
      titleHtml = '<a href="' + escapeHtml(d.url) + '" target="_blank" rel="noopener noreferrer">' + titleHtml + '</a>';
    }

    var sentimentHtml = formatSentimentScore(d.sentiment_score !== undefined ? d.sentiment_score : 0.0);
    var controversyVal = typeof d.controversy_score === "number" ? d.controversy_score.toFixed(2) : "0.00";
    var controversyHtml = '<span class="badge badge-score tabular-nums">Controversy: ' + controversyVal + '</span>';
    var modelBadgeHtml = renderModelBadge(d.model_used);

    var spotlightHtml = "";
    if (d.anchor_comment_spotlight) {
      var anchorIdText = d.anchor_comment_id ? ' <span class="tabular-nums">#' + escapeHtml(d.anchor_comment_id) + '</span>' : "";
      spotlightHtml =
        '<div class="analysis-section">' +
          '<span class="spotlight-label">Anchor Comment Spotlight' + anchorIdText + '</span>' +
          '<div class="spotlight-box">' + escapeHtml(d.anchor_comment_spotlight) + '</div>' +
        '</div>';
    }

    var takeawaysHtml = "";
    if (d.actionable_takeaways && d.actionable_takeaways.length > 0) {
      takeawaysHtml =
        '<div class="analysis-section">' +
          '<span class="analysis-label">Actionable Takeaways</span>' +
          '<ul class="takeaways-list">' +
            d.actionable_takeaways.map(function (item) {
              return "<li>" + escapeHtml(item) + "</li>";
            }).join("") +
          "</ul>" +
        '</div>';
    }

    return (
      '<div class="card card-nested">' +
        '<div class="card-header">' +
          '<div>' +
            '<h3 class="card-title">' + titleHtml + '</h3>' +
          '</div>' +
          '<div class="card-meta">' +
            sentimentHtml +
            controversyHtml +
            modelBadgeHtml +
          '</div>' +
        '</div>' +
        '<div class="analysis-section">' +
          '<span class="analysis-label">Core Thesis</span>' +
          '<div class="analysis-box">' + escapeHtml(d.core_thesis || "No thesis provided.") + '</div>' +
        '</div>' +
        '<div class="analysis-section">' +
          '<span class="analysis-label">Community Consensus</span>' +
          '<div class="analysis-box">' + escapeHtml(d.community_consensus || "No consensus recorded.") + '</div>' +
        '</div>' +
        '<div class="analysis-section">' +
          '<span class="analysis-label">Contrarian Pushback</span>' +
          '<div class="analysis-box">' + escapeHtml(d.contrarian_pushback || "No contrarian pushback recorded.") + '</div>' +
        '</div>' +
        spotlightHtml +
        takeawaysHtml +
      '</div>'
    );
  }

  /**
   * Render list of discussion analysis cards into target container.
   * @param {HTMLElement|null} container - Target container element.
   * @param {Array<Object>} discussions - List of discussion analysis objects.
   * @returns {void}
   */
  function renderDiscussions(container, discussions) {
    if (!container) return;
    container.setAttribute("aria-busy", "false");
    if (!discussions || discussions.length === 0) {
      renderDiscussionsEmpty(container);
      return;
    }
    container.innerHTML = discussions.map(renderDiscussionCardHtml).join("");
  }

  /**
   * Render loading state in the analysis modal.
   * @param {HTMLElement|null} container - Modal body container.
   * @returns {void}
   */
  function renderAnalysisModalLoading(container) {
    if (!container) return;
    container.setAttribute("aria-busy", "true");
    container.innerHTML =
      '<div class="state-loading skeleton-card">' +
        '<p class="card-subtitle">Contacting DGX Spark vLLM engine...</p>' +
        '<div class="skeleton skeleton-line skeleton-w-50"></div>' +
        '<div class="skeleton skeleton-line skeleton-w-80"></div>' +
        '<div class="skeleton skeleton-line skeleton-w-70"></div>' +
        '<div class="skeleton skeleton-well skeleton-well-compact"></div>' +
      '</div>';
  }

  /**
   * Render discussion synthesis result in the analysis modal.
   * @param {HTMLElement|null} container - Modal body container.
   * @param {Object} d - DiscussionAnalysis payload.
   * @returns {void}
   */
  function renderAnalysisModalResult(container, d) {
    if (!container) return;
    container.setAttribute("aria-busy", "false");
    container.innerHTML = renderDiscussionCardHtml(d);
  }

  /**
   * Render error state in the analysis modal.
   * @param {HTMLElement|null} container - Modal body container.
   * @param {string} errorMsg - Error description.
   * @param {string} itemId - Identifier of the item being analyzed.
   * @param {string} itemTitle - Title of the item.
   * @returns {void}
   */
  function renderAnalysisModalError(container, errorMsg, itemId, itemTitle) {
    if (!container) return;
    container.setAttribute("aria-busy", "false");
    container.innerHTML =
      '<div class="state-error" role="alert">' +
        '<p>Synthesis error: ' + escapeHtml(errorMsg) + '</p>' +
        '<div class="state-actions">' +
          '<button type="button" class="btn-secondary btn-retry" data-item-id="' +
          escapeHtml(itemId || "") + '" data-item-title="' + escapeHtml(itemTitle || "") +
          '" onclick="analyzeItem(this.getAttribute(\'data-item-id\'), this.getAttribute(\'data-item-title\'), this)">Retry Synthesis</button>' +
        '</div>' +
      '</div>';
  }

  /* -------------------------------------------------------------------------
   * Tab 1: Markdown Preview
   * ------------------------------------------------------------------------- */

  /**
   * Render loading state for the markdown preview.
   * @param {HTMLElement|null} container - Markdown container element.
   * @returns {void}
   */
  function renderMarkdownLoading(container) {
    if (!container) return;
    container.setAttribute("aria-busy", "true");
    container.innerHTML = '<div class="skeleton skeleton-well"></div>';
  }

  /**
   * Render nominal markdown preview text.
   * @param {HTMLElement|null} container - Markdown container element.
   * @param {string} markdownText - Raw markdown text.
   * @returns {void}
   */
  function renderMarkdownNominal(container, markdownText) {
    if (!container) return;
    container.setAttribute("aria-busy", "false");
    if (!markdownText || String(markdownText).trim() === "") {
      renderMarkdownEmpty(container);
      return;
    }
    container.textContent = String(markdownText);
  }

  /**
   * Render markdown preview (alias for renderMarkdownNominal).
   * @param {HTMLElement|null} container - Markdown container element.
   * @param {string} markdownText - Raw markdown text.
   * @returns {void}
   */
  function renderMarkdownPreview(container, markdownText) {
    renderMarkdownNominal(container, markdownText);
  }

  /**
   * Render empty state for markdown preview.
   * @param {HTMLElement|null} container - Markdown container element.
   * @returns {void}
   */
  function renderMarkdownEmpty(container) {
    if (!container) return;
    container.setAttribute("aria-busy", "false");
    container.innerHTML =
      '<div class="state-empty">' +
        '<p>No markdown digest generated for this capsule date.</p>' +
      '</div>';
  }

  /**
   * Render error state for markdown preview.
   * @param {HTMLElement|null} container - Markdown container element.
   * @param {string} errorMsg - Error description.
   * @returns {void}
   */
  function renderMarkdownError(container, errorMsg) {
    if (!container) return;
    container.setAttribute("aria-busy", "false");
    container.innerHTML =
      '<div class="state-error" role="alert">' +
        '<p>Failed to generate markdown: ' + escapeHtml(errorMsg) + '</p>' +
        '<div class="state-actions">' +
          '<button type="button" class="btn-secondary btn-retry" onclick="loadCapsuleDigest()">Retry</button>' +
        '</div>' +
      '</div>';
  }

  /* -------------------------------------------------------------------------
   * Tab 2: 3-Epoch Reading Vault Table
   * ------------------------------------------------------------------------- */

  /**
   * Render loading skeleton rows for the vault table.
   * @param {HTMLElement|null} tbody - Table body element.
   * @param {HTMLElement|null} [tableEl] - Optional parent table element.
   * @returns {void}
   */
  function renderVaultLoading(tbody, tableEl) {
    if (tableEl) tableEl.setAttribute("aria-busy", "true");
    if (!tbody) return;
    var rows = "";
    for (var i = 0; i < 6; i++) {
      rows += '<tr><td colspan="7"><div class="skeleton skeleton-row skeleton-row-vault"></div></td></tr>';
    }
    tbody.innerHTML = rows;
  }

  /**
   * Render empty state for the vault table.
   * @param {HTMLElement|null} tbody - Table body element.
   * @param {HTMLElement|null} [tableEl] - Optional parent table element.
   * @returns {void}
   */
  function renderVaultEmpty(tbody, tableEl) {
    if (tableEl) tableEl.setAttribute("aria-busy", "false");
    if (!tbody) return;
    tbody.innerHTML =
      '<tr>' +
        '<td colspan="7">' +
          '<div class="state-empty">' +
            '<p>No items found matching the active filters.</p>' +
            '<div class="state-actions">' +
              '<button type="button" class="btn-secondary" onclick="clearVaultFilters()">Clear Active Filters</button>' +
              '<button type="button" class="btn-primary" onclick="openImportModal()">Import Safari Notes</button>' +
            '</div>' +
          '</div>' +
        '</td>' +
      '</tr>';
  }

  /**
   * Render error state for the vault table.
   * @param {HTMLElement|null} tbody - Table body element.
   * @param {HTMLElement|null} tableEl - Parent table element.
   * @param {string} errorMsg - Error description.
   * @returns {void}
   */
  function renderVaultError(tbody, tableEl, errorMsg) {
    if (tableEl) tableEl.setAttribute("aria-busy", "false");
    if (!tbody) return;
    tbody.innerHTML =
      '<tr>' +
        '<td colspan="7">' +
          '<div class="state-error" role="alert">' +
            '<p>Failed to query vault items: ' + escapeHtml(errorMsg) + '</p>' +
            '<div class="state-actions">' +
              '<button type="button" class="btn-secondary btn-retry" onclick="loadVaultItems()">Retry Vault Query</button>' +
            '</div>' +
          '</div>' +
        '</td>' +
      '</tr>';
  }

  /**
   * Render nominal data rows for the vault table.
   * @param {HTMLElement|null} tbody - Table body element.
   * @param {HTMLElement|null} tableEl - Parent table element.
   * @param {Array<Object>} items - Array of SafariLinkItem objects.
   * @returns {void}
   */
  function renderVaultRows(tbody, tableEl, items) {
    if (tableEl) tableEl.setAttribute("aria-busy", "false");
    if (!tbody) return;
    if (!items || items.length === 0) {
      renderVaultEmpty(tbody, tableEl);
      return;
    }

    tbody.innerHTML = items.map(function (item) {
      var titleText = escapeHtml(item.title || item.canonical_url || "Untitled");
      var hrefUrl = item.canonical_url || item.url || "";
      var linkHtml = hrefUrl
        ? '<a href="' + escapeHtml(hrefUrl) + '" target="_blank" rel="noopener noreferrer">' + titleText + '</a>'
        : titleText;

      var subParts = [];
      if (item.domain) {
        subParts.push('<span class="tabular-nums">' + escapeHtml(item.domain) + '</span>');
      }
      if (item.search_query) {
        subParts.push('Query: "' + escapeHtml(item.search_query) + '"');
      }
      var subtitleHtml = subParts.length > 0
        ? '<div class="card-subtitle">' + subParts.join(" | ") + '</div>'
        : "";

      var sourceBadge = renderSourceBadge(item.source_type);
      var rawPillar = item.primary_pillar || (item.pillar_tags && item.pillar_tags[0]) ||
        item.intellectual_pillar || item.pillar || "Unassigned";
      var pillarBadge = '<span class="badge badge-pillar">' + escapeHtml(String(rawPillar).replace("PILLAR_", "")) + '</span>';

      var epochsList = (item.epochs_present && item.epochs_present.length > 0)
        ? item.epochs_present
        : (item.first_epoch ? [item.first_epoch] : []);
      var epochsHtml = '<div class="card-meta">' + epochsList.map(function (ep) {
        return '<span class="badge badge-epoch tabular-nums">' + escapeHtml(ep) + '</span>';
      }).join("") + '</div>';

      var crossCount = item.cross_epoch_count || epochsList.length || 1;
      var occurrences = item.total_occurrences || crossCount;
      var occurrencesCell =
        '<td class="num-col tabular-nums">' +
          String(crossCount) + ' ep / ' + String(occurrences) + 'x' +
        '</td>';

      var statusBadge = item.is_evergreen_canon
        ? '<span class="badge badge-canon">Evergreen Canon</span>'
        : (item.anchor_comment_id
          ? '<span class="badge badge-hn tabular-nums">Anchored #' + escapeHtml(item.anchor_comment_id) + '</span>'
          : '<span class="badge">Archived</span>');

      var actionBtn =
        '<button type="button" class="btn-secondary" data-item-id="' + escapeHtml(item.item_id) +
        '" data-item-title="' + escapeHtml(item.title || item.canonical_url || "") +
        '" onclick="analyzeItem(this.getAttribute(\'data-item-id\'), this.getAttribute(\'data-item-title\'), this)">Analyze via Spark</button>';

      return (
        '<tr>' +
          '<td>' + linkHtml + subtitleHtml + '</td>' +
          '<td>' + sourceBadge + '</td>' +
          '<td>' + pillarBadge + '</td>' +
          '<td>' + epochsHtml + '</td>' +
          occurrencesCell +
          '<td>' + statusBadge + '</td>' +
          '<td>' + actionBtn + '</td>' +
        '</tr>'
      );
    }).join("");
  }

  /* -------------------------------------------------------------------------
   * Tab 3: Personal Time Capsule
   * ------------------------------------------------------------------------- */

  /**
   * Render loading skeleton for taste profile container.
   * @param {HTMLElement|null} container - Target container element.
   * @returns {void}
   */
  function renderTasteProfileLoading(container) {
    if (!container) return;
    container.setAttribute("aria-busy", "true");
    container.innerHTML =
      '<div class="skeleton-card skeleton-card-compact">' +
        '<div class="skeleton skeleton-line skeleton-w-50"></div>' +
        '<div class="skeleton skeleton-well skeleton-well-compact"></div>' +
      '</div>' +
      '<div class="skeleton-card skeleton-card-compact">' +
        '<div class="skeleton skeleton-line skeleton-w-50"></div>' +
        '<div class="skeleton skeleton-well skeleton-well-compact"></div>' +
      '</div>' +
      '<div class="skeleton-card skeleton-card-compact">' +
        '<div class="skeleton skeleton-line skeleton-w-50"></div>' +
        '<div class="skeleton skeleton-well skeleton-well-compact"></div>' +
      '</div>';
  }

  /**
   * Render empty state for taste profile container.
   * @param {HTMLElement|null} container - Target container element.
   * @returns {void}
   */
  function renderTasteProfileEmpty(container) {
    if (!container) return;
    container.setAttribute("aria-busy", "false");
    container.innerHTML =
      '<div class="state-empty grid-span-full">' +
        '<p>No longitudinal taste profile records found.</p>' +
        '<div class="state-actions">' +
          '<button type="button" class="btn-primary" onclick="openImportModal()">Import Safari Notes</button>' +
          '<button type="button" class="btn-secondary" onclick="loadTasteProfile()">Reload Taste Profile</button>' +
        '</div>' +
      '</div>';
  }

  /**
   * Render error state for taste profile container.
   * @param {HTMLElement|null} container - Target container element.
   * @param {string} errorMsg - Error description.
   * @returns {void}
   */
  function renderTasteProfileError(container, errorMsg) {
    if (!container) return;
    container.setAttribute("aria-busy", "false");
    container.innerHTML =
      '<div class="state-error grid-span-full" role="alert">' +
        '<p>Failed to load taste profile: ' + escapeHtml(errorMsg) + '</p>' +
        '<div class="state-actions">' +
          '<button type="button" class="btn-secondary btn-retry" onclick="loadTasteProfile()">Retry</button>' +
        '</div>' +
      '</div>';
  }

  /**
   * Render nominal taste profile distribution cards across the 3 epochs.
   * @param {HTMLElement|null} container - Target container element.
   * @param {Object} summary - Epochs summary payload.
   * @returns {void}
   */
  function renderTasteProfile(container, summary) {
    if (!container) return;
    container.setAttribute("aria-busy", "false");
    if (!summary || !summary.epoch_breakdown) {
      renderTasteProfileEmpty(container);
      return;
    }

    var epochs = Object.keys(summary.epoch_breakdown);
    if (epochs.length === 0) {
      renderTasteProfileEmpty(container);
      return;
    }

    var tasteProfile = summary.taste_profile || {};
    var epochProfiles = (tasteProfile && tasteProfile.epoch_breakdown) || tasteProfile;

    container.innerHTML = epochs.map(function (epoch) {
      var totalItems = summary.epoch_breakdown[epoch] || 0;
      var epochProfile = epochProfiles[epoch] || {};

      var rowsHtml = Object.keys(epochProfile).map(function (pillar) {
        var count = epochProfile[pillar] || 0;
        var pctNum = totalItems > 0 ? Math.min(100, (count / totalItems) * 100) : 0;
        var pct = pctNum.toFixed(1);
        return (
          '<div class="taste-row">' +
            '<div class="taste-row-header">' +
              '<span>' + escapeHtml(String(pillar).replace("PILLAR_", "")) + '</span>' +
              '<span class="tabular-nums">' + String(count) + ' (' + pct + '%)</span>' +
            '</div>' +
            '<div class="taste-bar-track">' +
              '<div class="taste-bar-fill" data-bar-pct="' + pct + '"></div>' +
            '</div>' +
          '</div>'
        );
      }).join("");

      return (
        '<div class="card card-nested">' +
          '<div class="card-header">' +
            '<h3 class="card-title tabular-nums">' + escapeHtml(epoch) + '</h3>' +
            '<span class="badge badge-epoch tabular-nums">' + String(totalItems) + ' items</span>' +
          '</div>' +
          rowsHtml +
        '</div>'
      );
    }).join("");

    container.querySelectorAll(".taste-bar-fill[data-bar-pct]").forEach(function (bar) {
      bar.style.width = String(bar.getAttribute("data-bar-pct") || "0") + "%";
    });
  }

  /**
   * Render loading skeleton for vocabulary table.
   * @param {HTMLElement|null} tbody - Target table body element.
   * @returns {void}
   */
  function renderVocabLoading(tbody, tableEl) {
    if (tableEl) tableEl.setAttribute("aria-busy", "true");
    if (!tbody) return;
    var rows = "";
    for (var i = 0; i < 5; i++) {
      rows += '<tr><td colspan="3"><div class="skeleton skeleton-row"></div></td></tr>';
    }
    tbody.innerHTML = rows;
  }

  /**
   * Render empty state for vocabulary table.
   * @param {HTMLElement|null} tbody - Target table body element.
   * @param {HTMLElement|null} [tableEl] - Optional parent table element.
   * @returns {void}
   */
  function renderVocabEmpty(tbody, tableEl) {
    if (tableEl) tableEl.setAttribute("aria-busy", "false");
    if (!tbody) return;
    tbody.innerHTML =
      '<tr>' +
        '<td colspan="3">' +
          '<div class="state-empty">' +
            '<p>No technical vocabulary entries cataloged.</p>' +
          '</div>' +
        '</td>' +
      '</tr>';
  }

  /**
   * Render error state for vocabulary table.
   * @param {HTMLElement|null} tbody - Target table body element.
   * @param {string} errorMsg - Error description.
   * @param {HTMLElement|null} [tableEl] - Optional parent table element.
   * @returns {void}
   */
  function renderVocabError(tbody, errorMsg, tableEl) {
    if (tableEl) tableEl.setAttribute("aria-busy", "false");
    if (!tbody) return;
    tbody.innerHTML =
      '<tr>' +
        '<td colspan="3">' +
          '<div class="state-error" role="alert">' +
            '<p>Failed to load vocabulary: ' + escapeHtml(errorMsg) + '</p>' +
            '<div class="state-actions">' +
              '<button type="button" class="btn-secondary btn-retry" onclick="loadVocab()">Retry Vocab</button>' +
            '</div>' +
          '</div>' +
        '</td>' +
      '</tr>';
  }

  /**
   * Render nominal vocabulary lexicon rows.
   * @param {HTMLElement|null} tbody - Target table body element.
   * @param {Array<Object>} entries - VocabularyEntry objects.
   * @param {HTMLElement|null} [tableEl] - Optional parent table element.
   * @returns {void}
   */
  function renderVocabRows(tbody, entries, tableEl) {
    if (tableEl) tableEl.setAttribute("aria-busy", "false");
    if (!tbody) return;
    if (!entries || entries.length === 0) {
      renderVocabEmpty(tbody, tableEl);
      return;
    }
    tbody.innerHTML = entries.map(function (e) {
      var hint = e.definition_hint || e.context_hint || "Technical vocabulary term";
      var epoch = e.epoch_first_seen || e.epoch || "2026_11_06";
      return (
        '<tr>' +
          '<td><code>' + escapeHtml(e.term) + '</code></td>' +
          '<td>' + escapeHtml(hint) + '</td>' +
          '<td><span class="badge badge-epoch tabular-nums">' + escapeHtml(epoch) + '</span></td>' +
        '</tr>'
      );
    }).join("");
  }

  /**
   * Render loading skeleton for search intents table.
   * @param {HTMLElement|null} tbody - Target table body element.
   * @param {HTMLElement|null} [tableEl] - Optional parent table element.
   * @returns {void}
   */
  function renderIntentsLoading(tbody, tableEl) {
    if (tableEl) tableEl.setAttribute("aria-busy", "true");
    if (!tbody) return;
    var rows = "";
    for (var i = 0; i < 5; i++) {
      rows += '<tr><td colspan="3"><div class="skeleton skeleton-row"></div></td></tr>';
    }
    tbody.innerHTML = rows;
  }

  /**
   * Render empty state for search intents table.
   * @param {HTMLElement|null} tbody - Target table body element.
   * @param {HTMLElement|null} [tableEl] - Optional parent table element.
   * @returns {void}
   */
  function renderIntentsEmpty(tbody, tableEl) {
    if (tableEl) tableEl.setAttribute("aria-busy", "false");
    if (!tbody) return;
    tbody.innerHTML =
      '<tr>' +
        '<td colspan="3">' +
          '<div class="state-empty">' +
            '<p>No search query intents found for this category.</p>' +
            '<div class="state-actions">' +
              '<button type="button" class="btn-secondary" onclick="resetIntentCategory()">Reset Category</button>' +
            '</div>' +
          '</div>' +
        '</td>' +
      '</tr>';
  }

  /**
   * Render error state for search intents table.
   * @param {HTMLElement|null} tbody - Target table body element.
   * @param {string} errorMsg - Error description.
   * @param {HTMLElement|null} [tableEl] - Optional parent table element.
   * @returns {void}
   */
  function renderIntentsError(tbody, errorMsg, tableEl) {
    if (tableEl) tableEl.setAttribute("aria-busy", "false");
    if (!tbody) return;
    tbody.innerHTML =
      '<tr>' +
        '<td colspan="3">' +
          '<div class="state-error" role="alert">' +
            '<p>Failed to load intents: ' + escapeHtml(errorMsg) + '</p>' +
            '<div class="state-actions">' +
              '<button type="button" class="btn-secondary btn-retry" onclick="loadIntents()">Retry Intents</button>' +
            '</div>' +
          '</div>' +
        '</td>' +
      '</tr>';
  }

  /**
   * Render nominal search query intent rows.
   * @param {HTMLElement|null} tbody - Target table body element.
   * @param {Array<Object>} intents - SearchQueryIntent objects.
   * @param {HTMLElement|null} [tableEl] - Optional parent table element.
   * @returns {void}
   */
  function renderIntentsRows(tbody, intents, tableEl) {
    if (tableEl) tableEl.setAttribute("aria-busy", "false");
    if (!tbody) return;
    if (!intents || intents.length === 0) {
      renderIntentsEmpty(tbody, tableEl);
      return;
    }
    tbody.innerHTML = intents.map(function (i) {
      var catClass = i.category === "technical_learning" ? "badge-pillar" : "badge-epoch";
      var epoch = i.epoch_first_seen || i.epoch || "2026_11_06";
      return (
        '<tr>' +
          '<td>' + escapeHtml(i.query_text) + '</td>' +
          '<td><span class="badge ' + catClass + '">' + escapeHtml(i.category) + '</span></td>' +
          '<td><span class="badge badge-epoch tabular-nums">' + escapeHtml(epoch) + '</span></td>' +
        '</tr>'
      );
    }).join("");
  }

  /* -------------------------------------------------------------------------
   * Tab 4: Macro Time Machine
   * ------------------------------------------------------------------------- */

  /**
   * Render loading skeleton for weather table.
   * @param {HTMLElement|null} weatherBody - Target table body element.
   * @param {HTMLElement|null} [tableEl] - Optional parent table element.
   * @returns {void}
   */
  function renderWeatherLoading(weatherBody, tableEl) {
    if (tableEl) tableEl.setAttribute("aria-busy", "true");
    if (!weatherBody) return;
    var rows = "";
    for (var i = 0; i < 5; i++) {
      rows += '<tr><td colspan="5"><div class="skeleton skeleton-row"></div></td></tr>';
    }
    weatherBody.innerHTML = rows;
  }

  /**
   * Render empty state for weather table.
   * @param {HTMLElement|null} weatherBody - Target table body element.
   * @param {HTMLElement|null} [tableEl] - Optional parent table element.
   * @returns {void}
   */
  function renderWeatherEmpty(weatherBody, tableEl) {
    if (tableEl) tableEl.setAttribute("aria-busy", "false");
    if (!weatherBody) return;
    weatherBody.innerHTML =
      '<tr>' +
        '<td colspan="5">' +
          '<div class="state-empty">' +
            '<p>No weather telemetry recorded for this capsule date.</p>' +
          '</div>' +
        '</td>' +
      '</tr>';
  }

  /**
   * Render error state for weather table.
   * @param {HTMLElement|null} weatherBody - Target table body element.
   * @param {string} errorMsg - Error description.
   * @param {HTMLElement|null} [tableEl] - Optional parent table element.
   * @returns {void}
   */
  function renderWeatherError(weatherBody, errorMsg, tableEl) {
    if (tableEl) tableEl.setAttribute("aria-busy", "false");
    if (!weatherBody) return;
    weatherBody.innerHTML =
      '<tr>' +
        '<td colspan="5">' +
          '<div class="state-error" role="alert">' +
            '<p>Weather telemetry error: ' + escapeHtml(errorMsg) + '</p>' +
            '<div class="state-actions">' +
              '<button type="button" class="btn-secondary btn-retry" onclick="loadMacro()">Retry</button>' +
            '</div>' +
          '</div>' +
        '</td>' +
      '</tr>';
  }

  /**
   * Render nominal rows for weather table.
   * @param {HTMLElement|null} weatherBody - Target table body element.
   * @param {Array<Object>} weather - Array of weather records.
   * @param {HTMLElement|null} [tableEl] - Optional parent table element.
   * @returns {void}
   */
  function renderWeatherRows(weatherBody, weather, tableEl) {
    if (tableEl) tableEl.setAttribute("aria-busy", "false");
    if (!weatherBody) return;
    if (!weather || weather.length === 0) {
      renderWeatherEmpty(weatherBody, tableEl);
      return;
    }
    weatherBody.innerHTML = weather.map(function (w) {
      var city = escapeHtml(w.city || "N/A");
      var cond = escapeHtml(w.weather_main || w.weather_description || "Clear");
      var temp = w.temp !== undefined ? String(w.temp) + "&deg;C" : "N/A";
      var hum = w.humidity !== undefined ? String(w.humidity) + "%" : "N/A";
      var pres = w.pressure !== undefined ? String(w.pressure) + " hPa" : "N/A";
      return (
        '<tr>' +
          '<td>' + city + '</td>' +
          '<td>' + cond + '</td>' +
          '<td class="num-col tabular-nums">' + temp + '</td>' +
          '<td class="num-col tabular-nums">' + hum + '</td>' +
          '<td class="num-col tabular-nums">' + pres + '</td>' +
        '</tr>'
      );
    }).join("");
  }

  /**
   * Render loading skeleton for stocks table.
   * @param {HTMLElement|null} stocksBody - Target table body element.
   * @param {HTMLElement|null} [tableEl] - Optional parent table element.
   * @returns {void}
   */
  function renderStocksLoading(stocksBody, tableEl) {
    if (tableEl) tableEl.setAttribute("aria-busy", "true");
    if (!stocksBody) return;
    var rows = "";
    for (var i = 0; i < 5; i++) {
      rows += '<tr><td colspan="6"><div class="skeleton skeleton-row"></div></td></tr>';
    }
    stocksBody.innerHTML = rows;
  }

  /**
   * Render empty state for stocks table.
   * @param {HTMLElement|null} stocksBody - Target table body element.
   * @param {HTMLElement|null} [tableEl] - Optional parent table element.
   * @returns {void}
   */
  function renderStocksEmpty(stocksBody, tableEl) {
    if (tableEl) tableEl.setAttribute("aria-busy", "false");
    if (!stocksBody) return;
    stocksBody.innerHTML =
      '<tr>' +
        '<td colspan="6">' +
          '<div class="state-empty">' +
            '<p>No equity market records found for this capsule date.</p>' +
          '</div>' +
        '</td>' +
      '</tr>';
  }

  /**
   * Render error state for stocks table.
   * @param {HTMLElement|null} stocksBody - Target table body element.
   * @param {string} errorMsg - Error description.
   * @param {HTMLElement|null} [tableEl] - Optional parent table element.
   * @returns {void}
   */
  function renderStocksError(stocksBody, errorMsg, tableEl) {
    if (tableEl) tableEl.setAttribute("aria-busy", "false");
    if (!stocksBody) return;
    stocksBody.innerHTML =
      '<tr>' +
        '<td colspan="6">' +
          '<div class="state-error" role="alert">' +
            '<p>Stock market error: ' + escapeHtml(errorMsg) + '</p>' +
            '<div class="state-actions">' +
              '<button type="button" class="btn-secondary btn-retry" onclick="loadMacro()">Retry</button>' +
            '</div>' +
          '</div>' +
        '</td>' +
      '</tr>';
  }

  /**
   * Render nominal rows for stocks table.
   * @param {HTMLElement|null} stocksBody - Target table body element.
   * @param {Array<Object>} stocks - Array of stock records.
   * @param {HTMLElement|null} [tableEl] - Optional parent table element.
   * @returns {void}
   */
  function renderStockRows(stocksBody, stocks, tableEl) {
    if (tableEl) tableEl.setAttribute("aria-busy", "false");
    if (!stocksBody) return;
    if (!stocks || stocks.length === 0) {
      renderStocksEmpty(stocksBody, tableEl);
      return;
    }
    stocksBody.innerHTML = stocks.map(function (s) {
      var ticker = escapeHtml(s.ticker || "N/A");
      var close = s.close !== undefined ? "$" + Number(s.close).toFixed(2) : "N/A";
      var open = s.open !== undefined ? "$" + Number(s.open).toFixed(2) : "N/A";
      var high = s.high !== undefined ? "$" + Number(s.high).toFixed(2) : "N/A";
      var low = s.low !== undefined ? "$" + Number(s.low).toFixed(2) : "N/A";
      var volume = s.volume !== undefined ? Number(s.volume).toLocaleString() : "N/A";
      return (
        '<tr>' +
          '<td><span class="badge badge-github tabular-nums">' + ticker + '</span></td>' +
          '<td class="num-col tabular-nums">' + close + '</td>' +
          '<td class="num-col tabular-nums">' + open + '</td>' +
          '<td class="num-col tabular-nums">' + high + '</td>' +
          '<td class="num-col tabular-nums">' + low + '</td>' +
          '<td class="num-col tabular-nums">' + volume + '</td>' +
        '</tr>'
      );
    }).join("");
  }

  /**
   * Render unified error state for macro telemetry.
   * @param {HTMLElement|null} weatherBody - Weather table body.
   * @param {HTMLElement|null} stocksBody - Stocks table body.
   * @param {string} errorMsg - Error description.
   * @param {HTMLElement|null} [weatherTableEl] - Optional weather table element.
   * @param {HTMLElement|null} [stocksTableEl] - Optional stocks table element.
   * @returns {void}
   */
  function renderMacroError(weatherBody, stocksBody, errorMsg, weatherTableEl, stocksTableEl) {
    renderWeatherError(weatherBody, errorMsg, weatherTableEl);
    renderStocksError(stocksBody, errorMsg, stocksTableEl);
  }

  /* -------------------------------------------------------------------------
   * Export to Global Namespace
   * ------------------------------------------------------------------------- */
  var TimeCapsuleViews = {
    escapeHtml: escapeHtml,
    formatSentimentScore: formatSentimentScore,
    renderModelBadge: renderModelBadge,
    renderSourceBadge: renderSourceBadge,

    renderDiscussionsLoading: renderDiscussionsLoading,
    renderDiscussionsEmpty: renderDiscussionsEmpty,
    renderDiscussionsError: renderDiscussionsError,
    renderDiscussionCardHtml: renderDiscussionCardHtml,
    renderDiscussions: renderDiscussions,

    renderAnalysisModalLoading: renderAnalysisModalLoading,
    renderAnalysisModalResult: renderAnalysisModalResult,
    renderAnalysisModalError: renderAnalysisModalError,

    renderMarkdownLoading: renderMarkdownLoading,
    renderMarkdownNominal: renderMarkdownNominal,
    renderMarkdownPreview: renderMarkdownPreview,
    renderMarkdownEmpty: renderMarkdownEmpty,
    renderMarkdownError: renderMarkdownError,

    renderVaultLoading: renderVaultLoading,
    renderVaultEmpty: renderVaultEmpty,
    renderVaultError: renderVaultError,
    renderVaultRows: renderVaultRows,

    renderTasteProfileLoading: renderTasteProfileLoading,
    renderTasteProfileEmpty: renderTasteProfileEmpty,
    renderTasteProfileError: renderTasteProfileError,
    renderTasteProfile: renderTasteProfile,

    renderVocabLoading: renderVocabLoading,
    renderVocabEmpty: renderVocabEmpty,
    renderVocabError: renderVocabError,
    renderVocabRows: renderVocabRows,

    renderIntentsLoading: renderIntentsLoading,
    renderIntentsEmpty: renderIntentsEmpty,
    renderIntentsError: renderIntentsError,
    renderIntentsRows: renderIntentsRows,

    renderWeatherLoading: renderWeatherLoading,
    renderWeatherEmpty: renderWeatherEmpty,
    renderWeatherError: renderWeatherError,
    renderWeatherRows: renderWeatherRows,

    renderStocksLoading: renderStocksLoading,
    renderStocksEmpty: renderStocksEmpty,
    renderStocksError: renderStocksError,
    renderStockRows: renderStockRows,
    renderMacroError: renderMacroError
  };

  window.TimeCapsuleViews = TimeCapsuleViews;
})();
