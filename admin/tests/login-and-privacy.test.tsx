import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AppRouter } from '../src/layout/AppRouter';
import { DataTable } from '../src/components/DataTable';
import type { Business } from '../src/api/types';
import { afterEach, expect, it, vi } from 'vitest';

const json = (status: number, payload: unknown) => new Response(JSON.stringify(payload), {
  status, headers: { 'Content-Type': 'application/json' },
});
afterEach(() => {
  window.history.pushState({}, '', '/');
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

it('keeps Login behind cookie bootstrap and then renders its labelled form', async () => {
  vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
  vi.stubGlobal('fetch', vi.fn(async () => json(401, { error: { code: 'ADMIN_UNAUTHENTICATED' } })));
  const user = userEvent.setup();
  window.history.pushState({}, '', '/admin/login');
  render(<AppRouter />);
  expect(screen.getByText('Загружаем безопасную сессию…')).toBeInTheDocument();
  await screen.findByRole('heading', { name: 'Вход в систему' });
  expect(screen.getByRole('form')).toBeInTheDocument();
  expect(screen.getByLabelText('Логин')).toBeInTheDocument();
  expect(screen.getByLabelText('Пароль')).toHaveAttribute('autocomplete', 'current-password');
  expect(user).toBeDefined();
});

it('shows the same safe message for failed credentials and clears the password field', async () => {
  vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
  vi.stubGlobal('fetch', vi.fn(async url => String(url).endsWith('/admin/auth/login')
    ? json(401, { error: { code: 'INVALID_CREDENTIALS', message: 'phone 77001112222 password very-private' } })
    : json(401, { error: { code: 'ADMIN_UNAUTHENTICATED' } })));
  const user = userEvent.setup();
  window.history.pushState({}, '', '/admin/login');
  render(<AppRouter />);
  await screen.findByRole('heading', { name: 'Вход в систему' });
  await user.type(screen.getByLabelText('Логин'), 'fixture.admin');
  await user.type(screen.getByLabelText('Пароль'), 'fixture-password-only');
  await user.click(screen.getByRole('button', { name: 'Войти' }));
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Неверный логин или пароль'));
  expect(document.body).not.toHaveTextContent('very-private');
  expect(screen.getByLabelText('Пароль')).toHaveValue('');
});

it('renders stored Business text rather than interpreting it as HTML', () => {
  const label = '<img src=x onerror=alert(1)>';
  const business: Business = {
    id: 'fixture-id', name: label, logo_url: null, colors: null, barcode_prefixes: null,
    status: 'active', created_at: '2026-10-01T00:00:00Z', updated_at: '2026-10-01T00:00:00Z',
  };
  const view = render(<DataTable<Business>
    rows={[business]} rowKey={row => row.id} page={{ limit: 25, offset: 0, has_more: false }} onPage={() => {}}
    columns={[{ key: 'name', title: 'Бизнес', render: row => row.name }]} />);
  expect(view.container.querySelector('img')).toBeNull();
  expect(screen.getByText(label)).toBeInTheDocument();
});
