import React from 'react';

export type BadgeIntent = 'success' | 'warning' | 'critical' | 'indigo' | 'neutral';

const INTENT_CLASSES: Record<BadgeIntent, string> = {
  success: 'text-emerald-700 bg-emerald-50 border-emerald-200',
  warning: 'text-amber-700 bg-amber-50 border-amber-200',
  critical: 'text-rose-700 bg-rose-50 border-rose-200',
  indigo: 'text-indigo-700 bg-indigo-50 border-indigo-200',
  neutral: 'text-slate-600 bg-slate-100 border-slate-300',
};

interface BadgeProps {
  intent?: BadgeIntent;
  children: React.ReactNode;
}

export const Badge: React.FC<BadgeProps> = ({ intent = 'neutral', children }) => {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-sm text-xs font-bold border whitespace-nowrap ${INTENT_CLASSES[intent]}`}
    >
      {children}
    </span>
  );
};
