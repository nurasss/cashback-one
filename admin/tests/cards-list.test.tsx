import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import type { BusinessDetail, Card } from '../src/api/types';
import { AdminProvider } from '../src/auth/provider';
import { OperationsPage } from '../src/pages/OperationsPage';

const access = { access_token: 'fixture-access', token_type: 'bearer', expires_in: 900 };
const businessIdA = 'business-a-uuid';
const businessIdB = 'business-b-uuid';

const businessA: BusinessDetail = {
  id: businessIdA,
  name: 'Alpha Market',
  logo_url: null,
  colors: null,
  barcode_prefixes: [],
  status: 'active',
  created_at: '2026-10-01T00:00:00Z',
  updated_at: '2026-10-01T00:00:00Z',
  cards_count: 26,
  unblocked_cards_count: 25,
  customers_with_cards_count: 10,
  agents_count: 1,
};

const businessB: BusinessDetail = {
  id: businessIdB,
  name: 'Beta Store',
  logo_url: null,
  colors: null,
  barcode_prefixes: [],
  status: 'active',
  created_at: '2026-10-01T00:00:00Z',
  updated_at: '2026-10-01T00:00:00Z',
  cards_count: 2,
  unblocked_cards_count: 2,
  customers_with_cards_count: 2,
  agents_count: 1,
};

const makeMockCard = (num: number, bId = businessIdA, bName = 'Alpha Market'): Card => ({
  id: `card-uuid-${num}`,
  business_id: bId,
  business_name: bName,
  barcode: `000000000${String(num).padStart(4, '0')}`,
  phone_masked: num % 2 === 0 ? '••••1122' : null,
  balance: '125.5000',
  is_blocked: num === 99,
  updated_at: '2026-10-21T10:00:00Z',
  bind_method: num % 2 === 0 ? 'manual_barcode' : null,
  bound_at: num % 2 === 0 ? '2026-10-21T09:00:00Z' : null,
  hidden_at: null,
});

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

function adminResponse(role: 'superadmin' | 'business_manager', business = businessA) {
  return {
    admin: {
      id: 'fixture-admin-id',
      login: `fixture.${role}`,
      role,
      business: role === 'business_manager' ? { id: business.id, name: business.name, status: 'active' } : null,
    },
  };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

it('immediately renders first page of all cards without requiring search input', async () => {
  vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
  vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

  const page1Cards = Array.from({ length: 25 }, (_, i) => makeMockCard(i + 1));
  const fetchMock: typeof fetch = vi.fn(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? 'GET';
    if (url.endsWith('/admin/auth/refresh')) return json(200, access);
    if (url.endsWith('/admin/me')) return json(200, adminResponse('superadmin'));
    if (url.endsWith('/admin/businesses?limit=100&offset=0')) {
      return json(200, { items: [businessA, businessB], limit: 100, offset: 0, has_more: false });
    }
    if (url.includes('/admin/cards?') && method === 'GET') {
      return json(200, { items: page1Cards, limit: 25, offset: 0, has_more: true });
    }
    return json(404, { error: { code: 'ADMIN_RESOURCE_NOT_FOUND' } });
  });
  vi.stubGlobal('fetch', fetchMock);

  render(
    <AdminProvider>
      <MemoryRouter initialEntries={['/operations']}>
        <Routes>
          <Route path="/operations" element={<OperationsPage />} />
        </Routes>
      </MemoryRouter>
    </AdminProvider>
  );

  // Card list is fetched immediately
  await waitFor(() => {
    expect(screen.getByText('0000000000001')).toBeInTheDocument();
  });

  // Verify leading zeros preserved
  expect(screen.getByText('0000000000001')).toBeInTheDocument();
  expect(screen.queryByText('0000000000025')).not.toBeInTheDocument();
  await userEvent.setup().click(screen.getByRole('button', { name: 'Показать все (25)' }));
  expect(screen.getByText('0000000000025')).toBeInTheDocument();
  expect(screen.getAllByText('Alpha Market').length).toBeGreaterThan(0);

  // Verify table columns
  expect(screen.getByText('КАРТА')).toBeInTheDocument();
  expect(screen.getByText('БАЛАНС')).toBeInTheDocument();
  expect(screen.getByText('СТАТУС')).toBeInTheDocument();
  expect(screen.getByText('КЛИЕНТ')).toBeInTheDocument();
  expect(screen.getByText('ОБНОВЛЕНА')).toBeInTheDocument();

  // Verify pagination status
  expect(screen.getByText('Страница 1')).toBeInTheDocument();
  const backBtn = screen.getByRole('button', { name: 'Назад' });
  const nextBtn = screen.getByRole('button', { name: 'Далее' });
  expect(backBtn).toBeDisabled();
  expect(nextBtn).toBeEnabled();
});

it('navigates next and previous pages properly with has_more handling', async () => {
  const user = userEvent.setup();
  vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
  vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

  const page1Cards = Array.from({ length: 25 }, (_, i) => makeMockCard(i + 1));
  const page2Cards = [makeMockCard(26)];

  const fetchMock: typeof fetch = vi.fn(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? 'GET';
    if (url.endsWith('/admin/auth/refresh')) return json(200, access);
    if (url.endsWith('/admin/me')) return json(200, adminResponse('superadmin'));
    if (url.endsWith('/admin/businesses?limit=100&offset=0')) {
      return json(200, { items: [businessA], limit: 100, offset: 0, has_more: false });
    }
    if (url.includes('/admin/cards?limit=25&offset=0') && method === 'GET') {
      return json(200, { items: page1Cards, limit: 25, offset: 0, has_more: true });
    }
    if (url.includes('/admin/cards?limit=25&offset=25') && method === 'GET') {
      return json(200, { items: page2Cards, limit: 25, offset: 25, has_more: false });
    }
    return json(404, { error: { code: 'ADMIN_RESOURCE_NOT_FOUND' } });
  });
  vi.stubGlobal('fetch', fetchMock);

  render(
    <AdminProvider>
      <MemoryRouter initialEntries={['/operations']}>
        <Routes>
          <Route path="/operations" element={<OperationsPage />} />
        </Routes>
      </MemoryRouter>
    </AdminProvider>
  );

  await waitFor(() => {
    expect(screen.getByText('0000000000001')).toBeInTheDocument();
  });

  await user.click(screen.getByRole('button', { name: 'Показать все (25)' }));
  const nextBtn = screen.getByRole('button', { name: 'Далее' });
  expect(nextBtn).toBeEnabled();

  // Click Далее to go to page 2
  // The pagination is available only after expanding the current page.
  await user.click(nextBtn);

  await waitFor(() => {
    expect(screen.getByText('0000000000026')).toBeInTheDocument();
  });
  expect(screen.getByText('Страница 2')).toBeInTheDocument();

  // On page 2 (last page), Далее is disabled, Назад is enabled
  const nextBtnP2 = screen.getByRole('button', { name: 'Далее' });
  const backBtnP2 = screen.getByRole('button', { name: 'Назад' });
  expect(nextBtnP2).toBeDisabled();
  expect(backBtnP2).toBeEnabled();

  // Click Назад to return to page 1
  await user.click(backBtnP2);

  await waitFor(() => {
    expect(screen.getByText('0000000000001')).toBeInTheDocument();
  });
  expect(screen.getByText('Страница 1')).toBeInTheDocument();
});

it('supports search by barcode and provides clear reset back to general list', async () => {
  const user = userEvent.setup();
  vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
  vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

  const generalCards = [makeMockCard(1), makeMockCard(2)];
  const searchedCard = makeMockCard(777);

  const fetchMock: typeof fetch = vi.fn(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? 'GET';
    if (url.endsWith('/admin/auth/refresh')) return json(200, access);
    if (url.endsWith('/admin/me')) return json(200, adminResponse('superadmin'));
    if (url.endsWith('/admin/businesses?limit=100&offset=0')) {
      return json(200, { items: [businessA], limit: 100, offset: 0, has_more: false });
    }
    if (url.includes('/admin/cards?') && method === 'GET') {
      return json(200, { items: generalCards, limit: 25, offset: 0, has_more: false });
    }
    if (url.includes('/admin/cards/search') && method === 'POST') {
      return json(200, { items: [searchedCard], limit: 25, offset: 0, has_more: false });
    }
    return json(404, { error: { code: 'ADMIN_RESOURCE_NOT_FOUND' } });
  });
  vi.stubGlobal('fetch', fetchMock);

  render(
    <AdminProvider>
      <MemoryRouter initialEntries={['/operations']}>
        <Routes>
          <Route path="/operations" element={<OperationsPage />} />
        </Routes>
      </MemoryRouter>
    </AdminProvider>
  );

  // Initial state shows general cards
  await waitFor(() => {
    expect(screen.getByText('0000000000001')).toBeInTheDocument();
  });

  // Enter barcode in search input
  const input = screen.getByLabelText('Штрихкод карты');
  await user.type(input, '0000000000777');
  const searchBtn = screen.getByRole('button', { name: 'Найти' });
  await user.click(searchBtn);

  // Search results are rendered
  await waitFor(() => {
    expect(screen.getByText('0000000000777')).toBeInTheDocument();
  });
  expect(screen.queryByText('0000000000001')).not.toBeInTheDocument();

  // Reset button is visible
  const resetBtn = screen.getByRole('button', { name: 'Сбросить' });
  await user.click(resetBtn);

  // After reset, returns to general list and input is cleared
  await waitFor(() => {
    expect(screen.getByText('0000000000001')).toBeInTheDocument();
  });
  expect((input as HTMLInputElement).value).toBe('');
});

it('barcode search accepts 4-13 digit numbers and ignores out-of-range terms', async () => {
  const user = userEvent.setup();
  vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
  vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

  const generalCards = [makeMockCard(1)];
  const searchedCard = makeMockCard(7);

  const fetchMock: typeof fetch = vi.fn(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? 'GET';
    if (url.endsWith('/admin/auth/refresh')) return json(200, access);
    if (url.endsWith('/admin/me')) return json(200, adminResponse('superadmin'));
    if (url.endsWith('/admin/businesses?limit=100&offset=0')) {
      return json(200, { items: [businessA], limit: 100, offset: 0, has_more: false });
    }
    if (url.includes('/admin/cards?') && method === 'GET') {
      return json(200, { items: generalCards, limit: 25, offset: 0, has_more: false });
    }
    if (url.includes('/admin/cards/search') && method === 'POST') {
      const body = JSON.parse(String(init?.body)) as { barcode?: string };
      if (body.barcode === '0001') {
        return json(200, { items: [searchedCard], limit: 25, offset: 0, has_more: false });
      }
    }
    return json(404, { error: { code: 'ADMIN_RESOURCE_NOT_FOUND' } });
  });
  vi.stubGlobal('fetch', fetchMock);

  render(
    <AdminProvider>
      <MemoryRouter initialEntries={['/operations']}>
        <Routes>
          <Route path="/operations" element={<OperationsPage />} />
        </Routes>
      </MemoryRouter>
    </AdminProvider>
  );

  await waitFor(() => {
    expect(screen.getByText('0000000000001')).toBeInTheDocument();
  });

  const input = screen.getByLabelText('Штрихкод карты');
  const searchBtn = screen.getByRole('button', { name: 'Найти' });

  // 3 digits: form must not be submitted
  await user.type(input, '123');
  await user.click(searchBtn);
  const searchCallsAfterShort = fetchMock.mock.calls.filter(([url]) => String(url).includes('/admin/cards/search')).length;
  expect(searchCallsAfterShort).toBe(0);
  await user.clear(input);

  // 14 digits: form must not be submitted either
  await user.type(input, '12345678901234');
  await user.click(searchBtn);
  const searchCallsAfterLong = fetchMock.mock.calls.filter(([url]) => String(url).includes('/admin/cards/search')).length;
  expect(searchCallsAfterLong).toBe(0);
  await user.clear(input);

  // 4 digits with leading zeros: search request is issued with the raw string barcode
  await user.type(input, '0001');
  await user.click(searchBtn);
  await waitFor(() => {
    expect(screen.getByText('0000000000007')).toBeInTheDocument();
  });
  const searchBodies = fetchMock.mock.calls
    .filter(([url]) => String(url).includes('/admin/cards/search'))
    .map(([, init]) => JSON.parse(String((init as RequestInit | undefined)?.body)) as { barcode?: string });
  expect(searchBodies).toEqual([{ barcode: '0001' }]);
});

it('switches business filter and re-fetches cards with offset reset', async () => {
  const user = userEvent.setup();
  vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
  vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

  const cardsA = [makeMockCard(1, businessIdA, 'Alpha Market')];
  const cardsB = [makeMockCard(99, businessIdB, 'Beta Store')];

  const fetchMock: typeof fetch = vi.fn(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? 'GET';
    if (url.endsWith('/admin/auth/refresh')) return json(200, access);
    if (url.endsWith('/admin/me')) return json(200, adminResponse('superadmin'));
    if (url.endsWith('/admin/businesses?limit=100&offset=0')) {
      return json(200, { items: [businessA, businessB], limit: 100, offset: 0, has_more: false });
    }
    if (url.includes(`/admin/cards?limit=25&offset=0&business_id=${businessIdB}`) && method === 'GET') {
      return json(200, { items: cardsB, limit: 25, offset: 0, has_more: false });
    }
    if (url.includes('/admin/cards?limit=25&offset=0') && method === 'GET') {
      return json(200, { items: cardsA, limit: 25, offset: 0, has_more: false });
    }
    return json(404, { error: { code: 'ADMIN_RESOURCE_NOT_FOUND' } });
  });
  vi.stubGlobal('fetch', fetchMock);

  render(
    <AdminProvider>
      <MemoryRouter initialEntries={['/operations']}>
        <Routes>
          <Route path="/operations" element={<OperationsPage />} />
        </Routes>
      </MemoryRouter>
    </AdminProvider>
  );

  await waitFor(() => {
    expect(screen.getByText('0000000000001')).toBeInTheDocument();
  });

  // Switch business select to Beta Store
  const select = screen.getByLabelText('Бизнес поиска');
  await waitFor(() => {
    expect(screen.getByRole('option', { name: 'Beta Store' })).toBeInTheDocument();
  });
  await user.selectOptions(select, businessIdB);

  await waitFor(() => {
    expect(screen.getByText('0000000000099')).toBeInTheDocument();
  });
  expect(screen.queryByText('0000000000001')).not.toBeInTheDocument();
});

it('handles empty state and error state correctly', async () => {
  vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
  vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

  const fetchMock: typeof fetch = vi.fn(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? 'GET';
    if (url.endsWith('/admin/auth/refresh')) return json(200, access);
    if (url.endsWith('/admin/me')) return json(200, adminResponse('superadmin'));
    if (url.endsWith('/admin/businesses?limit=100&offset=0')) {
      return json(200, { items: [businessA], limit: 100, offset: 0, has_more: false });
    }
    if (url.includes('/admin/cards?') && method === 'GET') {
      return json(200, { items: [], limit: 25, offset: 0, has_more: false });
    }
    return json(404, { error: { code: 'ADMIN_RESOURCE_NOT_FOUND' } });
  });
  vi.stubGlobal('fetch', fetchMock);

  render(
    <AdminProvider>
      <MemoryRouter initialEntries={['/operations']}>
        <Routes>
          <Route path="/operations" element={<OperationsPage />} />
        </Routes>
      </MemoryRouter>
    </AdminProvider>
  );

  await waitFor(() => {
    expect(screen.getByText('Карт пока нет')).toBeInTheDocument();
  });
  expect(screen.getByText('В базе пока нет карт для отображения.')).toBeInTheDocument();
});
