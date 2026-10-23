import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { DataTable } from '../src/components/DataTable';
import { LocaleProvider } from '../src/i18n/LocaleContext';

afterEach(cleanup);

const rows = Array.from({ length: 25 }, (_, id) => ({ id: String(id), name: `Row ${id}` }));
const columns = [{ key: 'name', title: 'Name', render: (row: typeof rows[number]) => row.name }];
const props = { rows, columns, rowKey: (row: typeof rows[number]) => row.id, page: { limit: 25, offset: 0, has_more: true }, onPage: vi.fn() };

it('renders three of 25 rows, expands and collapses with an accessible control and pagination', async () => {
  const user = userEvent.setup();
  render(<DataTable {...props} />);
  expect(screen.getAllByRole('row')).toHaveLength(4);
  expect(screen.queryByText('Страница 1')).not.toBeInTheDocument();
  const toggle = screen.getByRole('button', { name: 'Показать все (25)' });
  expect(toggle).toHaveAttribute('aria-expanded', 'false');
  expect(document.getElementById(toggle.getAttribute('aria-controls')!)).toBe(screen.getByRole('table').querySelector('tbody'));
  await user.click(toggle);
  expect(screen.getAllByRole('row')).toHaveLength(26);
  expect(screen.getByText('Страница 1')).toBeInTheDocument();
  expect(toggle).toHaveTextContent('Свернуть');
  expect(toggle).toHaveAttribute('aria-expanded', 'true');
  await user.click(toggle);
  expect(screen.getAllByRole('row')).toHaveLength(4);
  expect(toggle).toHaveAttribute('aria-expanded', 'false');
  expect(screen.queryByRole('button', { name: 'Далее' })).not.toBeInTheDocument();
});

it.each([1, 2, 3])('does not add a toggle to %i rows and retains pagination', count => {
  render(<DataTable {...props} rows={rows.slice(0, count)} />);
  expect(screen.getAllByRole('row')).toHaveLength(count + 1);
  expect(screen.queryByRole('button', { name: /Показать все|Свернуть/ })).not.toBeInTheDocument();
  expect(screen.getByText('Страница 1')).toBeInTheDocument();
});

it('keeps the empty state without pagination or toggle', () => {
  render(<DataTable {...props} rows={[]} />);
  expect(screen.getByText('По заданным условиям записей не найдено.')).toBeInTheDocument();
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
});

it('keeps expansion when paging and changing row counts, and resets after remount', async () => {
  const user = userEvent.setup();
  function PagedTable() {
    const [offset, setOffset] = useState(0);
    return <DataTable {...props} page={{ ...props.page, offset }} onPage={setOffset} />;
  }
  const { unmount } = render(<PagedTable />);
  await user.click(screen.getByRole('button', { name: 'Показать все (25)' }));
  await user.click(screen.getByRole('button', { name: 'Далее' }));
  expect(screen.getByText('Страница 2')).toBeInTheDocument();
  expect(screen.getAllByRole('row')).toHaveLength(26);
  unmount();
  const { rerender } = render(<DataTable {...props} />);
  expect(screen.getByRole('button', { name: 'Показать все (25)' })).toHaveAttribute('aria-expanded', 'false');
  rerender(<DataTable {...props} rows={rows.slice(0, 8)} />);
  expect(screen.getByRole('button', { name: 'Показать все (8)' })).toHaveAttribute('aria-expanded', 'false');
  await user.click(screen.getByRole('button', { name: 'Показать все (8)' }));
  rerender(<DataTable {...props} rows={rows.slice(0, 2)} />);
  rerender(<DataTable {...props} rows={rows.slice(0, 10)} />);
  expect(screen.getByRole('button', { name: 'Свернуть' })).toHaveAttribute('aria-expanded', 'true');
  expect(screen.getAllByRole('row')).toHaveLength(11);
});

it('uses Kazakh labels for both states', async () => {
  const user = userEvent.setup();
  render(<LocaleProvider initialLocale="kk"><DataTable {...props} /></LocaleProvider>);
  await user.click(screen.getByRole('button', { name: 'Барлығын көрсету (25)' }));
  expect(screen.getByRole('button', { name: 'Жию' })).toHaveAttribute('aria-expanded', 'true');
});
