import React, { createContext, useContext, useState, useEffect } from 'react';
import { readView, ViewId } from './navigation';
export type EntityScope = 'ALL' | 'USD' | 'EUR' | 'GBP';
export type ErpModuleId = ViewId;
interface ShellContextValue {
 sidebarCollapsed: boolean; toggleSidebar: () => void;
 activeCompany: EntityScope; setActiveCompany: (scope: EntityScope) => void;
 activeModule: ErpModuleId; setActiveModule: (moduleId: ErpModuleId) => void;
 commandMenuOpen: boolean; setCommandMenuOpen: (open: boolean) => void;
}
const ShellContext = createContext<ShellContextValue | undefined>(undefined);
export const ShellProvider: React.FC<{children: React.ReactNode}> = ({children}) => {
 const [sidebarCollapsed,setSidebarCollapsed]=useState(false);
 const [activeCompany,setActiveCompany]=useState<EntityScope>('ALL');
 const [activeModule,updateModule]=useState<ErpModuleId>(readView);
 const setActiveModule=(value: ErpModuleId)=>{window.location.hash=value;updateModule(value);};
 useEffect(()=>{const sync=()=>updateModule(readView());window.addEventListener('hashchange',sync);return()=>window.removeEventListener('hashchange',sync);},[]);
 const [commandMenuOpen,setCommandMenuOpen]=useState(false);
 const toggleSidebar=()=>setSidebarCollapsed(prev=>!prev);
 return <ShellContext.Provider value={{sidebarCollapsed,toggleSidebar,activeCompany,setActiveCompany,activeModule,setActiveModule,commandMenuOpen,setCommandMenuOpen}}>{children}</ShellContext.Provider>;
};
export function useShell(): ShellContextValue {const ctx=useContext(ShellContext);if(!ctx)throw new Error('useShell must be used inside a ShellProvider');return ctx;}
