import React from 'react';
import { useShell } from '../../context/ShellContext';

export const TopNav: React.FC = () => {
  const { setCommandMenuOpen } = useShell();

  return (
    <header className="bg-white border-b border-slate-200 px-5 py-3 flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 className="text-base font-bold text-slate-900 tracking-tight">
          Archon Treasury (powered by Kerdon)
        </h1>
        <p className="text-xs text-slate-500 mt-0.5 max-w-3xl">
          Archon Treasury recalculates Airwallex FX and supplier payouts when a deposit lands,
          invalidating stale approvals so cross-border teams never breach their cash reserve floor.
        </p>
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => setCommandMenuOpen(true)}
          aria-label="Open command menu (Ctrl+K)"
          className="inline-flex items-center gap-2 bg-slate-50 border border-slate-300 rounded-md px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 transition-colors duration-150"
        >
          <span>Quick Command &amp; Search...</span>
          <kbd className="font-mono text-[11px] bg-white border border-slate-300 rounded-sm px-1.5 py-0.5 text-slate-600">
            Ctrl+K
          </kbd>
        </button>
      </div>
    </header>
  );
};
