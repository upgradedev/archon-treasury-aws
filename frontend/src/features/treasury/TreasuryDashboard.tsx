import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { CommandMenu } from '../../components/layout/CommandMenu';
import { Drawer } from '../../components/layout/Drawer';
import { Button } from '../../components/ui/Button';
import { useShell } from '../../context/ShellContext';
import { CompletenessAlerts } from './CompletenessAlerts';
import { KpiGrid } from './KpiGrid';
import { ObligationsTable } from './ObligationsTable';
import { TreasurySnapshot } from './types';

export const TreasuryDashboard: React.FC = () => {
  const { activeCompany } = useShell();
  const [snapshot, setSnapshot] = useState<TreasurySnapshot>({
    balances: [],
    obligations: [],
    findings: [],
  });
  const [statusMessage, setStatusMessage] = useState<string>(
    'Ready. Approve a USD payout and a EUR payout, then land a EUR 500.00 deposit to watch selective invalidation.',
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
    ],
    [handleSimulateDeposit],
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

      <KpiGrid balances={filteredBalances} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-start">
        <div className="lg:col-span-2 space-y-4">
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
        </div>

        <div className="space-y-4">
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

          <Drawer title="Completeness Findings (21 Rules)" subtitle="Zero-LLM Engine">
            <CompletenessAlerts findings={snapshot.findings} />
          </Drawer>
        </div>
      </div>

      <CommandMenu actions={commandActions} />
    </>
  );
};
