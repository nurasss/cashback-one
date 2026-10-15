import { Pagination } from './Feedback';
import type { ReactNode } from 'react';

export interface Column<T> { key: string; title: string; render: (row: T) => ReactNode; align?: 'left' | 'right' }
export function DataTable<T>({ columns, rows, rowKey, page, onPage }: {
  columns: Column<T>[]; rows: T[]; rowKey: (row: T) => string;
  page: { limit: number; offset: number; has_more: boolean }; onPage: (offset: number) => void;
}) {
  return <div className="table-card">
    <div className="table-wrap"><table><thead><tr>{columns.map(column => <th key={column.key} scope="col" className={column.align === 'right' ? 'align-right' : undefined}>{column.title}</th>)}</tr></thead>
      <tbody>{rows.map(row => <tr key={rowKey(row)}>{columns.map(column => <td key={column.key} className={column.align === 'right' ? 'align-right' : undefined}>{column.render(row)}</td>)}</tr>)}</tbody>
    </table></div>
    {rows.length === 0 ? <p className="table-empty">По заданным условиям записей не найдено.</p> : <Pagination page={page} onChange={onPage} />}
  </div>;
}

export function ErrorPanel({ children }: { children: ReactNode }) { return <div className="form-error" role="alert">{children}</div>; }
