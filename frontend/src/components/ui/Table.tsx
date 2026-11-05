import React from 'react';

export interface TableColumn<T> {
  key: string;
  header: string;
  align?: 'left' | 'right';
  render: (row: T) => React.ReactNode;
}

interface TableProps<T> {
  ariaLabel: string;
  columns: ReadonlyArray<TableColumn<T>>;
  rows: ReadonlyArray<T>;
  getRowKey: (row: T) => string;
}

export function Table<T>({ ariaLabel, columns, rows, getRowKey }: TableProps<T>) {
  return (
    <div className="overflow-x-auto border border-slate-200 rounded-md bg-white" role="region" aria-label={ariaLabel} tabIndex={0}>
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="bg-slate-50 border-b border-slate-200">
            {columns.map((col) => (
              <th
                key={col.key}
                className={`px-3 py-2 text-xs font-bold uppercase tracking-wider text-slate-500 ${
                  col.align === 'right' ? 'text-right' : 'text-left'
                }`}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200">
          {rows.map((row) => (
            <tr
              key={getRowKey(row)}
              className="hover:bg-slate-50/80 transition-colors duration-150 align-top"
            >
              {columns.map((col) => (
                <td
                  key={col.key}
                  className={`px-3 py-2.5 text-slate-900 ${
                    col.align === 'right' ? 'text-right font-mono tabular-nums' : 'text-left'
                  }`}
                >
                  {col.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
