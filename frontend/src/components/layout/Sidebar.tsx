import React from 'react';
import { EntityScope, ErpModuleId, useShell } from '../../context/ShellContext';
import { Badge, BadgeIntent } from '../ui/Badge';

interface NavItem {
  id: ErpModuleId;
  label: string;
  badgeText: string;
  badgeIntent: BadgeIntent;
}

const NAV_ITEMS: ReadonlyArray<NavItem> = [
  { id: 'all', label: 'All Modules (Cockpit)', badgeText: '7', badgeIntent: 'indigo' },
  { id: 'payouts', label: 'Supplier Payouts (Kit 1)', badgeText: '4', badgeIntent: 'neutral' },
  { id: 'audit', label: 'Completeness Audit', badgeText: '21', badgeIntent: 'warning' },
  { id: 'incidents', label: 'Incident Ops (Kit 3)', badgeText: 'SWIFT', badgeIntent: 'critical' },
  { id: 'visa', label: 'Visa Cards (Kit 9)', badgeText: 'VISA', badgeIntent: 'indigo' },
  { id: 'metal', label: 'Metal x402 (Kit 11)', badgeText: 'USDZ', badgeIntent: 'success' },
  { id: 'evaluator', label: 'Bedrock Evaluator', badgeText: 'AI', badgeIntent: 'indigo' },
];

export const Sidebar: React.FC = () => {
  const {
    sidebarCollapsed,
    toggleSidebar,
    activeCompany,
    setActiveCompany,
    activeModule,
    setActiveModule,
  } = useShell();

  return (
    <aside
      aria-label="ERP Module Navigation"
      className={`${
        sidebarCollapsed ? 'w-16' : 'w-64'
      } flex-shrink-0 bg-slate-900 text-slate-300 flex flex-col border-r border-slate-800 transition-all duration-150`}
    >
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center justify-center w-6 h-6 rounded-sm bg-indigo-500 text-white font-bold text-xs">
            A
          </span>
          {!sidebarCollapsed && (
            <span className="font-bold text-white text-sm tracking-tight">Archon ERP</span>
          )}
        </div>
        <button
          type="button"
          onClick={toggleSidebar}
          title="Collapse or expand sidebar"
          className="px-1.5 py-0.5 text-xs bg-slate-800 text-slate-200 border border-slate-700 rounded-sm hover:bg-slate-700"
        >
          {sidebarCollapsed ? '»' : '«'}
        </button>
      </div>

      {!sidebarCollapsed && (
        <div className="m-3 p-2 bg-slate-800 border border-slate-700 rounded-sm">
          <label
            htmlFor="company-switcher-select"
            className="block text-[11px] uppercase tracking-wider text-slate-400 font-semibold mb-1"
          >
            Entity Scope
          </label>
          <select
            id="company-switcher-select"
            value={activeCompany}
            onChange={(e) => setActiveCompany(e.target.value as EntityScope)}
            className="w-full bg-slate-800 text-white text-xs font-semibold focus:outline-none"
          >
            <option value="ALL">Vance Hardware Studio [Consolidated]</option>
            <option value="USD">Vance US Operations Inc. [USD]</option>
            <option value="EUR">Vance Europe GmbH [EUR]</option>
            <option value="GBP">Vance UK Logistics Ltd. [GBP]</option>
          </select>
        </div>
      )}

      <ul className="flex-1 py-2 space-y-0.5">
        {NAV_ITEMS.map((item) => {
          const isActive = activeModule === item.id;
          return (
            <li key={item.id}>
              <button
                type="button"
                onClick={() => setActiveModule(item.id)}
                className={`w-full text-left px-3.5 py-2 text-xs font-medium flex items-center justify-between transition-colors duration-150 ${
                  isActive
                    ? 'bg-slate-800 text-white border-l-4 border-indigo-500 font-semibold'
                    : 'text-slate-300 border-l-4 border-transparent hover:bg-slate-800/70 hover:text-white'
                }`}
              >
                {!sidebarCollapsed && <span>{item.label}</span>}
                <Badge intent={item.badgeIntent}>{item.badgeText}</Badge>
              </button>
            </li>
          );
        })}
      </ul>

      {!sidebarCollapsed && (
        <div className="p-3 border-t border-slate-800 text-xs text-slate-400">
          <div className="font-mono tabular-nums text-slate-100 font-semibold">
            Engine: 74/74 (2ms)
          </div>
          <div>LLM Baseline: 28/62 (3,400ms)</div>
        </div>
      )}
    </aside>
  );
};
