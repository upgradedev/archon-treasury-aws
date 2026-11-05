"""The single judge page. Landmarks, native controls, visible reasons.

Design constraints honored: plain hierarchy, system serif headings with a
system sans body, deep teal accent, no gradients, no animation, focus
outlines always visible, works at 375px and 1280px, results announced in
an aria-live region, and every blocked action explains itself in text.
"""

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Archon Treasury, payout approval demo</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Crect width='16' height='16' fill='%230f5f5c'/%3E%3Ctext x='8' y='12' font-size='10' text-anchor='middle' fill='white'%3EA%3C/text%3E%3C/svg%3E">
<style>
  :root { --ink:#17201d; --accent:#0f5f5c; --line:#c9d4d0; --bad:#8c2b1d; }
  * { box-sizing:border-box; }
  html { max-width:100vw; }
  body { margin:0; color:var(--ink); background:#ffffff; overflow-x:hidden;
         font-family:-apple-system,"Segoe UI",Helvetica,sans-serif; line-height:1.5; }
  header, main, footer { max-width:980px; width:100%; margin:0 auto; padding:20px 16px; }
  h1,h2 { font-family:Georgia,"Times New Roman",serif; line-height:1.2; }
  h1 { font-size:2rem; margin:0 0 8px; } h2 { font-size:1.3rem; margin:28px 0 8px; }
  .lede { font-size:1.1rem; max-width:46rem; }
  .mode { border:1px solid var(--line); padding:10px 12px; background:#f2f6f4; }
  .skip { position:absolute; left:-9999px; top:0; background:#ffffff; padding:10px 14px; z-index:2; }
  .skip:focus-visible { left:8px; }
  .scroll-x { overflow-x:auto; max-width:100%; }
  table { border-collapse:collapse; width:100%; }
  th,td { border-bottom:1px solid var(--line); padding:8px 6px; text-align:left; vertical-align:top; }
  th { font-size:.85rem; text-transform:uppercase; letter-spacing:.04em; }
  button { font:inherit; padding:8px 14px; margin:2px 4px 2px 0; cursor:pointer;
           border:2px solid var(--accent); background:#ffffff; color:var(--accent); border-radius:4px; }
  button.primary { background:var(--accent); color:#ffffff; }
  a.cta { display:inline-block; padding:10px 16px; border:2px solid var(--accent);
          background:var(--accent); color:#ffffff; border-radius:4px; text-decoration:none; font-weight:700; }
  button:focus-visible, a:focus-visible, summary:focus-visible { outline:3px solid var(--accent); outline-offset:2px; }
  .state-VALID { color:var(--accent); font-weight:700; }
  .state-INVALIDATED, .err { color:var(--bad); font-weight:700; }
  .reason { display:block; font-size:.9rem; }
  #status { min-height:1.6em; border:1px solid var(--line); padding:10px 12px; background:#f2f6f4; }
  form.deposit { display:flex; flex-wrap:wrap; gap:8px; align-items:end; }
  label { display:block; font-size:.9rem; font-weight:600; }
  input,select { font:inherit; padding:8px; border:1px solid var(--line); border-radius:4px; }
  pre { white-space:pre-wrap; word-break:break-all; background:#f2f6f4; padding:10px; }
  code { word-break:break-all; }
  @media (max-width:640px) {
    h1 { font-size:1.6rem; }
    th,td { padding:6px 4px; font-size:.85rem; word-break:break-word; }
    button { padding:6px 8px; }
  }
  @media (prefers-reduced-motion: reduce) { * { transition:none; animation:none; } }
</style>
</head>
<body>
<a class="skip" href="#main">Skip to the demo</a>
<header>
  <h1>Archon Treasury</h1>
  <p class="lede">Archon Treasury recalculates Airwallex FX and supplier payouts when a
  deposit lands, invalidating stale approvals so cross-border teams never breach
  their cash reserve floor.</p>
  <p>For Elena Vance, Finance and Operations Manager at a 14-person cross-border
  hardware studio. Five supplier payouts, three currencies, 72 hours.</p>
  <p class="mode" role="note">Anonymous demo with synthetic data on a fake Airwallex
  transport. No live money moves. Live sandbox wiring follows sandbox approval.
  Your demo state is yours alone: each visitor gets a private session that
  resets often. The rules, digests, and receipts below are the real
  deterministic core. Measured in the repo: 74 of 74 frozen benchmark cases
  for this engine, 24 of 74 for a naive one-pass matcher, and 28 of 62 for a
  hosted Claude model alone on the rule cases. Reproduce with
  <code>python scripts/run_benchmark.py</code>.</p>
  <p><a class="cta" href="#obl-h">Start the 60-second story</a></p>
</header>
<main id="main">
  <section aria-labelledby="try-h">
    <h2 id="try-h">Try the 60-second story</h2>
    <ol>
      <li>Approve two payouts, one in USD and one in EUR.</li>
      <li>Land a EUR deposit with the form below. Only the EUR approval falls.</li>
      <li>Execute the USD payout. Then try the stale EUR one and read why it refuses.</li>
    </ol>
    <div id="status" role="status" aria-live="polite">Loading balances.</div>
  </section>
  <section aria-labelledby="bal-h">
    <h2 id="bal-h">Balances and reserve floors</h2>
    <div class="scroll-x" role="region" aria-label="Balances table, scrollable" tabindex="0">
    <table><thead><tr><th>Account</th><th>Balance</th><th>Reserve floor</th></tr></thead>
    <tbody id="balances"></tbody></table></div>
  </section>
  <section aria-labelledby="obl-h">
    <h2 id="obl-h">Supplier payouts</h2>
    <div class="scroll-x" role="region" aria-label="Supplier payouts table, scrollable" tabindex="0">
    <table><thead><tr><th>Payout</th><th>Amount</th><th>Approval</th><th>Actions</th></tr></thead>
    <tbody id="obligations"></tbody></table></div>
  </section>
  <section aria-labelledby="dep-h">
    <h2 id="dep-h">Simulate an incoming deposit</h2>
    <form class="deposit" id="deposit-form">
      <div><label for="currency">Currency</label>
        <select id="currency"><option>EUR</option><option>USD</option><option>GBP</option></select></div>
      <div><label for="amount">Amount, major units</label>
        <input id="amount" inputmode="decimal" value="500.00" required></div>
      <button class="primary" type="submit">Land deposit</button>
      <button type="button" id="reset">Reset demo</button>
    </form>
  </section>
  <section aria-labelledby="find-h">
    <h2 id="find-h">Completeness findings, 21 deterministic rules</h2>
    <ul id="findings"></ul>
  </section>
  <section aria-labelledby="metal-h">
    <h2 id="metal-h">Metal x402 USDZ sub-agent spend governor</h2>
    <p>Three sub-agents share a fixed USDZ 100.00 (10000 cents) budget by weight. When a per-call price rises, only that sub-agent's call cap shrinks.</p>
    <div class="scroll-x" role="region" aria-label="Metal USDZ budgets table, scrollable" tabindex="0">
    <table><thead><tr><th>Sub-agent</th><th>Allowance</th><th>Price per call</th><th>Calls used / cap</th><th>Actions</th></tr></thead>
    <tbody id="metal-agents"></tbody></table></div>
  </section>
  <section aria-labelledby="wire-h">
    <h2 id="wire-h">Live wiring map, coded and waiting for sandbox keys</h2>
    <ul>
      <li>Balances and quotes: <code>GET /api/v1/balances</code>, <code>POST /api/v1/fx/quotes/create</code> (coded, not connected).</li>
      <li>Payouts: <code>POST /api/v1/transfers/create</code> with a derived request_id, only through the Writer gate (coded, not connected).</li>
      <li>Trigger: signed deposit webhooks, HMAC verified, plus <code>POST /api/v1/simulation/deposit/create</code> for sandbox funding (coded, not connected).</li>
      <li>Evaluator: Claude on Amazon Bedrock extracts invoice fields; deterministic code still decides. Verified live from the repo, kept off this public page so anonymous clicks cannot spend model tokens.</li>
    </ul>
  </section>
</main>
<footer><p>Amounts speak in major units with cents beside them, so the number you hear
is the number the bank boundary receives.</p></footer>
<script>
const statusBox = document.getElementById('status');
function say(text, isError) {
  statusBox.textContent = text; statusBox.className = isError ? 'err' : '';
}
async function call(path, body) {
  const res = await fetch(path, {method: body ? 'POST' : 'GET',
    headers: {'Content-Type': 'application/json'}, body: body ? JSON.stringify(body) : undefined});
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || ('HTTP ' + res.status));
  return data;
}
function esc(s) { return String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
async function render() {
  const s = await call('/api/state');
  document.getElementById('balances').innerHTML = s.balances.map(b =>
    `<tr><td>${esc(b.account_id)}</td><td>${esc(b.amount)}</td><td>${esc(b.reserve_floor)}</td></tr>`).join('');
  document.getElementById('obligations').innerHTML = s.obligations.map(o => `
    <tr><td>${esc(o.obligation_id)} to ${esc(o.counterparty_id)}</td><td>${esc(o.amount)}</td>
    <td><span class="state-${esc(o.approval_state)}">${esc(o.approval_state)}</span>
      <span class="reason">${esc(o.action_reason)}</span>
      ${o.receipt ? `<details><summary>Spoken receipt, Merkle sealed</summary>
        <p aria-label="${esc(o.receipt.spoken_text)}">${esc(o.receipt.spoken_text)}</p>
        <pre>${esc(o.receipt.braille_transcript)}</pre>
        <p>Root ${esc(o.receipt.merkle_root_sha256)} verified: ${o.receipt.merkle_verified}</p></details>` : ''}
    </td>
    <td><button data-act="approve" data-id="${esc(o.obligation_id)}">Approve</button>
        <button class="primary" data-act="execute" data-id="${esc(o.obligation_id)}" data-sha="${esc(o.approval_sha256 || '')}">Execute</button></td></tr>`).join('');
  document.getElementById('findings').innerHTML = s.findings.length
    ? s.findings.map(f => `<li>${esc(f.rule_id)} ${esc(f.message)}</li>`).join('')
    : '<li>No blockers on current evidence.</li>';
  document.getElementById('metal-agents').innerHTML = (s.metal_agents || []).map(m => `
    <tr><td>${esc(m.agent_id)} (${esc(m.weight_percent)}%)</td><td>${esc(m.allowance)}</td><td>${esc(m.price_per_call)}</td>
    <td>${esc(m.calls_used)} / ${esc(m.call_cap)} (spent ${esc(m.spent)})</td>
    <td><button data-metal-call="${esc(m.agent_id)}">Pay 1 call</button>
        <button data-metal-spike="${esc(m.agent_id)}">Spike to 0.50</button></td></tr>`).join('');
  document.querySelectorAll('button[data-act]').forEach(btn => btn.onclick = async () => {
    say('Working. One moment.');
    try {
      const payload = (btn.dataset.act === 'execute' && btn.dataset.sha) ? {approval_sha256: btn.dataset.sha} : {};
      const r = await call(`/api/${btn.dataset.act}/${btn.dataset.id}`, payload);
      if (btn.dataset.act === 'approve') say(`Approved ${r.obligation_id}. Its spoken receipt is sealed in the table.`);
      else say(`Paid ${r.obligation_id}. Transfer ${r.transfer_id} sent.`);
    } catch (e) { say(`Refused: ${e.message}`, true); }
    await render();
  });
  document.querySelectorAll('button[data-metal-call]').forEach(btn => btn.onclick = async () => {
    try {
      const r = await call(`/api/metal-call/${btn.dataset.metalCall}`, {});
      say(`Metal x402 call paid for ${r.agent_id} (${r.tx_id}). Used ${r.calls_used} of ${r.call_cap}.`);
    } catch (e) { say(`Refused: ${e.message}`, true); }
    await render();
  });
  document.querySelectorAll('button[data-metal-spike]').forEach(btn => btn.onclick = async () => {
    try {
      const r = await call('/api/metal-rebalance', {agent_id: btn.dataset.metalSpike, new_price: '0.50'});
      say(`Rebalanced ${r.agent_id} price to ${r.new_price}. Only its call cap changed.`);
    } catch (e) { say(`Refused: ${e.message}`, true); }
    await render();
  });
}
document.getElementById('deposit-form').onsubmit = async (ev) => {
  ev.preventDefault();
  say('Working. One moment.');
  try {
    const r = await call('/api/simulate-deposit',
      {currency: document.getElementById('currency').value, amount: document.getElementById('amount').value});
    say(`Deposit landed: ${r.amount}. Invalidated: ${r.invalidated.join(', ') || 'none'}. Still valid: ${r.still_valid.join(', ') || 'none'}.`);
  } catch (e) { say(`Refused: ${e.message}`, true); }
  await render();
};
document.getElementById('reset').onclick = async () => { await call('/api/reset', {}); say('Demo reset.'); await render(); };
render().then(() => say('Ready. Approve a USD and a EUR payout to begin.'));
</script>
</body>
</html>
"""
