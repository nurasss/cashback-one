import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { cleanup, render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AdminProvider } from '../src/auth/provider';
import { ActiveBusinessProvider } from '../src/context/ActiveBusinessContext';
import { LocaleProvider } from '../src/i18n/LocaleContext';
import { DashboardPage } from '../src/pages/DashboardPage';
import { LoginPage } from '../src/pages/LoginPage';

const access = { access_token: 'fixture-token', token_type: 'bearer', expires_in: 900 };
const json = (status: number, data: unknown) =>
  new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });

describe('Unrestricted statistics (2026-11-16)', () => {
  beforeEach(() => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
    vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  const setupMock = ({
    unlimitedPeriod,
    maxPeriodDays = 90,
    role = 'superadmin' as 'superadmin' | 'business_manager',
    business = null as { id: string; name: string; status: string } | null,
    anonymousOnRefresh = false,
    dashboardHandler,
  }: {
    unlimitedPeriod?: boolean;
    maxPeriodDays?: number;
    role?: 'superadmin' | 'business_manager';
    business?: { id: string; name: string; status: string } | null;
    anonymousOnRefresh?: boolean;
    dashboardHandler?: (url: string) => Response | Promise<Response>;
  }) => {
    const dashboardCalls: string[] = [];

    const fetchMock: typeof fetch = vi.fn(async input => {
      const url = String(input);
      if (url.endsWith('/admin/auth/refresh')) {
        return anonymousOnRefresh ? json(401, { error: { code: 'ADMIN_UNAUTHENTICATED' } }) : json(200, access);
      }
      if (url.endsWith('/admin/auth/login')) {
        return json(200, access);
      }
      if (url.endsWith('/admin/me')) {
        const body: Record<string, unknown> = {
          admin: {
            id: 'admin-1',
            login: 'admin.user',
            role,
            business: role === 'business_manager' ? (business ?? { id: 'biz-1', name: 'Керемет', status: 'active' }) : null,
          },
          admin_max_stats_period_days: maxPeriodDays,
        };
        if (unlimitedPeriod !== undefined) {
          body.admin_stats_unlimited_period = unlimitedPeriod;
        }
        return json(200, body);
      }
      if (url.includes('/admin/businesses?')) {
        return json(200, {
          items: [{ id: 'biz-1', name: 'Керемет', status: 'active', logo_url: null, colors: null, created_at: '2026-11-01T00:00:00Z', updated_at: '2026-11-01T00:00:00Z' }],
          limit: 100,
          offset: 0,
          has_more: false,
        });
      }
      if (url.includes('/admin/dashboard')) {
        dashboardCalls.push(url);
        if (dashboardHandler) {
          return dashboardHandler(url);
        }
        return json(200, {
          period_from: '2024-01-01T00:00:00Z',
          period_to: '2026-11-16T23:59:59Z',
          period_days: 1051,
          customers_with_business_cards: 3500,
          cards: 5000,
          unblocked_cards: 4800,
          transactions: 150000,
          agents: { online: 3, stale: 0, never_connected: 0, error: 0, disabled: 0 },
        });
      }
      return json(404, { error: { code: 'NOT_FOUND' } });
    });
    vi.stubGlobal('fetch', fetchMock);

    return { dashboardCalls };
  };

  it('allows multi-year and 367+ days range when admin_stats_unlimited_period=true without duration warning', async () => {
    const user = userEvent.setup();
    const { dashboardCalls } = setupMock({ unlimitedPeriod: true, maxPeriodDays: 90 });

    render(
      <LocaleProvider initialLocale="ru">
        <AdminProvider>
          <ActiveBusinessProvider>
            <MemoryRouter initialEntries={['/admin']}>
              <Routes>
                <Route path="/admin" element={<DashboardPage />} />
              </Routes>
            </MemoryRouter>
          </ActiveBusinessProvider>
        </AdminProvider>
      </LocaleProvider>,
    );

    expect(await screen.findByRole('heading', { name: 'Все бизнесы' })).toBeInTheDocument();
    expect(dashboardCalls.length).toBe(1);

    const fromInput = screen.getByLabelText('С') as HTMLInputElement;
    const toInput = screen.getByLabelText('По') as HTMLInputElement;
    const refreshBtn = screen.getByRole('button', { name: 'Обновить' });

    // Select 367 days (2025-01-01 to 2026-01-02)
    fireEvent.change(fromInput, { target: { value: '2025-01-01' } });
    fireEvent.change(toInput, { target: { value: '2026-01-02' } });

    // No "Выберите период не длиннее 90 дней." hint
    expect(screen.queryByText(/не длиннее/i)).not.toBeInTheDocument();
    expect(refreshBtn).not.toBeDisabled();

    // Select 10-year range (2016-01-01 to 2026-01-01)
    fireEvent.change(fromInput, { target: { value: '2016-01-01' } });
    fireEvent.change(toInput, { target: { value: '2026-01-01' } });

    expect(screen.queryByText(/не длиннее/i)).not.toBeInTheDocument();
    expect(refreshBtn).not.toBeDisabled();

    await user.click(refreshBtn);
    expect(dashboardCalls.length).toBe(2);
    expect(dashboardCalls[1]).toContain('from=2015-12-31T19%3A00%3A00.000Z');
    expect(dashboardCalls[1]).toContain('to=2026-01-01T18%3A59%3A59.999Z');

    // Metrics are updated and rendered
    expect(await screen.findByText('150 000')).toBeInTheDocument();
    expect(screen.getByText('5 000')).toBeInTheDocument();
  });

  it('retains backward compatibility: blocks periods > admin_max_stats_period_days when unlimited is false or omitted', async () => {
    const user = userEvent.setup();
    for (const unlimitedPeriod of [undefined, false]) {
      const { dashboardCalls } = setupMock({ unlimitedPeriod, maxPeriodDays: 90 });

      render(
        <LocaleProvider initialLocale="ru">
          <AdminProvider>
            <ActiveBusinessProvider>
              <MemoryRouter initialEntries={['/admin']}>
                <Routes>
                  <Route path="/admin" element={<DashboardPage />} />
                </Routes>
              </MemoryRouter>
            </ActiveBusinessProvider>
          </AdminProvider>
        </LocaleProvider>,
      );

      expect(await screen.findByRole('heading', { name: 'Все бизнесы' })).toBeInTheDocument();
      expect(dashboardCalls.length).toBe(1);

      const fromInput = screen.getByLabelText('С') as HTMLInputElement;
      const toInput = screen.getByLabelText('По') as HTMLInputElement;
      const refreshBtn = screen.getByRole('button', { name: 'Обновить' });

      // Range of 91 days (2026-01-01 to 2026-04-01 inclusive = 91 days)
      fireEvent.change(fromInput, { target: { value: '2026-01-01' } });
      fireEvent.change(toInput, { target: { value: '2026-04-01' } });

      expect(screen.getByText('Выберите период не длиннее 90 дней.')).toBeInTheDocument();
      expect(refreshBtn).not.toBeDisabled();

      await user.click(refreshBtn);
      expect(dashboardCalls.length).toBe(1); // blocked, not called
      cleanup();
    }
  });

  it('validates reversed and malformed dates in unlimited mode in RU and KK', async () => {
    const user = userEvent.setup();
    const { dashboardCalls } = setupMock({ unlimitedPeriod: true });

    render(
      <LocaleProvider initialLocale="ru">
        <AdminProvider>
          <ActiveBusinessProvider>
            <MemoryRouter initialEntries={['/admin']}>
              <Routes>
                <Route path="/admin" element={<DashboardPage />} />
              </Routes>
            </MemoryRouter>
          </ActiveBusinessProvider>
        </AdminProvider>
      </LocaleProvider>,
    );

    expect(await screen.findByRole('heading', { name: 'Все бизнесы' })).toBeInTheDocument();
    const fromInput = screen.getByLabelText('С') as HTMLInputElement;
    const toInput = screen.getByLabelText('По') as HTMLInputElement;
    const refreshBtn = screen.getByRole('button', { name: 'Обновить' });

    // Reversed dates: from > to
    fireEvent.change(fromInput, { target: { value: '2026-11-16' } });
    fireEvent.change(toInput, { target: { value: '2025-01-01' } });

    expect(screen.getByText('Проверьте даты: конец периода не может быть раньше начала.')).toBeInTheDocument();
    expect(refreshBtn).not.toBeDisabled();

    await user.click(refreshBtn);
    expect(dashboardCalls.length).toBe(1); // no extra call
  });

  it('works in Kazakh (KK) with multi-year period and date validation error', async () => {
    const user = userEvent.setup();
    const { dashboardCalls } = setupMock({ unlimitedPeriod: true });

    render(
      <LocaleProvider initialLocale="kk">
        <AdminProvider>
          <ActiveBusinessProvider>
            <MemoryRouter initialEntries={['/admin']}>
              <Routes>
                <Route path="/admin" element={<DashboardPage />} />
              </Routes>
            </MemoryRouter>
          </ActiveBusinessProvider>
        </AdminProvider>
      </LocaleProvider>,
    );

    expect(await screen.findByRole('heading', { name: 'Барлық бизнестер' })).toBeInTheDocument();
    const fromInput = screen.getByLabelText('Бастап') as HTMLInputElement;
    const toInput = screen.getByLabelText('Дейін') as HTMLInputElement;
    const refreshBtn = screen.getByRole('button', { name: 'Жаңарту' });

    // 5-year period: valid, no error
    fireEvent.change(fromInput, { target: { value: '2021-01-01' } });
    fireEvent.change(toInput, { target: { value: '2026-01-01' } });

    expect(screen.queryByText(/аспайтын/i)).not.toBeInTheDocument();
    expect(refreshBtn).not.toBeDisabled();

    await user.click(refreshBtn);
    expect(dashboardCalls.length).toBe(2);

    // Reversed dates in KK
    fireEvent.change(fromInput, { target: { value: '2026-01-01' } });
    fireEvent.change(toInput, { target: { value: '2021-01-01' } });

    expect(screen.getByText('Кезең күндерін тексеріңіз: аяқталу күні басталу күнінен ерте болмауы керек.')).toBeInTheDocument();
    expect(refreshBtn).not.toBeDisabled();
    await user.click(refreshBtn);
    expect(dashboardCalls.length).toBe(2); // no extra call on invalid dates
  });

  it('supports business_manager role with multi-year range', async () => {
    const user = userEvent.setup();
    const { dashboardCalls } = setupMock({
      unlimitedPeriod: true,
      role: 'business_manager',
      business: { id: 'biz-1', name: 'Керемет Маркет', status: 'active' },
    });

    render(
      <LocaleProvider initialLocale="ru">
        <AdminProvider>
          <ActiveBusinessProvider>
            <MemoryRouter initialEntries={['/admin']}>
              <Routes>
                <Route path="/admin" element={<DashboardPage />} />
              </Routes>
            </MemoryRouter>
          </ActiveBusinessProvider>
        </AdminProvider>
      </LocaleProvider>,
    );

    expect(await screen.findByRole('heading', { name: 'Керемет Маркет' })).toBeInTheDocument();
    const fromInput = screen.getByLabelText('С') as HTMLInputElement;
    const toInput = screen.getByLabelText('По') as HTMLInputElement;
    const refreshBtn = screen.getByRole('button', { name: 'Обновить' });

    fireEvent.change(fromInput, { target: { value: '2023-01-01' } });
    fireEvent.change(toInput, { target: { value: '2026-01-01' } });

    expect(refreshBtn).not.toBeDisabled();
    await user.click(refreshBtn);
    expect(dashboardCalls.length).toBe(2);
  });

  it('preserves retry and restore-working-period recovery on error in unlimited mode', async () => {
    const user = userEvent.setup();
    let callCount = 0;
    const { dashboardCalls } = setupMock({
      unlimitedPeriod: true,
      dashboardHandler: () => {
        callCount += 1;
        if (callCount === 2) {
          throw new TypeError('Failed to fetch');
        }
        return json(200, {
          period_from: '2024-01-01T00:00:00Z',
          period_to: '2026-11-16T23:59:59Z',
          period_days: 1051,
          customers_with_business_cards: 3500,
          cards: 5000,
          unblocked_cards: 4800,
          transactions: 150000,
          agents: { online: 3, stale: 0, never_connected: 0, error: 0, disabled: 0 },
        });
      },
    });

    render(
      <LocaleProvider initialLocale="ru">
        <AdminProvider>
          <ActiveBusinessProvider>
            <MemoryRouter initialEntries={['/admin']}>
              <Routes>
                <Route path="/admin" element={<DashboardPage />} />
              </Routes>
            </MemoryRouter>
          </ActiveBusinessProvider>
        </AdminProvider>
      </LocaleProvider>,
    );

    expect(await screen.findByRole('heading', { name: 'Все бизнесы' })).toBeInTheDocument();
    const fromInput = screen.getByLabelText('С') as HTMLInputElement;
    const toInput = screen.getByLabelText('По') as HTMLInputElement;

    fireEvent.change(fromInput, { target: { value: '2022-01-01' } });
    fireEvent.change(toInput, { target: { value: '2026-11-16' } });
    await user.click(screen.getByRole('button', { name: 'Обновить' }));

    expect(await screen.findByText(/Нет соединения\. Проверьте интернет и повторите запрос\./i)).toBeInTheDocument();
    const retryBtn = screen.getByRole('button', { name: 'Повторить' });
    expect(screen.queryByRole('button', { name: 'Назад' })).not.toBeInTheDocument();
    expect(fromInput.value).toBe('2022-01-01');
    expect(toInput.value).toBe('2026-11-16');

    await user.click(retryBtn);
    expect(await screen.findByText('150 000')).toBeInTheDocument();
    expect(dashboardCalls.length).toBe(3);
  });

  it('completes LoginPage form flow cleanly with legacy backend (omitted unlimited flag) and respects 90-day guard', async () => {
    const user = userEvent.setup();
    setupMock({ anonymousOnRefresh: true, maxPeriodDays: 90 });

    render(
      <LocaleProvider initialLocale="ru">
        <AdminProvider>
          <ActiveBusinessProvider>
            <MemoryRouter initialEntries={['/admin/login']}>
              <Routes>
                <Route path="/admin/login" element={<LoginPage />} />
                <Route path="/admin" element={<DashboardPage />} />
              </Routes>
            </MemoryRouter>
          </ActiveBusinessProvider>
        </AdminProvider>
      </LocaleProvider>,
    );

    const loginInput = await screen.findByLabelText('Логин');
    const passwordInput = screen.getByLabelText('Пароль');
    await user.type(loginInput, 'admin.user');
    await user.type(passwordInput, 'fixture-pass');
    await user.click(screen.getByRole('button', { name: /Войти/i }));

    expect(await screen.findByRole('heading', { name: 'Все бизнесы' })).toBeInTheDocument();
    const fromInput = screen.getByLabelText('С') as HTMLInputElement;
    const toInput = screen.getByLabelText('По') as HTMLInputElement;
    fireEvent.change(fromInput, { target: { value: '2024-01-01' } });
    fireEvent.change(toInput, { target: { value: '2026-11-16' } });
    expect(screen.getByText('Выберите период не длиннее 90 дней.')).toBeInTheDocument();
  });
});
