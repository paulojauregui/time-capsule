"""FastAPI service and interactive web dashboard for Digital Time Capsule.

Pre-conditions:
    - FastAPI and uvicorn must be installed.
    - duckdb and time_capsule library modules must be available.

Post-conditions:
    - Exposes RESTful endpoints for multi-epoch vaults, discussions, and time capsule digests.
    - Serves high-density single-page web dashboard for desktop and mobile exploration.
"""

import os
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from time_capsule.cultural_assets import CulturalExtractor
from time_capsule.enrichment import SparkDiscussionAnalyzer
from time_capsule.financial_assets import get_fallback_stock_records
from time_capsule.models import (
    DailyCapsuleSnapshot,
    SafariLinkItem,
    SourceType,
)
from time_capsule.news_assets import HNClient
from time_capsule.repository import TimeCapsuleRepository
from time_capsule.safari_parser import merge_vault_items, parse_safari_reading_list
from time_capsule.weather_assets import get_fallback_weather_records
from time_capsule.workflows import render_capsule_markdown, seed_database_from_seeds

__all__ = ["AnalyzeRequest", "VaultImportRequest", "app", "create_app"]


class VaultImportRequest(BaseModel):
    """Payload for importing raw Safari Reading List markdown text into the lakehouse.

    Pre-conditions:
        - text must contain newline-separated reading list items or markdown links.
        - epoch_id must be a non-empty epoch identifier.

    Post-conditions:
        - Parsed and merged into DuckDB vault Lakehouse.
    """

    text: str = Field(description="Raw markdown links or pasted Safari reading list lines.")
    epoch_id: str = Field(
        default="2026_11_06",
        description="Target epoch identifier, e.g. 2023_2024, 2026_08_16, or 2026_11_06.",
    )


class AnalyzeRequest(BaseModel):
    """Configuration payload for triggering on-demand discussion synthesis.

    Pre-conditions:
        - None.

    Post-conditions:
        - Specifies whether LLM inference and external network hydration are permitted.
    """

    allow_llm: bool = Field(
        default=True,
        description="Allow DGX Spark vLLM inference if online; falls back to heuristic if false or offline.",
    )
    allow_external_hydration: bool = Field(
        default=False,
        description="Allow live network calls to Hacker News Algolia / Reddit APIs.",
    )


INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Digital Time Capsule & Autonomous Reading Vault</title>
  <style>
    :root {
      --bg: #0b0f19;
      --card-bg: #111827;
      --card-border: #1f293d;
      --text-main: #f3f4f6;
      --text-muted: #9ca3af;
      --accent: #3b82f6;
      --accent-hover: #2563eb;
      --accent-green: #10b981;
      --accent-amber: #f59e0b;
      --accent-purple: #8b5cf6;
      --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
      --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg);
      color: var(--text-main);
      font-family: var(--font-sans);
      line-height: 1.5;
      padding: 1.5rem;
    }
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 1.25rem;
      border-bottom: 1px solid var(--card-border);
      margin-bottom: 1.5rem;
      flex-wrap: wrap;
      gap: 1rem;
    }
    .header-titles h1 { font-size: 1.5rem; font-weight: 700; color: #fff; letter-spacing: -0.025em; }
    .header-titles p { font-size: 0.875rem; color: var(--text-muted); }
    .status-pills { display: flex; gap: 0.5rem; flex-wrap: wrap; font-size: 0.75rem; font-family: var(--font-mono); }
    .pill {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      padding: 0.25rem 0.6rem;
      border-radius: 9999px;
      color: var(--text-muted);
    }
    .pill-green { border-color: rgba(16, 185, 129, 0.4); color: #34d399; }
    .pill-blue { border-color: rgba(59, 130, 246, 0.4); color: #60a5fa; }
    .pill-amber { border-color: rgba(245, 158, 11, 0.4); color: #fbbf24; }

    nav.tab-bar {
      display: flex;
      gap: 0.5rem;
      border-bottom: 1px solid var(--card-border);
      margin-bottom: 1.5rem;
    }
    .tab-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      padding: 0.75rem 1.25rem;
      font-size: 0.9375rem;
      font-weight: 600;
      cursor: pointer;
      border-bottom: 2px solid transparent;
      transition: all 0.15s ease-in-out;
    }
    .tab-btn:hover { color: var(--text-main); }
    .tab-btn.active {
      color: #60a5fa;
      border-bottom-color: #3b82f6;
    }

    .tab-content { display: none; }
    .tab-content.active { display: block; }

    .control-panel {
      display: flex;
      gap: 0.75rem;
      flex-wrap: wrap;
      align-items: center;
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 0.5rem;
      padding: 0.75rem 1rem;
      margin-bottom: 1.5rem;
    }
    .control-panel input, .control-panel select, .control-panel button {
      background: #0f172a;
      border: 1px solid var(--card-border);
      color: var(--text-main);
      padding: 0.5rem 0.75rem;
      border-radius: 0.375rem;
      font-size: 0.875rem;
    }
    .control-panel input:focus, .control-panel select:focus {
      outline: none;
      border-color: var(--accent);
    }
    .btn-primary {
      background: var(--accent) !important;
      color: #fff !important;
      border: none !important;
      cursor: pointer;
      font-weight: 600;
    }
    .btn-primary:hover { background: var(--accent-hover) !important; }
    .btn-secondary {
      background: #1e293b !important;
      color: var(--text-main) !important;
      cursor: pointer;
    }
    .btn-secondary:hover { background: #334155 !important; }

    .grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 1.25rem; margin-bottom: 1.5rem; }
    .grid-3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.25rem; margin-bottom: 1.5rem; }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 0.5rem;
      padding: 1.25rem;
      transition: border-color 0.15s ease-in-out;
    }
    .card:hover { border-color: rgba(59, 130, 246, 0.4); }
    .card-title { font-size: 1.05rem; font-weight: 600; margin-bottom: 0.5rem; color: #fff; }
    .card-title a { color: #60a5fa; text-decoration: none; }
    .card-title a:hover { text-decoration: underline; }
    .card-meta { font-size: 0.75rem; color: var(--text-muted); font-family: var(--font-mono); margin-bottom: 0.75rem; display: flex; gap: 0.5rem; flex-wrap: wrap; }
    .badge {
      display: inline-block;
      padding: 0.15rem 0.45rem;
      border-radius: 0.25rem;
      font-size: 0.7rem;
      font-weight: 600;
      text-transform: uppercase;
      font-family: var(--font-mono);
    }
    .badge-canon { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
    .badge-hn { background: rgba(255, 102, 0, 0.15); color: #ff7700; border: 1px solid rgba(255, 102, 0, 0.3); }
    .badge-pillar { background: rgba(59, 130, 246, 0.15); color: #93c5fd; border: 1px solid rgba(59, 130, 246, 0.3); }
    .badge-epoch { background: rgba(139, 92, 246, 0.15); color: #c4b5fd; border: 1px solid rgba(139, 92, 246, 0.3); }

    .analysis-section { margin-top: 0.5rem; font-size: 0.875rem; }
    .analysis-label { font-weight: 600; color: #93c5fd; font-size: 0.75rem; text-transform: uppercase; margin-top: 0.5rem; }
    .analysis-box { background: #0b0f19; border: 1px solid var(--card-border); border-radius: 0.375rem; padding: 0.5rem 0.75rem; margin-top: 0.25rem; font-size: 0.8125rem; }
    .spotlight-box { border-left: 3px solid #f59e0b; background: rgba(245, 158, 11, 0.05); }

    table.data-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.875rem;
      background: var(--card-bg);
      border-radius: 0.5rem;
      overflow: hidden;
      border: 1px solid var(--card-border);
    }
    table.data-table th, table.data-table td {
      padding: 0.75rem 1rem;
      text-align: left;
      border-bottom: 1px solid var(--card-border);
    }
    table.data-table th {
      background: #0f172a;
      font-weight: 600;
      color: var(--text-muted);
      font-size: 0.75rem;
      text-transform: uppercase;
      font-family: var(--font-mono);
    }
    table.data-table tr:hover { background: #131c31; }
    table.data-table a { color: #60a5fa; text-decoration: none; }
    table.data-table a:hover { text-decoration: underline; }

    .modal {
      display: none;
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0, 0, 0, 0.8);
      z-index: 100;
      align-items: center;
      justify-content: center;
    }
    .modal.active { display: flex; }
    .modal-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 0.5rem;
      width: 90%;
      max-width: 640px;
      max-height: 85vh;
      overflow-y: auto;
      padding: 1.5rem;
    }
    .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
    .modal-header h3 { font-size: 1.15rem; color: #fff; }
    .modal-close { background: none; border: none; color: var(--text-muted); font-size: 1.25rem; cursor: pointer; }
    .modal-body textarea {
      width: 100%;
      height: 200px;
      background: #0b0f19;
      border: 1px solid var(--card-border);
      border-radius: 0.375rem;
      color: var(--text-main);
      padding: 0.75rem;
      font-family: var(--font-mono);
      font-size: 0.8125rem;
      margin-bottom: 1rem;
    }

    .markdown-preview {
      background: #090d16;
      border: 1px solid var(--card-border);
      border-radius: 0.5rem;
      padding: 1.25rem;
      font-family: var(--font-mono);
      font-size: 0.8125rem;
      white-space: pre-wrap;
      max-height: 400px;
      overflow-y: auto;
      color: #e2e8f0;
      margin-top: 1rem;
    }
  </style>
</head>
<body>

  <header>
    <div class="header-titles">
      <h1>Digital Time Capsule & Autonomous Reading Vault</h1>
      <p>Longitudinal 3-Epoch Knowledge Lakehouse & DGX Spark Discussion Synthesis</p>
    </div>
    <div class="status-pills">
      <span class="pill pill-green" id="service-status">Service: Checking...</span>
      <span class="pill pill-blue" id="vault-count-pill">Vault: Loading...</span>
      <span class="pill pill-amber" id="evergreen-count-pill">Evergreen Canon: 14 items</span>
      <span class="pill">Model: Qwen3.8-Flash-Next-FP4-Local</span>
    </div>
  </header>

  <nav class="tab-bar">
    <button class="tab-btn active" onclick="switchTab('digest')">Daily Tech Digest</button>
    <button class="tab-btn" onclick="switchTab('vault')">3-Epoch Reading Vault & Evergreen Canon</button>
    <button class="tab-btn" onclick="switchTab('capsule')">Personal Time Capsule</button>
    <button class="tab-btn" onclick="switchTab('macro')">Macro Time Machine</button>
  </nav>

  <!-- TAB 1: DAILY TECH DIGEST -->
  <section id="tab-digest" class="tab-content active">
    <div class="control-panel">
      <label for="capsule-date-input" style="font-size:0.875rem; color:var(--text-muted);">Capsule Date:</label>
      <input type="text" id="capsule-date-input" value="2026-11-06" style="width:130px;">
      <button class="btn-primary" onclick="loadCapsuleDigest()">Load Capsule</button>
      <button class="btn-secondary" onclick="copyMarkdownDigest()">Copy Markdown Digest</button>
      <span id="copy-status" style="font-size:0.8125rem; color:#34d399;"></span>
    </div>

    <div class="card" style="margin-bottom:1.5rem;">
      <div class="card-title">Executive Discussion Highlights</div>
      <div id="discussions-container" class="grid-2" style="margin-top:1rem;">
        <div style="color:var(--text-muted); font-size:0.875rem;">Loading discussion analyses...</div>
      </div>
    </div>

    <div class="card">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div class="card-title">Publication Digest (paulojauregui.com Markdown)</div>
        <button class="btn-secondary" style="font-size:0.75rem;" onclick="copyMarkdownDigest()">Copy Digest</button>
      </div>
      <div id="markdown-preview" class="markdown-preview">Loading markdown preview...</div>
    </div>
  </section>

  <!-- TAB 2: 3-EPOCH READING VAULT -->
  <section id="tab-vault" class="tab-content">
    <div class="control-panel">
      <select id="vault-epoch-select" onchange="loadVaultItems()">
        <option value="">All Epochs</option>
        <option value="2023_2024">2023-2024 Genesis Epoch</option>
        <option value="2026_08_16">2026-08-16 Summer Bridge Epoch</option>
        <option value="2026_11_06">2026-11-06 Production Epoch</option>
      </select>

      <select id="vault-evergreen-select" onchange="loadVaultItems()">
        <option value="">All Items</option>
        <option value="true">Evergreen Canon Only (14 Items)</option>
      </select>

      <select id="vault-pillar-select" onchange="loadVaultItems()">
        <option value="">All Intellectual Pillars</option>
        <option value="PILLAR_1_AI_LLM_AGENTS">AI, LLMs & Agents</option>
        <option value="PILLAR_2_SYSTEMS_KERNEL">Systems & Kernel</option>
        <option value="PILLAR_3_INFRA_K8S_HOMELAB">Infra, K8s & Homelab</option>
        <option value="PILLAR_4_MATH_ML_THEORY">Math & ML Theory</option>
        <option value="PILLAR_5_SWE_CRAFT_CAREER">SWE Craft & Career</option>
        <option value="PILLAR_6_HUMANITIES_LIFE">Humanities & Life</option>
      </select>

      <select id="vault-source-select" onchange="loadVaultItems()">
        <option value="">All Sources</option>
        <option value="hacker_news">Hacker News</option>
        <option value="reddit">Reddit</option>
        <option value="github">GitHub</option>
        <option value="google_search">Google Search</option>
        <option value="dictionary">Dictionary</option>
      </select>

      <input type="text" id="vault-search-input" placeholder="Search title, URL, query..." oninput="debounce(loadVaultItems, 300)()" style="flex:1; min-width:180px;">

      <button class="btn-primary" onclick="openImportModal()">Import Safari Notes</button>
    </div>

    <div style="margin-bottom:0.75rem; font-size:0.8125rem; color:var(--text-muted); font-family:var(--font-mono);" id="vault-results-count">
      Showing items...
    </div>

    <div style="overflow-x:auto;">
      <table class="data-table" id="vault-table">
        <thead>
          <tr>
            <th>Title & URL</th>
            <th>Domain</th>
            <th>Source</th>
            <th>Epochs Present</th>
            <th>Cross-Epoch / Occurrences</th>
            <th>Primary Pillar</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody id="vault-table-body">
          <tr><td colspan="7" style="text-align:center; color:var(--text-muted);">Loading vault items...</td></tr>
        </tbody>
      </table>
    </div>
  </section>

  <!-- TAB 3: PERSONAL TIME CAPSULE -->
  <section id="tab-capsule" class="tab-content">
    <div class="card" style="margin-bottom:1.5rem;">
      <div class="card-title">Longitudinal Intellectual Taste Evolution (3 Epochs)</div>
      <p style="font-size:0.8125rem; color:var(--text-muted); margin-bottom:1rem;">Distribution of active inquiry across the 6 Intellectual Pillars across 2023-2024, August 2026, and November 2026.</p>
      <div id="taste-profile-container" class="grid-3">
        <div style="color:var(--text-muted); font-size:0.875rem;">Loading taste profile...</div>
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
          <div class="card-title">Personal Vocabulary Lexicon</div>
          <span class="badge badge-epoch" id="vocab-count-badge">0 terms</span>
        </div>
        <div style="overflow-x:auto; max-height:480px; overflow-y:auto;">
          <table class="data-table" id="vocab-table">
            <thead>
              <tr>
                <th>Term</th>
                <th>Definition Hint</th>
                <th>First Seen</th>
              </tr>
            </thead>
            <tbody id="vocab-table-body">
              <tr><td colspan="3" style="color:var(--text-muted); text-align:center;">Loading vocabulary...</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
          <div class="card-title">Learning Intents & Technical Queries</div>
          <select id="intent-category-select" onchange="loadIntents()" style="background:#0f172a; border:1px solid var(--card-border); color:var(--text-main); padding:0.25rem 0.5rem; border-radius:0.25rem; font-size:0.75rem;">
            <option value="">All Categories</option>
            <option value="technical_learning">Technical Learning</option>
            <option value="vocabulary">Vocabulary Lookup</option>
            <option value="personal_life">Personal Life</option>
          </select>
        </div>
        <div style="overflow-x:auto; max-height:480px; overflow-y:auto;">
          <table class="data-table" id="intents-table">
            <thead>
              <tr>
                <th>Query Intent</th>
                <th>Category</th>
                <th>First Seen</th>
              </tr>
            </thead>
            <tbody id="intents-table-body">
              <tr><td colspan="3" style="color:var(--text-muted); text-align:center;">Loading intents...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </section>

  <!-- TAB 4: MACRO TIME MACHINE -->
  <section id="tab-macro" class="tab-content">
    <div class="card" style="margin-bottom:1.5rem;">
      <div class="card-title">Global Weather Snapshot (Tokyo, New York, London, Beijing, Sydney)</div>
      <p style="font-size:0.8125rem; color:var(--text-muted); margin-bottom:1rem;">Surface meteorological state captured at daily capsule generation.</p>
      <table class="data-table" id="weather-table">
        <thead>
          <tr>
            <th>City</th>
            <th>Temperature (°C)</th>
            <th>Conditions</th>
            <th>Humidity (%)</th>
            <th>Pressure (hPa)</th>
          </tr>
        </thead>
        <tbody id="weather-table-body">
          <tr><td colspan="5" style="color:var(--text-muted); text-align:center;">Loading weather telemetry...</td></tr>
        </tbody>
      </table>
    </div>

    <div class="card">
      <div class="card-title">Global Equities Benchmark (Alpha Vantage Daily OHLCV)</div>
      <p style="font-size:0.8125rem; color:var(--text-muted); margin-bottom:1rem;">Market equity telemetry for foundational infrastructure & technology assets.</p>
      <table class="data-table" id="stocks-table">
        <thead>
          <tr>
            <th>Ticker</th>
            <th>Close ($)</th>
            <th>Open ($)</th>
            <th>High ($)</th>
            <th>Low ($)</th>
            <th>Volume</th>
          </tr>
        </thead>
        <tbody id="stocks-table-body">
          <tr><td colspan="6" style="color:var(--text-muted); text-align:center;">Loading equities telemetry...</td></tr>
        </tbody>
      </table>
    </div>
  </section>

  <!-- IMPORT MODAL -->
  <div class="modal" id="import-modal">
    <div class="modal-card">
      <div class="modal-header">
        <h3>Import Safari Reading List Lines</h3>
        <button class="modal-close" onclick="closeImportModal()">&times;</button>
      </div>
      <p style="font-size:0.8125rem; color:var(--text-muted); margin-bottom:0.75rem;">
        Paste raw lines copied from Safari Reading List (URLs or Markdown links) into the target epoch.
      </p>
      <label style="font-size:0.75rem; color:var(--text-muted); display:block; margin-bottom:0.25rem;">Target Epoch:</label>
      <select id="import-epoch-select" style="background:#0f172a; border:1px solid var(--card-border); color:var(--text-main); padding:0.5rem; border-radius:0.375rem; width:100%; margin-bottom:0.75rem;">
        <option value="2026_11_06">2026_11_06 (Production Epoch)</option>
        <option value="2026_08_16">2026_08_16 (Summer Bridge Epoch)</option>
        <option value="2023_2024">2023_2024 (Genesis Epoch)</option>
      </select>
      <textarea id="import-text" placeholder="https://news.ycombinator.com/item?id=...\n[Article Title](https://example.com)"></textarea>
      <div style="display:flex; justify-content:flex-end; gap:0.5rem;">
        <button class="btn-secondary" onclick="closeImportModal()">Cancel</button>
        <button class="btn-primary" onclick="submitImport()">Import Items</button>
      </div>
    </div>
  </div>

  <!-- ANALYSIS MODAL -->
  <div class="modal" id="analysis-modal">
    <div class="modal-card">
      <div class="modal-header">
        <h3 id="analysis-modal-title">Discussion Synthesis</h3>
        <button class="modal-close" onclick="closeAnalysisModal()">&times;</button>
      </div>
      <div id="analysis-modal-body">
        <div style="color:var(--text-muted);">Synthesizing...</div>
      </div>
    </div>
  </div>

  <script>
    let currentDigestMarkdown = "";
    let debounceTimer = null;

    function debounce(func, delay) {
      return function(...args) {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => func.apply(this, args), delay);
      };
    }

    function switchTab(tabName) {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
      event.target.classList.add("active");
      document.getElementById("tab-" + tabName).classList.add("active");
      if (tabName === "vault") loadVaultItems();
      if (tabName === "capsule") { loadTasteProfile(); loadVocab(); loadIntents(); }
      if (tabName === "macro") loadMacro();
    }

    async function initDashboard() {
      try {
        const hRes = await fetch("/healthz");
        const hData = await hRes.json();
        document.getElementById("service-status").innerText = "Service: " + hData.status;

        const rRes = await fetch("/ready");
        const rData = await rRes.json();
        document.getElementById("vault-count-pill").innerText = "Vault: " + rData.vault_count + " items";
        document.getElementById("evergreen-count-pill").innerText = "Evergreen Canon: " + rData.evergreen_count + " items";
      } catch (err) {
        document.getElementById("service-status").innerText = "Service: Degraded";
      }
      loadCapsuleDigest();
    }

    async function loadCapsuleDigest() {
      const dateVal = document.getElementById("capsule-date-input").value.trim() || "2026-11-06";
      const cont = document.getElementById("discussions-container");
      cont.innerHTML = "<div style='color:var(--text-muted);'>Synthesizing discussions...</div>";

      try {
        const res = await fetch("/api/v1/capsule/" + dateVal);
        const data = await res.json();
        currentDigestMarkdown = data.markdown_digest || "";
        document.getElementById("markdown-preview").innerText = currentDigestMarkdown;

        if (!data.top_discussions || data.top_discussions.length === 0) {
          cont.innerHTML = "<div style='color:var(--text-muted);'>No discussion threads available for this date.</div>";
          return;
        }

        cont.innerHTML = data.top_discussions.map(d => `
          <div class="card" style="background:#090d16;">
            <div class="card-title">${d.title}</div>
            <div class="card-meta">
              <span class="badge badge-canon">Sentiment: ${d.sentiment_score >= 0 ? "+" + d.sentiment_score.toFixed(2) : d.sentiment_score.toFixed(2)}</span>
              <span class="badge badge-epoch">Controversy: ${d.controversy_score.toFixed(2)}</span>
              <span class="badge">${d.model_used}</span>
            </div>
            <div class="analysis-section">
              <div class="analysis-label">Core Thesis</div>
              <div class="analysis-box">${d.core_thesis}</div>
              <div class="analysis-label">Community Consensus</div>
              <div class="analysis-box">${d.community_consensus}</div>
              <div class="analysis-label">Contrarian Pushback</div>
              <div class="analysis-box">${d.contrarian_pushback}</div>
              ${d.anchor_comment_spotlight ? `
                <div class="analysis-label" style="color:#fbbf24;">Anchor Comment Spotlight (#${d.anchor_comment_id || ""})</div>
                <div class="analysis-box spotlight-box">${d.anchor_comment_spotlight}</div>
              ` : ""}
              ${d.actionable_takeaways && d.actionable_takeaways.length ? `
                <div class="analysis-label">Actionable Takeaways</div>
                <div class="analysis-box">
                  <ul style="padding-left:1.25rem;">
                    ${d.actionable_takeaways.map(t => `<li>${t}</li>`).join("")}
                  </ul>
                </div>
              ` : ""}
            </div>
          </div>
        `).join("");
      } catch (err) {
        cont.innerHTML = "<div style='color:#ef4444;'>Failed to load capsule digest: " + err + "</div>";
      }
    }

    function copyMarkdownDigest() {
      if (!currentDigestMarkdown) return;
      navigator.clipboard.writeText(currentDigestMarkdown).then(() => {
        const el = document.getElementById("copy-status");
        el.innerText = "Copied to clipboard.";
        setTimeout(() => { el.innerText = ""; }, 2500);
      });
    }

    async function loadVaultItems() {
      const epoch = document.getElementById("vault-epoch-select").value;
      const isEvergreen = document.getElementById("vault-evergreen-select").value;
      const pillar = document.getElementById("vault-pillar-select").value;
      const source = document.getElementById("vault-source-select").value;
      const search = document.getElementById("vault-search-input").value.trim();

      const params = new URLSearchParams();
      if (epoch) params.set("epoch", epoch);
      if (isEvergreen) params.set("is_evergreen_canon", isEvergreen);
      if (pillar) params.set("pillar", pillar);
      if (source) params.set("source_type", source);
      if (search) params.set("search", search);
      params.set("limit", "250");

      const tbody = document.getElementById("vault-table-body");
      tbody.innerHTML = "<tr><td colspan='7' style='text-align:center; color:var(--text-muted);'>Filtering vault...</td></tr>";

      try {
        const res = await fetch("/api/v1/vault?" + params.toString());
        const data = await res.json();
        document.getElementById("vault-results-count").innerText = `Displaying ${data.count} items (limit 250)`;

        if (data.items.length === 0) {
          tbody.innerHTML = "<tr><td colspan='7' style='text-align:center; color:var(--text-muted);'>No matching vault items found.</td></tr>";
          return;
        }

        tbody.innerHTML = data.items.map(item => `
          <tr>
            <td style="max-width:320px;">
              <a href="${item.canonical_url}" target="_blank" rel="noopener">${item.title || item.canonical_url}</a>
              ${item.search_query ? `<div style="font-size:0.75rem; color:var(--text-muted);">Query: "${item.search_query}"</div>` : ""}
            </td>
            <td style="font-family:var(--font-mono); font-size:0.75rem; color:var(--text-muted);">${item.domain}</td>
            <td><span class="badge ${item.source_type === 'hacker_news' ? 'badge-hn' : ''}">${item.source_type}</span></td>
            <td>
              <div style="display:flex; gap:0.25rem; flex-wrap:wrap;">
                ${item.epochs_present.map(e => `<span class="badge badge-epoch">${e}</span>`).join("")}
              </div>
            </td>
            <td>
              ${item.is_evergreen_canon ? `<span class="badge badge-canon">Evergreen Canon</span>` : ""}
              <span style="font-family:var(--font-mono); font-size:0.75rem;">${item.total_occurrences}x</span>
            </td>
            <td><span class="badge badge-pillar">${item.primary_pillar.replace("PILLAR_", "")}</span></td>
            <td>
              <button class="btn-secondary" style="font-size:0.75rem; padding:0.25rem 0.5rem;" onclick="analyzeItem('${item.item_id}', '${encodeURIComponent(item.title)}')">
                Analyze via Spark
              </button>
            </td>
          </tr>
        `).join("");
      } catch (err) {
        tbody.innerHTML = "<tr><td colspan='7' style='color:#ef4444;'>Failed to load items: " + err + "</td></tr>";
      }
    }

    async function analyzeItem(itemId, itemTitle) {
      const modal = document.getElementById("analysis-modal");
      document.getElementById("analysis-modal-title").innerText = decodeURIComponent(itemTitle);
      const body = document.getElementById("analysis-modal-body");
      body.innerHTML = "<div style='color:var(--text-muted);'>Contacting DGX Spark vLLM engine...</div>";
      modal.classList.add("active");

      try {
        const res = await fetch(`/api/v1/vault/${itemId}/analyze`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ allow_llm: true, allow_external_hydration: false })
        });
        if (!res.ok) throw new Error("HTTP " + res.status);
        const d = await res.json();
        body.innerHTML = `
          <div class="card-meta" style="margin-bottom:0.75rem;">
            <span class="badge badge-canon">Sentiment: ${d.sentiment_score >= 0 ? "+" + d.sentiment_score.toFixed(2) : d.sentiment_score.toFixed(2)}</span>
            <span class="badge badge-epoch">Controversy: ${d.controversy_score.toFixed(2)}</span>
            <span class="badge">${d.model_used}</span>
          </div>
          <div class="analysis-section">
            <div class="analysis-label">Core Thesis</div>
            <div class="analysis-box">${d.core_thesis}</div>
            <div class="analysis-label">Community Consensus</div>
            <div class="analysis-box">${d.community_consensus}</div>
            <div class="analysis-label">Contrarian Pushback</div>
            <div class="analysis-box">${d.contrarian_pushback}</div>
            ${d.anchor_comment_spotlight ? `
              <div class="analysis-label" style="color:#fbbf24;">Anchor Comment Spotlight (#${d.anchor_comment_id || ""})</div>
              <div class="analysis-box spotlight-box">${d.anchor_comment_spotlight}</div>
            ` : ""}
            ${d.actionable_takeaways && d.actionable_takeaways.length ? `
              <div class="analysis-label">Actionable Takeaways</div>
              <div class="analysis-box">
                <ul style="padding-left:1.25rem;">
                  ${d.actionable_takeaways.map(t => `<li>${t}</li>`).join("")}
                </ul>
              </div>
            ` : ""}
          </div>
        `;
      } catch (err) {
        body.innerHTML = "<div style='color:#ef4444;'>Analysis failed: " + err + "</div>";
      }
    }

    function closeAnalysisModal() {
      document.getElementById("analysis-modal").classList.remove("active");
    }

    function openImportModal() {
      document.getElementById("import-modal").classList.add("active");
    }

    function closeImportModal() {
      document.getElementById("import-modal").classList.remove("active");
    }

    async function submitImport() {
      const text = document.getElementById("import-text").value.trim();
      const epochId = document.getElementById("import-epoch-select").value;
      if (!text) return;

      try {
        const res = await fetch("/api/v1/vault/import", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: text, epoch_id: epochId })
        });
        const d = await res.json();
        alert(`Successfully imported ${d.imported_raw_count} raw links. Total vault items: ${d.total_vault_items}.`);
        closeImportModal();
        document.getElementById("import-text").value = "";
        loadVaultItems();
        initDashboard();
      } catch (err) {
        alert("Import failed: " + err);
      }
    }

    async function loadTasteProfile() {
      const cont = document.getElementById("taste-profile-container");
      try {
        const res = await fetch("/api/v1/epochs/summary");
        const data = await res.json();
        const tp = data.taste_profile || {};
        const epochs = Object.keys(tp.epoch_taste || {});

        cont.innerHTML = epochs.map(ep => {
          const dist = tp.epoch_taste[ep] || {};
          return `
            <div class="card" style="background:#090d16;">
              <div class="card-title" style="font-size:0.95rem;">Epoch: ${ep}</div>
              <div style="font-size:0.75rem; color:var(--text-muted); margin-bottom:0.75rem;">Total items: ${data.epoch_breakdown[ep] || 0}</div>
              ${Object.entries(dist).map(([pillar, count]) => `
                <div style="margin-bottom:0.4rem;">
                  <div style="display:flex; justify-content:space-between; font-size:0.75rem;">
                    <span>${pillar.replace("PILLAR_", "")}</span>
                    <span style="font-family:var(--font-mono);">${count}</span>
                  </div>
                  <div style="background:#1f293d; height:4px; border-radius:2px; overflow:hidden;">
                    <div style="background:#3b82f6; width:${Math.min(100, (count / (data.epoch_breakdown[ep] || 1)) * 100)}%; height:100%;"></div>
                  </div>
                </div>
              `).join("")}
            </div>
          `;
        }).join("");
      } catch (err) {
        cont.innerHTML = "<div style='color:#ef4444;'>Failed to load taste profile: " + err + "</div>";
      }
    }

    async function loadVocab() {
      const tbody = document.getElementById("vocab-table-body");
      try {
        const res = await fetch("/api/v1/vocabulary");
        const data = await res.json();
        document.getElementById("vocab-count-badge").innerText = `${data.count} terms`;
        if (data.vocabulary.length === 0) {
          tbody.innerHTML = "<tr><td colspan='3' style='text-align:center; color:var(--text-muted);'>No vocabulary terms tracked.</td></tr>";
          return;
        }
        tbody.innerHTML = data.vocabulary.map(v => `
          <tr>
            <td style="font-weight:600; font-family:var(--font-mono); color:#93c5fd;">${v.term}</td>
            <td style="font-size:0.8125rem;">${v.definition_hint || "N/A"}</td>
            <td><span class="badge badge-epoch">${v.epoch_first_seen}</span></td>
          </tr>
        `).join("");
      } catch (err) {
        tbody.innerHTML = "<tr><td colspan='3' style='color:#ef4444;'>Failed to load vocabulary: " + err + "</td></tr>";
      }
    }

    async function loadIntents() {
      const cat = document.getElementById("intent-category-select").value;
      const params = new URLSearchParams();
      if (cat) params.set("category", cat);
      const tbody = document.getElementById("intents-table-body");

      try {
        const res = await fetch("/api/v1/intents?" + params.toString());
        const data = await res.json();
        if (data.intents.length === 0) {
          tbody.innerHTML = "<tr><td colspan='3' style='text-align:center; color:var(--text-muted);'>No search intents found.</td></tr>";
          return;
        }
        tbody.innerHTML = data.intents.map(i => `
          <tr>
            <td style="font-weight:500;">"${i.query_text}"</td>
            <td><span class="badge ${i.category === 'technical_learning' ? 'badge-pillar' : 'badge-epoch'}">${i.category}</span></td>
            <td><span class="badge">${i.epoch_first_seen}</span></td>
          </tr>
        `).join("");
      } catch (err) {
        tbody.innerHTML = "<tr><td colspan='3' style='color:#ef4444;'>Failed to load intents: " + err + "</td></tr>";
      }
    }

    async function loadMacro() {
      const dateVal = document.getElementById("capsule-date-input").value.trim() || "2026-11-06";
      const wBody = document.getElementById("weather-table-body");
      const sBody = document.getElementById("stocks-table-body");

      try {
        const res = await fetch("/api/v1/capsule/" + dateVal);
        const data = await res.json();

        if (data.weather_records && data.weather_records.length > 0) {
          wBody.innerHTML = data.weather_records.map(w => `
            <tr>
              <td style="font-weight:600;">${w.city || "N/A"}</td>
              <td style="font-family:var(--font-mono);">${w.temp !== undefined ? w.temp : "N/A"}</td>
              <td>${w.weather_main || w.weather_description || "Clear"}</td>
              <td style="font-family:var(--font-mono);">${w.humidity !== undefined ? w.humidity : "N/A"}</td>
              <td style="font-family:var(--font-mono);">${w.pressure !== undefined ? w.pressure : "N/A"}</td>
            </tr>
          `).join("");
        } else {
          wBody.innerHTML = "<tr><td colspan='5' style='text-align:center; color:var(--text-muted);'>No weather records.</td></tr>";
        }

        if (data.stock_records && data.stock_records.length > 0) {
          sBody.innerHTML = data.stock_records.map(s => `
            <tr>
              <td style="font-weight:600; font-family:var(--font-mono); color:#60a5fa;">${s.ticker || "N/A"}</td>
              <td style="font-family:var(--font-mono);">${s.close !== undefined ? "$" + Number(s.close).toFixed(2) : "N/A"}</td>
              <td style="font-family:var(--font-mono);">${s.open !== undefined ? "$" + Number(s.open).toFixed(2) : "N/A"}</td>
              <td style="font-family:var(--font-mono);">${s.high !== undefined ? "$" + Number(s.high).toFixed(2) : "N/A"}</td>
              <td style="font-family:var(--font-mono);">${s.low !== undefined ? "$" + Number(s.low).toFixed(2) : "N/A"}</td>
              <td style="font-family:var(--font-mono);">${s.volume !== undefined ? Number(s.volume).toLocaleString() : "N/A"}</td>
            </tr>
          `).join("");
        } else {
          sBody.innerHTML = "<tr><td colspan='6' style='text-align:center; color:var(--text-muted);'>No stock records.</td></tr>";
        }
      } catch (err) {
        wBody.innerHTML = "<tr><td colspan='5' style='color:#ef4444;'>Failed to load weather: " + err + "</td></tr>";
        sBody.innerHTML = "<tr><td colspan='6' style='color:#ef4444;'>Failed to load stocks: " + err + "</td></tr>";
      }
    }

    window.addEventListener("DOMContentLoaded", initDashboard);
  </script>
</body>
</html>
"""


def get_repo(request: Request) -> TimeCapsuleRepository:
    """Dependency provider for retrieving the lakehouse repository instance.

    Pre-conditions:
        - request.app.state.repo must be initialized.

    Post-conditions:
        - Returns TimeCapsuleRepository connected to the configured database.
    """
    return request.app.state.repo  # type: ignore[no-any-return]


def create_app(db_path: str | None = None, seed_dir: str | None = None) -> FastAPI:
    """Factory creating and configuring the Digital Time Capsule FastAPI service.

    Pre-conditions:
        - db_path is None or a valid DuckDB database path or ':memory:'.
        - seed_dir is None or a valid filesystem path containing raw Safari seed files.

    Post-conditions:
        - Returns configured FastAPI application with initialized routes and lakehouse storage.
    """
    configured_db_path: str = (
        db_path if db_path is not None else os.getenv("TIME_CAPSULE_DB_PATH", "data/time_capsule.duckdb")
    )
    configured_seed_dir: str = (
        seed_dir if seed_dir is not None else os.getenv("TIME_CAPSULE_SEED_DIR", "data/seeds")
    )

    repo = TimeCapsuleRepository(configured_db_path)

    # Startup auto-seeding if the repository is empty and seed directory exists
    if repo.count_vault_items() == 0 and Path(configured_seed_dir).exists():
        seed_database_from_seeds(repo, seed_dir=configured_seed_dir)

    service = FastAPI(
        title="Digital Time Capsule Service",
        description="Autonomous Multi-Epoch Safari Reading Vault & Tech Discussion Synthesis Lakehouse.",
        version="0.2.0",
    )

    service.state.repo = repo
    service.state.seed_dir = configured_seed_dir

    @service.get("/healthz", response_model=dict[str, str])
    def health_check() -> dict[str, str]:
        """Liveness probe verifying HTTP availability of the application.

        Pre-conditions:
            - HTTP GET request to /healthz.

        Post-conditions:
            - Returns HTTP 200 with service health status.
        """
        return {"status": "ok", "service": "time-capsule"}

    @service.get("/ready", response_model=dict[str, Any])
    def readiness_check(
        repository: Annotated[TimeCapsuleRepository, Depends(get_repo)],
    ) -> dict[str, Any]:
        """Readiness probe verifying DuckDB connectivity and seed state.

        Pre-conditions:
            - Database connection must be responsive.

        Post-conditions:
            - Returns HTTP 200 with total vault count and evergreen canon count.
        """
        vault_count = repository.count_vault_items()
        evergreen_items = repository.query_vault_items(is_evergreen_canon=True)
        return {
            "status": "ready",
            "vault_count": vault_count,
            "evergreen_count": len(evergreen_items),
        }

    @service.get("/api/v1/vault", response_model=dict[str, Any])
    def get_vault_items(
        repository: Annotated[TimeCapsuleRepository, Depends(get_repo)],
        epoch: Annotated[str | None, Query(description="Filter by snapshot epoch.")] = None,
        is_evergreen_canon: Annotated[
            bool | None, Query(description="Filter by Evergreen Canon membership.")
        ] = None,
        pillar: Annotated[
            str | None, Query(description="Filter by primary intellectual pillar.")
        ] = None,
        source_type: Annotated[
            str | None, Query(description="Filter by content source type.")
        ] = None,
        min_sentiment: Annotated[
            float | None, Query(description="Filter by minimum sentiment score.")
        ] = None,
        search: Annotated[
            str | None, Query(description="Search term across title, URL, or query.")
        ] = None,
        limit: Annotated[
            int, Query(ge=1, le=5000, description="Maximum items to return.")
        ] = 1000,
    ) -> dict[str, Any]:
        """Query reading vault items with multi-parameter filtering and text search.

        Pre-conditions:
            - Valid query parameters and active database connection.

        Post-conditions:
            - Returns list of matching SafariLinkItem models and total count.
        """
        items = repository.query_vault_items(
            epoch=epoch,
            is_evergreen_canon=is_evergreen_canon,
            pillar=pillar,
            source_type=source_type,
            min_sentiment=min_sentiment,
            search=search,
            limit=limit,
        )
        return {
            "count": len(items),
            "items": [item.model_dump() for item in items],
        }

    @service.get("/api/v1/epochs/summary", response_model=dict[str, Any])
    def get_epochs_summary_endpoint(
        repository: Annotated[TimeCapsuleRepository, Depends(get_repo)],
    ) -> dict[str, Any]:
        """Retrieve longitudinal summary across all three historical reading epochs.

        Pre-conditions:
            - Database populated with multi-epoch vault items.

        Post-conditions:
            - Returns breakdown of items per epoch, evergreen canon list, anchored items, and taste distribution.
        """
        summary = repository.get_epochs_summary()
        summary["evergreen_canon"] = [
            i.model_dump() if hasattr(i, "model_dump") else i
            for i in summary.get("evergreen_canon_items", [])
        ]
        summary["total_unique_items"] = summary.get("total_vault_items", 0)
        summary["epoch_breakdown"] = summary.get("epoch_counts", {})
        return summary

    @service.post("/api/v1/vault/import", response_model=dict[str, Any])
    def import_vault_text(
        req: VaultImportRequest,
        repository: Annotated[TimeCapsuleRepository, Depends(get_repo)],
    ) -> dict[str, Any]:
        """Ingest raw Safari Reading List lines or markdown text and merge into lakehouse.

        Pre-conditions:
            - req.text contains newline-separated URLs or markdown links.
            - req.epoch_id specifies the target historical epoch.

        Post-conditions:
            - Merges items with existing vault data, updates cross-epoch occurrences, and returns counts.
        """
        parsed_links = parse_safari_reading_list(req.text, epoch=req.epoch_id)

        merged_links: list[SafariLinkItem] = []
        for link in parsed_links:
            existing = repository.get_vault_item(link.item_id)
            if existing:
                epochs = sorted(list(set(existing.epochs_present + [req.epoch_id])))
                link.epochs_present = epochs
                link.cross_epoch_count = len(epochs)
                link.total_occurrences = existing.total_occurrences + 1
                link.is_evergreen_canon = len(epochs) >= 3
                if (not link.title or link.was_untitled_tab) and existing.title:
                    link.title = existing.title
                    link.was_untitled_tab = existing.was_untitled_tab
            else:
                link.epochs_present = [req.epoch_id]
                link.cross_epoch_count = 1
                link.total_occurrences = 1
                link.is_evergreen_canon = False
            merged_links.append(link)

        parse_result = merge_vault_items(merged_links, {req.epoch_id: len(merged_links)})
        repository.upsert_vault_parse_result(parse_result)

        return {
            "imported_raw_count": len(parsed_links),
            "total_vault_items": repository.count_vault_items(),
            "evergreen_count": len(repository.query_vault_items(is_evergreen_canon=True)),
        }

    @service.post("/api/v1/vault/{item_id}/analyze", response_model=dict[str, Any])
    async def analyze_vault_item_endpoint(
        item_id: str,
        repository: Annotated[TimeCapsuleRepository, Depends(get_repo)],
        req: AnalyzeRequest | None = None,
    ) -> dict[str, Any]:
        """Synthesize architectural perspective and community consensus for a vault item.

        Pre-conditions:
            - item_id must identify an existing vault item in DuckDB.

        Post-conditions:
            - Generates and persists DiscussionAnalysis into DuckDB; returns analysis payload.
        """
        config = req or AnalyzeRequest()
        item = repository.get_vault_item(item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vault item {item_id} not found in reading vault",
            )

        if config.allow_external_hydration:
            if item.source_type == SourceType.HACKER_NEWS:
                hn_client = HNClient()
                item, _ = hn_client.hydrate_safari_item(item)
            elif item.source_type == SourceType.REDDIT or item.url:
                extractor = CulturalExtractor()
                _ = extractor.extract_metadata(item.url)

        analyzer = SparkDiscussionAnalyzer()
        analysis = await analyzer.analyze_item_async(item, allow_llm=config.allow_llm)
        repository.upsert_discussion_analyses([analysis])
        return analysis.model_dump()

    @service.get("/api/v1/intents", response_model=dict[str, Any])
    def get_search_intents_endpoint(
        repository: Annotated[TimeCapsuleRepository, Depends(get_repo)],
        category: Annotated[
            str | None, Query(description="Filter by query intent category.")
        ] = None,
        epoch: Annotated[str | None, Query(description="Filter by epoch first seen.")] = None,
    ) -> dict[str, Any]:
        """Retrieve categorized search intents and technical inquiry history.

        Pre-conditions:
            - Valid query parameters and active database connection.

        Post-conditions:
            - Returns list of search intents and count.
        """
        intents = repository.list_search_intents(category=category, epoch=epoch)
        return {
            "count": len(intents),
            "intents": [intent.model_dump() for intent in intents],
        }

    @service.get("/api/v1/vocabulary", response_model=dict[str, Any])
    def get_vocabulary_endpoint(
        repository: Annotated[TimeCapsuleRepository, Depends(get_repo)],
        epoch: Annotated[str | None, Query(description="Filter by epoch first seen.")] = None,
    ) -> dict[str, Any]:
        """Retrieve personal technical vocabulary lexicon entries.

        Pre-conditions:
            - Valid query parameter and active database connection.

        Post-conditions:
            - Returns list of vocabulary entries and count.
        """
        entries = repository.list_vocabulary_entries(epoch=epoch)
        return {
            "count": len(entries),
            "vocabulary": [entry.model_dump() for entry in entries],
        }

    @service.get("/api/v1/digests", response_model=dict[str, Any])
    def get_digests_endpoint(
        repository: Annotated[TimeCapsuleRepository, Depends(get_repo)],
    ) -> dict[str, Any]:
        """Retrieve list of stored daily capsule snapshots and top discussion analyses.

        Pre-conditions:
            - Active database connection.

        Post-conditions:
            - Returns list of daily capsule summaries and recent discussion analyses.
        """
        snapshots = repository.list_daily_capsules(limit=30)
        analyses = repository.list_discussion_analyses(limit=20)
        return {
            "digests": [s.model_dump() for s in snapshots],
            "top_analyses": [a.model_dump() for a in analyses],
        }

    @service.get("/api/v1/capsule/{capsule_date}", response_model=dict[str, Any])
    def get_daily_capsule_endpoint(
        capsule_date: str,
        repository: Annotated[TimeCapsuleRepository, Depends(get_repo)],
    ) -> dict[str, Any]:
        """Retrieve or synthesize a daily capsule snapshot for the specified date.

        Pre-conditions:
            - capsule_date formatted as YYYY-MM-DD.

        Post-conditions:
            - Returns existing DailyCapsuleSnapshot or synthesizes one on demand.
        """
        snapshot = repository.get_daily_capsule(capsule_date)
        if snapshot is None:
            evergreen_items = repository.query_vault_items(is_evergreen_canon=True, limit=5)
            analyses = repository.list_discussion_analyses(limit=5)
            weather_data = get_fallback_weather_records()
            stock_data = get_fallback_stock_records()

            snapshot = DailyCapsuleSnapshot(
                capsule_date=capsule_date,
                weather_records=weather_data,
                stock_records=stock_data,
                top_discussions=analyses,
                evergreen_spotlight=evergreen_items,
            )
            snapshot.markdown_digest = render_capsule_markdown(snapshot)
            repository.upsert_daily_capsule(snapshot)

        return snapshot.model_dump()

    @service.get("/", response_class=HTMLResponse)
    def render_dashboard() -> HTMLResponse:
        """Serve the interactive single-page Digital Time Capsule dashboard.

        Pre-conditions:
            - HTTP GET request to root path /.

        Post-conditions:
            - Returns HTML document containing the 4 primary application tabs.
        """
        return HTMLResponse(content=INDEX_HTML, status_code=status.HTTP_200_OK)

    return service


# Default application instance for ASGI servers
app = create_app()


if __name__ == "__main__":
    import uvicorn

    server_host = os.getenv("HOST", "0.0.0.0")
    server_port = int(os.getenv("PORT", "8000"))
    uvicorn.run("time_capsule.api.main:app", host=server_host, port=server_port, reload=False)
