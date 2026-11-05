import React from 'react';
import { PageWrapper } from './components/layout/PageWrapper';
import { ShellProvider } from './context/ShellContext';
import { TreasuryDashboard } from './features/treasury/TreasuryDashboard';

export const App: React.FC = () => {
  return (
    <ShellProvider>
      <PageWrapper>
        <TreasuryDashboard />
      </PageWrapper>
    </ShellProvider>
  );
};

export default App;
