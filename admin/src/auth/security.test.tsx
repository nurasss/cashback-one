import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Navigation } from '../features/Navigation';
import { AppRouter } from '../layout/AppRouter';

const json = (status: number, body: unknown, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', ...headers } });

beforeEach(() => {
  vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
  vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');
  vi.stubGlobal('fetch', vi.fn(async () => json(401, { error: { code: 'ADMIN_UNAUTHENTICATED', message: 'private backend detail' } })));
});
afterEach(() => { cleanup(); window.history.pushState({}, '', '/'); vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

describe('role-aware admin navigation', () => {
  it('renders tenant Audit for managers while keeping Businesses superadmin-only', () => {
    const view = render(<MemoryRouter><Navigation role="superadmin" /></MemoryRouter>);
    expect(view.getByRole('link', { name: /Бизнесы/ })).toBeInTheDocument();
    expect(view.getByRole('link', { name: /Журнал событий/ })).toBeInTheDocument();
    view.unmount();
    view.unmount();
    const manager = render(<MemoryRouter><Navigation role="business_manager" /></MemoryRouter>);
    expect(manager.queryByRole('link', { name: /Бизнесы/ })).not.toBeInTheDocument();
    expect(manager.getByRole('link', { name: /Журнал событий/ })).toBeInTheDocument();
    expect(manager.getByRole('link', { name: /Агенты/ })).toBeInTheDocument();
    expect(manager.getByRole('link', { name: /Карты и клиенты/ })).toBeInTheDocument();
  });
});

it('keeps one-time agent-key disclosure out of persistent browser and query storage', async () => {
  const fs = await import('node:fs');
  const source = fs.readFileSync(`${process.cwd()}/src/features/AdminMutations.tsx`, 'utf8');
  expect(source).not.toMatch(/\b(?:localStorage|sessionStorage|indexedDB)\b/i);
  expect(source).not.toMatch(/useMutation|setQueryData|persistQueryClient/);
  expect(source).toContain("session.api.request<AgentKeyDisclosure>('/admin/agents'");
});

it('keeps the SPA in a bootstrap state before revealing the sign-in form', async () => {
  const user = userEvent.setup();
  window.history.pushState({}, '', '/admin/login');
  render(<AppRouter />);
  expect(screen.getByText('Загружаем безопасную сессию…')).toBeInTheDocument();
  await screen.findByRole('heading', { name: 'Вход в систему' });
  expect(screen.getByLabelText('Логин')).toBeInTheDocument();
  expect(screen.getByLabelText('Пароль')).toHaveAttribute('type', 'password');
  expect(user).toBeDefined();
});

it('maps rejected credentials to generic copy without rendering the backend body', async () => {
  const fetchMock = vi.mocked(fetch);
  fetchMock.mockImplementation(async (input, init) => {
    if (String(input).endsWith('/admin/auth/login') && init?.method === 'POST') {
      return json(401, { error: { code: 'INVALID_CREDENTIALS', message: 'distinctive PII backend body' } });
    }
    return json(401, { error: { code: 'ADMIN_UNAUTHENTICATED' } });
  });
  const user = userEvent.setup();
  window.history.pushState({}, '', '/admin/login');
  render(<AppRouter />);
  await screen.findByRole('heading', { name: 'Вход в систему' });
  await user.type(screen.getByLabelText('Логин'), 'test.admin');
  await user.type(screen.getByLabelText('Пароль'), 'fixture-only-password');
  await user.click(screen.getByRole('button', { name: 'Войти' }));
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Неверный логин или пароль'));
  expect(document.body).not.toHaveTextContent('distinctive PII backend body');
  expect(screen.getByLabelText('Пароль')).toHaveValue('');
});

it('renders agent-provided strings as text, never as HTML', () => {
  const maliciousLabel = '<img src=x onerror=alert(1)>';
  const view = render(<article><span>{maliciousLabel}</span></article>);
  expect(view.container.querySelector('img')).toBeNull();
  expect(view.getByText(maliciousLabel)).toBeInTheDocument();
});
