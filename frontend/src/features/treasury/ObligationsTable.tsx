import React, { useMemo } from 'react';
import { Badge, BadgeIntent } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Table, TableColumn } from '../../components/ui/Table';
import { SupplierObligation } from './types';

interface ObligationsTableProps {
  obligations: ReadonlyArray<SupplierObligation>;
  onApprove: (obligationId: string) => void;
  onExecute: (obligationId: string, approvalSha256: string | null) => void;
}

const PLAN_INTENT: Record<SupplierObligation['plan_action'], BadgeIntent> = {
  FUND_NOW: 'success',
  CONVERT_FX: 'indigo',
  DEFER: 'warning',
  ESCALATE: 'critical',
  SETTLED: 'neutral',
};

const STATE_INTENT: Record<SupplierObligation['approval_state'], BadgeIntent> = {
  VALID: 'success',
  INVALIDATED: 'critical',
  PAID: 'indigo',
  NOT_APPROVED: 'neutral',
};

const getObligationRowKey = (row: SupplierObligation): string => row.obligation_id;

export const ObligationsTable: React.FC<ObligationsTableProps> = ({
  obligations,
  onApprove,
  onExecute,
}) => {
  const columns = useMemo<ReadonlyArray<TableColumn<SupplierObligation>>>(
    () => [
      {
        key: 'supplier',
        header: 'Supplier & Invoice',
        render: (o) => (
          <div>
            <div className="font-semibold text-slate-900">{o.supplier_name}</div>
            <div className="text-xs text-slate-500 mt-0.5">
              <code className="font-mono bg-slate-100 border border-slate-200 px-1 rounded-sm">
                {o.obligation_id}
              </code>{' '}
              · {o.invoice_ref} · {o.summary}
            </div>
          </div>
        ),
      },
      {
        key: 'amount',
        header: 'Amount & Rail',
        align: 'right',
        render: (o) => (
          <div>
            <div className="font-mono tracking-tight tabular-nums font-bold text-slate-900">
              {o.amount}
            </div>
            <div className="text-xs text-slate-500 mt-0.5">
              <span className="inline-block bg-slate-100 border border-slate-300 px-1 rounded-sm font-bold text-[11px] text-slate-900">
                {o.rail}
              </span>{' '}
              Fee: <span className="font-mono tabular-nums">{o.rail_fee}</span>
            </div>
          </div>
        ),
      },
      {
        key: 'plan',
        header: 'Agent Triage Plan',
        render: (o) => (
          <div>
            <Badge intent={PLAN_INTENT[o.plan_action]}>{o.plan_action}</Badge>
            <div className="text-xs text-slate-500 mt-1">{o.plan_rationale}</div>
          </div>
        ),
      },
      {
        key: 'approval',
        header: 'Approval & Gate Status',
        render: (o) => (
          <div>
            <Badge intent={STATE_INTENT[o.approval_state]}>{o.approval_state}</Badge>
            {o.approval_sha256 && (
              <div className="text-xs text-slate-500 mt-1 font-mono tabular-nums">
                SHA-256: {o.approval_sha256.slice(0, 12)}
              </div>
            )}
            <div className="text-xs text-slate-500 mt-0.5">{o.action_reason}</div>
          </div>
        ),
      },
      {
        key: 'actions',
        header: 'Actions',
        render: (o) => (
          <div className="flex flex-col gap-1.5">
            <Button size="sm" variant="secondary" onClick={() => onApprove(o.obligation_id)}>
              Approve
            </Button>
            <Button
              size="sm"
              variant="primary"
              onClick={() => onExecute(o.obligation_id, o.approval_sha256)}
            >
              Execute
            </Button>
          </div>
        ),
      },
    ],
    [onApprove, onExecute],
  );

  return (
    <Table
      ariaLabel="Supplier payouts table, scrollable"
      columns={columns}
      rows={obligations}
      getRowKey={getObligationRowKey}
    />
  );
};
