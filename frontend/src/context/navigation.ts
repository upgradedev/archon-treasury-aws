export const views = [
  { id: 'all', label: 'Command Center', icon: '◈', group: 'Operate' },
  { id: 'payouts', label: 'Payouts', icon: '↗', group: 'Operate' },
  { id: 'approvals', label: 'Approvals', icon: '✓', group: 'Operate' },
  { id: 'deposits', label: 'Deposits', icon: '↓', group: 'Operate' },
  { id: 'wallets', label: 'Wallets & floors', icon: '▤', group: 'Liquidity' },
  { id: 'fx', label: 'FX desk', icon: '⇄', group: 'Liquidity' },
  { id: 'audit', label: 'Completeness', icon: '☷', group: 'Assurance' },
  { id: 'receipts', label: 'Receipts & audit', icon: '▧', group: 'Assurance' },
  { id: 'incidents', label: 'Incidents', icon: '△', group: 'Assurance' },
  { id: 'visa', label: 'Virtual cards', icon: '▣', group: 'Extend' },
  { id: 'metal', label: 'Agent spending', icon: '◇', group: 'Extend' },
  { id: 'evaluator', label: 'Invoice evaluator', icon: '✧', group: 'Extend' },
  { id: 'integrations', label: 'Integrations', icon: '⌁', group: 'Extend' },
] as const;
export type ViewId = typeof views[number]['id'];
export function readView(): ViewId {
 const value = window.location.hash.slice(1);
 return views.find(v => v.id === value)?.id ?? 'all';
}
