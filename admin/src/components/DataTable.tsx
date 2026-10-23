import { Pagination } from './Feedback';
import type { ReactNode } from 'react';
import { useLocale } from '../i18n/LocaleContext';
import { CompactTableToggle, useCompactRows, type TableExpansion } from './CompactTable';

export interface Column<T> {
  key: string;
  title: string;
  render: (row: T) => ReactNode;
  align?: 'left' | 'right';
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  page,
  onPage,
  expansion,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  page: { limit: number; offset: number; has_more: boolean };
  onPage: (offset: number) => void;
  expansion?: TableExpansion;
}) {
  const { locale } = useLocale();
  const compact = useCompactRows(rows, expansion);

  return (
    <div className="table-card">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {columns.map(column => (
                <th
                  key={column.key}
                  scope="col"
                  className={column.align === 'right' ? 'align-right' : undefined}
                >
                  {column.title}
                </th>
              ))}
            </tr>
          </thead>
          <tbody id={compact.bodyId}>
            {compact.visibleRows.map(row => (
              <tr key={rowKey(row)}>
                {columns.map(column => (
                  <td
                    key={column.key}
                    className={column.align === 'right' ? 'align-right' : undefined}
                  >
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <CompactTableToggle {...compact} />
      {rows.length === 0 ? (
        <p className="table-empty">
          {locale === 'kk'
            ? 'Берілген шарттар бойынша жазбалар табылмады.'
            : 'По заданным условиям записей не найдено.'}
        </p>
      ) : (
        compact.showPagination && <Pagination page={page} onChange={onPage} />
      )}
    </div>
  );
}

export function ErrorPanel({ children }: { children: ReactNode }) {
  return (
    <div className="form-error" role="alert">
      {children}
    </div>
  );
}
