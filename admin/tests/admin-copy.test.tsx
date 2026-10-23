import { cleanup, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { LocaleProvider } from '../src/i18n/LocaleContext';
import { getAdminTranslations } from '../src/i18n/admin';
import { DashboardPage } from '../src/pages/DashboardPage';

vi.mock('../src/auth/provider', () => ({
  useAdminSession: () => ({
    view: {
      status: 'authenticated',
      admin: { role: 'business_manager', business: { name: 'Fixture Market' } },
    },
  }),
}));

vi.mock('../src/api/queries', () => ({
  useBusinesses: () => ({ data: { items: [] } }),
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
});
