import React, { useMemo, useState } from 'react';
import { useShell } from '../../context/ShellContext';
import { useCommandShortcut } from '../../hooks/useCommandShortcut';
import { Badge } from '../ui/Badge';
import { Modal } from '../ui/Modal';

interface CommandAction {
  id: string;
  label: string;
  moduleTag: string;
  run: () => void;
}

interface CommandMenuProps {
  actions: ReadonlyArray<CommandAction>;
}

export const CommandMenu: React.FC<CommandMenuProps> = ({ actions }) => {
  const { commandMenuOpen, setCommandMenuOpen } = useShell();
  const [query, setQuery] = useState('');

  useCommandShortcut(
    () => setCommandMenuOpen(!commandMenuOpen),
    () => setCommandMenuOpen(false),
  );

  const filteredActions = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return actions;
    return actions.filter(
      (a) => a.label.toLowerCase().includes(q) || a.moduleTag.toLowerCase().includes(q),
    );
  }, [actions, query]);

  return (
    <Modal
      open={commandMenuOpen}
      title="Global Command Menu"
      onClose={() => setCommandMenuOpen(false)}
    >
      <div className="p-3 border-b border-slate-200 flex items-center gap-2">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Type a command or search obligations (e.g. EUR, Bedrock, x402)..."
          aria-label="Search commands"
          className="w-full px-3 py-1.5 text-sm border border-slate-300 rounded-sm focus:outline-none focus:border-indigo-600"
          autoFocus
        />
        <button
          type="button"
          onClick={() => setCommandMenuOpen(false)}
          className="px-2 py-1 text-xs border border-slate-300 rounded-sm text-slate-600 hover:bg-slate-100"
        >
          Esc
        </button>
      </div>
      <ul className="p-2 max-h-72 overflow-y-auto divide-y divide-slate-100">
        {filteredActions.map((action) => (
          <li key={action.id}>
            <button
              type="button"
              onClick={() => {
                setCommandMenuOpen(false);
                action.run();
              }}
              className="w-full text-left px-3 py-2 text-xs rounded-sm flex items-center justify-between hover:bg-indigo-50 hover:text-indigo-700 transition-colors duration-150"
            >
              <span className="font-medium">{action.label}</span>
              <Badge intent="indigo">{action.moduleTag}</Badge>
            </button>
          </li>
        ))}
      </ul>
    </Modal>
  );
};
