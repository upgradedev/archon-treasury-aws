import React,{useEffect} from 'react';
import {PageWrapper} from './components/layout/PageWrapper';
import {ShellProvider} from './context/ShellContext';
import {TreasuryDashboard} from './features/treasury/TreasuryDashboard';
export const App:React.FC=()=>{useEffect(()=>{document.title='Archon Treasury — Command Center';const link=document.createElement('link');link.rel='stylesheet';link.href='https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Instrument+Serif:ital@0;1&family=JetBrains+Mono:wght@400;500&display=swap';document.head.appendChild(link);return()=>link.remove();},[]);return <ShellProvider><PageWrapper><TreasuryDashboard/></PageWrapper></ShellProvider>;};
export default App;
