import React from 'react';
import { useShell } from '../../context/ShellContext';
import { views } from '../../context/navigation';
import { Button } from '../ui/Button';
export const TopNav: React.FC = () => {
 const { setCommandMenuOpen, activeModule } = useShell();
 return <header className="top-nav"><span className="muted">Workspace / <strong>{views.find(v => v.id === activeModule)?.label}</strong></span><div className="top-actions"><a className="audit-link" href="/api/audit-export.csv" download="archon-treasury-audit.csv">↓ Export audit</a><Button onClick={() => setCommandMenuOpen(true)} aria-label="Open command menu">⌕ <span>Search & commands</span></Button></div></header>;
};
