import React from 'react';
import { Badge } from '../../components/ui/Badge';
import { CompletenessFinding } from './types';

interface CompletenessAlertsProps {
  findings: ReadonlyArray<CompletenessFinding>;
}

export const CompletenessAlerts: React.FC<CompletenessAlertsProps> = ({ findings }) => {
  if (findings.length === 0) {
    return (
      <p className="text-xs text-slate-500">
        No completeness gaps detected across 21 deterministic rules.
      </p>
    );
  }

  return (
    <ul className="space-y-2 text-xs">
      {findings.map((finding) => {
        const findingKey = `${finding.rule_id}-${finding.subject_id}`;
        const intent = finding.severity === 'BLOCKER' ? 'critical' : 'warning';
        return (
          <li
            key={findingKey}
            className="p-2.5 bg-slate-50/50 border border-slate-200 rounded-sm hover:bg-slate-50/80 transition-colors duration-150"
          >
            <div className="flex items-center gap-2 mb-1">
              <Badge intent={intent}>
                {finding.rule_id} · {finding.severity}
              </Badge>
              <strong className="font-mono text-slate-900">{finding.subject_id}</strong>
            </div>
            <p className="text-slate-600">{finding.message}</p>
          </li>
        );
      })}
    </ul>
  );
};
