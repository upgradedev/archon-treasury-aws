import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { CommandMenu } from '../../components/layout/CommandMenu';
import { Drawer } from '../../components/layout/Drawer';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { useShell } from '../../context/ShellContext';
import { CompletenessAlerts } from './CompletenessAlerts';
import { KpiGrid } from './KpiGrid';
import { ObligationsTable } from './ObligationsTable';
import { TreasurySnapshot } from './types';

export const TreasuryDashboard: React.FC = () => {
  const { activeCompany, activeModule } = useShell();
  const [snapshot, setSnapshot] = useState<TreasurySnapshot>({
    balances: [],
    obligations: [],
    findings: [],
  });
  const [customInvoice, setCustomInvoice] = useState<string>(
    'INVOICE INV-2026-8841\nSupplier: Shenzhen Precision PCB Ltd.\nCounterparty: supplier-a\nObligation: obl-usd-1\nTotal due USD 450.00',
  );
  const [statusMessage, setStatusMessage] = useState<string>(
    'Ready. Approve USD & EUR payouts, then land a EUR 500.00 deposit to watch selective invalidation.',
  );

  const fetchSnapshot = useCallback(async () => {
    const res = await fetch('/api/state');
    if (res.ok) {
      const data = (await res.json()) as TreasurySnapshot;
      setSnapshot(data);
    }
  }, []);

  useEffect(() => {
    void fetchSnapshot();
  }, [fetchSnapshot]);

  const handleApprove = useCallback(
    async (obligationId: string) => {
      const res = await fetch(`/api/approve/${obligationId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      const data = await res.json();
      if (res.ok) {
        setStatusMessage(`Approved ${obligationId} (${String(data.approval_sha256).slice(0, 12)}).`);
        await fetchSnapshot();
      }
    },
    [fetchSnapshot],
  );

  const handleExecute = useCallback(
    async (obligationId: string, approvalSha256: string | null) => {
      const res = await fetch(`/api/execute/${obligationId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(approvalSha256 ? { approval_sha256: approvalSha256 } : {}),
      });
      const data = await res.json();
      if (res.ok) {
        setStatusMessage(`Executed ${obligationId} (${String(data.transfer_id)}).`);
      } else {
        setStatusMessage(String(data.error || 'Refused by Writer gate.'));
      }
      await fetchSnapshot();
    },
    [fetchSnapshot],
  );

  const handleSimulateDeposit = useCallback(
    async (currency: string, amount: string) => {
      const res = await fetch('/api/simulate-deposit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ currency, amount }),
      });
      const data = await res.json();
      if (res.ok) {
        const inv = Array.isArray(data.invalidated) ? data.invalidated.join(', ') : 'none';
        setStatusMessage(`Landed ${currency} ${amount} deposit. Invalidated: ${inv || 'none'}.`);
        await fetchSnapshot();
      }
    },
    [fetchSnapshot],
  );

  const handleVisaIssue = useCallback(async () => {
    const res = await fetch('/api/visa-issue', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    const data = await res.json();
    if (res.ok) {
      setStatusMessage(`Issued single-use Virtual Visa *${String(data.card_last4)} locked to MCC ${String(data.allowed_mcc)}.`);
      await fetchSnapshot();
    }
  }, [fetchSnapshot]);

  const handleVisaCharge = useCallback(
    async (chargeCents: number, mcc: string) => {
      const res = await fetch('/api/visa-charge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ charge_cents: chargeCents, merchant_mcc: mcc }),
      });
      const data = await res.json();
      if (res.ok) {
        setStatusMessage(`${String(data.last_verdict)}: ${String(data.last_reason)}`);
        await fetchSnapshot();
      }
    },
    [fetchSnapshot],
  );

  const handleInspectCustomInvoice = useCallback(async () => {
    const res = await fetch('/api/evaluate-invoice', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        obligation_id: 'obl-usd-1',
        mode: 'custom',
        custom_text: customInvoice,
      }),
    });
    const data = await res.json();
    if (res.ok) {
      setStatusMessage(
        `Evaluator (${String(data.engine)}, ${String(data.latency_ms)}ms): ${String(data.verdict)} - ${String(data.reason)}`,
      );
      await fetchSnapshot();
    }
  }, [customInvoice, fetchSnapshot]);

  const showModule = (mod: string) => activeModule === 'all' || activeModule === mod;

  const filteredBalances = useMemo(
    () =>
      activeCompany === 'ALL'
        ? snapshot.balances
        : snapshot.balances.filter((b) => b.currency === activeCompany),
    [activeCompany, snapshot.balances],
  );

  const filteredObligations = useMemo(
    () =>
      activeCompany === 'ALL'
        ? snapshot.obligations
        : snapshot.obligations.filter((o) => o.currency === activeCompany),
    [activeCompany, snapshot.obligations],
  );

  const commandActions = useMemo(
    () => [
      {
        id: 'cmd-eur-deposit',
        label: 'Land Signed EUR 500.00 Deposit Webhook (Selective Invalidation)',
        moduleTag: 'Kit 1',
        run: () => void handleSimulateDeposit('EUR', '500.00'),
      },
      {
        id: 'cmd-usd-deposit',
        label: 'Land Signed USD 200.00 Deposit (Restore Reserve Floor)',
        moduleTag: 'Kit 1',
        run: () => void handleSimulateDeposit('USD', '200.00'),
      },
      {
        id: 'cmd-visa-issue',
        label: 'Issue Single-Use Virtual Visa Card (*4829) Locked to MCC 5045',
        moduleTag: 'Kit 9 Visa',
        run: () => void handleVisaIssue(),
      },
      {
        id: 'cmd-bedrock-custom',
        label: 'Inspect Custom Supplier Invoice Text via Live Amazon Bedrock',
        moduleTag: 'Bedrock AI',
        run: () => void handleInspectCustomInvoice(),
      },
    ],
    [handleInspectCustomInvoice, handleSimulateDeposit, handleVisaIssue],
  );

  return (
    <>
      <div
        role="status"
        aria-live="polite"
        className="px-3.5 py-2 rounded-md border border-emerald-200 bg-emerald-50 text-emerald-700 text-xs font-semibold"
      >
        {statusMessage}
      </div>

      {showModule('payouts') && <KpiGrid balances={filteredBalances} />}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-start">
        <div className="lg:col-span-2 space-y-4">
          {showModule('payouts') && (
            <Drawer
              title="Supplier Payouts & Adaptive Triage Plan (72-Hour Window)"
              subtitle="Tabular-Nums · SHA-256 Bound"
            >
              <ObligationsTable
                obligations={filteredObligations}
                onApprove={(id) => void handleApprove(id)}
                onExecute={(id, sha) => void handleExecute(id, sha)}
              />
            </Drawer>
          )}

          {showModule('visa') && snapshot.visa_mandate && (
            <Drawer
              title="Kit 9: Visa Virtual Commercial Card & MCC Spend Controls"
              subtitle="Single-Use Mandate · 150 bps Rebate"
            >
              <div className="text-xs space-y-1.5 mb-3">
                <div>
                  Card <code className="font-mono">{snapshot.visa_mandate.card_id}</code> (*
                  {snapshot.visa_mandate.card_last4}) ·{' '}
                  <strong>{snapshot.visa_mandate.supplier_name}</strong>
                </div>
                <div className="font-mono tabular-nums">
                  Cap: {snapshot.visa_mandate.limit} · Locked MCC:{' '}
                  {snapshot.visa_mandate.allowed_mcc} · Rebate:{' '}
                  {snapshot.visa_mandate.rebate_earned}
                </div>
                <div className="flex items-center gap-2">
                  <Badge intent="indigo">{snapshot.visa_mandate.status}</Badge>
                  {snapshot.visa_mandate.last_reason && (
                    <span className="text-slate-600">{snapshot.visa_mandate.last_reason}</span>
                  )}
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="secondary" onClick={() => void handleVisaIssue()}>
                  1. Issue Single-Use Visa (*4829)
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => void handleVisaCharge(45000, '5812')}
                >
                  2. Test Wrong MCC (5812)
                </Button>
                <Button
                  size="sm"
                  variant="primary"
                  onClick={() => void handleVisaCharge(45000, '5045')}
                >
                  3. Authorize Valid PCB Charge (MCC 5045)
                </Button>
              </div>
            </Drawer>
          )}
        </div>

        <div className="space-y-4">
          {showModule('payouts') && (
            <Drawer title="Simulate Signed Airwallex Deposit" subtitle="HMAC-SHA256">
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => void handleSimulateDeposit('EUR', '500.00')}
                >
                  Land EUR 500.00
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => void handleSimulateDeposit('USD', '200.00')}
                >
                  Land USD 200.00
                </Button>
              </div>
            </Drawer>
          )}

          {showModule('evaluator') && (
            <Drawer
              title="Evaluator Port: Unstructured Invoice Verification"
              subtitle="Claude Haiku 4.5 (Bedrock)"
            >
              <textarea
                rows={4}
                value={customInvoice}
                onChange={(e) => setCustomInvoice(e.target.value)}
                aria-label="Raw unstructured supplier invoice"
                className="w-full p-2 text-xs font-mono border border-slate-300 rounded-sm mb-2"
              />
              <Button
                variant="primary"
                size="sm"
                onClick={() => void handleInspectCustomInvoice()}
              >
                Inspect Custom Invoice Text (Live Bedrock)
              </Button>
            </Drawer>
          )}

          {showModule('audit') && (
            <Drawer title="Completeness Findings (21 Rules)" subtitle="Zero-LLM Engine">
              <CompletenessAlerts findings={snapshot.findings} />
            </Drawer>
          )}
        </div>
      </div>

      <CommandMenu actions={commandActions} />
    </>
  );
};
