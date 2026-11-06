"""Figma-to-Code Enterprise ERP Design Tokens & CSS Architecture.

Mirrors the exact Tailwind CSS / Figma variable hierarchy:
- Workspace Shell: h-screen overflow-hidden flex (desktop), w-64 bg-slate-900
  collapsible sidebar with active border-l-4 border-indigo-500, and scrollable
  bg-slate-50/50 canvas.
- Flat Enterprise Styling: strict 1px solid slate-200 (#e2e8f0) borders,
  geometric 4px-6px radii (rounded-sm / rounded-md), zero heavy drop shadows.
- Typography & Tabular Numbers: font-mono + tabular-nums tracking-tight on all
  financial amounts, cents, rates, and digests for vertical column alignment.
- Semantic Status Indicators: emerald-50/700/200, amber-50/700/200,
  rose-50/700/200, indigo-50/700/200 (tuned for WCAG AAA contrast).
"""

ERP_STYLES = """<style>
  :root {
    color-scheme: light;
    --slate-50: #f8fafc;
    --slate-100: #f1f5f9;
    --slate-200: #e2e8f0;
    --slate-300: #cbd5e1;
    --slate-400: #94a3b8;
    --slate-500: #475569;
    --slate-600: #334155;
    --slate-800: #1e293b;
    --slate-900: #0f172a;
    --indigo-50: #eef2ff;
    --indigo-200: #c7d2fe;
    --indigo-500: #6366f1;
    --indigo-600: #4f46e5;
    --indigo-700: #3730a3;
    --emerald-50: #ecfdf5;
    --emerald-200: #a7f3d0;
    --emerald-700: #065f46;
    --amber-50: #fffbeb;
    --amber-200: #fde68a;
    --amber-700: #92400e;
    --rose-50: #fff1f2;
    --rose-200: #fecdd3;
    --rose-700: #9f1239;
    --radius-sm: 4px;
    --radius-md: 6px;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--slate-50);
    color: var(--slate-900);
    font: 13.5px/1.45 Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    overflow-x: hidden;
  }
  .tabular-nums {
    font-variant-numeric: tabular-nums;
  }
  .font-mono {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.015em;
  }
  .skip {
    position: absolute; left: 0.5rem; top: -10rem;
    background: #ffffff; color: var(--slate-900); padding: 0.45rem 0.75rem;
    border: 2px solid var(--indigo-600); border-radius: var(--radius-sm); z-index: 200;
    font-weight: 600;
  }
  .skip:focus { top: 0.5rem; }

  /* Workspace Shell: h-screen overflow-hidden flex on desktop */
  .erp-shell {
    display: flex;
    min-height: 100vh;
    width: 100%;
  }
  @media (min-width: 1024px) {
    .erp-shell {
      height: 100vh;
      overflow: hidden;
    }
  }

  /* Left Sidebar: w-64 flex-shrink-0 bg-slate-900 text-slate-300 */
  .erp-sidebar {
    width: 256px;
    flex-shrink: 0;
    background: var(--slate-900);
    color: #cbd5e1;
    display: flex;
    flex-direction: column;
    border-right: 1px solid var(--slate-800);
    transition: width 150ms ease;
  }
  .erp-sidebar.collapsed {
    width: 68px;
  }
  .erp-sidebar.collapsed .hide-when-collapsed {
    display: none;
  }
  @media (max-width: 1023px) {
    .erp-shell { flex-direction: column; }
    .erp-sidebar {
      width: 100%;
      border-right: 0;
      border-bottom: 1px solid var(--slate-800);
    }
    .erp-nav-list {
      display: flex;
      flex-wrap: wrap;
      gap: 0.25rem;
      padding: 0.4rem 0.75rem !important;
    }
  }
  .sidebar-brand {
    padding: 0.85rem 1rem;
    border-bottom: 1px solid var(--slate-800);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }
  .brand-mark {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    border-radius: var(--radius-sm);
    background: var(--indigo-500);
    color: #ffffff;
    font-weight: 800;
    font-size: 0.85rem;
    flex-shrink: 0;
  }
  .company-switcher {
    margin: 0.65rem 0.75rem;
    padding: 0.45rem 0.6rem;
    background: var(--slate-800);
    border: 1px solid #334155;
    border-radius: var(--radius-sm);
    color: #f8fafc;
    font-size: 0.78rem;
  }
  .company-switcher select {
    width: 100%;
    background: var(--slate-800);
    color: #ffffff;
    border: 0;
    padding: 0;
    font-weight: 600;
    font-size: 0.8rem;
  }
  .erp-nav-list {
    list-style: none;
    margin: 0;
    padding: 0.5rem 0;
    flex: 1;
  }
  .nav-btn {
    width: 100%;
    text-align: left;
    background: transparent;
    color: #cbd5e1;
    border: 0;
    border-left: 4px solid transparent;
    border-radius: 0;
    padding: 0.55rem 0.9rem;
    font-size: 0.82rem;
    font-weight: 500;
    display: flex;
    align-items: center;
    justify-content: space-between;
    cursor: pointer;
    transition: background-color 150ms ease, color 150ms ease;
  }
  .nav-btn:hover {
    background: rgba(30, 41, 59, 0.7);
    color: #ffffff;
  }
  .nav-btn.active {
    background: var(--slate-800);
    color: #ffffff;
    border-left-color: var(--indigo-500);
    font-weight: 600;
  }
  .sidebar-foot {
    padding: 0.75rem 0.9rem;
    border-top: 1px solid var(--slate-800);
    font-size: 0.74rem;
    color: #cbd5e1;
  }

  /* Right Canvas: flex-1 flex flex-col overflow-hidden bg-slate-50 */
  .erp-canvas {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
    background: var(--slate-50);
  }
  @media (min-width: 1024px) {
    .erp-canvas {
      overflow: hidden;
    }
    .erp-scroll-area {
      flex: 1;
      overflow-y: auto;
    }
  }

  /* TopNav Header */
  header {
    background: #ffffff;
    border-bottom: 1px solid var(--slate-200);
    padding: 0.65rem 1.15rem;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }
  h1 {
    font-size: 1.05rem;
    font-weight: 700;
    margin: 0;
    color: var(--slate-900);
    letter-spacing: -0.01em;
  }
  .lede {
    margin: 0.15rem 0 0;
    font-size: 0.79rem;
    color: var(--slate-500);
    max-width: 780px;
  }
  .topnav-controls {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
  }
  .cmdk-trigger {
    display: inline-flex;
    align-items: center;
    gap: 0.55rem;
    background: var(--slate-50);
    border: 1px solid var(--slate-300);
    border-radius: var(--radius-md);
    padding: 0.35rem 0.65rem;
    color: var(--slate-600);
    font-size: 0.8rem;
  }
  .kbd {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.7rem;
    background: #ffffff;
    border: 1px solid var(--slate-300);
    border-radius: 3px;
    padding: 0.05rem 0.3rem;
    color: var(--slate-600);
  }

  /* Quick Action Bar */
  .quick-bar {
    background: #ffffff;
    border-bottom: 1px solid var(--slate-200);
    padding: 0.45rem 1.15rem;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.45rem;
  }
  .quick-label {
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--slate-500);
    margin-right: 0.25rem;
  }
  .cta {
    display: inline-block;
    background: var(--indigo-700);
    color: #ffffff;
    text-decoration: none;
    padding: 0.3rem 0.65rem;
    border-radius: var(--radius-sm);
    font-weight: 600;
    font-size: 0.78rem;
  }

  main {
    padding: 0.9rem 1.15rem 1.5rem;
    max-width: 1600px;
    width: 100%;
    margin: 0 auto;
  }

  .status-banner {
    padding: 0.55rem 0.85rem;
    border-radius: var(--radius-md);
    margin-bottom: 0.85rem;
    font-weight: 600;
    font-size: 0.82rem;
    border: 1px solid var(--emerald-200);
    background: var(--emerald-50);
    color: var(--emerald-700);
  }
  .status-banner.err {
    border-color: var(--rose-200);
    background: var(--rose-50);
    color: var(--rose-700);
  }

  /* Flat Enterprise Cards: 1px border-slate-200, rounded-md (6px) */
  .kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
    gap: 0.75rem;
    margin-bottom: 0.85rem;
  }
  .card {
    background: #ffffff;
    border: 1px solid var(--slate-200);
    border-radius: var(--radius-md);
    padding: 0.8rem 0.95rem;
    transition: background-color 150ms ease;
  }
  .card:hover {
    background: rgba(248, 250, 252, 0.8);
  }
  .card-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.25rem;
  }
  .acct-tag {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    color: var(--slate-600);
    text-transform: uppercase;
  }
  .mono-sm {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-variant-numeric: tabular-nums;
    font-size: 0.76rem;
    color: var(--slate-500);
  }
  .big-num {
    font-size: 1.15rem;
    font-weight: 700;
    margin-bottom: 0.4rem;
    color: var(--slate-900);
  }
  .meter-bar {
    height: 6px;
    background: var(--slate-200);
    border-radius: var(--radius-sm);
    overflow: hidden;
    margin-bottom: 0.4rem;
  }
  .meter-fill {
    height: 100%;
    background: var(--indigo-600);
  }
  .card-foot {
    display: flex;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 0.3rem;
    font-size: 0.76rem;
    color: var(--slate-500);
  }

  .cockpit-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.75fr) minmax(0, 1fr);
    gap: 0.85rem;
    align-items: start;
  }
  @media (max-width: 1100px) {
    .cockpit-grid { grid-template-columns: 1fr; }
  }

  section, section.erp-panel {
    background: #ffffff;
    border: 1px solid var(--slate-200);
    border-radius: var(--radius-md);
    padding: 0.85rem 1rem;
    margin-bottom: 0.85rem;
  }
  .forecast-panel {
    margin-bottom: 0.85rem;
  }
  .panel-head {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: center;
    gap: 0.5rem;
    padding-bottom: 0.55rem;
    margin-bottom: 0.65rem;
    border-bottom: 1px solid var(--slate-200);
  }
  h2 {
    font-size: 0.92rem;
    font-weight: 700;
    margin: 0;
    color: var(--slate-900);
  }

  /* High-Density ERP Table */
  .scroll-x {
    overflow-x: auto;
    max-width: 100%;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82rem;
  }
  th, td {
    text-align: left;
    padding: 0.5rem 0.45rem;
    border-bottom: 1px solid var(--slate-200);
    vertical-align: top;
  }
  th {
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--slate-500);
    background: var(--slate-50);
  }
  tbody tr {
    transition: background-color 150ms ease;
  }
  tbody tr:hover {
    background: rgba(248, 250, 252, 0.85);
  }
  .sup-title { font-weight: 600; color: var(--slate-900); }
  .sup-sub { font-size: 0.75rem; color: var(--slate-500); margin-top: 0.15rem; }
  .amt-main {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-variant-numeric: tabular-nums;
    font-weight: 700;
    white-space: nowrap;
    color: var(--slate-900);
  }
  .rail-pill {
    display: inline-block;
    background: var(--slate-100);
    border: 1px solid var(--slate-300);
    color: var(--slate-900);
    padding: 0.05rem 0.35rem;
    border-radius: var(--radius-sm);
    font-weight: 700;
    font-size: 0.68rem;
  }

  /* Semantic Status Badges (Figma tokens) */
  .badge {
    display: inline-block;
    padding: 0.12rem 0.45rem;
    border-radius: var(--radius-sm);
    font-size: 0.7rem;
    font-weight: 700;
    border: 1px solid transparent;
    white-space: nowrap;
  }
  .badge-ok { background: var(--emerald-50); color: var(--emerald-700); border-color: var(--emerald-200); }
  .badge-err { background: var(--rose-50); color: var(--rose-700); border-color: var(--rose-200); }
  .badge-amber { background: var(--amber-50); color: var(--amber-700); border-color: var(--amber-200); }
  .badge-indigo { background: var(--indigo-50); color: var(--indigo-700); border-color: var(--indigo-200); }
  .badge-neutral { background: var(--slate-100); color: var(--slate-600); border-color: var(--slate-300); }

  button, select, input, textarea {
    font: inherit;
    font-size: 0.79rem;
    padding: 0.32rem 0.6rem;
    border: 1px solid var(--slate-300);
    border-radius: var(--radius-sm);
    background: #ffffff;
    color: var(--slate-900);
    transition: background-color 150ms ease, border-color 150ms ease;
  }
  button {
    cursor: pointer;
    font-weight: 600;
  }
  button:hover { background: var(--slate-100); }
  button.primary {
    background: var(--indigo-700);
    color: #ffffff;
    border-color: var(--indigo-700);
  }
  button.primary:hover { background: #312e81; }
  button:focus-visible, select:focus-visible, input:focus-visible, a:focus-visible {
    outline: 2px solid var(--indigo-600);
    outline-offset: 2px;
  }
  .btn-col { display: flex; flex-direction: column; gap: 0.3rem; }
  .btn-row { display: flex; flex-wrap: wrap; gap: 0.35rem; }
  .deposit {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: end;
  }
  label {
    display: block;
    font-weight: 600;
    font-size: 0.76rem;
    color: var(--slate-600);
    margin-bottom: 0.18rem;
  }
  code {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-variant-numeric: tabular-nums;
    font-size: 0.8em;
    background: var(--slate-100);
    border: 1px solid var(--slate-200);
    padding: 0.05rem 0.28rem;
    border-radius: var(--radius-sm);
    word-break: break-all;
  }
  .receipt-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 0.55rem;
    background: var(--slate-50);
    border: 1px solid var(--slate-200);
    border-radius: var(--radius-md);
    padding: 0.65rem;
  }
  .full-span { grid-column: 1 / -1; }
  .kv-label { font-size: 0.7rem; font-weight: 700; color: var(--slate-500); text-transform: uppercase; }
  .kv-val { font-size: 0.82rem; margin-top: 0.12rem; }
  .kv-grid { display: grid; gap: 0.3rem; font-size: 0.82rem; margin-bottom: 0.55rem; }
  .finding-item { margin-bottom: 0.4rem; font-size: 0.82rem; }
  .sub-card {
    background: var(--slate-50);
    border: 1px solid var(--slate-200);
    border-radius: var(--radius-md);
    padding: 0.55rem 0.75rem;
    margin-top: 0.55rem;
    font-size: 0.8rem;
  }
  .code-preview {
    background: var(--slate-900);
    color: #f8fafc;
    padding: 0.5rem 0.65rem;
    border-radius: var(--radius-sm);
    font-size: 0.75rem;
    overflow-x: auto;
    margin: 0.4rem 0 0;
  }
  .compact-list { margin: 0.35rem 0 0; padding-left: 1.15rem; }
  .muted-note { color: var(--slate-500); font-size: 0.8rem; margin: 0; }
  .forecast-row {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: center;
    gap: 0.5rem;
  }

  /* Command Menu Modal (Ctrl+K / Meta+K) */
  .cmdk-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(15, 23, 42, 0.55);
    display: none;
    align-items: flex-start;
    justify-content: center;
    padding-top: 10vh;
    z-index: 150;
  }
  .cmdk-backdrop.open {
    display: flex;
  }
  .cmdk-dialog {
    background: #ffffff;
    border: 1px solid var(--slate-300);
    border-radius: var(--radius-md);
    width: 92%;
    max-width: 560px;
    overflow: hidden;
    box-shadow: 0 10px 25px rgba(15, 23, 42, 0.2);
  }
  .cmdk-head {
    padding: 0.65rem 0.8rem;
    border-bottom: 1px solid var(--slate-200);
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .cmdk-head input {
    width: 100%;
    border: 1px solid var(--slate-300);
    padding: 0.4rem 0.6rem;
    font-size: 0.85rem;
  }
  .cmdk-list {
    list-style: none;
    margin: 0;
    padding: 0.4rem;
    max-height: 300px;
    overflow-y: auto;
  }
  .cmdk-item {
    width: 100%;
    text-align: left;
    border: 0;
    background: transparent;
    padding: 0.45rem 0.6rem;
    border-radius: var(--radius-sm);
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.8rem;
  }
  .cmdk-item:hover, .cmdk-item:focus {
    background: var(--indigo-50);
    color: var(--indigo-700);
  }

  footer {
    padding: 0.75rem 1.15rem 1.25rem;
    border-top: 1px solid var(--slate-200);
    background: #ffffff;
    color: var(--slate-500);
    font-size: 0.78rem;
  }
</style>"""
