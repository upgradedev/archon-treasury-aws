import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { CommandMenu } from '../../components/layout/CommandMenu';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { useShell } from '../../context/ShellContext';
import { views } from '../../context/navigation';
import { CompletenessAlerts } from './CompletenessAlerts';
import { KpiGrid } from './KpiGrid';
import { ObligationsTable } from './ObligationsTable';
import { ConfirmActionState, ConfirmDialog } from './components/ConfirmDialog';
import { OperatorAuthBar } from './components/OperatorAuthBar';
import { ReceiptInspector } from './components/ReceiptInspector';
import { requestJson, setCsrfToken } from './api';
import { TreasurySnapshot } from './types';

const EMPTY: TreasurySnapshot = { balances: [], obligations: [], findings: [] };

const Details: React.FC<{ value: object }> = ({ value }) => (
  <dl className="details">
    {Object.entries(value).map(([key, val]) => (
      <React.Fragment key={key}>
        <dt>{key.replaceAll('_', ' ')}</dt>
        <dd className="money">{val === null ? 'N/A' : typeof val === 'object' ? JSON.stringify(val) : String(val)}</dd>
      </React.Fragment>
    ))}
  </dl>
);

const JsonResult: React.FC<{ value: unknown }> = ({ value }) =>
  value ? (
    <pre className="data-block">{JSON.stringify(value, null, 2)}</pre>
  ) : (
    <p className="empty-state">No result recorded in this session.</p>
  );

export const TreasuryDashboard: React.FC = () => {
  const { activeCompany, activeModule, setActiveModule } = useShell();
  const [snapshot, setSnapshot] = useState<TreasurySnapshot>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [staleAfterMutation, setStaleAfterMutation] = useState(false);
  const [busy, setBusy] = useState(false);
  const mutationLock = useRef(false);
  const [status, setStatus] = useState<{ text: string; error: boolean } | null>(null);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [customInvoice, setCustomInvoice] = useState(
    'INVOICE INV-2026-8841\nSupplier: Shenzhen Precision PCB Ltd.\nCounterparty: supplier-a\nObligation: obl-usd-1\nTotal due USD 450.00'
  );
  const [depositCurrency, setDepositCurrency] = useState('EUR');
  const [depositAmount, setDepositAmount] = useState('500.00');
  const [depositPayer, setDepositPayer] = useState('Munich Industrial Client');
  const [depositRef, setDepositRef] = useState('WIRE-EUR-771');
  const [floorCurrency, setFloorCurrency] = useState('EUR');
  const [floorAmount, setFloorAmount] = useState('400.00');
  const [fxSellCurrency, setFxSellCurrency] = useState('EUR');
  const [fxBuyCurrency, setFxBuyCurrency] = useState('USD');
  const [fxSellAmount, setFxSellAmount] = useState('200.00');
  const [chargeCents, setChargeCents] = useState('45000');
  const [mcc, setMcc] = useState('5045');
  const [failureType, setFailureType] = useState('bank_return');
  const [agentId, setAgentId] = useState('');
  const [newPrice, setNewPrice] = useState('0.10');
  const [maxPrice, setMaxPrice] = useState('20');
  const [confirmAction, setConfirmAction] = useState<ConfirmActionState | null>(null);
  const [lastDeposit, setLastDeposit] = useState<unknown>(null);

  const fetchSnapshot = useCallback(async () => {
    try {
      const data = await requestJson<TreasurySnapshot>('/api/state');
      if (
        !Array.isArray(data.balances) ||
        !Array.isArray(data.obligations) ||
        !Array.isArray(data.findings)
      ) {
        throw new Error('The service returned incomplete treasury data.');
      }
      if (data.session?.csrf_token) {
        setCsrfToken(data.session.csrf_token);
      }
      setSnapshot(data);
      setLoadError('');
      setStaleAfterMutation(false);
      return data;
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Unable to load treasury state.';
      setLoadError(message);
      throw e;
    }
  }, []);

  useEffect(() => {
    void fetchSnapshot()
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }, [fetchSnapshot]);

  useEffect(() => {
    const label = views.find((v) => v.id === activeModule)?.label ?? 'Command Center';
    document.title = `Archon Treasury - ${label}`;
  }, [activeModule]);

  const perform = useCallback(
    async (name: string, path: string, body: Record<string, unknown>) => {
      if (mutationLock.current) return;
      mutationLock.current = true;
      setBusy(true);
      setStatus(null);
      let succeeded = false;
      try {
        const result = await requestJson<Record<string, unknown>>(path, body);
        succeeded = true;
        const detail =
          result.error ??
          result.last_reason ??
          result.reason ??
          result.transfer_id ??
          result.approval_sha256 ??
          result.quote_id ??
          result.conversion_id ??
          result.reserve_floor_major ??
          result.state ??
          result.verdict ??
          '';
        setStatus({
          text: `${name}: ${detail ? String(detail) : 'Request accepted by service.'}`,
          error: false,
        });
        if (path === '/api/simulate-deposit' || path === '/api/deposits') {
          setLastDeposit(result);
        }
        if (path === '/api/reset') {
          setLastDeposit(null);
        }
      } catch (e) {
        setStatus({
          text: e instanceof Error ? e.message : 'Service request failed.',
          error: true,
        });
      } finally {
        try {
          await fetchSnapshot();
        } catch {
          if (succeeded) {
            setStaleAfterMutation(true);
            setStatus({
              text: 'The action was accepted, but refreshed state could not be loaded. Refresh before taking another action.',
              error: true,
            });
          }
        }
        mutationLock.current = false;
        setBusy(false);
      }
    },
    [fetchSnapshot]
  );

  const requestAction = (
    name: string,
    path: string,
    body: Record<string, unknown> = {}
  ) => setConfirmAction({ name, path, body });

  const balances = useMemo(
    () =>
      activeCompany === 'ALL'
        ? snapshot.balances
        : snapshot.balances.filter((b) => b.currency === activeCompany),
    [activeCompany, snapshot.balances]
  );

  const obligations = useMemo(
    () =>
      snapshot.obligations.filter(
        (o) =>
          (activeCompany === 'ALL' || o.currency === activeCompany) &&
          `${o.supplier_name} ${o.invoice_ref} ${o.obligation_id}`
            .toLowerCase()
            .includes(search.toLowerCase()) &&
          (activeModule !== 'approvals' || o.approval_state !== 'PAID') &&
          (filter === 'all' || o.approval_state === filter)
      ),
    [snapshot.obligations, activeCompany, search, activeModule, filter]
  );

  const invalidated = snapshot.obligations.filter(
    (o) => o.approval_state === 'INVALIDATED'
  );
  const blockers = snapshot.findings.filter((f) => f.severity === 'BLOCKER');
  const selectedAgent = agentId || snapshot.metal_agents?.[0]?.agent_id || '';
  const unavailable = loading || busy || !!loadError || staleAfterMutation;

  const actions = views
    .map<{ id: string; label: string; moduleTag: string; run: () => void }>((v) => ({
      id: `view-${v.id}`,
      label: v.label,
      moduleTag: v.group,
      run: () => setActiveModule(v.id),
    }))
    .concat([
      {
        id: 'deposit-eur',
        label: 'Simulate EUR 500.00 deposit',
        moduleTag: 'Demo',
        run: () =>
          requestAction('Simulate EUR 500.00 deposit', '/api/simulate-deposit', {
            currency: 'EUR',
            amount: '500.00',
          }),
      },
      {
        id: 'deposit-usd',
        label: 'Simulate USD 200.00 deposit',
        moduleTag: 'Demo',
        run: () =>
          requestAction('Simulate USD 200.00 deposit', '/api/simulate-deposit', {
            currency: 'USD',
            amount: '200.00',
          }),
      },
      {
        id: 'issue-visa',
        label: 'Issue single-use virtual card',
        moduleTag: 'Cards',
        run: () => requestAction('Issue virtual card', '/api/visa-issue'),
      },
    ]);

  const payoutTable = (
    <>
      <div className="section-heading">
        <h2>{activeModule === 'approvals' ? 'Approval queue' : 'Supplier payouts'}</h2>
        <div className="toolbar">
          <input
            aria-label="Search payouts"
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Supplier or invoice"
          />
          <select
            aria-label="Payout status"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="all">All statuses</option>
            <option value="NOT_APPROVED">Needs approval</option>
            <option value="INVALIDATED">Evidence changed</option>
            <option value="VALID">Ready to execute</option>
            <option value="PAID">Paid</option>
          </select>
        </div>
      </div>
      <ObligationsTable
        obligations={obligations}
        busy={unavailable}
        onApprove={(id) =>
          requestAction(`Approve ${id}`, `/api/approve/${encodeURIComponent(id)}`)
        }
        onExecute={(id, sha) =>
          requestAction(
            `Execute ${id}`,
            `/api/execute/${encodeURIComponent(id)}`,
            sha ? { approval_sha256: sha } : {}
          )
        }
      />
    </>
  );

  const label = views.find((v) => v.id === activeModule)?.label ?? 'Command Center';
  const subtitles: Record<string, string> = {
    all: `${snapshot.obligations.filter((o) => o.approval_state !== 'PAID').length} open payouts · ${invalidated.length} changed approvals · ${blockers.length} blockers`,
    payouts: 'Supplier obligations and execution gates',
    approvals: 'Evidence-bound approval decisions',
    deposits: 'Deposit simulation, persistent ledger and selective invalidation',
    wallets: 'Balances, protected reserves and spendable funds',
    fx: 'Reference exchange rates, locked FX quotes and conversions',
    audit: 'Current completeness findings',
    receipts: 'Service-issued receipts and audit export',
    incidents: 'Payment failure and recovery',
    visa: 'Single-use cards and merchant restrictions',
    metal: 'Agent budgets and spending mandates',
    evaluator: 'Invoice evidence inspection',
    integrations: 'Provider status, reconciliation and operator access control',
  };

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">Vance Hardware / Treasury</span>
          <h1 className="display">{label}</h1>
          <p>{subtitles[activeModule]}</p>
        </div>
        <div className="toolbar">
          <span className="demo-badge">◇ {snapshot.mode ?? 'Mode unverified'}</span>
          {snapshot.session && (
            <span className="demo-badge" title={`Tenant: ${snapshot.session.tenant_id}`}>
              Role: {snapshot.session.role}
            </span>
          )}
          <Button
            disabled={loading || busy}
            onClick={() => {
              setLoading(true);
              void fetchSnapshot()
                .catch(() => undefined)
                .finally(() => setLoading(false));
            }}
          >
            ↻ Refresh
          </Button>
        </div>
      </div>

      {loading && (
        <p role="status" className="status-bar">
          Loading treasury state…
        </p>
      )}
      {loadError && (
        <p role="alert" className="status-bar error">
          {loadError}
        </p>
      )}
      {staleAfterMutation && (
        <div role="alert" className="status-bar error">
          <span>
            Mutation was accepted by the server, but state refresh failed. Mutating
            actions are locked until state is refreshed.
          </span>{' '}
          <Button
            size="sm"
            onClick={() => {
              setLoading(true);
              void fetchSnapshot()
                .catch(() => undefined)
                .finally(() => setLoading(false));
            }}
          >
            Retry refresh now
          </Button>
        </div>
      )}
      {status && (
        <p
          role={status.error ? 'alert' : 'status'}
          aria-live="polite"
          className={`status-bar ${status.error ? 'error' : 'success'}`}
        >
          {status.text}
        </p>
      )}
      {busy && (
        <p role="status" className="status-bar">
          Waiting for service confirmation…
        </p>
      )}

      {!loading && !loadError && (
        <>
          {activeModule === 'all' && (
            <div className="workspace-grid">
              <div className="workspace-main">
                <KpiGrid balances={balances} />
                <section>{payoutTable}</section>
              </div>
              <aside className="workspace-side">
                <section className="callout">
                  <h3>
                    {invalidated.length ? 'Evidence changed' : 'Approval integrity'}
                  </h3>
                  {invalidated.length ? (
                    invalidated.map((o) => (
                      <div key={o.obligation_id}>
                        <p>
                          {o.supplier_name}
                          <br />
                          {o.action_reason}
                        </p>
                        <Button
                          onClick={() => {
                            setActiveModule('approvals');
                            setSearch(o.obligation_id);
                          }}
                        >
                          Review approval →
                        </Button>
                      </div>
                    ))
                  ) : (
                    <p>No invalidated approvals in the current state.</p>
                  )}
                </section>
                <section>
                  <div className="section-heading">
                    <h2>Completeness</h2>
                    <Badge intent={blockers.length ? 'critical' : 'success'}>
                      {blockers.length} blockers
                    </Badge>
                  </div>
                  <CompletenessAlerts findings={snapshot.findings.slice(0, 3)} />
                  <Button variant="ghost" onClick={() => setActiveModule('audit')}>
                    All findings →
                  </Button>
                </section>
                {snapshot.forecast && (
                  <section>
                    <div className="section-heading">
                      <h2>Forecast confidence</h2>
                      <span className="money">{snapshot.forecast.confidence_pct}%</span>
                    </div>
                    <p className="muted">{snapshot.forecast.reason}</p>
                    <span className="money">
                      Limit {snapshot.forecast.autonomous_limit_major}
                    </span>
                  </section>
                )}
              </aside>
            </div>
          )}

          {(activeModule === 'payouts' || activeModule === 'approvals') && (
            <section>{payoutTable}</section>
          )}

          {activeModule === 'wallets' && (
            <>
              <KpiGrid balances={balances} />
              <section className="list-row">
                <div className="section-heading">
                  <h2>Update reserve floor</h2>
                  <Badge intent="indigo">Evidence-bound control</Badge>
                </div>
                <p className="muted">
                  Updating a currency reserve floor immediately re-evaluates all pending
                  approvals in that currency and invalidates any payout whose bound
                  reserve evidence changed.
                </p>
                <div className="toolbar">
                  <select
                    aria-label="Reserve floor currency"
                    value={floorCurrency}
                    onChange={(e) => setFloorCurrency(e.target.value)}
                  >
                    {['EUR', 'USD', 'GBP'].map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    aria-label="New reserve floor amount"
                    value={floorAmount}
                    onChange={(e) => setFloorAmount(e.target.value)}
                  />
                  <Button
                    variant="primary"
                    disabled={unavailable || Number(floorAmount) < 0}
                    onClick={() =>
                      requestAction(
                        `Update ${floorCurrency} reserve floor to ${floorAmount}`,
                        '/api/reserve-floor',
                        { currency: floorCurrency, reserve_floor: floorAmount }
                      )
                    }
                  >
                    Change reserve floor
                  </Button>
                </div>
              </section>
            </>
          )}

          {activeModule === 'deposits' && (
            <div className="detail-grid">
              <section>
                <div className="section-heading">
                  <h2>Simulate a signed deposit</h2>
                  <Badge intent="warning">Demo action</Badge>
                </div>
                <div className="toolbar">
                  <select
                    aria-label="Deposit currency"
                    value={depositCurrency}
                    onChange={(e) => setDepositCurrency(e.target.value)}
                  >
                    {['EUR', 'USD', 'GBP'].map((c) => (
                      <option key={c}>{c}</option>
                    ))}
                  </select>
                  <input
                    type="number"
                    min="0.01"
                    step="0.01"
                    aria-label="Deposit amount"
                    value={depositAmount}
                    onChange={(e) => setDepositAmount(e.target.value)}
                  />
                  <Button
                    variant="primary"
                    disabled={unavailable || !(Number(depositAmount) > 0)}
                    onClick={() =>
                      requestAction(
                        `Simulate ${depositCurrency} ${depositAmount} deposit`,
                        '/api/simulate-deposit',
                        { currency: depositCurrency, amount: depositAmount }
                      )
                    }
                  >
                    Simulate deposit
                  </Button>
                </div>
                <div className="list-row">
                  <Button
                    disabled={unavailable}
                    onClick={() =>
                      requestAction(
                        'Simulate EUR 500.00 deposit',
                        '/api/simulate-deposit',
                        { currency: 'EUR', amount: '500.00' }
                      )
                    }
                  >
                    EUR 500.00
                  </Button>
                  <Button
                    disabled={unavailable}
                    onClick={() =>
                      requestAction(
                        'Simulate USD 200.00 deposit',
                        '/api/simulate-deposit',
                        { currency: 'USD', amount: '200.00' }
                      )
                    }
                  >
                    USD 200.00
                  </Button>
                </div>
                <div className="list-row">
                  <h3>Record authenticated inbound wire</h3>
                  <div className="toolbar">
                    <input
                      aria-label="Deposit payer name"
                      value={depositPayer}
                      onChange={(e) => setDepositPayer(e.target.value)}
                      placeholder="Payer name"
                    />
                    <input
                      aria-label="Deposit reference"
                      value={depositRef}
                      onChange={(e) => setDepositRef(e.target.value)}
                      placeholder="Wire reference"
                    />
                    <Button
                      disabled={unavailable || !(Number(depositAmount) > 0)}
                      onClick={() =>
                        requestAction(
                          `Record ${depositCurrency} ${depositAmount} deposit`,
                          '/api/deposits',
                          {
                            currency: depositCurrency,
                            amount: depositAmount,
                            payer_name: depositPayer,
                            reference: depositRef,
                          }
                        )
                      }
                    >
                      Record deposit
                    </Button>
                  </div>
                </div>
              </section>
              <section>
                <h2>Last deposit response</h2>
                <JsonResult value={lastDeposit} />
                <h3>Persisted deposit ledger ({snapshot.deposit_history?.length ?? 0})</h3>
                {snapshot.deposit_history && snapshot.deposit_history.length > 0 ? (
                  <div className="space-y-2">
                    {snapshot.deposit_history.map((d) => (
                      <div key={d.deposit_id} className="list-row">
                        <div className="section-heading">
                          <strong className="money">{d.amount_major}</strong>
                          <Badge intent="success">{d.reference}</Badge>
                        </div>
                        <p className="muted">
                          {d.payer_name} · Account {d.account_id} · Invalidated:{' '}
                          {d.invalidated.length ? d.invalidated.join(', ') : 'none'}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="empty-state">No deposits recorded in this tenant yet.</p>
                )}
              </section>
            </div>
          )}

          {activeModule === 'fx' && (
            <>
              <section>
                <div className="section-heading">
                  <h2>Reference rates</h2>
                  <span className="muted">
                    {snapshot.fx_rates?.source} · {snapshot.fx_rates?.as_of_date}
                  </span>
                </div>
                {snapshot.fx_rates ? (
                  <div className="metric-grid">
                    {[
                      ['EUR / USD', snapshot.fx_rates.eur_usd],
                      ['EUR / GBP', snapshot.fx_rates.eur_gbp],
                      ['GBP / USD', snapshot.fx_rates.gbp_usd],
                    ].map(([pair, rate]) => (
                      <article key={pair} className="metric">
                        <span className="eyebrow">{pair}</span>
                        <div className="money value">{rate}</div>
                      </article>
                    ))}
                  </div>
                ) : (
                  <p className="empty-state">Rates unavailable.</p>
                )}
              </section>

              <section className="list-row">
                <div className="section-heading">
                  <h2>Lock standalone FX quote</h2>
                  <Badge intent="indigo">Integer-ratio quote</Badge>
                </div>
                <div className="toolbar">
                  <select
                    aria-label="FX sell currency"
                    value={fxSellCurrency}
                    onChange={(e) => setFxSellCurrency(e.target.value)}
                  >
                    {['EUR', 'USD', 'GBP'].map((c) => (
                      <option key={c} value={c}>
                        Sell {c}
                      </option>
                    ))}
                  </select>
                  <select
                    aria-label="FX buy currency"
                    value={fxBuyCurrency}
                    onChange={(e) => setFxBuyCurrency(e.target.value)}
                  >
                    {['USD', 'EUR', 'GBP'].map((c) => (
                      <option key={c} value={c}>
                        Buy {c}
                      </option>
                    ))}
                  </select>
                  <input
                    type="number"
                    min="0.01"
                    step="0.01"
                    aria-label="FX sell amount"
                    value={fxSellAmount}
                    onChange={(e) => setFxSellAmount(e.target.value)}
                  />
                  <Button
                    variant="primary"
                    disabled={
                      unavailable ||
                      fxSellCurrency === fxBuyCurrency ||
                      !(Number(fxSellAmount) > 0)
                    }
                    onClick={() =>
                      requestAction(
                        `Lock FX quote ${fxSellCurrency} -> ${fxBuyCurrency}`,
                        '/api/fx/quote',
                        {
                          sell_currency: fxSellCurrency,
                          buy_currency: fxBuyCurrency,
                          sell_amount: fxSellAmount,
                          ttl_seconds: 300,
                        }
                      )
                    }
                  >
                    Lock FX quote
                  </Button>
                </div>

                {snapshot.fx_quotes && snapshot.fx_quotes.length > 0 && (
                  <div className="space-y-2 mt-3">
                    <h3>Active locked FX quotes</h3>
                    {snapshot.fx_quotes.map((q) => (
                      <div key={q.quote_id} className="list-row">
                        <div className="section-heading">
                          <span className="money">
                            {q.quote_id}: {q.sell_amount_major} → {q.buy_amount_major}
                          </span>
                          <Badge intent={q.expired ? 'critical' : 'success'}>
                            {q.expired ? 'EXPIRED' : 'ACTIVE'}
                          </Badge>
                        </div>
                        <Button
                          size="sm"
                          variant="primary"
                          disabled={unavailable || q.expired}
                          onClick={() =>
                            requestAction(
                              `Execute FX conversion ${q.quote_id}`,
                              '/api/fx/convert',
                              { quote_id: q.quote_id }
                            )
                          }
                        >
                          Execute conversion
                        </Button>
                      </div>
                    ))}
                  </div>
                )}

                {snapshot.fx_conversions && snapshot.fx_conversions.length > 0 && (
                  <div className="space-y-2 mt-3">
                    <h3>Executed FX conversions</h3>
                    {snapshot.fx_conversions.map((c) => (
                      <div key={c.conversion_id} className="list-row">
                        <span className="money">
                          {c.conversion_id}: Sold {c.sold_major} → Bought {c.bought_major}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              <section className="list-row">
                <h2>Conversion requirements</h2>
                {snapshot.obligations
                  .filter((o) => o.plan_action === 'CONVERT_FX')
                  .map((o) => (
                    <div key={o.obligation_id}>
                      <strong>{o.supplier_name}</strong>
                      <p className="muted">{o.plan_rationale}</p>
                      <Button
                        onClick={() => {
                          setActiveModule('payouts');
                          setSearch(o.obligation_id);
                        }}
                      >
                        Review payout →
                      </Button>
                    </div>
                  ))}
              </section>
            </>
          )}

          {activeModule === 'audit' && (
            <CompletenessAlerts findings={snapshot.findings} />
          )}

          {activeModule === 'receipts' && (
            <>
              <div className="section-heading">
                <h2>Sealed payout receipts</h2>
                <a className="audit-link" href="/api/audit-export.csv" download>
                  ↓ Download audit CSV
                </a>
              </div>
              {snapshot.obligations.some((o) => o.receipt) ? (
                snapshot.obligations
                  .filter((o) => o.receipt)
                  .map((o) => (
                    <ReceiptInspector
                      key={o.obligation_id}
                      supplierName={o.supplier_name}
                      invoiceRef={o.invoice_ref}
                      approvalSha256={o.approval_sha256}
                      receipt={o.receipt}
                    />
                  ))
              ) : (
                <p className="empty-state">No payout receipts yet.</p>
              )}
            </>
          )}

          {activeModule === 'incidents' && (
            <>
              {snapshot.incident ? (
                <Details value={snapshot.incident} />
              ) : (
                <p className="empty-state">No incident data.</p>
              )}
              <div className="list-row">
                <Badge intent="warning">Demo failure injection</Badge>
                <div className="toolbar">
                  <select
                    aria-label="Incident failure type"
                    value={failureType}
                    onChange={(e) => setFailureType(e.target.value)}
                  >
                    <option value="bank_return">Bank return</option>
                    <option value="timeout">Timeout</option>
                  </select>
                  <Button
                    disabled={unavailable}
                    onClick={() =>
                      requestAction('Simulate payment failure', '/api/incident-fail', {
                        failure_type: failureType,
                      })
                    }
                  >
                    Simulate failure
                  </Button>
                  <Button
                    variant="primary"
                    disabled={unavailable}
                    onClick={() =>
                      requestAction('Resolve payment incident', '/api/incident-resolve')
                    }
                  >
                    Resolve incident
                  </Button>
                </div>
              </div>
            </>
          )}

          {activeModule === 'visa' && (
            <>
              {snapshot.visa_mandate ? (
                <div className="detail-grid">
                  <section>
                    <div className="card-visual">
                      <div className="section-heading">
                        <span className="display">Archon</span>
                        <span>VISA</span>
                      </div>
                      <div className="money">
                        •••• •••• •••• {snapshot.visa_mandate.card_last4}
                      </div>
                      <span>{snapshot.visa_mandate.supplier_name}</span>
                    </div>
                    <Details value={snapshot.visa_mandate} />
                  </section>
                  <section>
                    <h2>Card controls</h2>
                    <div className="toolbar">
                      <Button
                        disabled={unavailable}
                        onClick={() =>
                          requestAction('Issue virtual card', '/api/visa-issue')
                        }
                      >
                        Issue single-use card
                      </Button>
                    </div>
                    <h3>Simulate authorization</h3>
                    <label>
                      Amount in cents
                      <input
                        type="number"
                        min="1"
                        step="1"
                        aria-label="Card charge cents"
                        value={chargeCents}
                        onChange={(e) => setChargeCents(e.target.value)}
                      />
                    </label>
                    <label>
                      Merchant category
                      <input
                        aria-label="Merchant MCC"
                        value={mcc}
                        onChange={(e) => setMcc(e.target.value)}
                      />
                    </label>
                    <div className="toolbar">
                      <Button
                        variant="primary"
                        disabled={
                          unavailable ||
                          !Number.isInteger(Number(chargeCents)) ||
                          Number(chargeCents) <= 0
                        }
                        onClick={() =>
                          requestAction(
                            'Simulate card authorization',
                            '/api/visa-charge',
                            {
                              charge_cents: Number(chargeCents),
                              merchant_mcc: mcc,
                            }
                          )
                        }
                      >
                        Test authorization
                      </Button>
                      <Button
                        disabled={unavailable}
                        onClick={() =>
                          requestAction('Test wrong MCC 5812', '/api/visa-charge', {
                            charge_cents: 45000,
                            merchant_mcc: '5812',
                          })
                        }
                      >
                        Test wrong MCC
                      </Button>
                    </div>
                  </section>
                </div>
              ) : (
                <p className="empty-state">Card mandate unavailable.</p>
              )}
            </>
          )}

          {activeModule === 'metal' && (
            <>
              <div className="metric-grid">
                {snapshot.metal_agents?.map((agent) => (
                  <article key={agent.agent_id} className="metric">
                    <h3>{agent.agent_id}</h3>
                    <Details value={agent} />
                    <Button
                      disabled={unavailable}
                      onClick={() =>
                        requestAction(
                          `Pay agent call: ${agent.agent_id}`,
                          `/api/metal-call/${encodeURIComponent(agent.agent_id)}`
                        )
                      }
                    >
                      Pay one call
                    </Button>
                  </article>
                ))}
              </div>
              <section className="list-row">
                <Badge intent="warning">Simulated Metal adapter</Badge>
                <div className="toolbar">
                  <select
                    aria-label="Spending agent"
                    value={selectedAgent}
                    onChange={(e) => setAgentId(e.target.value)}
                  >
                    {snapshot.metal_agents?.map((a) => (
                      <option key={a.agent_id}>{a.agent_id}</option>
                    ))}
                  </select>
                  <input
                    aria-label="Agent new price"
                    type="number"
                    min="0.01"
                    step="0.01"
                    value={newPrice}
                    onChange={(e) => setNewPrice(e.target.value)}
                  />
                  <Button
                    disabled={unavailable || !selectedAgent || !(Number(newPrice) > 0)}
                    onClick={() =>
                      requestAction('Rebalance agent pricing', '/api/metal-rebalance', {
                        agent_id: selectedAgent,
                        new_price: newPrice,
                      })
                    }
                  >
                    Rebalance
                  </Button>
                  <input
                    aria-label="Agent maximum price cents"
                    type="number"
                    min="1"
                    step="1"
                    value={maxPrice}
                    onChange={(e) => setMaxPrice(e.target.value)}
                  />
                  <Button
                    disabled={
                      unavailable ||
                      !selectedAgent ||
                      !Number.isInteger(Number(maxPrice)) ||
                      Number(maxPrice) <= 0
                    }
                    onClick={() =>
                      requestAction('Replace agent mandate', '/api/metal-mandate', {
                        agent_id: selectedAgent,
                        new_max_price_cents: Number(maxPrice),
                      })
                    }
                  >
                    Replace mandate
                  </Button>
                  <Button
                    disabled={unavailable}
                    onClick={() =>
                      requestAction('Resolve agent dispute', '/api/metal-dispute')
                    }
                  >
                    Resolve dispute
                  </Button>
                </div>
                <JsonResult value={snapshot.last_dispute_report} />
              </section>
            </>
          )}

          {activeModule === 'evaluator' && (
            <div className="detail-grid">
              <section>
                <h2>Invoice evidence</h2>
                <textarea
                  rows={9}
                  aria-label="Raw unstructured supplier invoice"
                  value={customInvoice}
                  onChange={(e) => setCustomInvoice(e.target.value)}
                />
                <div className="toolbar">
                  <Button
                    variant="primary"
                    disabled={unavailable || !customInvoice.trim()}
                    onClick={() =>
                      requestAction('Inspect custom invoice', '/api/evaluate-invoice', {
                        obligation_id: 'obl-usd-1',
                        mode: 'custom',
                        custom_text: customInvoice,
                      })
                    }
                  >
                    Inspect invoice
                  </Button>
                  <Button
                    disabled={unavailable}
                    onClick={() =>
                      requestAction('Inspect matching invoice', '/api/evaluate-invoice', {
                        obligation_id: 'obl-usd-1',
                        mode: 'matching',
                      })
                    }
                  >
                    Matching invoice
                  </Button>
                  <Button
                    disabled={unavailable}
                    onClick={() =>
                      requestAction(
                        'Inspect mismatched invoice',
                        '/api/evaluate-invoice',
                        { obligation_id: 'obl-usd-1', mode: 'mismatched' }
                      )
                    }
                  >
                    Mismatched invoice
                  </Button>
                </div>
              </section>
              <section>
                <h2>Latest inspection</h2>
                <JsonResult value={snapshot.last_ai_inspection} />
                <h3>Forecast evidence</h3>
                <div className="toolbar">
                  <Button
                    disabled={unavailable}
                    onClick={() =>
                      requestAction(
                        'Simulate contradicting customer email',
                        '/api/customer-email',
                        { contradicts: true }
                      )
                    }
                  >
                    Simulate contradiction
                  </Button>
                  <Button
                    disabled={unavailable}
                    onClick={() =>
                      requestAction(
                        'Simulate confirming customer email',
                        '/api/customer-email',
                        { contradicts: false }
                      )
                    }
                  >
                    Simulate confirmation
                  </Button>
                </div>
              </section>
            </div>
          )}

          {activeModule === 'integrations' && (
            <>
              <OperatorAuthBar
                session={snapshot.session}
                unavailable={unavailable}
                onSwitchRole={(role, sod) =>
                  void perform(`Switch role to ${role}`, '/api/auth/role', {
                    role,
                    separation_of_duties: sod,
                  })
                }
                onQuickLogin={(email) =>
                  void perform(`Sign in ${email}`, '/api/auth/login', {
                    email,
                    password: 'ArchonTreasury#2026',
                  })
                }
              />
              <div className="list-row">
                <div className="section-heading">
                  <h2>Airwallex</h2>
                  <span className="money">{snapshot.mode ?? 'Unverified'}</span>
                </div>
                {snapshot.integrations?.airwallex && (
                  <Details value={snapshot.integrations.airwallex} />
                )}
                <div className="toolbar">
                  <Button
                    variant="primary"
                    disabled={unavailable}
                    onClick={() =>
                      requestAction(
                        'Verify provider integrations & reconcile',
                        '/api/integrations/verify'
                      )
                    }
                  >
                    Verify connection & reconcile
                  </Button>
                </div>
              </div>
              <div className="list-row">
                <h2>Bedrock & FX Feed</h2>
                {snapshot.integrations?.bedrock && (
                  <Details value={snapshot.integrations.bedrock} />
                )}
              </div>
              <div className="list-row">
                <h2>Metal</h2>
                <Badge intent="warning">Simulated adapter</Badge>
                {snapshot.integrations?.metal_x402 && (
                  <Details value={snapshot.integrations.metal_x402} />
                )}
              </div>
              {snapshot.reconciliation && (
                <div className="list-row">
                  <div className="section-heading">
                    <h2>Ledger reconciliation</h2>
                    <Badge
                      intent={
                        snapshot.reconciliation.execution_integrity_ok
                          ? 'success'
                          : 'critical'
                      }
                    >
                      {snapshot.reconciliation.execution_integrity_ok
                        ? 'INTEGRITY OK'
                        : 'DRIFT DETECTED'}
                    </Badge>
                  </div>
                  <Details value={snapshot.reconciliation} />
                </div>
              )}
              <div className="list-row">
                <h2>Invoice evaluator</h2>
                <JsonResult value={snapshot.last_ai_inspection} />
              </div>
              <div className="list-row">
                <h2>Session data</h2>
                <p className="muted">
                  Tenant state is persisted in SQLite WAL across restarts and isolated per
                  tenant.
                </p>
                <Button
                  disabled={unavailable}
                  onClick={() => requestAction('Reset synthetic session', '/api/reset')}
                >
                  Reset demo session
                </Button>
              </div>
            </>
          )}
        </>
      )}

      <ConfirmDialog
        confirmAction={confirmAction}
        unavailable={unavailable}
        onCancel={() => setConfirmAction(null)}
        onConfirm={(action) => {
          setConfirmAction(null);
          void perform(action.name, action.path, action.body);
        }}
      />
      <CommandMenu actions={actions} />
    </>
  );
};
