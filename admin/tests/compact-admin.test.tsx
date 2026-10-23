import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { AppRouter } from '../src/layout/AppRouter';
import { LOCALE_STORAGE_KEY } from '../src/i18n/LocaleContext';

const timestamp = '2026-10-23T00:00:00Z';
const business = { id: 'fixture-business', name: 'Fixture Business', status: 'active', logo_url: null, colors: null, barcode_prefixes: [], created_at: timestamp, updated_at: timestamp, cards_count: 25, unblocked_cards_count: 25, customers_with_cards_count: 1, agents_count: 1 };
const card = (i: number) => ({ id: `fixture-card-${i}`, business_id: business.id, business_name: business.name, barcode: String(100000 + i), phone_masked: null, balance: '10', is_blocked: false, updated_at: timestamp, bind_method: null, bound_at: null, hidden_at: null });
const agent = { id: 'fixture-agent', business_id: business.id, business_name: business.name, status: 'active', health: 'online', last_seen_at: timestamp, last_sync_at: timestamp, version: 'fixture', last_error: null, created_at: timestamp };

function setup(path: string, locale: 'ru' | 'kk' = 'ru', count = 25) {
  window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  vi.stubEnv('VITE_API_BASE_URL', 'https://compact.test');
  vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input));
    const offset = Number(url.searchParams.get('offset') ?? 0);
    const page = { items: Array.from({ length: count }, (_, i) => card(offset + i)), limit: 25, offset, has_more: offset === 0 };
    let body: unknown;
    let status = 200;
    if (url.pathname === '/admin/auth/refresh') {
      status = path === '/admin/login' ? 401 : 200;
      body = status === 401 ? { error: { code: 'ADMIN_UNAUTHENTICATED' } } : { access_token: 'fixture-access', token_type: 'bearer', expires_in: 900 };
    } else if (url.pathname === '/admin/me') body = { admin: { id: 'fixture-admin', login: 'fixture.admin', role: 'superadmin', business: null } };
    else if (url.pathname === '/admin/businesses') body = { ...page, items: [business], has_more: false };
    else if (url.pathname === `/admin/businesses/${business.id}`) body = business;
    else if (url.pathname === '/admin/agents') body = { ...page, items: [agent], has_more: false };
    else if (url.pathname === '/admin/agents/fixture-agent') body = agent;
    else if (url.pathname === '/admin/users/fixture-user') body = { id: 'fixture-user', phone: null, language: 'ru', created_at: timestamp, cards: page };
    else if (url.pathname === '/admin/cards/fixture-card-0') body = { ...card(0), full_name: null, owner_language: null };
    else if (url.pathname === '/admin/cards' || url.pathname === '/admin/cards/search') body = page;
    else if (url.pathname === '/admin/dashboard') body = { business_id: null, business_name: null, period_from: timestamp, period_to: timestamp, period_days: 1, customers_with_business_cards: 1, cards: 25, unblocked_cards: 25, transactions: 0, agents: { online: 1, stale: 0, never_connected: 0, error: 0, disabled: 0 } };
    else body = { ...page, items: [], has_more: false };
    return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
  }));
  return render(<MemoryRouter initialEntries={[path]}><AppRouter /></MemoryRouter>);
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  window.localStorage.clear();
  document.documentElement.lang = 'ru';
});

const paths = ['/admin', '/admin/businesses', '/admin/businesses/fixture-business', '/admin/agents', '/admin/agents/fixture-agent', '/admin/content', '/admin/audit', '/admin/operations', '/admin/cards/fixture-card-0', '/admin/users/fixture-user'];
it.each(paths.flatMap(path => (['ru', 'kk'] as const).map(locale => ({ path, locale }))))('removes only the page eyebrow at $path ($locale)', async ({ path, locale }) => {
  const { container } = setup(path, locale);
  await waitFor(() => expect(container.querySelector('.page-heading h1')).not.toBeNull());
  expect(container.querySelector('.page-heading .eyebrow')).toBeNull();
  expect(screen.getByText('poscenter.kz')).toBeInTheDocument();
  expect(container.textContent).not.toContain('POSCENTER.KZ');
});

it.each(['ru', 'kk'] as const)('preserves login eyebrows and uses lowercase brand (%s)', async locale => {
  const { container } = setup('/admin/login', locale);
  expect(await screen.findByText('poscenter.kz')).toBeInTheDocument();
  expect(container.textContent).not.toContain('POSCENTER.KZ');
  expect(container.querySelector('.story-copy .eyebrow')).toHaveTextContent('ADMIN CONSOLE');
  expect(container.querySelector('img[alt="POSCENTER.KZ"]')).not.toBeNull();
});

it.each(['ru', 'kk'] as const)('compacts user cards, retains expansion through real query paging and collapses (%s)', async locale => {
  const user = userEvent.setup();
  const { container } = setup('/admin/users/fixture-user', locale);
  const expand = locale === 'ru' ? 'Показать все (25)' : 'Барлығын көрсету (25)';
  const collapse = locale === 'ru' ? 'Свернуть' : 'Жию';
  const next = locale === 'ru' ? 'Далее' : 'Келесі';
  const toggle = await screen.findByRole('button', { name: expand });
  expect(container.querySelectorAll('tbody tr')).toHaveLength(3);
  expect(screen.queryByRole('button', { name: next })).not.toBeInTheDocument();
  expect(toggle).toHaveAttribute('aria-expanded', 'false');
  expect(document.getElementById(toggle.getAttribute('aria-controls')!)).toBe(container.querySelector('tbody'));
  await user.click(toggle);
  expect(container.querySelectorAll('tbody tr')).toHaveLength(25);
  await user.click(screen.getByRole('button', { name: next }));
  expect(await screen.findByText('100025')).toBeInTheDocument();
  expect(container.querySelectorAll('tbody tr')).toHaveLength(25);
  expect(screen.getByRole('button', { name: collapse })).toHaveAttribute('aria-expanded', 'true');
  await user.click(screen.getByRole('button', { name: collapse }));
  expect(container.querySelectorAll('tbody tr')).toHaveLength(3);
  expect(screen.queryByRole('button', { name: next })).not.toBeInTheDocument();
});

it.each([1, 3])('retains existing user card pagination for %i rows', async count => {
  const { container } = setup('/admin/users/fixture-user', 'ru', count);
  expect(await screen.findByRole('button', { name: 'Далее' })).toBeEnabled();
  expect(container.querySelectorAll('tbody tr')).toHaveLength(count);
  expect(screen.queryByRole('button', { name: /Показать все/ })).not.toBeInTheDocument();
});

it('keeps card list expansion through pending search/filter queries and resets on section navigation', async () => {
  const user = userEvent.setup();
  const { container } = setup('/admin/operations');
  await user.click(await screen.findByRole('button', { name: 'Показать все (25)' }));
  await user.selectOptions(screen.getByLabelText('Бизнес поиска'), business.id);
  expect(await screen.findByRole('button', { name: 'Свернуть' })).toHaveAttribute('aria-expanded', 'true');
  await user.type(screen.getByLabelText('Штрихкод карты'), '100000');
  await user.click(screen.getByRole('button', { name: 'Найти' }));
  expect(await screen.findByRole('button', { name: 'Свернуть' })).toHaveAttribute('aria-expanded', 'true');
  expect(container.querySelectorAll('tbody tr')).toHaveLength(25);
  await user.click(screen.getByRole('link', { name: /Журнал событий/ }));
  await screen.findByRole('heading', { name: 'Журнал событий' });
  await user.click(screen.getByRole('link', { name: /Карты и клиенты/ }));
  expect(await screen.findByRole('button', { name: 'Показать все (25)' })).toHaveAttribute('aria-expanded', 'false');
});
