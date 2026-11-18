import { cleanup, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { LocaleProvider } from '../src/i18n/LocaleContext';
import { getAdminTranslations } from '../src/i18n/admin';
import { DashboardPage } from '../src/pages/DashboardPage';

let currentAdminRole: 'superadmin' | 'business_manager' = 'superadmin';

vi.mock('../src/auth/provider', () => ({
  useAdminSession: () => ({
    view: {
      status: 'authenticated',
      admin: {
        role: currentAdminRole,
        business: currentAdminRole === 'business_manager' ? { name: 'Fixture Market' } : null,
      },
    },
  }),
}));

vi.mock('../src/api/queries', () => ({
  useBusinesses: () => ({ data: { items: [] } }),
  useAllBusinesses: (enabled = true) => ({
    items: enabled ? [] : [],
    isPending: false,
    isLoadingMore: false,
    hasMore: false,
    isError: false,
    error: null,
    loadedCount: 0,
    retry: vi.fn(),
  }),
  useDashboard: () => ({
    isPending: false,
    isError: false,
    data: {
      customers_with_business_cards: 1,
      cards: 1704,
      unblocked_cards: 1704,
      transactions: 12,
      period_days: 30,
      period_from: '2026-09-22T00:00:00Z',
      period_to: '2026-10-22T00:00:00Z',
      agents: { online: 0, stale: 0, never_connected: 0, error: 0, disabled: 0 },
    },
  }),
}));

afterEach(() => {
  cleanup();
  document.documentElement.lang = 'ru';
});

describe('Approved admin copy', () => {
  it('uses the requested Russian sorting label and matching validation terminology', () => {
    const t = getAdminTranslations('ru');
    expect(t.content.promoFieldSort).toBe('Сортировка (чем меньше число, тем выше отображается)');
    expect(t.content.promoErrSort).toBe('Сортировка — целое число от -1000 до 1000.');
  });

  it('keeps the Kazakh sorting label and validation consistent', () => {
    const t = getAdminTranslations('kk');
    expect(t.content.promoFieldSort).toBe('Сұрыптау (сан неғұрлым аз болса, соғұрлым жоғары көрсетіледі)');
    expect(t.content.promoErrSort).toBe('Сұрыптау — -1000-нан 1000-ға дейінгі бүтін сан.');
  });

  it.each(['ru', 'kk'] as const)('removes the loyalty caption from all four metric cards in %s', locale => {
    currentAdminRole = 'superadmin';
    const t = getAdminTranslations(locale);
    render(
      <MemoryRouter>
        <LocaleProvider initialLocale={locale}>
          <DashboardPage />
        </LocaleProvider>
      </MemoryRouter>,
    );
    const metrics = screen.getByRole('region', { name: t.dashboard.metricsAria });
    expect(within(metrics).getAllByRole('article')).toHaveLength(4);
    expect(metrics.querySelector('.metric-caption')).toBeNull();
    expect(within(metrics).queryByText(/^(ЛОЯЛЬНОСТЬ|АДАЛДЫҚ)$/)).not.toBeInTheDocument();
    expect(within(metrics).getByText(t.dashboard.cardsTitle)).toBeInTheDocument();
    expect(metrics.querySelectorAll('.metric-value')[0]).toHaveTextContent('1');
    expect(metrics.querySelectorAll('.metric-value')[3]).toHaveTextContent('12');
  });

  it('renders three metric cards for business_manager without unblocked cards', () => {
    currentAdminRole = 'business_manager';
    render(
      <MemoryRouter>
        <LocaleProvider initialLocale="ru">
          <DashboardPage />
        </LocaleProvider>
      </MemoryRouter>,
    );
    const metrics = screen.getByRole('region', { name: 'Показатели бизнеса' });
    expect(within(metrics).getAllByRole('article')).toHaveLength(3);
    expect(within(metrics).queryByText('Незаблокированные карты')).not.toBeInTheDocument();
    expect(within(metrics).getByText('Карты')).toBeInTheDocument();
    expect(within(metrics).getByText('Клиенты с картами')).toBeInTheDocument();
    expect(within(metrics).getByText('Операции за период')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Найти клиента' })).toHaveAttribute('href', '/admin/operations');
    expect(screen.getByRole('link', { name: 'Создать рассылку' })).toHaveAttribute('href', '/admin/notifications?create=1');
    expect(screen.getByText('Баланс и операции обновляются после передачи данных из магазина.')).toBeInTheDocument();
    expect(screen.getByText('Подключение к магазину / агенты')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Подробнее/ })).toHaveAttribute('href', '/admin/agents');
  });
});
