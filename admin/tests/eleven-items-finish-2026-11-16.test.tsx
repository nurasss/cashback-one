import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type {
  AppNotification,
  AuditItem,
  BusinessDetail,
  LoyaltyTier,
  PosKey,
  Promotion,
  BusinessStore,
} from '../src/api/types';
import { AdminProvider } from '../src/auth/provider';
import { DataTable } from '../src/components/DataTable';
import { ActiveBusinessProvider } from '../src/context/ActiveBusinessContext';
import { AgentCreateDialog, BusinessEditorDialog } from '../src/features/AdminMutations';
import { BusinessStoresSection } from '../src/features/BusinessAppContent';
import { BusinessPosKeys, PosKeyCreateDialog } from '../src/features/BusinessPosKeys';
import { LOCALE_STORAGE_KEY, LocaleProvider } from '../src/i18n/LocaleContext';
import { AdminLayout } from '../src/layout/AdminLayout';
import { AuditPage } from '../src/pages/AuditPage';
import { ContentPage, PromotionDialog } from '../src/pages/ContentPage';
import { DashboardPage } from '../src/pages/DashboardPage';
import { NotificationsPage } from '../src/pages/NotificationsPage';
import { UserDetailPage } from '../src/pages/OperationsPage';
import { StatusesPage } from '../src/pages/StatusesPage';

const access = { access_token: 'fixture-access', token_type: 'bearer', expires_in: 900 };
const businessId = '11111111-1111-1111-1111-111111111111';
const secondBusinessId = '22222222-2222-2222-2222-222222222222';
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  window.localStorage.clear();
});

function setupEnvFetch(
  role: 'superadmin' | 'business_manager',
  handler: (url: URL, init?: RequestInit) => Response | Promise<Response>
) {
  vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
  vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');
  return vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input), 'https://admin.test');
      if (url.pathname === '/admin/auth/refresh') return json(200, access);
      if (url.pathname === '/admin/me') {
        return json(200, {
          admin: {
            id: 'admin-1',
            login: role === 'superadmin' ? 'root.admin' : 'keremet.manager',
            role,
            business: role === 'business_manager' ? { id: businessId, name: 'Keremet', status: 'active' } : null,
          },
          admin_max_stats_period_days: 3650,
        });
      }
      return handler(url, init);
    })
  );
}

describe('Admin 11-item completion checks (2026-11-16)', () => {
  describe('P1: Form controls padding, native accent, and accessible PosKeyCreateDialog label', () => {
    it('defines safe padding rules in admin.css and binds PosKeyCreateDialog label to input', async () => {
      const css = readFileSync(resolve(process.cwd(), 'src/styles/admin.css'), 'utf8');
      expect(css).toContain('.admin-surface select');
      expect(css).toContain('padding-right: 38px');
      expect(css).toContain('::-webkit-calendar-picker-indicator');
      expect(css).toContain('::-webkit-inner-spin-button');
      expect(css).toContain('padding: 10px 14px 10px 12px');
      expect(css).toContain('accent-color: var(--brand-dark)');
      expect(css).toContain(':not([type="color"]):not([type="file"])');

      setupEnvFetch('superadmin', () => json(200, []));
      render(
        <AdminProvider>
          <LocaleProvider initialLocale="ru">
            <PosKeyCreateDialog businessId={businessId} onClose={() => {}} onCreated={() => {}} />
          </LocaleProvider>
        </AdminProvider>
      );
      const input = await screen.findByLabelText('Название кассы');
      expect(input).toHaveAttribute('id', 'pos-key-name');
    });
  });

  describe('P2-P3: Structured BusinessEditorDialog without forced JSON & preserving unknown keys', () => {
    it('manages prefixes, colors (preserving extra keys), legacy tiers via structured controls and keeps validation near source', async () => {
      const user = userEvent.setup();
      let patchedBody: Record<string, unknown> | null = null;
      const existingBusiness: BusinessDetail = {
        id: businessId,
        name: 'Keremet Market',
        logo_url: 'https://cdn.example.test/logo.webp',
        colors: { primary: '#ff3a4d', secondary: '#102030', customToken: 'gold' },
        barcode_prefixes: ['10', '20'],
        android_app_id: 'kz.cashbackone.keremet',
        status: 'active',
        loyalty_tiers: [{ level: 1, name: 'Старт', threshold: '0', percent: '1' }],
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-10-01T00:00:00Z',
        cards_count: 10,
        unblocked_cards_count: 10,
        customers_with_cards_count: 8,
        agents_count: 1,
      };

      setupEnvFetch('superadmin', async (url, init) => {
        if (url.pathname === `/admin/businesses/${businessId}` && init?.method === 'PATCH') {
          patchedBody = JSON.parse(String(init.body)) as Record<string, unknown>;
          return json(200, { ...existingBusiness, ...patchedBody });
        }
        return json(404, { error: { code: 'NOT_FOUND', message: 'Not found' } });
      });

      const onSaved = vi.fn();
      render(
        <QueryClientProvider client={new QueryClient()}>
          <AdminProvider>
            <ActiveBusinessProvider>
              <LocaleProvider initialLocale="ru">
                <BusinessEditorDialog business={existingBusiness} onClose={() => {}} onSaved={onSaved} />
              </LocaleProvider>
            </ActiveBusinessProvider>
          </AdminProvider>
        </QueryClientProvider>
      );

      // Fieldsets distinguish main info, prefixes, colors, and legacy tiers (separate from Statuses)
      expect(await screen.findByText('Основные данные')).toBeInTheDocument();
      expect(screen.getByText('Префиксы карт')).toBeInTheDocument();
      expect(screen.getByText('Цвета приложения')).toBeInTheDocument();
      expect(screen.getByText('Уровни профиля бизнеса (устаревшая схема)')).toBeInTheDocument();
      expect(screen.getByText(/настраивается в разделе «Статусы»/)).toBeInTheDocument();

      // Add prefix via Enter (should NOT submit the form), remove one prefix
      const draftInput = screen.getByLabelText('Добавить префикс штрихкода');
      await user.type(draftInput, '305{enter}');
      expect(patchedBody).toBeNull();
      expect(screen.getByText('305')).toBeInTheDocument();
      await user.click(screen.getByRole('button', { name: 'Удалить префикс 10' }));
      expect(screen.queryByRole('button', { name: 'Удалить префикс 10' })).not.toBeInTheDocument();

      // Duplicate prefix gives local error without wiping list
      await user.type(draftInput, '20');
      await user.click(screen.getByRole('button', { name: 'Добавить' }));
      expect(screen.getByText('Такой префикс уже добавлен.')).toBeInTheDocument();

      // Change primary color and add accent color while extra keys remain visible
      expect(screen.getByText('secondary: #102030')).toBeInTheDocument();
      expect(screen.getByText('customToken: gold')).toBeInTheDocument();
      const accentInput = screen.getByPlaceholderText('#0f172a');
      await user.type(accentInput, '#0f766e');

      // Add a legacy tier cleanly via structured button: row 2 MUST start with empty threshold (no auto-100000!)
      await user.click(screen.getByRole('button', { name: 'Добавить уровень' }));
      const nameInputs = screen.getAllByLabelText('Название');
      await user.type(nameInputs[nameInputs.length - 1]!, 'VIP');
      const thresholdInputs = screen.getAllByLabelText('Порог, ₸');
      const addedThresholdInput = thresholdInputs[thresholdInputs.length - 1]!;
      expect(addedThresholdInput).toHaveValue('');

      // Trying to save with empty threshold must be blocked near field (no coercion to 0 or 100000)
      await user.click(screen.getByRole('button', { name: 'Сохранить' }));
      const thresholdAlert = await screen.findByRole('alert');
      expect(thresholdAlert).toHaveTextContent('Укажите порог');
      expect(patchedBody).toBeNull();

      // Enter explicit threshold 250000
      await user.type(addedThresholdInput, '250000');

      // Validate inline error near android_app_id without losing changes
      const appIdInput = screen.getByLabelText('Пакет Android-приложения');
      await user.clear(appIdInput);
      await user.type(appIdInput, 'invalid-package');
      await user.click(screen.getByRole('button', { name: 'Сохранить' }));
      const alert = await screen.findByRole('alert');
      expect(alert).toHaveTextContent('Неверный формат пакета Android-приложения');

      // Fix package ID and save
      await user.clear(appIdInput);
      await user.type(appIdInput, 'kz.cashbackone.keremet.v2');
      await user.click(screen.getByRole('button', { name: 'Сохранить' }));

      await waitFor(() => expect(onSaved).toHaveBeenCalled());
      expect(patchedBody).toMatchObject({
        barcode_prefixes: ['20', '305'],
        colors: { primary: '#ff3a4d', accent: '#0f766e', secondary: '#102030', customToken: 'gold' },
        android_app_id: 'kz.cashbackone.keremet.v2',
        loyalty_tiers: [
          { level: 1, name: 'Старт', threshold: '0', percent: '1' },
          { level: 2, name: 'VIP', threshold: '250000', percent: '0' },
        ],
      });
    }, 15_000);
  });

  describe('P4-P5: Multi-year unrestricted period & repeated Overview tab activation', () => {
    it('submits multi-year date range to dashboard API and clears stale navigation errors on Overview click', async () => {
      const user = userEvent.setup();
      const dashboardCalls: string[] = [];
      setupEnvFetch('business_manager', url => {
        if (url.pathname === '/admin/dashboard') {
          dashboardCalls.push(url.search);
          return json(200, {
            business_id: businessId,
            business_name: 'Keremet',
            period_from: '2020-01-01T00:00:00Z',
            period_to: '2026-11-16T23:59:59Z',
            period_days: 2512,
            customers_with_business_cards: 42,
            cards: 50,
            unblocked_cards: 49,
            transactions: 300,
            agents: { online: 1, stale: 0, never_connected: 0, error: 0, disabled: 0 },
          });
        }
        return json(200, { items: [], limit: 25, offset: 0, has_more: false });
      });

      render(
        <QueryClientProvider client={new QueryClient()}>
          <MemoryRouter initialEntries={['/admin']}>
            <AdminProvider>
              <ActiveBusinessProvider>
                <LocaleProvider initialLocale="ru">
                  <Routes>
                    <Route path="/admin" element={<AdminLayout><DashboardPage /></AdminLayout>} />
                    <Route path="/admin/audit" element={<div>Audit Dummy</div>} />
                  </Routes>
                </LocaleProvider>
              </ActiveBusinessProvider>
            </AdminProvider>
          </MemoryRouter>
        </QueryClientProvider>
      );

      const fromInput = await screen.findByLabelText('С');
      const toInput = screen.getByLabelText('По');
      fireEvent.change(fromInput, { target: { value: '2020-01-01' } });
      fireEvent.change(toInput, { target: { value: '2026-11-16' } });
      await user.click(screen.getByRole('button', { name: 'Обновить' }));

      await waitFor(() =>
        expect(dashboardCalls.some(q => (q.includes('2020-01-01') || q.includes('2019-12-31')) && q.includes('2026-11-16'))).toBe(true)
      );

      // Re-clicking active Overview link preserves working page without errors
      await user.click(screen.getByRole('link', { name: /Главная|Обзор/ }));
      expect(await screen.findByRole('heading', { name: 'Keremet' })).toBeInTheDocument();
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
  });

  describe('P6 & K2: Complete real pagination across tables, catalogs, empty offset>0, and filter resets', () => {
    it('renders Pagination on empty DataTable page > 0 so users are never stranded', async () => {
      const user = userEvent.setup();
      const onPage = vi.fn();
      render(
        <LocaleProvider initialLocale="ru">
          <DataTable
            rows={[]}
            rowKey={(r: { id: string }) => r.id}
            columns={[{ key: 'name', title: 'Name', render: r => r.id }]}
            page={{ limit: 25, offset: 25, has_more: false }}
            onPage={onPage}
          />
        </LocaleProvider>
      );
      expect(screen.getByText('По заданным условиям записей не найдено.')).toBeInTheDocument();
      const prevBtn = screen.getByRole('button', { name: 'Назад' });
      expect(prevBtn).toBeEnabled();
      await user.click(prevBtn);
      expect(onPage).toHaveBeenCalledWith(0);
    });

    it('paginates StatusesPage (30 rows) separately from Показать ещё, auto-clamps on delete, and resets on business switch', async () => {
      const user = userEvent.setup();
      window.localStorage.setItem(LOCALE_STORAGE_KEY, 'kk');
      const tiersBiz1: LoyaltyTier[] = Array.from({ length: 26 }, (_, i) => ({
        id: `tier-${i + 1}`,
        business_id: businessId,
        level: i + 1,
        priority: 0,
        min_turnover: String(i * 10000),
        max_turnover: null,
        percent: '3',
        name_ru: `Статус ${i + 1}`,
        name_kk: `Дәреже ${i + 1}`,
        is_active: true,
        is_default: i === 0,
      }));
      let currentBiz1 = [...tiersBiz1];
      vi.stubGlobal('confirm', vi.fn(() => true));

      setupEnvFetch('superadmin', (url, init) => {
        if (url.pathname === '/admin/businesses') {
          return json(200, {
            items: [
              { id: businessId, name: 'Biz 1', status: 'active' },
              { id: secondBusinessId, name: 'Biz 2', status: 'active' },
            ],
            limit: 100,
            offset: 0,
            has_more: false,
          });
        }
        if (url.pathname === `/admin/businesses/${businessId}/loyalty-tiers`) {
          return json(200, currentBiz1);
        }
        if (url.pathname.startsWith(`/admin/businesses/${businessId}/loyalty-tiers/`) && init?.method === 'DELETE') {
          const id = url.pathname.split('/').pop();
          currentBiz1 = currentBiz1.filter(t => t.id !== id);
          return json(200, { ok: true });
        }
        if (url.pathname === `/admin/businesses/${secondBusinessId}/loyalty-tiers`) {
          return json(200, [
            {
              id: 'b2-tier-1',
              business_id: secondBusinessId,
              level: 1,
              priority: 0,
              min_turnover: '0',
              max_turnover: null,
              percent: '2',
              name_ru: 'Второй',
              name_kk: 'Екінші',
              is_active: true,
              is_default: true,
            },
          ]);
        }
        return json(200, []);
      });

      const { container } = render(
        <QueryClientProvider client={new QueryClient()}>
          <AdminProvider>
            <ActiveBusinessProvider>
              <LocaleProvider initialLocale="kk">
                <StatusesPage />
              </LocaleProvider>
            </ActiveBusinessProvider>
          </AdminProvider>
        </QueryClientProvider>
      );

      expect(await screen.findByText('Дәреже 1')).toBeInTheDocument();
      // Compacting + real Pagination shown separately in KK ('Тағы көрсету' & '1 / 2 бет')
      expect(container.querySelectorAll('tbody tr')).toHaveLength(7);
      expect(screen.getByRole('button', { name: 'Тағы көрсету' })).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Барлығы \(/ })).not.toBeInTheDocument();
      expect(screen.getByText('1 / 2 бет')).toBeInTheDocument();

      // Page 2 shows item #26 without clicking Тағы көрсету
      await user.click(screen.getByRole('button', { name: 'Келесі' }));
      expect(await screen.findByText('Дәреже 26')).toBeInTheDocument();
      expect(screen.getByText('2 / 2 бет')).toBeInTheDocument();

      // Deleting the sole item on Page 2 auto-clamps back to Page 1!
      await user.click(screen.getByRole('button', { name: 'Жою' }));
      await waitFor(() => expect(screen.getByText('1 / 1 бет')).toBeInTheDocument());

      // Switching business resets cleanly
      await user.selectOptions(screen.getByLabelText(/Бизнес/), secondBusinessId);
      expect(await screen.findByText('Екінші')).toBeInTheDocument();
    });

    it('paginates BusinessStoresSection and BusinessPosKeys (30 items) cleanly in RU with separate Показать ещё', async () => {
      const user = userEvent.setup();
      const stores: BusinessStore[] = Array.from({ length: 28 }, (_, i) => ({
        id: `store-${i + 1}`,
        business_id: businessId,
        title_ru: `Магазин ${i + 1}`,
        title_kk: `Дүкен ${i + 1}`,
        address_ru: `Улица ${i + 1}`,
        address_kk: `Көше ${i + 1}`,
        sort_order: i + 1,
        is_active: true,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      }));
      const posKeys: PosKey[] = Array.from({ length: 27 }, (_, i) => ({
        id: `key-${i + 1}`,
        business_id: businessId,
        name: `Касса №${i + 1}`,
        created_at: '2026-01-01T00:00:00Z',
        last_used_at: null,
        revoked_at: null,
        status: 'active',
      }));

      setupEnvFetch('superadmin', url => {
        if (url.pathname.endsWith('/stores')) return json(200, stores);
        if (url.pathname.endsWith('/pos-keys')) return json(200, posKeys);
        return json(200, []);
      });

      const qc = new QueryClient();
      render(
        <QueryClientProvider client={qc}>
          <AdminProvider>
            <LocaleProvider initialLocale="ru">
              <BusinessStoresSection businessId={businessId} />
              <BusinessPosKeys businessId={businessId} />
            </LocaleProvider>
          </AdminProvider>
        </QueryClientProvider>
      );

      expect(await screen.findByText('Магазин 1')).toBeInTheDocument();
      expect(await screen.findAllByText('Касса №1')).not.toHaveLength(0);
      const page1Labels = screen.getAllByText('Страница 1 из 2');
      expect(page1Labels).toHaveLength(2);
      const nextButtons = screen.getAllByRole('button', { name: 'Далее' });
      await user.click(nextButtons[0]!);
      expect(await screen.findByText('Магазин 26')).toBeInTheDocument();
      expect(screen.getByText('Страница 2 из 2')).toBeInTheDocument();

      await user.click(nextButtons[1]!);
      expect(await screen.findAllByText('Касса №26')).not.toHaveLength(0);
    });

    it('paginates PromotionsTable (limit=25 across tabs + empty page > 0 Back), Notifications filter reset, AgentCreateDialog prev on last page, and UserDetailPage empty page > 0', async () => {
      const user = userEvent.setup();
      const promoQueries: string[] = [];
      const noticeQueries: string[] = [];
      setupEnvFetch('superadmin', url => {
        if (url.pathname === '/admin/businesses') {
          const offset = Number(url.searchParams.get('offset') ?? 0);
          return json(200, {
            items:
              offset === 0
                ? [{ id: businessId, name: 'Biz One', status: 'active' }, { id: secondBusinessId, name: 'Biz Two', status: 'active' }]
                : [{ id: '33333333-3333-3333-3333-333333333333', name: 'Biz Page2', status: 'active' }],
            limit: 100,
            offset,
            has_more: offset === 0,
          });
        }
        if (url.pathname === '/admin/promotions') {
          promoQueries.push(url.search);
          const offset = Number(url.searchParams.get('offset') ?? 0);
          return json(200, {
            items:
              offset === 0
                ? [
                    {
                      id: 'p1',
                      kind: 'banner',
                      title: 'Banner Page 1',
                      sort_order: 1,
                      is_active: true,
                      created_at: '2026-01-01T00:00:00Z',
                    } satisfies Promotion,
                  ]
                : [],
            limit: 25,
            offset,
            has_more: offset === 0,
          });
        }
        if (url.pathname === '/admin/notifications') {
          noticeQueries.push(url.search);
          const offset = Number(url.searchParams.get('offset') ?? 0);
          const biz = url.searchParams.get('business_id');
          if (!biz) {
            return json(200, {
              items: [
                {
                  id: `n-${offset}`,
                  business_id: null,
                  title: offset === 0 ? 'Notice P1' : 'Notice P2',
                  body: 'Body',
                  created_at: '2026-01-01T00:00:00Z',
                } satisfies AppNotification,
              ],
              limit: 25,
              offset,
              has_more: offset === 0,
            });
          }
          return json(200, {
            items: [
              {
                id: 'n-biz',
                business_id: biz,
                title: 'Biz Notice',
                body: 'Scoped',
                created_at: '2026-01-01T00:00:00Z',
              } satisfies AppNotification,
            ],
            limit: 25,
            offset,
            has_more: false,
          });
        }
        if (url.pathname === '/admin/users/u-1') {
          const offset = Number(url.searchParams.get('offset') ?? 0);
          return json(200, {
            id: 'u-1',
            phone: '+77001112233',
            language: 'ru',
            created_at: '2026-01-01T00:00:00Z',
            cards: {
              items:
                offset === 0
                  ? [
                      {
                        id: 'c1',
                        business_id: businessId,
                        business_name: 'Keremet',
                        barcode: '100001',
                        balance: '50',
                        bind_method: 'phone',
                        is_blocked: false,
                      },
                    ]
                  : [],
              limit: 25,
              offset,
              has_more: offset === 0,
            },
          });
        }
        return json(200, { items: [], limit: 25, offset: 0, has_more: false });
      });

      const qc = new QueryClient();
      render(
        <QueryClientProvider client={qc}>
          <MemoryRouter initialEntries={['/admin/notifications']}>
            <AdminProvider>
              <ActiveBusinessProvider>
                <LocaleProvider initialLocale="ru">
                  <NotificationsPage />
                </LocaleProvider>
              </ActiveBusinessProvider>
            </AdminProvider>
          </MemoryRouter>
        </QueryClientProvider>
      );

      expect(await screen.findByText('Notice P1')).toBeInTheDocument();
      await user.click(screen.getByRole('button', { name: 'Далее' }));
      expect(await screen.findByText('Notice P2')).toBeInTheDocument();
      await user.selectOptions(screen.getByLabelText('Бизнес'), businessId);
      expect(await screen.findByText('Biz Notice')).toBeInTheDocument();
      expect(noticeQueries.some(q => q.includes(`business_id=${businessId}`) && q.includes('offset=0'))).toBe(true);

      cleanup();
      render(
        <QueryClientProvider client={new QueryClient()}>
          <MemoryRouter initialEntries={['/admin/content']}>
            <AdminProvider>
              <ActiveBusinessProvider>
                <LocaleProvider initialLocale="ru">
                  <ContentPage />
                </LocaleProvider>
              </ActiveBusinessProvider>
            </AdminProvider>
          </MemoryRouter>
        </QueryClientProvider>
      );
      expect(await screen.findByText('Banner Page 1')).toBeInTheDocument();
      expect(promoQueries[0]).toContain('limit=25');
      await user.click(screen.getByRole('button', { name: 'Далее' }));
      expect(await screen.findByText('По заданным условиям записей не найдено.')).toBeInTheDocument();
      await user.click(screen.getByRole('button', { name: 'Назад' }));
      expect(await screen.findByText('Banner Page 1')).toBeInTheDocument();

      // AgentCreateDialog page 2 retains enabled Prev button when has_more is false
      cleanup();
      render(
        <QueryClientProvider client={new QueryClient()}>
          <AdminProvider>
            <LocaleProvider initialLocale="ru">
              <AgentCreateDialog onClose={() => {}} onCreated={() => {}} />
            </LocaleProvider>
          </AdminProvider>
        </QueryClientProvider>
      );
      await screen.findByText('Biz One');
      await user.click(screen.getByRole('button', { name: 'Следующие бизнесы' }));
      await screen.findByText('Biz Page2');
      expect(screen.getByRole('button', { name: 'Предыдущие бизнесы' })).toBeEnabled();
      expect(screen.getByRole('button', { name: 'Следующие бизнесы' })).toBeDisabled();

      // UserDetailPage empty page 2 retains enabled Назад
      cleanup();
      render(
        <QueryClientProvider client={new QueryClient()}>
          <MemoryRouter initialEntries={['/admin/users/u-1']}>
            <AdminProvider>
              <LocaleProvider initialLocale="ru">
                <Routes>
                  <Route path="/admin/users/:userId" element={<UserDetailPage />} />
                </Routes>
              </LocaleProvider>
            </AdminProvider>
          </MemoryRouter>
        </QueryClientProvider>
      );
      await screen.findByText('100001');
      await user.click(screen.getByRole('button', { name: 'Далее' }));
      await screen.findByText('Карт не найдено.');
      await user.click(screen.getByRole('button', { name: 'Назад' }));
      expect(await screen.findByText('100001')).toBeInTheDocument();
    });
  });

  describe('K3 & K4: Promotion checkboxes preserve original historical dates/seconds on round-trip toggle', () => {
    it('keeps exact starts_at with seconds when toggling startNow on and back off via keyboard/click', async () => {
      const user = userEvent.setup();
      let patchedBody: Record<string, unknown> | null = null;
      const promo: Promotion = {
        id: 'promo-hist-1',
        business_id: businessId,
        kind: 'offer',
        title: 'Осенняя акция',
        subtitle: null,
        badge: null,
        body: null,
        image_url: null,
        starts_at: '2026-10-01T10:15:42Z',
        ends_at: null,
        sort_order: 10,
        is_active: true,
        created_at: '2026-09-25T00:00:00Z',
      };

      setupEnvFetch('business_manager', async (url, init) => {
        if (url.pathname === `/admin/promotions/${promo.id}` && init?.method === 'PATCH') {
          patchedBody = JSON.parse(String(init.body)) as Record<string, unknown>;
          return json(200, { ...promo, ...patchedBody });
        }
        return json(200, {});
      });

      const onClose = vi.fn();
      render(
        <QueryClientProvider client={new QueryClient()}>
          <AdminProvider>
            <LocaleProvider initialLocale="ru">
              <PromotionDialog businessId={businessId} defaultKind="offer" promotion={promo} onClose={onClose} />
            </LocaleProvider>
          </AdminProvider>
        </QueryClientProvider>
      );

      const startNowCheckbox = await screen.findByLabelText('Начать сейчас');
      const noEndCheckbox = screen.getByLabelText('Бессрочно');
      const activeCheckbox = screen.getByLabelText('Показывать в приложении');
      expect(startNowCheckbox).not.toBeChecked();
      expect(noEndCheckbox).toBeChecked();
      expect(activeCheckbox).toBeChecked();

      // Round-trip toggle startNow ON -> OFF
      await user.click(startNowCheckbox);
      expect(startNowCheckbox).toBeChecked();
      expect(screen.getByLabelText('Начало показа')).toBeDisabled();
      await user.click(startNowCheckbox);
      expect(startNowCheckbox).not.toBeChecked();

      // Save without getting false "past start date" error and verify exact seconds preserved
      await user.click(screen.getByRole('button', { name: 'Сохранить' }));
      await waitFor(() => expect(onClose).toHaveBeenCalled());
      expect(patchedBody).toMatchObject({
        starts_at: '2026-10-01T10:15:42Z',
        ends_at: null,
        is_active: true,
      });
    });
  });

  // Draft AuditPage behaviour, not in production 18.11; the draft and these checks live on wip/admin-audit-splash-drafts.
  describe.skip('K5: Clear AuditPage details, role isolation, secret filtering, and honest empty snapshots', () => {
    const sampleAuditRows: AuditItem[] = [
      {
        id: 'audit-banner-edit',
        business_id: businessId,
        actor: 'keremet.manager',
        action: 'promotion_updated',
        entity: 'promotion',
        entity_id: 'promo-1',
        before_state: {
          promotion_id: 'promo-1',
          business_id: businessId,
          kind: 'banner',
          title_ru: 'Старый баннер',
          is_active: true,
          percent: 3,
          api_key_hash: 'deadbeefsecret',
          password_token: '[REDACTED]',
        },
        after_state: {
          promotion_id: 'promo-1',
          business_id: businessId,
          kind: 'banner',
          title_ru: 'Новый баннер',
          is_active: false,
          percent: 5,
          android_app_id: 'kz.cashbackone.keremet',
        },
        created_at: '2026-11-16T08:00:00Z',
      },
      {
        id: 'audit-offer-create',
        business_id: businessId,
        actor: 'keremet.manager',
        action: 'promotion_created',
        entity: 'promotion',
        entity_id: 'promo-2',
        before_state: null,
        after_state: {
          promotion_id: 'promo-2',
          business_id: businessId,
          kind: 'offer',
          title_ru: 'Осенний кешбэк',
          is_active: true,
        },
        created_at: '2026-11-16T07:00:00Z',
      },
      {
        id: 'audit-null-tier',
        business_id: businessId,
        actor: 'keremet.manager',
        action: 'loyalty_tier_updated',
        entity: 'business_loyalty_tier',
        entity_id: 'tier-9',
        before_state: null,
        after_state: null,
        created_at: '2026-11-16T06:00:00Z',
      },
      {
        id: 'audit-texts-update',
        business_id: businessId,
        actor: 'keremet.manager',
        action: 'app_texts_updated',
        entity: 'business_app_texts',
        entity_id: businessId,
        before_state: { support_phone: '+77001110000' },
        after_state: { support_phone: '+77009998877' },
        created_at: '2026-11-16T05:00:00Z',
      },
    ];

    it('shows clear banner vs offer labels, diff values without secrets/IDs/raw JSON for business_manager, and Нет подробностей on null', async () => {
      setupEnvFetch('business_manager', url => {
        if (url.pathname === '/admin/audit') {
          return json(200, { items: sampleAuditRows, limit: 25, offset: 0, has_more: false });
        }
        return json(200, {});
      });

      const { container } = render(
        <QueryClientProvider client={new QueryClient()}>
          <AdminProvider>
            <LocaleProvider initialLocale="ru">
              <AuditPage />
            </LocaleProvider>
          </AdminProvider>
        </QueryClientProvider>
      );

      expect(await screen.findByText('Изменён баннер')).toBeInTheDocument();
      expect(screen.getByText('Создана акция')).toBeInTheDocument();
      expect(screen.getByText('Обновлены тексты приложения')).toBeInTheDocument();
      expect(screen.getByText('Тексты приложения')).toBeInTheDocument();

      // Readable Before -> After fields
      expect(screen.getByText('Старый баннер')).toBeInTheDocument();
      expect(screen.getByText('Новый баннер')).toBeInTheDocument();
      expect(screen.getByText('+77001110000')).toBeInTheDocument();
      expect(screen.getByText('+77009998877')).toBeInTheDocument();

      // Both snapshots null: explain that the values were not stored.
      expect(screen.getAllByText('Данные об изменении не сохранялись').length).toBeGreaterThanOrEqual(2);
      const text = container.textContent ?? '';
      expect(text).not.toContain('[REDACTED]');
      expect(text).not.toContain('deadbeefsecret');
      expect(text).not.toContain('promotion_id');
      expect(text).not.toContain('android_app_id');
      expect(text).not.toContain('Технические детали');
    });

    it('renders KK "Толық мәлімет жоқ" and allows superadmin sanitized technical details without secret leaks', async () => {
      setupEnvFetch('superadmin', url => {
        if (url.pathname === '/admin/audit') {
          return json(200, { items: sampleAuditRows, limit: 25, offset: 0, has_more: false });
        }
        return json(200, {});
      });

      const { container } = render(
        <QueryClientProvider client={new QueryClient()}>
          <AdminProvider>
            <LocaleProvider initialLocale="kk">
              <AuditPage />
            </LocaleProvider>
          </AdminProvider>
        </QueryClientProvider>
      );

      expect(await screen.findByText('Баннер өзгертілді')).toBeInTheDocument();
      expect(screen.getByText('Акция жасалды')).toBeInTheDocument();
      expect(screen.getAllByText('Өзгеріс туралы мәліметтер сақталмаған').length).toBeGreaterThanOrEqual(2);
      expect(screen.getAllByText('Техникалық мәлімет').length).toBeGreaterThan(0);

      // Even for superadmin, secret hashes/redacted placeholders are scrubbed
      expect(container.textContent ?? '').not.toContain('deadbeefsecret');
      expect(container.textContent ?? '').not.toContain('[REDACTED]');
      expect(screen.getAllByText('Android пакеті:').length).toBeGreaterThanOrEqual(1);
    });
  });
});

// Quick sanity check on AdminLayout import (used in P4-P5 test above)
expect(AdminLayout).toBeDefined();
