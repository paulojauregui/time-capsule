# Milestone M06 Specification: Design Tokens & Component Layout Stylesheet

## 1. Objective
Implement the modular CSS architecture for the `v2-ux` Digital Time Capsule & Autonomous Reading Vault frontend in `src/time_capsule/api/static/tokens.css` and `src/time_capsule/api/static/components.css`, together with deterministic contract tests in `tests/test_ui_assets.py`.

## 2. Target Files
1. `src/time_capsule/api/static/tokens.css`
2. `src/time_capsule/api/static/components.css`
3. `tests/test_ui_assets.py`

## 3. Non-Negotiable Invariants
- **Zero Emojis**: Do not place any emoji characters in CSS comments, content strings, or test files.
- **Strict Token Encapsulation**:
  - `src/time_capsule/api/static/tokens.css` declares all `:root` CSS Custom Properties (`--bg-*`, `--border-*`, `--focus-ring`, `--text-*`, `--accent-*`, `--canon-amber-*`, `--source-*`, `--pillar-*`, `--epoch-*`, `--status-*`, `--font-*`, `--space-*`, `--radius-*`, `--ease-out`, `--duration-fast`).
  - `src/time_capsule/api/static/components.css` consumes `var(--*)` exclusively and MUST NOT contain any raw hex color literals (`#...`).
- **Python Test Quality**:
  - Absolute imports only in `tests/test_ui_assets.py`.
  - Full Python type annotations (`-> None` on all test and helper functions) so `mypy` passes with `disallow_untyped_defs = true`.
  - Design by Contract docstrings (`Pre-conditions:` and `Post-conditions:`) on module and every test/helper function.

## 4. Exact Token Contract (`src/time_capsule/api/static/tokens.css`)
`tokens.css` must define `:root` with the following exact custom properties:
```css
/* Design Token Contract - Digital Time Capsule & Autonomous Reading Vault (v2-ux) */
:root {
  /* 1. 4-Tier Dark Surface Elevation Hierarchy */
  --bg-canvas: #090c12;
  --bg-surface-1: #101520;
  --bg-surface-2: #171f2e;
  --bg-elevated: #1e283b;
  --bg-backdrop: rgba(9, 12, 18, 0.82);

  /* 2. Structural Hairline Borders & Focus Ring */
  --border-subtle: #1e293b;
  --border-default: #2b3950;
  --border-strong: #3e5272;
  --focus-ring: #60a5fa;

  /* 3. Primary Text Hierarchy (Verified >= 4.5:1 AA / >= 10:1 AAA) */
  --text-primary: #f1f5f9;
  --text-secondary: #cbd5e1;
  --text-muted: #94a3b8;

  /* 4. Interactive & Link Accents */
  --accent-primary: #3b82f6;
  --accent-primary-hover: #2563eb;
  --accent-text: #93c5fd;

  /* 5. Strictly Reserved Archival Canon Tokens (14 Evergreen Canon & Anchor Spotlights ONLY) */
  --canon-amber-text: #fbbf24;
  --canon-amber-bg: rgba(245, 158, 11, 0.14);
  --canon-amber-border: rgba(245, 158, 11, 0.42);

  /* 6. Source Platform & Taxonomy Badge Tokens */
  --source-hn-text: #fdba74;
  --source-hn-bg: rgba(249, 115, 22, 0.14);
  --source-hn-border: rgba(249, 115, 22, 0.40);

  --source-reddit-text: #fca5a5;
  --source-reddit-bg: rgba(239, 68, 68, 0.14);
  --source-reddit-border: rgba(239, 68, 68, 0.40);

  --source-github-text: #e2e8f0;
  --source-github-bg: rgba(148, 163, 184, 0.16);
  --source-github-border: rgba(148, 163, 184, 0.40);

  --pillar-text: #93c5fd;
  --pillar-bg: rgba(59, 130, 246, 0.14);
  --pillar-border: rgba(59, 130, 246, 0.38);

  --epoch-text: #d8b4fe;
  --epoch-bg: rgba(168, 85, 247, 0.14);
  --epoch-border: rgba(168, 85, 247, 0.38);

  /* 7. Operational & Model Synthesis Status Tokens */
  --status-nominal-text: #6ee7b7;
  --status-nominal-bg: rgba(16, 185, 129, 0.14);
  --status-nominal-border: rgba(16, 185, 129, 0.40);

  --status-degraded-text: #fcd34d;
  --status-degraded-bg: rgba(234, 179, 8, 0.14);
  --status-degraded-border: rgba(234, 179, 8, 0.42);

  --status-error-text: #fca5a5;
  --status-error-bg: rgba(239, 68, 68, 0.14);
  --status-error-border: rgba(239, 68, 68, 0.42);

  /* 8. Typography Stacks & Modular Scale */
  --font-sans: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, SFMono-Regular, "SF Mono", Menlo, Monaco, Consolas, monospace;

  --text-xs: 0.75rem;
  --text-sm: 0.8125rem;
  --text-base: 0.875rem;
  --text-md: 0.9375rem;
  --text-lg: 1.0625rem;
  --text-xl: 1.5rem;

  /* 9. Spatial Grid (4px / 8px Scale) & Radii */
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 0.75rem;
  --space-4: 1rem;
  --space-5: 1.25rem;
  --space-6: 1.5rem;
  --space-8: 2rem;

  --radius-sm: 0.25rem;
  --radius-md: 0.375rem;
  --radius-lg: 0.5rem;
  --radius-pill: 9999px;

  /* 10. Purposeful Motion */
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --duration-fast: 150ms;
}
```

## 5. Exact Component Stylesheet Contract (`src/time_capsule/api/static/components.css`)
`components.css` must contain zero `#hex` literals and must define styles for:
1. **Reset, Root Shell & Accessibility Utilities**:
   - `* { box-sizing: border-box; margin: 0; padding: 0; }`
   - `body` using `background-color: var(--bg-canvas); color: var(--text-primary); font-family: var(--font-sans); font-size: var(--text-base); line-height: 1.55;`
   - `.app-shell` (`max-width: 1600px; margin: 0 auto; padding: var(--space-6);`)
   - `.skip-link` (positioned offscreen at `top: -100px`, moving to `top: var(--space-3); left: var(--space-3); z-index: 200;` on `:focus` / `:focus-visible`)
   - `.sr-only` (visually hidden screen-reader utility)
   - `:focus-visible` (`outline: 2px solid var(--focus-ring); outline-offset: 2px;`)
   - `[hidden] { display: none !important; }`
2. **Site Header & Operational Telemetry Pills**:
   - `.site-header`, `.header-titles`, `.status-pills`, `.pill`
   - `.pill-nominal` / `.pill-green` (`--status-nominal-*`)
   - `.pill-degraded` / `.pill-amber` (`--status-degraded-*`)
   - `.pill-error` / `.pill-red` (`--status-error-*`)
   - `.pill-canon` (`--canon-amber-*`)
   - `.pill-info` / `.pill-blue` (`--pillar-*`)
3. **WAI-ARIA Tab Bar (`role="tablist"`) & Workspaces (`role="tabpanel"`)**:
   - `.tab-bar`, `.tab-btn`, `.tab-btn:hover`, `.tab-btn.active`, `.tab-btn[aria-selected="true"]`
   - `.workspace-main`, `.tab-content`, `.tab-content.active`
4. **Control Panel, Form Inputs, Shortcut Hints & Buttons**:
   - `.control-panel`, `.filter-group`, `.control-label`, `.kbd-hint`
   - `.btn-primary`, `.btn-secondary`, `.btn-ghost`, `.btn-retry`
5. **Grid Layouts, Cards, Discussion Synthesis & Markdown Preview**:
   - `.grid-2`, `.grid-3`, `.card`, `.card-nested`, `.card-header`, `.card-title`, `.card-subtitle`, `.card-meta`
   - `.analysis-section`, `.analysis-label`, `.analysis-box`, `.spotlight-label`, `.spotlight-box`, `.takeaways-list`
   - `.markdown-preview`, `.taste-row`, `.taste-row-header`, `.taste-bar-track`, `.taste-bar-fill`
6. **Semantic Badges & Tabular Numerics**:
   - `.badge`, `.badge-canon`, `.badge-hn`, `.badge-reddit`, `.badge-github`, `.badge-pillar`, `.badge-epoch`, `.badge-model-spark`, `.badge-model-fallback`, `.badge-score`, `.score-positive`, `.score-negative`
   - `.tabular-nums`, `.num-col`, `th.num-col`, `td.num-col` with `font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-feature-settings: "tnum" 1;`
7. **Data Tables & Scroll Containers**:
   - `.table-scroll-container`, `.table-scroll-bounded`, `table.data-table`, `.results-meta`
8. **5-State Component Classes (`Empty`, `Loading`, `Nominal`, `Degraded`, `Error`)**:
   - `.state-banner`, `.state-banner-degraded`, `.state-empty`, `.state-actions`, `.state-error`, `.state-loading`
   - `.skeleton`, `.skeleton-card`, `.skeleton-row`, `.skeleton-line`, `.skeleton-well` with `@keyframes skeleton-pulse` and geometry-matched `min-height` rules (`CLS = 0`).
9. **Accessible Modals (`role="dialog"`)**:
   - `.modal`, `.modal.active`, `.modal-card`, `.modal-header`, `.modal-close`, `.modal-body`, `.modal-footer`, `.import-feedback`
10. **Responsive Media Queries & Reduced Motion**:
    - `@media (max-width: 767px)` (mobile single-column, scrollable tab-bar, stacked controls)
    - `@media (min-width: 768px) and (max-width: 1279px)` (tablet 2-column grid)
    - `@media (min-width: 1280px)` (desktop 2/3-column grid and `var(--space-8)` padding)
    - `@media (prefers-reduced-motion: reduce)` disabling animations and transitions.

## 6. Verification Test Suite (`tests/test_ui_assets.py`)
Write deterministic unit tests in `tests/test_ui_assets.py` verifying:
1. `tokens.css` exists and defines all required `:root` custom properties (`--bg-canvas`, `--bg-surface-1`, `--bg-surface-2`, `--bg-elevated`, `--focus-ring`, `--text-primary`, `--text-secondary`, `--text-muted`, `--canon-amber-text`, `--status-nominal-text`, `--status-degraded-text`, `--status-error-text`, `--font-sans`, `--font-mono`, `--space-1`..`--space-8`).
2. `components.css` exists, contains zero raw `#hex` color literals (`re.findall(r"#[0-9a-fA-F]{3,8}\b", content) == []`), and uses `var(--*)` token references.
3. `components.css` defines `.tabular-nums` and `.num-col` with `font-variant-numeric: tabular-nums`.
4. `components.css` defines `:focus-visible`, `.skip-link`, `.sr-only`, and `@media (prefers-reduced-motion: reduce)`.
5. `components.css` defines all 5-state classes (`.state-empty`, `.state-loading`, `.skeleton`, `.skeleton-card`, `.skeleton-row`, `.skeleton-line`, `.state-banner-degraded`, `.state-error`, `.badge-model-spark`, `.badge-model-fallback`) and responsive `@media` queries.
