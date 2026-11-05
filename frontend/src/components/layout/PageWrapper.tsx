import React from 'react';
import { Sidebar } from './Sidebar';
import { TopNav } from './TopNav';

interface PageWrapperProps {
  children: React.ReactNode;
}

export const PageWrapper: React.FC<PageWrapperProps> = ({ children }) => {
  return (
    <div className="h-screen overflow-hidden flex bg-slate-50/50 text-slate-900">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden bg-slate-50/50">
        <TopNav />
        <main id="main" className="flex-1 overflow-y-auto p-5">
          <div className="max-w-7xl mx-auto space-y-4">{children}</div>
        </main>
      </div>
    </div>
  );
};
