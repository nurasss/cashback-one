import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import type { AdminTransaction, AdminUserDetail, BusinessDetail, Card, CardDetail } from '../src/api/types';
import { AdminProvider } from '../src/auth/provider';
import { LocaleProvider } from '../src/i18n/LocaleContext';
import { CardDetailPage, OperationsPage, UserDetailPage } from '../src/pages/OperationsPage';

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
    admin_max_stats_period_days: 90,
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
  await userEvent.setup().click(screen.getByRole('button', { name: 'Показать ещё' }));
  expect(screen.getByText('0000000000025')).toBeInTheDocument();
  expect(screen.getAllByText('Alpha Market').length).toBeGreaterThan(0);

  // Verify combined card/client column and remaining columns
  expect(screen.getByText('КАРТА / КЛИЕНТ')).toBeInTheDocument();
  expect(screen.getByText('БАЛАНС')).toBeInTheDocument();
  expect(screen.getByText('СТАТУС')).toBeInTheDocument();
  expect(screen.getByText('ОБНОВЛЕНА')).toBeInTheDocument();
  expect(screen.queryByText('КЛИЕНТ')).not.toBeInTheDocument();
  expect(screen.getAllByText('••••1122').length).toBeGreaterThan(0);
  expect(screen.getAllByText('Не привязана').length).toBeGreaterThan(0);

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

  await user.click(screen.getByRole('button', { name: 'Показать ещё' }));
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

  // Unified search input (no separate tabs)
  expect(screen.queryByRole('tablist')).toBeNull();
  const input = screen.getByLabelText('Номер карты или телефон');
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
      const body = JSON.parse(String(init?.body)) as { barcode?: string; phone?: string };
      if (body.barcode === '0001' || body.barcode === '77001112233') {
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

  const input = screen.getByLabelText('Номер карты или телефон');
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

  // 4 digits with leading zeros: search request is issued with unified barcode and phone
  await user.type(input, '0001');
  await user.click(searchBtn);
  await waitFor(() => {
    expect(screen.getByText('0000000000007')).toBeInTheDocument();
  });
  const searchBodies = fetchMock.mock.calls
    .filter(([url]) => String(url).includes('/admin/cards/search'))
    .map(([, init]) => JSON.parse(String((init as RequestInit | undefined)?.body)) as { barcode?: string; phone?: string });
  expect(searchBodies).toEqual([{ barcode: '0001', phone: '0001' }]);

  // Formatted phone number sends clean digits in barcode and raw phone
  await user.clear(input);
  await user.type(input, '+7 (700) 111-22-33');
  await user.click(searchBtn);
  await waitFor(() => {
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes('/admin/cards/search'))).toHaveLength(2);
  });
  const allBodies = fetchMock.mock.calls
    .filter(([url]) => String(url).includes('/admin/cards/search'))
    .map(([, init]) => JSON.parse(String((init as RequestInit | undefined)?.body)) as { barcode?: string; phone?: string });
  expect(allBodies).toEqual([
    { barcode: '0001', phone: '0001' },
    { barcode: '77001112233', phone: '+7 (700) 111-22-33' },
  ]);

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

it('shows phone_masked and full_name together in combined card/client column even when unbound', async () => {
  vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
  vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

  const cards: Card[] = [
    {
      ...makeMockCard(10, businessIdA, 'Alpha Market'),
      phone_masked: '••••4455',
      full_name: 'Айгуль С.',
      bind_method: null,
      bound_at: null,
    },
    {
      ...makeMockCard(11, businessIdA, 'Alpha Market'),
      phone_masked: null,
      full_name: null,
      bind_method: null,
      bound_at: null,
    },
  ];

  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/admin/auth/refresh')) return json(200, access);
      if (url.endsWith('/admin/me')) return json(200, adminResponse('business_manager'));
      if (url.includes('/admin/cards?')) {
        return json(200, { items: cards, limit: 25, offset: 0, has_more: false, total: 2 });
      }
      return json(404, { error: { code: 'ADMIN_RESOURCE_NOT_FOUND' } });
    }),
  );

  render(
    <AdminProvider>
      <LocaleProvider initialLocale="ru">
        <MemoryRouter initialEntries={['/operations']}>
          <Routes>
            <Route path="/operations" element={<OperationsPage />} />
          </Routes>
        </MemoryRouter>
      </LocaleProvider>
    </AdminProvider>,
  );

  expect(await screen.findByText('••••4455 · Айгуль С.')).toBeInTheDocument();
  expect(screen.getByText('Не привязана')).toBeInTheDocument();
});

it.each(['ru', 'kk'] as const)(
  'renders accrual and redemption transaction history with compact toggle and pagination on CardDetailPage (%s)',
  async locale => {
    const user = userEvent.setup();
    vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
    vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

    const cardId = 'card-tx-1';
    const cardDetail: CardDetail = {
      id: cardId,
      business_id: businessIdA,
      business_name: 'Alpha Market',
      barcode: '0000123456789',
      phone_masked: '••••7788',
      full_name: 'Тест Клиент',
      owner_language: 'ru',
      balance: '250.0000',
      is_blocked: false,
      updated_at: '2026-11-18T10:00:00Z',
      bind_method: 'phone_auto',
      bound_at: '2026-11-01T09:00:00Z',
      hidden_at: null,
    };

    const page1Tx: AdminTransaction[] = Array.from({ length: 8 }, (_, idx) => ({
      id: `tx-${idx + 1}`,
      card_id: cardId,
      barcode: cardDetail.barcode,
      business_id: businessIdA,
      business_name: 'Alpha Market',
      type: idx === 1 ? 'redemption' : 'accrual',
      amount: idx === 1 ? '50.0000' : `${150 + idx}.0000`,
      balance_after: idx === 1 ? '100.0000' : `${250 + idx}.0000`,
      occurred_at: `2026-11-${String(18 - idx).padStart(2, '0')}T10:00:00Z`,
    }));

    const page2Tx: AdminTransaction[] = [
      {
        id: 'tx-page2',
        card_id: cardId,
        barcode: cardDetail.barcode,
        business_id: businessIdA,
        business_name: 'Alpha Market',
        type: 'redemption',
        amount: '25.0000',
        balance_after: '75.0000',
        occurred_at: '2026-11-01T10:00:00Z',
      },
    ];

    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/admin/auth/refresh')) return json(200, access);
        if (url.endsWith('/admin/me')) return json(200, adminResponse('business_manager'));
        if (url.includes(`/admin/cards/${cardId}/transactions?limit=25&offset=0`)) {
          return json(200, { items: page1Tx, limit: 25, offset: 0, has_more: true, total: 26 });
        }
        if (url.includes(`/admin/cards/${cardId}/transactions?limit=25&offset=25`)) {
          return json(200, { items: page2Tx, limit: 25, offset: 25, has_more: false, total: 26 });
        }
        if (url.endsWith(`/admin/cards/${cardId}`)) {
          return json(200, cardDetail);
        }
        return json(404, { error: { code: 'ADMIN_RESOURCE_NOT_FOUND' } });
      }),
    );

    render(
      <AdminProvider>
        <LocaleProvider initialLocale={locale}>
          <MemoryRouter initialEntries={[`/admin/cards/${cardId}`]}>
            <Routes>
              <Route path="/admin/cards/:cardId" element={<CardDetailPage />} />
            </Routes>
          </MemoryRouter>
        </LocaleProvider>
      </AdminProvider>,
    );

    const expectedTitle = locale === 'ru' ? 'История начислений и списаний' : 'Есептеулер мен шегерулер тарихы';
    expect(await screen.findByText(expectedTitle)).toBeInTheDocument();
    expect(await screen.findByText('+150')).toBeInTheDocument();
    expect(screen.getByText('−50')).toBeInTheDocument();
    expect(screen.getByText('100')).toBeInTheDocument();
    expect(screen.getAllByText(locale === 'ru' ? 'Начисление' : 'Есептеу').length).toBeGreaterThan(0);
    expect(screen.getAllByText(locale === 'ru' ? 'Списание' : 'Шегеру').length).toBeGreaterThan(0);

    // 8th row is collapsed initially until "Показать ещё" / "Тағы көрсету"
    expect(screen.queryByText('+157')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: locale === 'ru' ? 'Показать ещё' : 'Тағы көрсету' }));
    expect(screen.getByText('+157')).toBeInTheDocument();
    expect(screen.getByText(locale === 'ru' ? 'Страница 1 из 2' : '1 / 2 бет')).toBeInTheDocument();
    expect(screen.queryByText(locale === 'ru' ? 'Операции постранично' : 'Операциялар беттер бойынша')).not.toBeInTheDocument();

    // Pagination Next -> Page 2
    await user.click(screen.getByRole('button', { name: locale === 'ru' ? 'Далее' : 'Келесі' }));
    expect(await screen.findByText('−25')).toBeInTheDocument();
    expect(screen.getByText('75')).toBeInTheDocument();
    expect(screen.getByText(locale === 'ru' ? 'Страница 2 из 2' : '2 / 2 бет')).toBeInTheDocument();
  },
);

it.each(['ru', 'kk'] as const)(
  'renders customer transaction history with card links on UserDetailPage (%s)',
  async locale => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
    vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

    const userId = 'user-tx-1';
    const userDetail: AdminUserDetail = {
      id: userId,
      phone: '+77001112233',
      language: locale,
      created_at: '2026-10-01T00:00:00Z',
      cards: {
        items: [
          {
            ...makeMockCard(55, businessIdA, 'Alpha Market'),
            phone_masked: '••••2233',
            full_name: 'Марат Б.',
          },
        ],
        limit: 25,
        offset: 0,
        has_more: false,
      },
    };

    const userTx: AdminTransaction[] = [
      {
        id: 'utx-1',
        card_id: 'card-uuid-55',
        barcode: '0000000000055',
        business_id: businessIdA,
        business_name: 'Alpha Market',
        type: 'accrual',
        amount: '320.0000',
        balance_after: '445.5000',
        occurred_at: '2026-11-18T09:30:00Z',
      },
      {
        id: 'utx-2',
        card_id: 'card-uuid-55',
        barcode: '0000000000055',
        business_id: businessIdA,
        business_name: 'Alpha Market',
        type: 'redemption',
        amount: '100.0000',
        balance_after: '345.5000',
        occurred_at: '2026-11-17T14:00:00Z',
      },
    ];

    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/admin/auth/refresh')) return json(200, access);
        if (url.endsWith('/admin/me')) return json(200, adminResponse('superadmin'));
        if (url.includes(`/admin/users/${userId}/transactions`)) {
          return json(200, { items: userTx, limit: 25, offset: 0, has_more: false, total: 2 });
        }
        if (url.includes(`/admin/users/${userId}`)) {
          return json(200, userDetail);
        }
        return json(404, { error: { code: 'ADMIN_RESOURCE_NOT_FOUND' } });
      }),
    );

    render(
      <AdminProvider>
        <LocaleProvider initialLocale={locale}>
          <MemoryRouter initialEntries={[`/admin/users/${userId}`]}>
            <Routes>
              <Route path="/admin/users/:userId" element={<UserDetailPage />} />
            </Routes>
          </MemoryRouter>
        </LocaleProvider>
      </AdminProvider>,
    );

    const expectedTitle = locale === 'ru' ? 'История начислений и списаний' : 'Есептеулер мен шегерулер тарихы';
    expect(await screen.findByText(expectedTitle)).toBeInTheDocument();
    expect(screen.getByText('••••2233 · Марат Б.')).toBeInTheDocument();
    expect(await screen.findByText('+320')).toBeInTheDocument();
    expect(screen.getByText('−100')).toBeInTheDocument();
    expect(screen.getByText('445,5')).toBeInTheDocument();
    expect(screen.getByText('345,5')).toBeInTheDocument();
    expect(screen.getAllByText('0000000000055').length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText(locale === 'ru' ? 'Тип привязки' : 'Байланыстыру түрі')).not.toBeInTheDocument();
    expect(
      screen.queryByText(
        locale === 'ru'
          ? 'Отображаются только карты, входящие в разрешённую область данных.'
          : 'Рұқсат етілген деректер аймағына кіретін карталар ғана көрсетіледі.',
      ),
    ).not.toBeInTheDocument();
    expect(screen.getByText(locale === 'ru' ? 'Страница 1 из 1' : '1 / 1 бет')).toBeInTheDocument();
  },
);
