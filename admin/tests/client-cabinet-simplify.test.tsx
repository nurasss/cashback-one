import { cleanup, render, screen, within, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, createMemoryRouter, RouterProvider } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { LocaleProvider, LanguageSwitcher } from '../src/i18n/LocaleContext';
import { Navigation, adminNavigation, isNavActive } from '../src/features/Navigation';
import { DashboardPage } from '../src/pages/DashboardPage';
import { ContentPage } from '../src/pages/ContentPage';
import { NotificationsPage } from '../src/pages/NotificationsPage';
import { SettingsPage } from '../src/pages/SettingsPage';

const businessId = 'fixture-biz-id';

const mockDashboardData = {
  customers_with_business_cards: 42,
  cards: 1707,
  unblocked_cards: 1700,
  transactions: 8068,
  period_days: 30,
  period_from: '2026-10-10T00:00:00Z',
  period_to: '2026-11-09T00:00:00Z',
  agents: { online: 1, stale: 0, never_connected: 0, error: 0, disabled: 0 },
};

let currentRole: 'superadmin' | 'business_manager' = 'business_manager';

vi.mock('../src/auth/provider', () => ({
  useAdminSession: () => ({
    session: {
      api: {
        request: vi.fn(async () => ({})),
      },
    },
    view: {
      status: 'authenticated',
      admin: {
        id: 'admin-1',
        login: 'manager@keremet.kz',
        role: currentRole,
        business: currentRole === 'business_manager' ? { id: businessId, name: 'КеремЕт' } : null,
      },
    },
  }),
  AdminProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock('../src/api/queries', () => ({
  privateKey: ['admin'],
  useBusinesses: () => ({
    data: { items: [{ id: businessId, name: 'КеремЕт' }], limit: 100, offset: 0, has_more: false },
  }),
  useAllBusinesses: (enabled = true) => {
    const items = enabled ? [{ id: businessId, name: 'КеремЕт' }] : [];
    return {
      items,
      isPending: false,
      isLoadingMore: false,
      hasMore: false,
      isError: false,
      error: null,
      loadedCount: items.length,
      retry: vi.fn(),
    };
  },
  useDashboard: () => ({
    isPending: false,
    isError: false,
    data: mockDashboardData,
    refetch: vi.fn(),
  }),
  usePromotions: () => ({
    isPending: false,
    isError: false,
    data: { items: [], limit: 25, offset: 0, has_more: false },
    refetch: vi.fn(),
  }),
  useAppNotifications: () => ({
    isPending: false,
    isError: false,
    data: {
      items: [
        {
          id: 'note-1',
          business_id: businessId,
          title: 'Скидка на чай',
          body: 'Только сегодня скидка 20%',
          scheduled_at: null,
          created_at: '2026-11-09T08:00:00Z',
        },
      ],
      limit: 25,
      offset: 0,
      has_more: false,
    },
    refetch: vi.fn(),
  }),
  useBusinessStores: () => ({
    isPending: false,
    isError: false,
    data: [
      {
        id: 'store-1',
        business_id: businessId,
        title_ru: 'Керемет на Сыганак',
        title_kk: 'Сығанақтағы Керемет',
        address_ru: 'ул. Сыганак, 1',
        address_kk: 'Сығанақ к-сі, 1',
        map_url: 'https://2gis.kz/astana',
        sort_order: 1,
        is_active: true,
      },
    ],
    refetch: vi.fn(),
  }),
  useBusinessAppTexts: () => ({
    isPending: false,
    isError: false,
    data: {
      home_store_note_lead: { ru: 'Потратить баллы можно тут:', kk: 'Ұпайларды мында жұмсауға болады:' },
      balance_delay_note: { ru: 'Баллы начисляются после смены', kk: 'Ұпайлар ауысымнан кейін' },
    },
    refetch: vi.fn(),
  }),
}));

afterEach(() => {
  cleanup();
});

describe('Client Cabinet Simplification (2026-11-09)', () => {
  describe('Navigation', () => {
    it('business_manager sees 4 main links and 1 secondary settings link', () => {
      currentRole = 'business_manager';
      render(
        <MemoryRouter>
          <Navigation role="business_manager" />
        </MemoryRouter>,
      );

      // Main links
      expect(screen.getByRole('link', { name: 'Главная' })).toHaveAttribute('href', '/admin');
      expect(screen.getByRole('link', { name: 'Клиенты' })).toHaveAttribute('href', '/admin/operations');
      expect(screen.getByRole('link', { name: 'Приложение' })).toHaveAttribute('href', '/admin/content');
      expect(screen.getByRole('link', { name: 'Рассылки' })).toHaveAttribute('href', '/admin/notifications');

      // Secondary link
      expect(screen.getByRole('link', { name: 'Настройки' })).toHaveAttribute('href', '/admin/settings');

      // Technical links not in main sidebar
      expect(screen.queryByRole('link', { name: 'Бизнесы' })).not.toBeInTheDocument();
      expect(screen.queryByRole('link', { name: 'Агенты' })).not.toBeInTheDocument();
      expect(screen.queryByRole('link', { name: 'Журнал событий' })).not.toBeInTheDocument();
    });

    it('business_manager sees correct Kazakh labels', () => {
      currentRole = 'business_manager';
      render(
        <MemoryRouter>
          <LocaleProvider initialLocale="kk">
            <Navigation role="business_manager" />
          </LocaleProvider>
        </MemoryRouter>,
      );

      expect(screen.getByRole('link', { name: 'Басты бет' })).toHaveAttribute('href', '/admin');
      expect(screen.getByRole('link', { name: 'Клиенттер' })).toHaveAttribute('href', '/admin/operations');
      expect(screen.getByRole('link', { name: 'Қолданба' })).toHaveAttribute('href', '/admin/content');
      expect(screen.getByRole('link', { name: 'Хабарламалар' })).toHaveAttribute('href', '/admin/notifications');
      expect(screen.getByRole('link', { name: 'Баптаулар' })).toHaveAttribute('href', '/admin/settings');
    });

    it('superadmin sees all 6 canonical sections and no client-specific entries', () => {
      currentRole = 'superadmin';
      render(
        <MemoryRouter>
          <Navigation role="superadmin" />
        </MemoryRouter>,
      );

      expect(screen.getByRole('link', { name: 'Обзор' })).toHaveAttribute('href', '/admin');
      expect(screen.getByRole('link', { name: 'Бизнесы' })).toHaveAttribute('href', '/admin/businesses');
      expect(screen.getByRole('link', { name: 'Агенты' })).toHaveAttribute('href', '/admin/agents');
      expect(screen.getByRole('link', { name: 'Карты и клиенты' })).toHaveAttribute('href', '/admin/operations');
      expect(screen.getByRole('link', { name: 'Приложение' })).toHaveAttribute('href', '/admin/content');
      expect(screen.getByRole('link', { name: 'Журнал событий' })).toHaveAttribute('href', '/admin/audit');

      expect(screen.queryByRole('link', { name: 'Рассылки' })).not.toBeInTheDocument();
      expect(screen.queryByRole('link', { name: 'Настройки' })).not.toBeInTheDocument();
    });

    it('highlights active item correctly on deep links', () => {
      const clientSettingsItem = adminNavigation.find(i => i.navKey === 'settings')!;
      const clientOperationsItem = adminNavigation.find(i => i.navKey === 'clients')!;
      const superadminAgentsItem = adminNavigation.find(i => i.navKey === 'agents')!;

      // Deep link to /admin/cards/123 highlights Клиенты
      expect(isNavActive(clientOperationsItem, '/admin/cards/123', 'business_manager')).toBe(true);
      expect(isNavActive(clientOperationsItem, '/admin/users/456', 'business_manager')).toBe(true);

      // Deep link to /admin/agents highlights Настройки for manager
      expect(isNavActive(clientSettingsItem, '/admin/agents', 'business_manager')).toBe(true);
      expect(isNavActive(clientSettingsItem, '/admin/audit', 'business_manager')).toBe(true);

      // For superadmin, /admin/agents highlights Агенты, not settings
      expect(isNavActive(superadminAgentsItem, '/admin/agents', 'superadmin')).toBe(true);
      expect(isNavActive(clientSettingsItem, '/admin/agents', 'superadmin')).toBe(false);
    });
  });

  describe('Dashboard for Client vs Superadmin', () => {
    it('client dashboard shows 3 metrics, direct actions, friendly health and notice', () => {
      currentRole = 'business_manager';
      render(
        <MemoryRouter>
          <LocaleProvider initialLocale="ru">
            <DashboardPage />
          </LocaleProvider>
        </MemoryRouter>,
      );

      // Store name
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('КеремЕт');

      // Direct actions
      expect(screen.getByRole('link', { name: 'Найти клиента' })).toHaveAttribute('href', '/admin/operations');
      expect(screen.getByRole('link', { name: 'Создать рассылку' })).toHaveAttribute('href', '/admin/notifications?create=1');

      // 3 metrics
      const metrics = screen.getByRole('region', { name: 'Показатели бизнеса' });
      const cards = within(metrics).getAllByRole('article');
      expect(cards).toHaveLength(3);
      expect(within(metrics).getByText('Карты')).toBeInTheDocument();
      expect(within(metrics).getByText('Клиенты с картами')).toBeInTheDocument();
      expect(within(metrics).getByText('Операции за период')).toBeInTheDocument();
      expect(within(metrics).queryByText('Незаблокированные карты')).not.toBeInTheDocument();

      // Friendly connection block
      expect(screen.getByText('Подключение к магазину / агенты')).toBeInTheDocument();
      expect(screen.getByText('Связь активна')).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /Подробнее/ })).toHaveAttribute('href', '/admin/agents');

      // Honest note
      expect(screen.getByText('Баланс и операции обновляются после передачи данных из магазина.')).toBeInTheDocument();
      expect(screen.queryByText(/is_blocked/)).not.toBeInTheDocument();
      expect(screen.queryByText(/Cloud Backend/)).not.toBeInTheDocument();
    });

    it('client dashboard works in Kazakh', () => {
      currentRole = 'business_manager';
      render(
        <MemoryRouter>
          <LocaleProvider initialLocale="kk">
            <DashboardPage />
          </LocaleProvider>
        </MemoryRouter>,
      );

      expect(screen.getByRole('link', { name: 'Клиентті табу' })).toHaveAttribute('href', '/admin/operations');
      expect(screen.getByRole('link', { name: 'Хабарлама жасау' })).toHaveAttribute('href', '/admin/notifications?create=1');
      expect(screen.getByText('Картасы бар клиенттер')).toBeInTheDocument();
      expect(screen.getByText('Кезеңдегі операциялар')).toBeInTheDocument();
      expect(screen.getByText('Дүкенге қосылу / агенттер')).toBeInTheDocument();
      expect(screen.getByText('Байланыс белсенді')).toBeInTheDocument();
      expect(screen.getByText('Баланс пен операциялар дүкеннен деректер жіберілгеннен кейін жаңартылады.')).toBeInTheDocument();
    });

    it('superadmin dashboard retains 4 metrics and original sync labels', () => {
      currentRole = 'superadmin';
      render(
        <MemoryRouter>
          <LocaleProvider initialLocale="ru">
            <DashboardPage />
          </LocaleProvider>
        </MemoryRouter>,
      );

      const metrics = screen.getByRole('region', { name: 'Показатели бизнеса' });
      expect(within(metrics).getAllByRole('article')).toHaveLength(4);
      expect(within(metrics).getByText('Незаблокированные карты')).toBeInTheDocument();
      expect(screen.getByText('Состояние агентов')).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /К списку агентов/ })).toHaveAttribute('href', '/admin/agents');
      expect(screen.getByText(/read-only зеркало данных из Cloud Backend/)).toBeInTheDocument();
    });
  });

  describe('Content and Notifications pages', () => {
    it('ContentPage shows 3 client tabs without notifications for manager', async () => {
      currentRole = 'business_manager';
      const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <LocaleProvider initialLocale="ru">
              <ContentPage />
            </LocaleProvider>
          </MemoryRouter>
        </QueryClientProvider>,
      );

      expect(screen.getByRole('tab', { name: 'Баннеры' })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: 'Акции' })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: 'Магазины' })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: 'Тексты' })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: 'Заставка' })).toBeInTheDocument();
      expect(screen.queryByRole('tab', { name: 'Уведомления' })).not.toBeInTheDocument();

      // Heading action on default banners tab
      expect(screen.getByRole('button', { name: 'Добавить баннер' })).toBeInTheDocument();
    });

    it('NotificationsPage shows notifications table and create button', async () => {
      currentRole = 'business_manager';
      const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <LocaleProvider initialLocale="ru">
              <NotificationsPage />
            </LocaleProvider>
          </MemoryRouter>
        </QueryClientProvider>,
      );

      expect(screen.getByRole('heading', { level: 1, name: 'Рассылки' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Создать рассылку' })).toBeInTheDocument();
      expect(await screen.findByText('Скидка на чай')).toBeInTheDocument();
      expect(screen.getByText('Только сегодня скидка 20%')).toBeInTheDocument();
    });

    it('NotificationsPage syncs create dialog with router history (back, forward, open button, cancel)', async () => {
      currentRole = 'business_manager';
      const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      const router = createMemoryRouter(
        [
          {
            path: '/admin/notifications',
            element: (
              <QueryClientProvider client={queryClient}>
                <LocaleProvider initialLocale="ru">
                  <NotificationsPage />
                </LocaleProvider>
              </QueryClientProvider>
            ),
          },
        ],
        {
          initialEntries: ['/admin/notifications'],
          initialIndex: 0,
        },
      );

      render(<RouterProvider router={router} />);

      // Initially closed
      expect(screen.queryByRole('heading', { level: 2, name: 'Отправить уведомление' })).not.toBeInTheDocument();

      // Click "Создать рассылку" button -> dialog opens, URL gets ?create=1
      fireEvent.click(screen.getByRole('button', { name: 'Создать рассылку' }));
      expect(await screen.findByRole('heading', { level: 2, name: 'Отправить уведомление' })).toBeInTheDocument();
      expect(router.state.location.search).toBe('?create=1');

      // Click browser Back -> dialog closes, URL has no create param
      await router.navigate(-1);
      await waitFor(() => {
        expect(screen.queryByRole('heading', { level: 2, name: 'Отправить уведомление' })).not.toBeInTheDocument();
      });
      expect(router.state.location.search).toBe('');

      // Click browser Forward -> dialog opens again
      await router.navigate(1);
      expect(await screen.findByRole('heading', { level: 2, name: 'Отправить уведомление' })).toBeInTheDocument();
      expect(router.state.location.search).toBe('?create=1');

      // Click "Отмена" -> dialog closes, URL param create removed
      fireEvent.click(screen.getByRole('button', { name: 'Отмена' }));
      await waitFor(() => {
        expect(screen.queryByRole('heading', { level: 2, name: 'Отправить уведомление' })).not.toBeInTheDocument();
      });
      expect(router.state.location.search).toBe('');
    });

    it('NotificationsPage mounts with dialog open when initial URL has create=1', async () => {
      currentRole = 'business_manager';
      const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      const router = createMemoryRouter(
        [
          {
            path: '/admin/notifications',
            element: (
              <QueryClientProvider client={queryClient}>
                <LocaleProvider initialLocale="ru">
                  <NotificationsPage />
                </LocaleProvider>
              </QueryClientProvider>
            ),
          },
        ],
        {
          initialEntries: ['/admin/notifications?create=1'],
          initialIndex: 0,
        },
      );

      render(<RouterProvider router={router} />);
      expect(await screen.findByRole('heading', { level: 2, name: 'Отправить уведомление' })).toBeInTheDocument();
    });

    it('NotificationsPage preserves form inputs across language switch', async () => {
      currentRole = 'business_manager';
      const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={['/admin/notifications?create=1']}>
            <LocaleProvider initialLocale="ru">
              <LanguageSwitcher />
              <NotificationsPage />
            </LocaleProvider>
          </MemoryRouter>
        </QueryClientProvider>,
      );

      const titleInput = await screen.findByLabelText(/Заголовок/i);
      const bodyInput = screen.getByLabelText(/^Текст$/i);

      fireEvent.change(titleInput, { target: { value: 'Праздничные скидки' } });
      fireEvent.change(bodyInput, { target: { value: 'Скидки до 50% на все товары' } });

      expect(titleInput).toHaveValue('Праздничные скидки');
      expect(bodyInput).toHaveValue('Скидки до 50% на все товары');

      // Switch language to Kazakh
      const kkBtn = screen.getByRole('button', { name: 'ҚАЗ' });
      fireEvent.click(kkBtn);

      // Dialog is still open and inputs retain values
      expect(screen.getByRole('heading', { level: 2, name: 'Хабарлама жіберу' })).toBeInTheDocument();
      expect(screen.getByLabelText(/Тақырып/i)).toHaveValue('Праздничные скидки');
      expect(screen.getByLabelText(/^Мәтін$/i)).toHaveValue('Скидки до 50% на все товары');
    });

    it('SettingsPage renders links to agents and audit', () => {
      render(
        <MemoryRouter>
          <LocaleProvider initialLocale="ru">
            <SettingsPage />
          </LocaleProvider>
        </MemoryRouter>,
      );

      expect(screen.getByRole('heading', { level: 1, name: 'Настройки' })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /К подключению/ })).toHaveAttribute('href', '/admin/agents');
      expect(screen.getByRole('link', { name: /К журналу/ })).toHaveAttribute('href', '/admin/audit');
    });

    it('SettingsPage works in Kazakh', () => {
      render(
        <MemoryRouter>
          <LocaleProvider initialLocale="kk">
            <SettingsPage />
          </LocaleProvider>
        </MemoryRouter>,
      );

      expect(screen.getByRole('heading', { level: 1, name: 'Баптаулар' })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /Қосылуға өту/ })).toHaveAttribute('href', '/admin/agents');
      expect(screen.getByRole('link', { name: /Журналға өту/ })).toHaveAttribute('href', '/admin/audit');
    });
  });
});
