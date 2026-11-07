import React,{useMemo,useState} from 'react';
import {useShell} from '../../context/ShellContext';
import {useCommandShortcut} from '../../hooks/useCommandShortcut';
import {Badge} from '../ui/Badge';
import {Button} from '../ui/Button';
import {Modal} from '../ui/Modal';
interface CommandAction{id:string;label:string;moduleTag:string;run:()=>void;}
export const CommandMenu:React.FC<{actions:ReadonlyArray<CommandAction>}>=({actions})=>{
 const {commandMenuOpen,setCommandMenuOpen}=useShell();const[query,setQuery]=useState('');
 useCommandShortcut(()=>setCommandMenuOpen(!commandMenuOpen),()=>setCommandMenuOpen(false));
 const filteredActions=useMemo(()=>{const q=query.trim().toLowerCase();return q?actions.filter(a=>a.label.toLowerCase().includes(q)||a.moduleTag.toLowerCase().includes(q)):actions;},[actions,query]);
 return <Modal open={commandMenuOpen} title="Global Command Menu" onClose={()=>setCommandMenuOpen(false)}><div className="p-3 border-b border-border flex items-center gap-2"><input type="search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search commands" aria-label="Search commands" className="w-full px-3 py-1.5 text-sm border border-border rounded-sm focus:outline-none focus:border-primary" autoFocus/><Button onClick={()=>setCommandMenuOpen(false)}>Esc</Button></div><ul className="p-2 max-h-72 overflow-y-auto divide-y divide-border">{filteredActions.map(a=><li key={a.id}><Button onClick={()=>{setCommandMenuOpen(false);a.run();}} className="w-full text-left px-3 py-2 text-xs rounded-sm flex items-center justify-between hover:bg-surface-2"><span className="font-medium">{a.label}</span><Badge intent="indigo">{a.moduleTag}</Badge></Button></li>)}{filteredActions.length===0&&<li className="empty-state">No matching commands.</li>}</ul></Modal>;
};
