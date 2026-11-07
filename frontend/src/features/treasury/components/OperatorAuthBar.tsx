import React from 'react';
import { Badge } from '../../../components/ui/Badge';
import { Button } from '../../../components/ui/Button';
import { SessionInfo } from '../types';

interface OperatorAuthBarProps {
  session?: SessionInfo;
  unavailable: boolean;
  onSwitchRole: (role: string, separationOfDuties?: boolean) => void;
  onQuickLogin: (email: string) => void;
}

export const OperatorAuthBar: React.FC<OperatorAuthBarProps> = ({
  session,
  unavailable,
  onSwitchRole,
  onQuickLogin,
}) => {
  if (!session) return null;

  return (
    <div
      aria-label="Operator identity and access controls"
      className="list-row"
    >
      <div className="section-heading">
        <div>
          <strong>{session.display_name}</strong>{' '}
          <span className="muted">({session.tenant_id})</span>
        </div>
        <div className="toolbar">
          <Badge intent="indigo">Role: {session.role}</Badge>
          {session.separation_of_duties && (
            <Badge intent="warning">SoD Enforced</Badge>
          )}
        </div>
      </div>
      <div className="toolbar">
        <select
          aria-label="Active operator role"
          value={session.role}
          disabled={unavailable}
          onChange={(e) => onSwitchRole(e.target.value, session.separation_of_duties)}
        >
          <option value="ADMIN">ADMIN (Full Access)</option>
          <option value="APPROVER">APPROVER (Approve / Deposit / Floor)</option>
          <option value="WRITER">WRITER (Execute / Convert)</option>
          <option value="EVALUATOR">EVALUATOR (Invoice Inspect)</option>
          <option value="READER">READER (Read / Export Only)</option>
        </select>
        <Button
          size="sm"
          disabled={unavailable}
          onClick={() => onQuickLogin('elena.vance@vancehardware.io')}
        >
          Sign in Approver
        </Button>
        <Button
          size="sm"
          disabled={unavailable}
          onClick={() => onQuickLogin('marcus.chen@vancehardware.io')}
        >
          Sign in Writer
        </Button>
      </div>
    </div>
  );
};
