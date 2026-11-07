"""High-Density Enterprise Treasury ERP Surface for the anonymous judge cockpit.

Implements the Principal Frontend Architect / Figma-to-Code specification:
- Workspace Layout: .erp-shell (h-screen overflow-hidden flex on desktop) with
  fixed collapsible w-64 bg-slate-900 sidebar and scrollable bg-slate-50 canvas.
- Flat Enterprise Styling: strict 1px slate-200 borders, geometric 4px-6px radii.
- Tabular-nums & font-mono vertical alignment on all financial figures & digests.
- Global Command Palette (Ctrl+K / Meta+K) and Multi-Company Entity Switcher.
- Complete Kit 1 (Adaptive Treasury), Kit 3 (Payment Ops Incident Commander),
  Kit 9 (Visa Virtual Commercial Card Spend Controls), and Kit 11 (Metal x402).
- Semantic landmarks (<header>, <main>, <footer>), skip link, single <h1>,
  WCAG AAA high-contrast tokens, and aria-live="polite" status region.
"""

from archon_demo.ui_script import UI_SCRIPT
from archon_demo.ui_styles import ERP_STYLES

PAGE = (
    """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Archon Treasury (powered by Kerdon) | Enterprise Treasury ERP</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='6' fill='%230f172a'/><text x='8' y='23' font-family='sans-serif' font-size='20' font-weight='bold' fill='%236366f1'>A</text></svg>">
"""
    + ERP_STYLES
    + """
</head>
<body>
<a class="skip" href="#main">Skip to main content</a>

<div class="erp-shell">
  <aside class="erp-sidebar" id="erp-sidebar" aria-label="ERP Module Navigation">
    <div class="sidebar-brand">
      <div style="display:flex;align-items:center;gap:0.55rem">
        <span class="brand-mark" aria-hidden="true">A</span>
        <span class="hide-when-collapsed" style="font-weight:700;color:#ffffff;font-size:0.9rem">Archon ERP</span>
      </div>
      <button type="button" id="sidebar-toggle" title="Collapse or expand sidebar" style="background:#1e293b;color:#f8fafc;border-color:#334155;padding:0.2rem 0.45rem;font-size:0.72rem">&laquo;</button>
    </div>

    <div class="company-switcher hide-when-collapsed">
      <label for="company-select" style="color:#cbd5e1;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:0.15rem">Entity Scope</label>
      <select id="company-select">
        <option value="ALL">Vance Hardware Studio [Consolidated]</option>
        <option value="USD">Vance US Operations Inc. [USD]</option>
        <option value="EUR">Vance Europe GmbH [EUR]</option>
        <option value="GBP">Vance UK Logistics Ltd. [GBP]</option>
      </select>
    </div>

    <ul class="erp-nav-list">
      <li><button type="button" class="nav-btn active" data-view="all"><span class="hide-when-collapsed">All Modules (Cockpit)</span><span class="badge badge-indigo">7</span></button></li>
      <li><button type="button" class="nav-btn" data-view="payouts"><span class="hide-when-collapsed">Supplier Payouts (Kit 1)</span><span class="badge badge-neutral">4</span></button></li>
      <li><button type="button" class="nav-btn" data-view="audit"><span class="hide-when-collapsed">Completeness Audit</span><span class="badge badge-amber">21</span></button></li>
      <li><button type="button" class="nav-btn" data-view="incidents"><span class="hide-when-collapsed">Incident Ops (Kit 3)</span><span class="badge badge-err">SWIFT</span></button></li>
      <li><button type="button" class="nav-btn" data-view="visa"><span class="hide-when-collapsed">Visa Cards (Kit 9)</span><span class="badge badge-indigo">VISA</span></button></li>
      <li><button type="button" class="nav-btn" data-view="metal"><span class="hide-when-collapsed">Metal x402 (Kit 11)</span><span class="badge badge-ok">USDZ</span></button></li>
      <li><button type="button" class="nav-btn" data-view="evaluator"><span class="hide-when-collapsed">Bedrock Evaluator</span><span class="badge badge-indigo">AI</span></button></li>
    </ul>

    <div class="sidebar-foot hide-when-collapsed">
      <div class="font-mono" style="color:#f8fafc;font-weight:600">Engine: 74/74 (2ms)</div>
      <div>LLM Baseline: 28/62 (3,400ms)</div>
      <div style="margin-top:0.25rem;color:#94a3b8">Zero-float integer cents core</div>
    </div>
  </aside>

  <div class="erp-canvas">
    <header>
      <div>
        <h1>Archon Treasury (powered by Kerdon)</h1>
        <p class="lede">Archon Treasury recalculates Airwallex FX and supplier payouts when a deposit lands, invalidating stale approvals so cross-border teams never breach their cash reserve floor.</p>
      </div>
      <div class="topnav-controls">
        <span id="roi-strip" class="badge badge-ok font-mono">Protected: USD 2,450.00 &middot; Engine: 1ms</span>
        <a class="cta" href="/api/audit-export.csv" download="archon-treasury-audit.csv">Export Audit CSV</a>
        <button type="button" class="cmdk-trigger" id="cmdk-open" aria-label="Open command menu (Ctrl+K)">
          <span>Quick Command &amp; Search...</span>
          <span class="kbd">Ctrl+K</span>
        </button>
      </div>
    </header>

    <div class="quick-bar" role="region" aria-label="Guided 60-second judge flow">
      <span class="quick-label">Guided 60s Flow:</span>
      <button type="button" class="primary" data-act="quick-approve-both">1. Approve USD &amp; EUR Payouts</button>
      <button type="button" data-act="quick-eur-deposit">2. Land EUR 500.00 Webhook</button>
      <button type="button" data-act="quick-usd-deposit">3. Land USD 200.00 Floor Recovery</button>
      <button type="button" data-act="ai-match">4. Run Evaluator on Invoice</button>
      <button type="button" data-act="visa-issue">5. Issue Single-Use Visa Card</button>
      <button type="button" data-act="metal-dispute">6. Resolve x402 Dispute Batch</button>
    </div>

    <div class="erp-scroll-area">
      <main id="main">
        <div id="status" class="status-banner" role="status" aria-live="polite">Ready. Click Step 1 to approve USD &amp; EUR payouts, then Step 2 to land a EUR 500.00 deposit and watch selective invalidation.</div>

        <section aria-labelledby="bal-h" data-module="payouts" style="background:transparent;border:0;padding:0;margin-bottom:0.5rem">
          <h2 id="bal-h" style="margin-bottom:0.5rem">Multi-Currency Liquidity &amp; Reserve Floors</h2>
          <div class="kpi-grid" id="balances"></div>
        </section>

        <section class="forecast-panel erp-panel" aria-labelledby="fc-h" data-module="payouts">
          <div class="panel-head">
            <h2 id="fc-h">Kit 1: Receipt Forecast Confidence &amp; Autonomous FX Conversion Limit</h2>
            <span class="mono-sm">Airwallex FX Boundary</span>
          </div>
          <div id="forecast-box"></div>
        </section>

        <div class="cockpit-grid">
          <div>
            <section class="erp-panel" aria-labelledby="obl-h" data-module="payouts">
              <div class="panel-head">
                <h2 id="obl-h">Supplier Payouts &amp; Adaptive Triage Plan (72-Hour Window)</h2>
                <span class="mono-sm">Tabular-Nums Alignment &middot; SHA-256 Bound</span>
              </div>
              <div class="scroll-x" role="region" aria-label="Supplier payouts table, scrollable" tabindex="0">
                <table>
                  <thead>
                    <tr>
                      <th>Supplier &amp; Invoice</th>
                      <th>Amount &amp; Rail</th>
                      <th>Agent Triage Plan</th>
                      <th>Approval &amp; Gate Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody id="obligations"></tbody>
                </table>
              </div>
            </section>

            <section class="erp-panel" aria-labelledby="rec-h" data-module="payouts">
              <div class="panel-head">
                <h2 id="rec-h">Cryptographic Merkle Receipt &amp; Refreshable Braille Inspector</h2>
                <span class="mono-sm">Aletheia Verification</span>
              </div>
              <div id="receipt-drawer"></div>
            </section>

            <section class="erp-panel" aria-labelledby="visa-h" data-module="visa">
              <div class="panel-head">
                <h2 id="visa-h">Kit 9: Visa Virtual Commercial Card &amp; MCC Spend Controls</h2>
                <span class="mono-sm">Single-Use Mandate &middot; 150 bps Rebate</span>
              </div>
              <p class="muted-note" style="margin-bottom:0.6rem">Issues a single-use Virtual Visa commercial card for hardware suppliers with deterministic MCC lock (5045 Computers &amp; Peripherals), exact invoice cap, zero wire fee, and automatic post-charge closure.</p>
              <div id="visa-box"></div>
              <div class="btn-row" style="margin-top:0.55rem">
                <button type="button" data-act="visa-issue">1. Issue Single-Use Visa (*4829)</button>
                <button type="button" data-act="visa-wrong-mcc">2. Test Wrong MCC (5812 &rarr; Block)</button>
                <button type="button" class="primary" data-act="visa-valid-charge">3. Authorize Valid PCB Charge (MCC 5045, USD 450.00)</button>
              </div>
            </section>

            <section class="erp-panel" aria-labelledby="metal-h" data-module="metal">
              <div class="panel-head">
                <h2 id="metal-h">Kit 11: Metal x402 USDZ Sub-Agent Spend Governor &amp; Mandate Desk</h2>
                <span class="mono-sm">10,000 Cents Cap</span>
              </div>
              <p class="muted-note" style="margin-bottom:0.6rem">Three sub-agents share a fixed USDZ 100.00 (10000 cents) budget by weight with per-purchase mandate caps. Spike a price or verify a disputed batch of signed customer orders.</p>
              <div class="scroll-x" role="region" aria-label="Metal USDZ budgets table, scrollable" tabindex="0">
                <table>
                  <thead>
                    <tr>
                      <th>Sub-Agent</th>
                      <th>Allowance</th>
                      <th>Price &amp; Mandate Cap</th>
                      <th>Calls Used / Cap</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody id="metal-agents"></tbody>
                </table>
              </div>
              <div style="margin-top:0.75rem" class="btn-row">
                <button type="button" class="primary" data-act="metal-dispute">Verify Signed x402 Disputed Order Batch &amp; Refund Faulty Feed</button>
              </div>
              <div id="dispute-box"></div>
            </section>
          </div>

          <div>
            <section class="erp-panel" aria-labelledby="dep-h" data-module="payouts">
              <div class="panel-head">
                <h2 id="dep-h">Simulate Signed Airwallex Deposit Webhook</h2>
                <span class="mono-sm">HMAC-SHA256</span>
              </div>
              <form class="deposit" id="deposit-form">
                <div>
                  <label for="currency">Currency</label>
                  <select id="currency"><option>EUR</option><option>USD</option><option>GBP</option></select>
                </div>
                <div>
                  <label for="amount">Amount, major units</label>
                  <input id="amount" class="font-mono" inputmode="decimal" value="500.00" required>
                </div>
                <button class="primary" type="submit">Land deposit</button>
                <button type="button" id="reset">Reset demo</button>
              </form>
            </section>

            <section class="erp-panel" aria-labelledby="find-h" data-module="audit">
              <div class="panel-head">
                <h2 id="find-h">Completeness Findings (21 Deterministic Rules)</h2>
                <span class="mono-sm">Zero-LLM Engine</span>
              </div>
              <ul id="findings" class="compact-list"></ul>
            </section>

            <section class="erp-panel" aria-labelledby="ai-h" data-module="evaluator">
              <div class="panel-head">
                <h2 id="ai-h">Evaluator Port: Unstructured Invoice Verification</h2>
                <span class="mono-sm">Claude Haiku 4.5 (Amazon Bedrock)</span>
              </div>
              <p class="muted-note" style="margin-bottom:0.55rem">Edit the raw supplier invoice below or click a preset to invoke Claude Haiku 4.5 on Amazon Bedrock and verify against obligation terms in integer cents.</p>
              <label for="custom-invoice-text">Raw Unstructured Supplier Invoice</label>
              <textarea id="custom-invoice-text" class="font-mono" rows="5" style="width:100%;margin-bottom:0.5rem">INVOICE INV-2026-8841
Supplier: Shenzhen Precision PCB Ltd.
Counterparty: supplier-a
Obligation: obl-usd-1
Total due USD 450.00</textarea>
              <div class="btn-row">
                <button type="button" class="primary" data-act="ai-custom">Inspect Custom Invoice Text (Live Bedrock)</button>
                <button type="button" data-act="ai-match">Preset: Valid (450.00)</button>
                <button type="button" data-act="ai-tamper">Preset: Tampered (495.00)</button>
              </div>
              <div id="ai-box"></div>
            </section>

            <section class="erp-panel" aria-labelledby="inc-h" data-module="incidents">
              <div class="panel-head">
                <h2 id="inc-h">Kit 3: Payment Ops Incident Commander</h2>
                <span class="mono-sm">7-Day Idempotency Lock</span>
              </div>
              <p class="muted-note" style="margin-bottom:0.55rem">Handles a delayed SWIFT supplier wire: transitions SENT to CANCELLED (bank_return) and issues a replacement under a 7-day duplicate lock with two SWIFT fees budgeted.</p>
              <div id="incident-box"></div>
              <div class="btn-row">
                <button type="button" data-act="inc-fail">1. Simulate Bank Return (CANCELLED)</button>
                <button type="button" class="primary" data-act="inc-resolve">2. Issue Replacement Transfer</button>
              </div>
            </section>

            <section class="erp-panel" aria-labelledby="wire-h" data-module="audit">
              <div class="panel-head">
                <h2 id="wire-h">Airwallex &amp; AWS Architecture Boundary</h2>
                <span class="mono-sm">Hexagonal Core</span>
              </div>
              <ul class="compact-list" style="font-size:0.8rem;color:var(--slate-600)">
                <li><strong>Balances &amp; FX:</strong> <code>GET /api/v1/balances/current</code>, <code>POST /api/v1/fx/quotes/create</code>, <code>POST /api/v1/fx/conversions/create</code> (flat EUR 12.85 SWIFT fee vs 0.00 LOCAL).</li>
                <li><strong>Writer Gate:</strong> <code>POST /api/v1/transfers/create</code> with derived <code>uuid5</code> request_id and 7-day idempotency lock.</li>
                <li><strong>Webhooks &amp; Simulation:</strong> HMAC-SHA256 verified deposit and transfer transition webhooks connected to live Airwallex Sandbox (<code>Sandbox Business</code>, IBAN <code>NL81AINH4272955670</code>).</li>
              </ul>
            </section>
          </div>
        </div>
      </main>
      <footer>
        <p>Amounts speak in major units with integer cents beside them so the number Elena hears on a screen reader is the exact number the Airwallex boundary receives.</p>
      </footer>
    </div>
  </div>
</div>

<div class="cmdk-backdrop" id="cmdk-modal" role="dialog" aria-modal="true" aria-label="Global Command Menu">
  <div class="cmdk-dialog">
    <div class="cmdk-head">
      <input type="search" id="cmdk-input" placeholder="Type a command or search obligations (e.g. EUR, Bedrock, Visa, x402, SWIFT)..." aria-label="Search commands">
      <button type="button" id="cmdk-close">Esc</button>
    </div>
    <ul class="cmdk-list" id="cmdk-list"></ul>
  </div>
</div>
"""
    + UI_SCRIPT
    + "\n</body>\n</html>\n"
)
