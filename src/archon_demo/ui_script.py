"""Client-side controller for the Archon Treasury High-Density ERP Cockpit."""

UI_SCRIPT = """<script>
const statusBox = document.getElementById('status');
let lastState = null;
let selectedReceiptId = null;
let activeEntityScope = 'ALL';

function say(text, isError) {
  statusBox.textContent = text;
  statusBox.className = isError ? 'status-banner err' : 'status-banner ok';
}

async function call(path, body) {
  const res = await fetch(path, {
    method: body ? 'POST' : 'GET',
    headers: {'Content-Type': 'application/json'},
    body: body ? JSON.stringify(body) : undefined
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || ('HTTP ' + res.status));
  return data;
}

function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => (
    {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]
  ));
}

function planBadge(action) {
  const map = {
    'FUND_NOW': ['badge-ok', 'FUND NOW'],
    'CONVERT_FX': ['badge-indigo', 'CONVERT FX + FEE'],
    'DEFER': ['badge-amber', 'DEFER (FLOOR GUARD)'],
    'ESCALATE': ['badge-err', 'ESCALATE'],
    'SETTLED': ['badge-neutral', 'SETTLED']
  };
  const [cls, label] = map[action] || ['badge-neutral', action];
  return `<span class="badge ${cls}">${esc(label)}</span>`;
}

function stateBadge(st) {
  const map = {
    'VALID': ['badge-ok', 'APPROVED (VALID)'],
    'INVALIDATED': ['badge-err', 'STALE (INVALIDATED)'],
    'PAID': ['badge-indigo', 'PAID (SETTLED)'],
    'NOT_APPROVED': ['badge-neutral', 'AWAITING APPROVAL']
  };
  const [cls, label] = map[st] || ['badge-neutral', st];
  return `<span class="badge ${cls}">${esc(label)}</span>`;
}

function renderReceiptDrawer(s) {
  const box = document.getElementById('receipt-drawer');
  const obls = s.obligations || [];
  let target = obls.find(o => o.obligation_id === selectedReceiptId && o.receipt);
  if (!target) target = obls.find(o => o.receipt);
  if (!target || !target.receipt) {
    box.innerHTML = `<p class="muted-note">Approve any supplier payout above to generate a Merkle-sealed spoken receipt and refreshable Braille display transcript.</p>`;
    return;
  }
  selectedReceiptId = target.obligation_id;
  const r = target.receipt;
  box.innerHTML = `
    <div class="receipt-grid">
      <div>
        <div class="kv-label">Payout &amp; Supplier</div>
        <div class="kv-val">${esc(target.supplier_name)} (<code>${esc(target.obligation_id)}</code>) &middot; <span class="font-mono">${esc(target.amount)}</span></div>
      </div>
      <div>
        <div class="kv-label">Merkle Root SHA-256 (Verified: ${r.merkle_verified ? 'YES' : 'NO'})</div>
        <div class="kv-val"><code>${esc(r.merkle_root_sha256)}</code></div>
      </div>
      <div class="full-span">
        <div class="kv-label">Spoken Screen-Reader Transcript (Aletheia)</div>
        <div class="kv-val">${esc(r.spoken_text)}</div>
      </div>
      <div class="full-span">
        <div class="kv-label">Refreshable Braille Display Transcript (ASCII + Unicode Braille)</div>
        <div class="kv-val"><code>${esc(r.braille_transcript)}</code></div>
      </div>
    </div>`;
}

function render(s) {
  lastState = s;
  const filteredBalances = activeEntityScope === 'ALL'
    ? s.balances
    : s.balances.filter(b => b.currency === activeEntityScope);

  document.getElementById('balances').innerHTML = filteredBalances.map(b => {
    const pct = b.amount_cents > 0 ? Math.min(100, Math.round((b.reserve_floor_cents / b.amount_cents) * 100)) : 100;
    const headroomPct = Math.max(0, 100 - pct);
    return `
      <div class="card kpi-card">
        <div class="card-top">
          <span class="acct-tag">${esc(b.currency)} WALLET</span>
          <span class="mono-sm">${esc(b.account_id)}</span>
        </div>
        <div class="big-num font-mono tabular-nums">${esc(b.amount)}</div>
        <div class="meter-bar" role="img" aria-label="${esc(b.currency)} reserve floor utilization">
          <div class="meter-fill" style="width:${headroomPct}%"></div>
        </div>
        <div class="card-foot">
          <span>Reserve floor: <strong class="font-mono">${esc(b.reserve_floor)}</strong></span>
          <span>Spendable: <strong class="font-mono">${esc(b.headroom_major)}</strong></span>
        </div>
      </div>`;
  }).join('');

  if (s.forecast) {
    const fc = s.forecast;
    const fcEl = document.getElementById('forecast-box');
    const badgeCls = fc.contradicted_by_email ? 'badge-err' : 'badge-ok';
    const badgeTxt = fc.contradicted_by_email ? 'LOW CONFIDENCE (EMAIL CONTRADICTION)' : 'HIGH CONFIDENCE (VERIFIED)';
    fcEl.innerHTML = `
      <div class="forecast-row">
        <div>
          <span class="badge ${badgeCls}">${badgeTxt}</span>
          <strong class="font-mono" style="margin-left:0.5rem">Confidence: ${fc.confidence_pct}% (${fc.confidence_bps} bps)</strong>
          <span class="mono-sm" style="margin-left:0.5rem">Autonomous FX Limit: ${esc(fc.autonomous_limit)}</span>
        </div>
        <div class="btn-row">
          <button type="button" data-act="email-contradict">Simulate Contradicting Customer Email</button>
          <button type="button" data-act="email-restore">Restore Forecast Confidence</button>
        </div>
      </div>
      <p class="muted-note" style="margin:0.35rem 0 0">${esc(fc.reason)}</p>`;
  }

  const filteredObls = activeEntityScope === 'ALL'
    ? s.obligations
    : s.obligations.filter(o => o.currency === activeEntityScope);

  document.getElementById('obligations').innerHTML = filteredObls.map(o => {
    const shaShort = o.approval_sha256 ? o.approval_sha256.slice(0, 12) : '';
    const inspectBtn = o.receipt
      ? `<button type="button" data-act="inspect-receipt" data-id="${esc(o.obligation_id)}">Receipt</button>`
      : '';
    return `<tr>
      <td>
        <div class="sup-title">${esc(o.supplier_name)}</div>
        <div class="sup-sub"><code>${esc(o.obligation_id)}</code> &middot; ${esc(o.invoice_ref)} &middot; ${esc(o.summary)}</div>
      </td>
      <td>
        <div class="amt-main font-mono tabular-nums">${esc(o.amount)}</div>
        <div class="sup-sub"><span class="rail-pill">${esc(o.rail)}</span> Fee: <span class="font-mono">${esc(o.rail_fee)}</span></div>
      </td>
      <td>
        ${planBadge(o.plan_action)}
        <div class="sup-sub">${esc(o.plan_rationale)}</div>
      </td>
      <td>
        ${stateBadge(o.approval_state)}
        ${shaShort ? `<div class="sup-sub">SHA-256: <code>${esc(shaShort)}</code></div>` : ''}
        <div class="sup-sub">${esc(o.action_reason)}</div>
      </td>
      <td>
        <div class="btn-col">
          <button type="button" data-act="approve" data-id="${esc(o.obligation_id)}">Approve</button>
          <button type="button" class="primary" data-act="execute" data-id="${esc(o.obligation_id)}" data-sha="${esc(o.approval_sha256 || '')}">Execute</button>
          ${inspectBtn}
        </div>
      </td>
    </tr>`;
  }).join('');

  renderReceiptDrawer(s);

  const fl = document.getElementById('findings');
  fl.innerHTML = s.findings.length
    ? s.findings.map(f => {
        const cls = f.severity === 'BLOCKER' ? 'badge-err' : 'badge-amber';
        return `<li class="finding-item"><span class="badge ${cls}">${esc(f.rule_id)} &middot; ${esc(f.severity)}</span> <strong>${esc(f.subject_id)}</strong>: ${esc(f.message)}</li>`;
      }).join('')
    : '<li class="finding-item">No completeness gaps detected across 21 deterministic rules.</li>';

  const ml = document.getElementById('metal-agents');
  if (ml && s.metal_agents) {
    ml.innerHTML = s.metal_agents.map(a => `<tr>
      <td><strong>${esc(a.agent_id)}</strong><div class="sup-sub font-mono">Share: ${a.weight_percent}%</div></td>
      <td class="font-mono">${esc(a.allowance)}</td>
      <td class="font-mono">${esc(a.price_per_call)}<div class="sup-sub">Mandate cap: ${a.max_price_per_call_cents ? a.max_price_per_call_cents + ' cents' : 'none'}</div></td>
      <td class="font-mono"><strong>${a.calls_used} / ${a.call_cap}</strong><div class="sup-sub">Spent: ${esc(a.spent)}</div></td>
      <td>
        <div class="btn-row">
          <button type="button" data-act="metal-call" data-id="${esc(a.agent_id)}">Pay 1 call</button>
          <button type="button" data-act="metal-spike" data-id="${esc(a.agent_id)}">Spike to 0.50</button>
          <button type="button" data-act="metal-mandate" data-id="${esc(a.agent_id)}">Raise Mandate (0.60)</button>
        </div>
      </td>
    </tr>`).join('');
  }

  if (s.incident) {
    const inc = s.incident;
    const incBox = document.getElementById('incident-box');
    const stCls = inc.status === 'CANCELLED' ? (inc.replacement_transfer_id ? 'badge-ok' : 'badge-err') : 'badge-amber';
    incBox.innerHTML = `
      <div class="kv-grid">
        <div><span class="kv-label">Incident ID:</span> <code>${esc(inc.incident_id)}</code> (<span class="font-mono">${esc(inc.amount)}</span> via ${esc(inc.rail)})</div>
        <div><span class="kv-label">Status:</span> <span class="badge ${stCls}">${esc(inc.status)}</span> ${inc.failure_type ? `<code>(${esc(inc.failure_type)})</code>` : ''}</div>
        <div><span class="kv-label">Original Transfer:</span> <code>${esc(inc.original_transfer_id)}</code> (req: <code>${esc(inc.original_request_id.slice(0, 12))}</code>)</div>
        <div><span class="kv-label">Replacement Transfer:</span> ${inc.replacement_transfer_id ? `<code>${esc(inc.replacement_transfer_id)}</code> (req: <code>${esc(inc.replacement_request_id.slice(0, 12))}</code>)` : '<em>None issued yet</em>'}</div>
        <div><span class="kv-label">SWIFT Fee Budget:</span> <strong class="font-mono">${esc(inc.swift_fees_budgeted)}</strong></div>
      </div>`;
  }

  if (s.last_dispute_report) {
    const dr = s.last_dispute_report;
    document.getElementById('dispute-box').innerHTML = `
      <div class="sub-card">
        <strong>Dispute Batch Verified (${dr.orders_checked} signed x402 orders) &middot; Refunded: <span class="font-mono">${esc(dr.refunded_spoken)}</span></strong>
        <ul class="compact-list">
          ${dr.verdicts.map(v => `<li><code>${esc(v.order_id)}</code>: HMAC Signature Valid=${v.signature_valid}, Data Quality OK=${v.data_quality_ok} &rarr; <strong>${esc(v.decision)}</strong> ${v.refund_tx ? `(tx: <code>${esc(v.refund_tx)}</code>)` : ''}</li>`).join('')}
        </ul>
      </div>`;
  } else {
    document.getElementById('dispute-box').innerHTML = '';
  }

  if (s.last_ai_inspection) {
    const ai = s.last_ai_inspection;
    const vCls = ai.verdict === 'PROPOSED' ? 'badge-ok' : 'badge-err';
    document.getElementById('ai-box').innerHTML = `
      <div class="sub-card">
        <div><span class="badge ${vCls}">${esc(ai.verdict)}</span> <strong>Engine:</strong> <code>${esc(ai.engine)}</code></div>
        <div style="margin-top:0.35rem">${esc(ai.reason)}</div>
        ${ai.evidence_sha256 ? `<div class="sup-sub">Bound Evidence SHA-256: <code>${esc(ai.evidence_sha256)}</code></div>` : ''}
        <pre class="code-preview">${esc(ai.invoice_preview)}</pre>
      </div>`;
  } else {
    document.getElementById('ai-box').innerHTML = '';
  }
}

async function refresh() { render(await call('/api/state')); }

async function runAction(btn, work) {
  if (btn) btn.disabled = true;
  say('Working...', false);
  try { await work(); }
  catch (err) { say(err.message, true); }
  finally { if (btn) btn.disabled = false; }
}

document.addEventListener('click', e => {
  const navBtn = e.target.closest('button.nav-btn[data-view]');
  if (navBtn) {
    document.querySelectorAll('button.nav-btn').forEach(el => el.classList.remove('active'));
    navBtn.classList.add('active');
    const view = navBtn.dataset.view;
    document.querySelectorAll('section[data-module]').forEach(sec => {
      sec.style.display = (view === 'all' || sec.dataset.module === view) ? '' : 'none';
    });
    say('Filtered workspace view to module: ' + view.toUpperCase() + '.', false);
    return;
  }

  const b = e.target.closest('button[data-act]');
  if (!b) return;
  const act = b.dataset.act;
  const id = b.dataset.id;
  runAction(b, async () => {
    if (act === 'approve') {
      const r = await call('/api/approve/' + id, {});
      selectedReceiptId = id;
      say('Approved ' + r.obligation_id + ' (digest ' + r.approval_sha256.slice(0, 12) + '). Merkle receipt sealed.', false);
    } else if (act === 'execute') {
      const sha = b.dataset.sha || undefined;
      const r = await call('/api/execute/' + id, sha ? {approval_sha256: sha} : {});
      say('Executed ' + r.obligation_id + ' through the Writer gate (' + r.transfer_id + ').', false);
    } else if (act === 'inspect-receipt') {
      selectedReceiptId = id;
      if (lastState) renderReceiptDrawer(lastState);
      say('Showing cryptographic Merkle receipt for ' + id + '.', false);
      return;
    } else if (act === 'metal-call') {
      const r = await call('/api/metal-call/' + id, {});
      say('Paid 1 USDZ call for ' + r.agent_id + ' (' + r.tx_id + ', ' + r.calls_used + '/' + r.call_cap + ' calls).', false);
    } else if (act === 'metal-spike') {
      const r = await call('/api/metal-rebalance', {agent_id: id, new_price: '0.50'});
      const c = (r.changes && r.changes[0]) ? ('cap ' + r.changes[0].old_call_cap + ' -> ' + r.changes[0].new_call_cap) : 'no cap change';
      say('Rebalanced ' + r.agent_id + ' to ' + r.new_price + ' (' + c + ').', false);
    } else if (act === 'metal-mandate') {
      const r = await call('/api/metal-mandate', {agent_id: id, new_max_price_cents: 60});
      say('Replaced mandate for ' + r.agent_id + ': per-call cap raised to ' + r.new_max_price_cents + ' cents.', false);
    } else if (act === 'metal-dispute') {
      const r = await call('/api/metal-dispute', {});
      say('Verified ' + r.orders_checked + ' signed x402 orders; refunded ' + r.refunded_spoken + ' for faulty upstream feed.', false);
    } else if (act === 'email-contradict') {
      const r = await call('/api/customer-email', {contradicts: true});
      say('Customer email applied: forecast confidence dropped to ' + r.confidence_pct + '% and autonomous limit set to ' + r.autonomous_limit + '.', false);
    } else if (act === 'email-restore') {
      const r = await call('/api/customer-email', {contradicts: false});
      say('Forecast confidence restored to ' + r.confidence_pct + '% (' + r.autonomous_limit + ').', false);
    } else if (act === 'ai-match') {
      const r = await call('/api/evaluate-invoice', {obligation_id: 'obl-usd-1', mode: 'matching'});
      say('Evaluator (' + r.engine + '): ' + r.verdict + ' for ' + r.obligation_id + '.', false);
    } else if (act === 'ai-tamper') {
      const r = await call('/api/evaluate-invoice', {obligation_id: 'obl-usd-1', mode: 'mismatched'});
      say('Evaluator (' + r.engine + '): ' + r.verdict + ' tampered invoice (' + r.reason + ').', true);
    } else if (act === 'inc-fail') {
      const r = await call('/api/incident-fail', {failure_type: 'bank_return'});
      say('Transfer ' + r.original_transfer_id + ' transitioned to CANCELLED (' + r.failure_type + ').', false);
    } else if (act === 'inc-resolve') {
      const r = await call('/api/incident-resolve', {});
      say('Incident Commander decision: ' + r.decision + ' -> issued ' + r.replacement_transfer_id + ' under duplicate lock.', false);
    } else if (act === 'quick-eur-deposit') {
      const r = await call('/api/simulate-deposit', {currency: 'EUR', amount: '500.00'});
      say('Signed EUR 500.00 deposit landed. Invalidated: ' + (r.invalidated.join(', ') || 'none') + '.', false);
    } else if (act === 'quick-usd-deposit') {
      const r = await call('/api/simulate-deposit', {currency: 'USD', amount: '200.00'});
      say('Signed USD 200.00 deposit landed. USD reserve floor headroom restored.', false);
    }
    await refresh();
  });
});

document.getElementById('sidebar-toggle').addEventListener('click', () => {
  const sb = document.getElementById('erp-sidebar');
  sb.classList.toggle('collapsed');
});

document.getElementById('company-select').addEventListener('change', e => {
  activeEntityScope = e.target.value;
  if (lastState) render(lastState);
  say('Switched entity scope to ' + e.target.options[e.target.selectedIndex].text + '.', false);
});

const COMMANDS = [
  {id: 'cmd-eur-dep', label: 'Land Signed EUR 500.00 Deposit Webhook (Selective Invalidation)', badge: 'Kit 1', run: () => document.querySelector('[data-act="quick-eur-deposit"]').click()},
  {id: 'cmd-usd-dep', label: 'Land Signed USD 200.00 Deposit (Restore Reserve Floor)', badge: 'Kit 1', run: () => document.querySelector('[data-act="quick-usd-deposit"]').click()},
  {id: 'cmd-ai-match', label: 'Run Amazon Bedrock Evaluator on Matching Invoice ($450.00)', badge: 'Bedrock AI', run: () => document.querySelector('[data-act="ai-match"]').click()},
  {id: 'cmd-ai-tamper', label: 'Run Amazon Bedrock Evaluator on Tampered Invoice ($495.00)', badge: 'Bedrock AI', run: () => document.querySelector('[data-act="ai-tamper"]').click()},
  {id: 'cmd-inc-fail', label: 'Simulate Delayed SWIFT Bank Return (SENT -> CANCELLED)', badge: 'Kit 3', run: () => document.querySelector('[data-act="inc-fail"]').click()},
  {id: 'cmd-inc-res', label: 'Issue Replacement SWIFT Transfer under 7-Day Duplicate Lock', badge: 'Kit 3', run: () => document.querySelector('[data-act="inc-resolve"]').click()},
  {id: 'cmd-x402', label: 'Verify Signed x402 Disputed Order Batch & Refund Faulty Feed', badge: 'Kit 11', run: () => document.querySelector('[data-act="metal-dispute"]').click()},
  {id: 'cmd-reset', label: 'Reset Demo Snapshot to Initial 72-Hour Close', badge: 'System', run: () => document.getElementById('reset').click()}
];

const cmdkModal = document.getElementById('cmdk-modal');
const cmdkInput = document.getElementById('cmdk-input');
const cmdkList = document.getElementById('cmdk-list');

function renderCmdk(query) {
  const q = (query || '').toLowerCase();
  const matches = COMMANDS.filter(c => c.label.toLowerCase().includes(q) || c.badge.toLowerCase().includes(q));
  cmdkList.innerHTML = matches.map((c, idx) => `
    <li>
      <button type="button" class="cmdk-item" data-cmd-idx="${COMMANDS.indexOf(c)}">
        <span>${esc(c.label)}</span>
        <span class="badge badge-indigo">${esc(c.badge)}</span>
      </button>
    </li>`).join('');
}

function openCmdk() {
  cmdkModal.classList.add('open');
  cmdkInput.value = '';
  renderCmdk('');
  setTimeout(() => cmdkInput.focus(), 20);
}

function closeCmdk() {
  cmdkModal.classList.remove('open');
}

document.getElementById('cmdk-open').addEventListener('click', openCmdk);
document.getElementById('cmdk-close').addEventListener('click', closeCmdk);
cmdkInput.addEventListener('input', e => renderCmdk(e.target.value));
cmdkList.addEventListener('click', e => {
  const btn = e.target.closest('button[data-cmd-idx]');
  if (!btn) return;
  const cmd = COMMANDS[Number(btn.dataset.cmdIdx)];
  closeCmdk();
  if (cmd) cmd.run();
});
document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    if (cmdkModal.classList.contains('open')) closeCmdk();
    else openCmdk();
  } else if (e.key === 'Escape' && cmdkModal.classList.contains('open')) {
    closeCmdk();
  }
});

document.getElementById('deposit-form').addEventListener('submit', e => {
  e.preventDefault();
  const cur = document.getElementById('currency').value;
  const amt = document.getElementById('amount').value;
  runAction(e.submitter, async () => {
    const r = await call('/api/simulate-deposit', {currency: cur, amount: amt});
    const inv = r.invalidated.length ? r.invalidated.join(', ') : 'none';
    const val = r.still_valid.length ? r.still_valid.join(', ') : 'none';
    say('Deposit ' + r.amount + ' landed. Invalidated: ' + inv + '. Still valid: ' + val + '.', false);
    await refresh();
  });
});

document.getElementById('reset').addEventListener('click', e => {
  runAction(e.currentTarget, async () => {
    selectedReceiptId = null;
    await call('/api/reset', {});
    say('Demo reset to initial 72-hour close snapshot.', false);
    await refresh();
  });
});

refresh();
</script>"""
