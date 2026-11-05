import React from 'react';

interface DrawerProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}

export const Drawer: React.FC<DrawerProps> = ({ title, subtitle, children }) => {
  return (
    <section className="bg-white border border-slate-200 rounded-md p-4">
      <div className="flex items-center justify-between pb-2.5 mb-3 border-b border-slate-200">
        <h2 className="text-sm font-bold text-slate-900">{title}</h2>
        {subtitle && <span className="font-mono text-xs text-slate-500">{subtitle}</span>}
      </div>
      {children}
    </section>
  );
};
