import React from 'react';
import { Sidebar } from './Sidebar';
import { TopNav } from './TopNav';
export const PageWrapper: React.FC<{children: React.ReactNode}> = ({children}) => <div className="app-shell"><a href="#main" className="skip-link">Skip to content</a><Sidebar/><div className="app-body"><TopNav/><main id="main" className="app-main"><div className="main-inner">{children}</div></main></div></div>;
