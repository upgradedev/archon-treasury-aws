import React from 'react';
import { WalletBalance } from './types';

interface KpiGridProps {
  balances: ReadonlyArray<WalletBalance>;
}

export const KpiGrid: React.FC<KpiGridProps> = ({ balances }) => {
  return (
    <section aria-label="Multi-Currency Liquidity and Reserve Floors">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {balances.map((wallet) => {
          const floorRatio =
            wallet.amount_cents > 0
              ? Math.min(100, Math.round((wallet.reserve_floor_cents / wallet.amount_cents) * 100))
              : 100;
          const headroomPct = Math.max(0, 100 - floorRatio);

          return (
            <div
              key={wallet.account_id}
              className="bg-white border border-slate-200 rounded-md p-3.5 hover:bg-slate-50/80 transition-colors duration-150"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-600">
                  {wallet.currency} Wallet
                </span>
                <span className="font-mono tabular-nums text-xs text-slate-500">
                  {wallet.account_id}
                </span>
              </div>
              <div className="text-lg font-bold font-mono tracking-tight tabular-nums text-slate-900 mb-2">
                {wallet.amount}
              </div>
              <div
                className="h-1.5 bg-slate-200 rounded-sm overflow-hidden mb-2"
                role="img"
                aria-label={`${wallet.currency} reserve floor utilization`}
              >
                <div className="h-full bg-indigo-600" style={{ width: `${headroomPct}%` }} />
              </div>
              <div className="flex items-center justify-between text-xs text-slate-500">
                <span>
                  Reserve floor:{' '}
                  <strong className="font-mono tabular-nums text-slate-900">
                    {wallet.reserve_floor}
                  </strong>
                </span>
                <span>
                  Spendable:{' '}
                  <strong className="font-mono tabular-nums text-slate-900">
                    {wallet.headroom_major}
                  </strong>
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
};
