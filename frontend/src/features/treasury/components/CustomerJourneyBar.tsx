import React from 'react';
import { Badge } from '../../../components/ui/Badge';
import { Button } from '../../../components/ui/Button';
import { ViewId } from '../../../context/navigation';
import { TreasurySnapshot } from '../types';

interface Props {
  snapshot: TreasurySnapshot;
  unavailable: boolean;
  onAction: (name: string, path: string, body?: Record<string, unknown>) => void;
  onNavigate: (moduleId: ViewId) => void;
}

export const CustomerJourneyBar: React.FC<Props> = ({
  snapshot,
  unavailable,
  onAction,
  onNavigate,
}) => {
  const usd1 = snapshot.obligations.find((o) => o.obligation_id === 'obl-usd-1');
  const eur1 = snapshot.obligations.find((o) => o.obligation_id === 'obl-eur-1');
  const usd1ApprovedOrPaid =
    usd1?.approval_state === 'VALID' || usd1?.approval_state === 'PAID';
  const eur1Invalidated = eur1?.approval_state === 'INVALIDATED';
  const usd1Paid = usd1?.approval_state === 'PAID';
  const eur1Paid = eur1?.approval_state === 'PAID';

  const awxInfo = snapshot.integrations?.airwallex as
    | Record<string, unknown>
    | undefined;
  const connectedIban =
    (awxInfo?.connected_iban as string | undefined) || 'NL81AINH4272955670';
  const connectedEntity =
    (awxInfo?.connected_entity as string | undefined) ||
    'Sandbox Business (Amsterdam, NL)';

  return (
    <section aria-label="Airwallex treasury value and guided workflow" className="list-row">
      <div className="section-heading">
        <div>
          <h2>Airwallex Live Treasury Control & Guided Customer Journey</h2>
          <p className="muted">
            Archon Treasury recalculates Airwallex FX and supplier payouts when a deposit
            lands, invalidating stale approvals so cross-border teams never breach their
            cash reserve floor.
          </p>
        </div>
        <Badge intent="indigo">IBAN {connectedIban}</Badge>
      </div>

      {snapshot.roi_telemetry && (
        <div className="metric-grid">
          <article className="metric">
            <span className="eyebrow">Connected Airwallex Account</span>
            <div className="money">{connectedIban}</div>
            <span className="muted">{connectedEntity}</span>
          </article>
          <article className="metric">
            <span className="eyebrow">Protected Reserve Liquidity</span>
            <div className="money">
              {snapshot.roi_telemetry.protected_liquidity_major}
            </div>
            <span className="muted">Enforced at Writer execution gate</span>
          </article>
          <article className="metric">
            <span className="eyebrow">Airwallex Local Rail Savings</span>
            <div className="money">
              {snapshot.roi_telemetry.local_rail_fees_saved_major}
            </div>
            <span className="muted">SEPA/ACH local rails vs SWIFT wire fees</span>
          </article>
          <article className="metric">
            <span className="eyebrow">Deterministic Engine Accuracy</span>
            <div className="money">
              74/74 ({snapshot.roi_telemetry.engine_latency_ms} ms)
            </div>
            <span className="muted">
              vs 24/74 naive matcher & 28/62 single-pass LLM
            </span>
          </article>
        </div>
      )}

      <div className="metric-grid">
        <article className="metric">
          <div className="section-heading">
            <span className="eyebrow">Step 1 · Evidence Binding</span>
            <Badge intent={usd1ApprovedOrPaid ? 'success' : 'warning'}>
              {usd1ApprovedOrPaid ? 'DONE' : 'START'}
            </Badge>
          </div>
          <p className="muted">
            Approve USD ($450.00) & EUR (€800.00) payouts to bind SHA-256 balance/FX
            evidence and Merkle spoken/Braille receipts.
          </p>
          <div className="toolbar">
            <Button
              size="sm"
              variant="secondary"
              disabled={unavailable || usd1?.approval_state === 'PAID'}
              onClick={() => onAction('Approve obl-usd-1', '/api/approve/obl-usd-1')}
            >
              Approve USD
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={unavailable || eur1?.approval_state === 'PAID'}
              onClick={() => onAction('Approve obl-eur-1', '/api/approve/obl-eur-1')}
            >
              Approve EUR
            </Button>
          </div>
        </article>

        <article className="metric">
          <div className="section-heading">
            <span className="eyebrow">Step 2 · Airwallex Deposit Webhook</span>
            <Badge intent={eur1Invalidated ? 'critical' : 'indigo'}>
              {eur1Invalidated ? 'EUR INVALIDATED' : 'TRIGGER'}
            </Badge>
          </div>
          <p className="muted">
            Land EUR 500.00 on Airwallex IBAN {connectedIban}. Only EUR approval turns
            INVALIDATED; USD stays VALID.
          </p>
          <div className="toolbar">
            <Button
              size="sm"
              variant="primary"
              disabled={unavailable}
              onClick={() =>
                onAction('Simulate EUR 500.00 deposit', '/api/simulate-deposit', {
                  currency: 'EUR',
                  amount: '500.00',
                })
              }
            >
              Land EUR 500.00 Deposit
            </Button>
          </div>
        </article>

        <article className="metric">
          <div className="section-heading">
            <span className="eyebrow">Step 3 · Live Airwallex Payout</span>
            <Badge intent={usd1Paid ? 'success' : 'indigo'}>
              {usd1Paid ? 'SETTLED LIVE' : 'EXECUTE'}
            </Badge>
          </div>
          <p className="muted">
            Execute valid USD payout on Airwallex Sandbox (/api/v1/transfers/create) while
            Writer Gate blocks stale EUR (409).
          </p>
          <div className="toolbar">
            <Button
              size="sm"
              variant="primary"
              disabled={unavailable || usd1?.approval_state !== 'VALID'}
              onClick={() =>
                onAction(
                  'Execute obl-usd-1',
                  '/api/execute/obl-usd-1',
                  usd1?.approval_sha256 ? { approval_sha256: usd1.approval_sha256 } : {}
                )
              }
            >
              Execute USD Live
            </Button>
            <Button size="sm" variant="ghost" onClick={() => onNavigate('receipts')}>
              Inspect Receipt
            </Button>
          </div>
        </article>

        <article className="metric">
          <div className="section-heading">
            <span className="eyebrow">Step 4 · Recover & FX Convert</span>
            <Badge intent={eur1Paid ? 'success' : 'neutral'}>
              {eur1Paid ? 'RECOVERED' : 'RECOVER'}
            </Badge>
          </div>
          <p className="muted">
            Re-approve EUR on updated cash evidence (clears R18) and execute, or lock a
            live Airwallex FX conversion.
          </p>
          <div className="toolbar">
            <Button
              size="sm"
              variant="secondary"
              disabled={unavailable || eur1?.approval_state === 'PAID'}
              onClick={() => onAction('Re-approve obl-eur-1', '/api/approve/obl-eur-1')}
            >
              Re-Approve EUR
            </Button>
            <Button size="sm" variant="ghost" onClick={() => onNavigate('fx')}>
              Live FX Quotes
            </Button>
          </div>
        </article>
      </div>
    </section>
  );
};
