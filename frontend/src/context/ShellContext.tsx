import React, { createContext, useContext, useState } from 'react';

export type EntityScope = 'ALL' | 'USD' | 'EUR' | 'GBP';
export type ErpModuleId = 'all' | 'payouts' | 'audit' | 'incidents' | 'metal' | 'evaluator';

interface ShellContextValue {
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  activeCompany: EntityScope;
  setActiveCompany: (scope: EntityScope) => void;
  activeModule: ErpModuleId;
  setActiveModule: (moduleId: ErpModuleId) => void;
  commandMenuOpen: boolean;
  setCommandMenuOpen: (open: boolean) => void;
}

const ShellContext = createContext<ShellContextValue | undefined>(undefined);

export const ShellProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [activeCompany, setActiveCompany] = useState<EntityScope>('ALL');
  const [activeModule, setActiveModule] = useState<ErpModuleId>('all');
  const [commandMenuOpen, setCommandMenuOpen] = useState(false);

  const toggleSidebar = () => setSidebarCollapsed((prev) => !prev);

  return (
    <ShellContext.Provider
      value={{
        sidebarCollapsed,
        toggleSidebar,
        activeCompany,
        setActiveCompany,
        activeModule,
        setActiveModule,
        commandMenuOpen,
        setCommandMenuOpen,
      }}
    >
      {children}
    </ShellContext.Provider>
  );
};

export function useShell(): ShellContextValue {
  const ctx = useContext(ShellContext);
  if (!ctx) {
    throw new Error('useShell must be used inside a ShellProvider');
  }
  return ctx;
}
