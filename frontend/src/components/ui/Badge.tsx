import React from 'react';
export type BadgeIntent='success'|'warning'|'critical'|'indigo'|'neutral';
const INTENT_CLASSES: Record<BadgeIntent,string>={success:'badge-success',warning:'badge-warning',critical:'badge-critical',indigo:'badge-indigo',neutral:'badge-neutral'};
export const Badge: React.FC<{intent?:BadgeIntent;children:React.ReactNode}>=({intent='neutral',children})=><span className={`inline-flex items-center px-2 py-0.5 rounded-sm text-xs font-bold border whitespace-nowrap ${INTENT_CLASSES[intent]}`}>{children}</span>;
