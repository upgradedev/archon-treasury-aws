import React from 'react';
import { EntityScope, useShell } from '../../context/ShellContext';
import { views } from '../../context/navigation';
import { Button } from '../ui/Button';
export const Sidebar: React.FC = () => {
 const { sidebarCollapsed, toggleSidebar, activeCompany, setActiveCompany, activeModule, setActiveModule } = useShell();
 return <aside className={`archon-sidebar ${sidebarCollapsed ? 'is-collapsed' : ''}`} aria-label="Treasury navigation">
  <div className="brand"><span className="brand-mark">A</span>{!sidebarCollapsed && <span className="display">Archon</span>}<Button variant="ghost" onClick={toggleSidebar} aria-label="Toggle navigation" title="Toggle navigation">{sidebarCollapsed ? '»' : '«'}</Button></div>
  {!sidebarCollapsed && <label className="scope-label">Currency scope<select value={activeCompany} onChange={e => setActiveCompany(e.target.value as EntityScope)}><option value="ALL">Vance Hardware · All currencies</option><option value="USD">USD wallet</option><option value="EUR">EUR wallet</option><option value="GBP">GBP wallet</option></select></label>}
  <nav>{['Operate', 'Liquidity', 'Assurance', 'Extend'].map(group => <div className="nav-group" key={group}>{!sidebarCollapsed && <p className="eyebrow">{group}</p>}{views.filter(v => v.group === group).map(v => <Button key={v.id} variant="ghost" className={`nav-item ${activeModule === v.id ? 'is-active' : ''}`} title={v.label} aria-label={v.label} aria-current={activeModule === v.id ? 'page' : undefined} onClick={() => setActiveModule(v.id)}><span aria-hidden="true" className="nav-icon">{v.icon}</span>{!sidebarCollapsed && v.label}</Button>)}</div>)}</nav>
  {!sidebarCollapsed && <div className="sidebar-foot"><span className="avatar">VH</span><div>Vance Hardware<div className="muted">Treasury workspace</div></div></div>}
 </aside>;
};
