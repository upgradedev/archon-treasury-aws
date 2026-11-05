"""Enterprise Treasury Cockpit HTML for the anonymous judge surface.

Built for zero-install delivery from AWS Lambda Function URL and local HTTP:
- Semantic landmarks (<header>, <main>, <footer>), skip link, single <h1>
- WCAG AAA high-contrast tokens and aria-live="polite" status region
- Responsive 2-column cockpit at 1280px, 1-column stack at 375px (0 overflow)
- Complete Kit 1 (Adaptive Treasury Controller), Kit 3 (Payment Ops Incident
  Commander), and Kit 11 (Metal x402 Business Agents) interactive controls.
"""

from archon_demo.ui_script import UI_SCRIPT

PAGE = (
    """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Archon Treasury (powered by Kerdon) | Autonomous Treasury OS</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='6' fill='%230f172a'/><text x='8' y='23' font-family='sans-serif' font-size='20' font-weight='bold' fill='%2338bdf8'>A</text></svg>">
<style>
  :root {
    color-scheme: light;
    --bg: #f1f5f9;
    --surface: #ffffff;
    --navy: #0f172a;
    --navy-sub: #1e293b;
    --fg: #0f172a;
    --muted: #334155;
    --border: #cbd5e1;
    --accent: #1d4ed8;
    --accent-hover: #1e40af;
    --ok-bg: #ecfdf5;
    --ok-fg: #065f46;
    --ok-bd: #6ee7b7;
    --err-bg: #fef2f2;
    --err-fg: #991b1b;
    --err-bd: #fca5a5;
    --amber-bg: #fffbeb;
    --amber-fg: #92400e;
    --amber-bd: #fcd34d;
    --indigo-bg: #eef2ff;
    --indigo-fg: #1e40af;
    --indigo-bd: #a5b4fc;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--fg);
    font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Inter, sans-serif;
    overflow-x: hidden;
  }
  .skip {
    position: absolute; left: 0.5rem; top: -10rem;
    background: #ffffff; color: var(--fg); padding: 0.5rem 0.85rem;
    border: 2px solid var(--accent); border-radius: 6px; z-index: 100;
  }
  .skip:focus { top: 0.5rem; }
  header {
    background: var(--navy);
    color: #f8fafc;
    padding: 1.25rem 1.25rem 1rem;
    border-bottom: 1px solid #334155;
  }
  .header-inner {
    max-width: 1240px;
    margin: 0 auto;
  }
  .brand-row {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: center;
    gap: 0.75rem;
  }
  h1 {
    font-size: 1.45rem;
    margin: 0;
    letter-spacing: -0.01em;
    color: #ffffff;
  }
  .telemetry-strip {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
  }
  .tel-pill {
    background: var(--navy-sub);
    color: #e2e8f0;
    border: 1px solid #475569;
    padding: 0.2rem 0.6rem;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 600;
  }
  .lede {
    margin: 0.55rem 0 0.75rem;
    color: #e2e8f0;
    max-width: 920px;
    font-size: 0.96rem;
  }
  .quick-bar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
    background: var(--navy-sub);
    border: 1px solid #475569;
    border-radius: 8px;
    padding: 0.55rem 0.75rem;
  }
  .quick-bar span {
    font-size: 0.82rem;
    font-weight: 600;
    color: #f8fafc;
  }
  .cta {
    display: inline-block;
    background: #38bdf8;
    color: #0f172a;
    text-decoration: none;
    padding: 0.35rem 0.75rem;
    border-radius: 6px;
    font-weight: 700;
    font-size: 0.84rem;
  }
  main {
    max-width: 1240px;
    margin: 0 auto;
    padding: 1rem 1.25rem 2rem;
  }
  .status-banner {
    padding: 0.7rem 0.95rem;
    border-radius: 8px;
    margin-bottom: 1rem;
    font-weight: 600;
    border: 1px solid var(--ok-bd);
    background: var(--ok-bg);
    color: var(--ok-fg);
  }
  .status-banner.err {
    border-color: var(--err-bd);
    background: var(--err-bg);
    color: var(--err-fg);
  }
  .kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 0.85rem;
    margin-bottom: 1rem;
  }
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 0.95rem 1.1rem;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  }
  .card-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.3rem;
  }
  .acct-tag {
    font-size: 0.76rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    color: var(--accent);
  }
  .mono-sm {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 0.8rem;
    color: var(--muted);
  }
  .big-num {
    font-size: 1.22rem;
    font-weight: 700;
    margin-bottom: 0.45rem;
  }
  .meter-bar {
    height: 8px;
    background: #e2e8f0;
    border-radius: 999px;
    overflow: hidden;
    margin-bottom: 0.45rem;
  }
  .meter-fill {
    height: 100%;
    background: var(--accent);
    border-radius: 999px;
  }
  .card-foot {
    display: flex;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 0.35rem;
    font-size: 0.82rem;
    color: var(--muted);
  }
  .forecast-panel {
    margin-bottom: 1rem;
  }
  .forecast-row {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: center;
    gap: 0.6rem;
  }
  .cockpit-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.65fr) minmax(0, 1fr);
    gap: 1rem;
    align-items: start;
  }
  @media (max-width: 980px) {
    .cockpit-grid { grid-template-columns: 1fr; }
  }
  section {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1rem 1.1rem;
    margin-bottom: 1rem;
  }
  h2 {
    font-size: 1.05rem;
    margin: 0 0 0.65rem;
    color: var(--fg);
  }
  .scroll-x {
    overflow-x: auto;
    max-width: 100%;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
  }
  th, td {
    text-align: left;
    padding: 0.6rem 0.5rem;
    border-bottom: 1px solid #e2e8f0;
    vertical-align: top;
  }
  th {
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--muted);
    background: #f8fafc;
  }
  .sup-title { font-weight: 700; color: var(--fg); }
  .sup-sub { font-size: 0.8rem; color: var(--muted); margin-top: 0.18rem; }
  .amt-main { font-weight: 700; white-space: nowrap; }
  .rail-pill {
    display: inline-block;
    background: #e2e8f0;
    color: var(--fg);
    padding: 0.05rem 0.4rem;
    border-radius: 4px;
    font-weight: 700;
    font-size: 0.72rem;
  }
  .badge {
    display: inline-block;
    padding: 0.15rem 0.5rem;
    border-radius: 999px;
    font-size: 0.74rem;
    font-weight: 700;
    border: 1px solid transparent;
    white-space: nowrap;
  }
  .badge-ok { background: var(--ok-bg); color: var(--ok-fg); border-color: var(--ok-bd); }
  .badge-err { background: var(--err-bg); color: var(--err-fg); border-color: var(--err-bd); }
  .badge-amber { background: var(--amber-bg); color: var(--amber-fg); border-color: var(--amber-bd); }
  .badge-indigo { background: var(--indigo-bg); color: var(--indigo-fg); border-color: var(--indigo-bd); }
  .badge-neutral { background: #f1f5f9; color: var(--muted); border-color: var(--border); }
  button, select, input {
    font: inherit;
    font-size: 0.85rem;
    padding: 0.4rem 0.7rem;
    border: 1px solid #64748b;
    border-radius: 6px;
    background: #ffffff;
    color: var(--fg);
  }
  button {
    cursor: pointer;
    font-weight: 600;
  }
  button:hover { background: #f1f5f9; }
  button.primary {
    background: var(--accent);
    color: #ffffff;
    border-color: var(--accent);
  }
  button.primary:hover { background: var(--accent-hover); }
  button:focus-visible, select:focus-visible, input:focus-visible, a:focus-visible {
    outline: 3px solid var(--accent);
    outline-offset: 2px;
  }
  .btn-col { display: flex; flex-direction: column; gap: 0.35rem; }
  .btn-row { display: flex; flex-wrap: wrap; gap: 0.4rem; }
  .deposit {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    align-items: end;
  }
  label {
    display: block;
    font-weight: 600;
    font-size: 0.82rem;
    margin-bottom: 0.2rem;
  }
  code {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 0.82em;
    background: #f1f5f9;
    padding: 0.1rem 0.3rem;
    border-radius: 4px;
    word-break: break-all;
  }
  .receipt-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 0.65rem;
    background: #f8fafc;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.75rem;
  }
  .full-span { grid-column: 1 / -1; }
  .kv-label { font-size: 0.76rem; font-weight: 700; color: var(--muted); text-transform: uppercase; }
  .kv-val { font-size: 0.88rem; margin-top: 0.15rem; }
  .kv-grid { display: grid; gap: 0.35rem; font-size: 0.88rem; margin-bottom: 0.65rem; }
  .finding-item { margin-bottom: 0.45rem; font-size: 0.88rem; }
  .sub-card {
    background: #f8fafc;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.65rem 0.8rem;
    margin-top: 0.6rem;
    font-size: 0.85rem;
  }
  .code-preview {
    background: #0f172a;
    color: #f8fafc;
    padding: 0.55rem 0.75rem;
    border-radius: 6px;
    font-size: 0.78rem;
    overflow-x: auto;
    margin: 0.45rem 0 0;
  }
  .compact-list { margin: 0.4rem 0 0; padding-left: 1.2rem; }
  .muted-note { color: var(--muted); font-size: 0.85rem; margin: 0; }
  footer {
    max-width: 1240px;
    margin: 0 auto;
    padding: 0 1.25rem 2rem;
    color: var(--muted);
    font-size: 0.85rem;
  }
</style>
</head>
<body>
<a class="skip" href="#main">Skip to main content</a>
<header>
  <div class="header-inner">
    <div class="brand-row">
      <h1>Archon Treasury (powered by Kerdon)</h1>
      <div class="telemetry-strip">
        <span class="tel-pill">Vance Hardware Studio Ltd. (72h Close)</span>
        <span class="tel-pill">Engine: 74/74 (2ms) vs LLM: 28/62</span>
        <span class="tel-pill">21 Completeness Rules</span>
        <span class="tel-pill">Metal *USDZ x402</span>
      </div>
    </div>
    <p class="lede">Archon Treasury recalculates Airwallex FX and supplier payouts when a deposit lands, invalidating stale approvals so cross-border teams never breach their cash reserve floor.</p>
    <div class="quick-bar">
      <span>Guided 60s Judge Flow:</span>
      <a class="cta" href="#obl-h">1. Approve USD &amp; EUR Payouts</a>
      <button type="button" data-act="quick-eur-deposit">2. Land EUR 500.00 Webhook</button>
      <button type="button" data-act="quick-usd-deposit">3. Land USD 200.00 Floor Recovery</button>
      <button type="button" data-act="ai-match">4. Run Evaluator on Invoice</button>
      <button type="button" data-act="metal-dispute">5. Resolve x402 Dispute Batch</button>
    </div>
  </div>
</header>
<main id="main">
  <div id="status" class="status-banner" role="status" aria-live="polite">Ready. Approve a USD payout and a EUR payout, then land a EUR 500.00 deposit to watch selective invalidation.</div>

  <section aria-labelledby="bal-h" style="background:transparent;border:0;padding:0;margin-bottom:0.5rem">
    <h2 id="bal-h" style="margin-bottom:0.5rem">Multi-Currency Liquidity &amp; Reserve Floors</h2>
    <div class="kpi-grid" id="balances"></div>
  </section>

  <section class="forecast-panel" aria-labelledby="fc-h">
    <h2 id="fc-h">Kit 1: Receipt Forecast Confidence &amp; Autonomous FX Conversion Limit</h2>
    <div id="forecast-box"></div>
  </section>

  <div class="cockpit-grid">
    <div>
      <section aria-labelledby="obl-h">
        <h2 id="obl-h">Supplier Payouts &amp; Adaptive Triage Plan (72-Hour Window)</h2>
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

      <section aria-labelledby="rec-h">
        <h2 id="rec-h">Cryptographic Merkle Receipt &amp; Refreshable Braille Inspector</h2>
        <div id="receipt-drawer"></div>
      </section>

      <section aria-labelledby="metal-h">
        <h2 id="metal-h">Kit 11: Metal x402 USDZ Sub-Agent Spend Governor &amp; Mandate Desk</h2>
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
      <section aria-labelledby="dep-h">
        <h2 id="dep-h">Simulate Signed Airwallex Deposit Webhook</h2>
        <form class="deposit" id="deposit-form">
          <div>
            <label for="currency">Currency</label>
            <select id="currency"><option>EUR</option><option>USD</option><option>GBP</option></select>
          </div>
          <div>
            <label for="amount">Amount, major units</label>
            <input id="amount" inputmode="decimal" value="500.00" required>
          </div>
          <button class="primary" type="submit">Land deposit</button>
          <button type="button" id="reset">Reset demo</button>
        </form>
      </section>

      <section aria-labelledby="find-h">
        <h2 id="find-h">Completeness Findings (21 Deterministic Rules)</h2>
        <ul id="findings" class="compact-list"></ul>
      </section>

      <section aria-labelledby="ai-h">
        <h2 id="ai-h">Evaluator Port: Unstructured Invoice Verification</h2>
        <p class="muted-note" style="margin-bottom:0.55rem">Extracts invoice fields (Claude Haiku on Amazon Bedrock when live, deterministic stand-in offline) and compares against obligation terms in integer cents.</p>
        <div class="btn-row">
          <button type="button" class="primary" data-act="ai-match">Inspect Valid Invoice (USD 450.00)</button>
          <button type="button" data-act="ai-tamper">Inspect Tampered Invoice (USD 495.00)</button>
        </div>
        <div id="ai-box"></div>
      </section>

      <section aria-labelledby="inc-h">
        <h2 id="inc-h">Kit 3: Payment Ops Incident Commander</h2>
        <p class="muted-note" style="margin-bottom:0.55rem">Handles a delayed SWIFT supplier wire: transitions SENT to CANCELLED (bank_return) and issues a replacement under a 7-day duplicate lock with two SWIFT fees budgeted.</p>
        <div id="incident-box"></div>
        <div class="btn-row">
          <button type="button" data-act="inc-fail">1. Simulate Bank Return (CANCELLED)</button>
          <button type="button" class="primary" data-act="inc-resolve">2. Issue Replacement Transfer</button>
        </div>
      </section>

      <section aria-labelledby="wire-h">
        <h2 id="wire-h">Airwallex &amp; AWS Architecture Boundary</h2>
        <ul class="compact-list" style="font-size:0.84rem;color:var(--muted)">
          <li><strong>Balances &amp; FX:</strong> <code>GET /api/v1/balances/current</code>, <code>POST /api/v1/fx/quotes/create</code>, <code>POST /api/v1/fx/conversions/create</code> (flat EUR 12.85 SWIFT fee vs 0.00 LOCAL).</li>
          <li><strong>Writer Gate:</strong> <code>POST /api/v1/transfers/create</code> with derived <code>uuid5</code> request_id and 7-day idempotency lock.</li>
          <li><strong>Webhooks &amp; Simulation:</strong> HMAC-SHA256 verified deposit and transfer transition webhooks (synthetic transport active until O-2 sandbox keys connect).</li>
        </ul>
      </section>
    </div>
  </div>
</main>
<footer>
  <p>Amounts speak in major units with integer cents beside them so the number Elena hears on a screen reader is the exact number the Airwallex boundary receives.</p>
</footer>
"""
    + UI_SCRIPT
    + "\n</body>\n</html>\n"
)
