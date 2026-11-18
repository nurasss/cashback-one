import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { BusinessDetail, Card, LoyaltyTier } from '../src/api/types';
import { AdminProvider } from '../src/auth/provider';
import { LocaleProvider } from '../src/i18n/LocaleContext';
import { StatusesPage, TierDialog } from '../src/pages/StatusesPage';
import { OperationsPage } from '../src/pages/OperationsPage';
import { PromotionDialog } from '../src/pages/ContentPage';
import { Pagination } from '../src/components/Feedback';

const access = { access_token: 'fixture-access', token_type: 'bearer', expires_in: 900 };
const businessId = 'fixture-biz-inna';

const sampleTier: LoyaltyTier = {
  id: 'tier-1',
  business_id: businessId,
  level: 1,
  priority: 10,
  name_ru: 'Базовый',
  name_kk: 'Базалық',
  description_ru: 'Стартовый уровень',
  description_kk: 'Бастапқы деңгей',
  image_url: null,
  turnover_period_months: 6,
  min_turnover: '0.00',
  max_turnover: '50000.00',
  percent: '2.50',
  is_active: true,
  created_at: '2026-11-01T00:00:00Z',
  updated_at: '2026-11-01T00:00:00Z',
};

const sampleBusiness: BusinessDetail = {
  id: businessId,
  name: 'Inna Market',
  logo_url: null,
  colors: null,
  barcode_prefixes: [],
  status: 'active',
  created_at: '2026-10-01T00:00:00Z',
  updated_at: '2026-10-01T00:00:00Z',
  cards_count: 5,
  unblocked_cards_count: 5,
  customers_with_cards_count: 5,
  agents_count: 1,
};

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

function setupAdminSession(role: 'superadmin' | 'business_manager' = 'superadmin', busId = businessId) {
  return {
    admin: {
      id: 'admin-1',
      login: 'manager',
      role,
      business: role === 'business_manager' ? { id: busId, name: 'Inna Market', status: 'active' } : null,
    },
    admin_max_stats_period_days: 90,
  };
}

beforeEach(() => {
  vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
  vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');
  localStorage.clear();
  sessionStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('Inna Admin Revisions 2026-11-12', () => {
  describe('1. Lifetime Turnover (No turnover_period_months in table or form)', () => {
    it('does not render turnover period column in Statuses table and ignores legacy period in API response', async () => {
      const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/admin/auth/refresh')) return json(200, access);
        if (url.endsWith('/admin/me')) return json(200, setupAdminSession('business_manager'));
        if (url.includes(`/admin/businesses/${businessId}/loyalty-tiers`)) {
          return json(200, [sampleTier]);
        }
        if (url.includes('/admin/businesses')) {
          return json(200, { items: [sampleBusiness], limit: 100, offset: 0, has_more: false });
        }
        return json(404, { detail: 'Not found' });
      });
      vi.stubGlobal('fetch', fetchMock);

      render(
        <AdminProvider>
          <LocaleProvider initialLocale="ru">
            <MemoryRouter>
              <StatusesPage />
            </MemoryRouter>
          </LocaleProvider>
        </AdminProvider>
      );

      await waitFor(() => {
        expect(screen.getByRole('columnheader', { name: /кэшбэк, %/i })).toBeInTheDocument();
      });

      // Turnover period column header is absent
      expect(screen.queryByRole('columnheader', { name: /период оборота/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('columnheader', { name: /айналым кезеңі/i })).not.toBeInTheDocument();
      // Period value like '6 мес.' is absent
      expect(screen.queryByText(/6 мес\./i)).not.toBeInTheDocument();
    });

    it('edits tier without turnover_period_months and persists changes omitting turnover_period_months', async () => {
      const user = userEvent.setup();
      let patchPayload: unknown = null;

      const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? 'GET';
        if (url.endsWith('/admin/auth/refresh')) return json(200, access);
        if (url.endsWith('/admin/me')) return json(200, setupAdminSession());
        if (url.includes(`/loyalty-tiers/${sampleTier.id}`) && method === 'PATCH') {
          patchPayload = JSON.parse(String(init?.body));
          return json(200, { ...sampleTier, percent: '3.00' });
        }
        return json(404, { detail: 'Not found' });
      });
      vi.stubGlobal('fetch', fetchMock);

      const onSaved = vi.fn();
      const onClose = vi.fn();

      render(
        <AdminProvider>
          <LocaleProvider initialLocale="ru">
            <TierDialog businessId={businessId} tier={sampleTier} onClose={onClose} onSaved={onSaved} />
          </LocaleProvider>
        </AdminProvider>
      );

      // Turnover period field is absent from form
      expect(screen.queryByLabelText(/период оборота/i)).not.toBeInTheDocument();
      expect(document.getElementById('tier-period')).toBeNull();

      // Percent field is updated
      const percentInput = screen.getByLabelText(/процент начисления бонусов/i) as HTMLInputElement;
      await user.clear(percentInput);
      await user.type(percentInput, '3.0');

      const submitBtn = screen.getByRole('button', { name: /сохранить/i });
      await user.click(submitBtn);

      await waitFor(() => {
        expect(onSaved).toHaveBeenCalledTimes(1);
      });

      expect(patchPayload).toMatchObject({
        level: 1,
        percent: 3.0,
      });
      expect((patchPayload as Record<string, unknown>).turnover_period_months).toBeUndefined();
    });

    it('creates a new tier without turnover_period_months in payload', async () => {
      const user = userEvent.setup();
      let postPayload: unknown = null;

      const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? 'GET';
        if (url.endsWith('/admin/auth/refresh')) return json(200, access);
        if (url.endsWith('/admin/me')) return json(200, setupAdminSession());
        if (url.includes('/loyalty-tiers') && method === 'POST') {
          postPayload = JSON.parse(String(init?.body));
          return json(201, { id: 'tier-created', ...postPayload });
        }
        return json(404, { detail: 'Not found' });
      });
      vi.stubGlobal('fetch', fetchMock);

      const onSaved = vi.fn();
      const onClose = vi.fn();

      render(
        <AdminProvider>
          <LocaleProvider initialLocale="ru">
            <TierDialog businessId={businessId} onClose={onClose} onSaved={onSaved} />
          </LocaleProvider>
        </AdminProvider>
      );

      await user.type(screen.getByLabelText(/название \(русский\)/i), 'Новый VIP');
      await user.type(screen.getByLabelText(/название \(қазақша\)/i), 'Жаңа VIP');

      const submitBtn = screen.getByRole('button', { name: /сохранить/i });
      await user.click(submitBtn);

      await waitFor(() => {
        expect(onSaved).toHaveBeenCalledTimes(1);
      });

      expect(postPayload).toMatchObject({
        level: 1,
        name_ru: 'Новый VIP',
        name_kk: 'Жаңа VIP',
      });
      expect((postPayload as Record<string, unknown>).turnover_period_months).toBeUndefined();
    });
  });

  describe('2. Cashback Percentage by Status (percent)', () => {
    it('displays «КЭШБЭК, %» column header and supports decimal percentages like 3.75%', async () => {
      const user = userEvent.setup();
      let patchPayload: unknown = null;

      const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? 'GET';
        if (url.endsWith('/admin/auth/refresh')) return json(200, access);
        if (url.endsWith('/admin/me')) {
          return json(200, setupAdminSession('business_manager'));
        }
        if (url.includes(`/admin/businesses/${businessId}/loyalty-tiers`)) {
          if (method === 'GET') {
            return json(200, [sampleTier]);
          }
          if (method === 'PATCH') {
            patchPayload = JSON.parse(String(init?.body));
            return json(200, { ...sampleTier, percent: '3.75' });
          }
        }
        if (url.includes('/admin/businesses')) {
          return json(200, { items: [sampleBusiness], limit: 100, offset: 0, has_more: false });
        }
        return json(404, { detail: 'Not found' });
      });
      vi.stubGlobal('fetch', fetchMock);

      render(
        <AdminProvider>
          <LocaleProvider initialLocale="ru">
            <MemoryRouter>
              <StatusesPage />
            </MemoryRouter>
          </LocaleProvider>
        </AdminProvider>
      );

      // Verify table header
      await waitFor(() => {
        expect(screen.getByRole('columnheader', { name: /кэшбэк, %/i })).toBeInTheDocument();
      });

      // Verify tier row percent
      expect(screen.getByText('2.50%')).toBeInTheDocument();

      // Open edit dialog
      const editBtn = screen.getByRole('button', { name: /изменить/i });
      await user.click(editBtn);

      const percentInput = screen.getByLabelText(/процент начисления бонусов|кэшбэк/i) as HTMLInputElement;
      expect(percentInput.value).toBe('2.50');

      await user.clear(percentInput);
      await user.type(percentInput, '3.75');

      const saveBtn = screen.getByRole('button', { name: /сохранить/i });
      await user.click(saveBtn);

      await waitFor(() => {
        expect(patchPayload).toMatchObject({
          percent: 3.75,
        });
      });
    });

    it('translates status column header and percent labels in Kazakh', async () => {
      const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/admin/auth/refresh')) return json(200, access);
        if (url.endsWith('/admin/me')) return json(200, setupAdminSession('business_manager'));
        if (url.includes(`/admin/businesses/${businessId}/loyalty-tiers`)) {
          return json(200, [sampleTier]);
        }
        if (url.includes('/admin/businesses')) {
          return json(200, { items: [sampleBusiness], limit: 100, offset: 0, has_more: false });
        }
        return json(404, { detail: 'Not found' });
      });
      vi.stubGlobal('fetch', fetchMock);

      render(
        <AdminProvider>
          <LocaleProvider initialLocale="kk">
            <MemoryRouter>
              <StatusesPage />
            </MemoryRouter>
          </LocaleProvider>
        </AdminProvider>
      );

      await waitFor(() => {
        expect(screen.getByRole('columnheader', { name: /кэшбэк, %/i })).toBeInTheDocument();
      });
    });
  });

  describe('3. Cards Pagination (total / "Страница X из N")', () => {
    it('renders "Страница 1 из 3" when total is 25 with limit 10 in RU', () => {
      const onChange = vi.fn();
      render(
        <LocaleProvider initialLocale="ru">
          <Pagination page={{ limit: 10, offset: 0, has_more: true, total: 25 }} onChange={onChange} />
        </LocaleProvider>
      );

      expect(screen.getByText('Страница 1 из 3')).toBeInTheDocument();
      const nextBtn = screen.getByRole('button', { name: /далее/i });
      expect(nextBtn).not.toBeDisabled();
      const prevBtn = screen.getByRole('button', { name: /назад/i });
      expect(prevBtn).toBeDisabled();
    });

    it('renders "1 / 3 бет" in KK and disables Next on last page', () => {
      const onChange = vi.fn();
      render(
        <LocaleProvider initialLocale="kk">
          <Pagination page={{ limit: 10, offset: 20, has_more: false, total: 25 }} onChange={onChange} />
        </LocaleProvider>
      );

      expect(screen.getByText('3 / 3 бет')).toBeInTheDocument();
      const nextBtn = screen.getByRole('button', { name: /келесі/i });
      expect(nextBtn).toBeDisabled();
      const prevBtn = screen.getByRole('button', { name: /артқа/i });
      expect(prevBtn).not.toBeDisabled();
    });

    it('does not render "1 из 0" when total is 0', () => {
      const { container } = render(
        <LocaleProvider initialLocale="ru">
          <Pagination page={{ limit: 10, offset: 0, has_more: false, total: 0 }} onChange={vi.fn()} />
        </LocaleProvider>
      );
      expect(container.firstChild).toBeNull();
      expect(screen.queryByText(/1 из 0/)).not.toBeInTheDocument();
    });

    it('falls back to "Страница X" when total is undefined', () => {
      render(
        <LocaleProvider initialLocale="ru">
          <Pagination page={{ limit: 10, offset: 10, has_more: true }} onChange={vi.fn()} />
        </LocaleProvider>
      );
      expect(screen.getByText('Страница 2')).toBeInTheDocument();
    });

    it('auto-adjusts card list page if list shrinks and offset >= total', async () => {
      const cards: Card[] = Array.from({ length: 5 }, (_, i) => ({
        id: `card-${i}`,
        business_id: businessId,
        business_name: 'Inna Market',
        barcode: `100000000000${i}`,
        phone_masked: '+7 701 ••• 11 22',
        balance: '100.0000',
        is_blocked: false,
        updated_at: '2026-11-01T00:00:00Z',
        bind_method: null,
        bound_at: null,
        hidden_at: null,
      }));

      const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/admin/auth/refresh')) return json(200, access);
        if (url.endsWith('/admin/me')) return json(200, setupAdminSession('business_manager'));
        if (url.includes('/admin/cards')) {
          return json(200, {
            items: cards,
            limit: 25,
            offset: 0,
            has_more: false,
            total: 5,
          });
        }
        if (url.includes('/admin/businesses')) {
          return json(200, { items: [sampleBusiness], limit: 100, offset: 0, has_more: false });
        }
        return json(404, { detail: 'Not found' });
      });
      vi.stubGlobal('fetch', fetchMock);

      render(
        <AdminProvider>
          <LocaleProvider initialLocale="ru">
            <MemoryRouter initialEntries={['/admin/cards']}>
              <Routes>
                <Route path="/admin/cards" element={<OperationsPage />} />
              </Routes>
            </MemoryRouter>
          </LocaleProvider>
        </AdminProvider>
      );

      await waitFor(() => {
        expect(screen.getByText('Страница 1 из 1')).toBeInTheDocument();
      });
    });
  });

  describe('4. Content Form (PromotionDialog)', () => {
    it('displays dynamic offer/banner image hints, aria-describedby, and accessible schedule checkboxes', async () => {
      const user = userEvent.setup();
      const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/admin/auth/refresh')) return json(200, access);
        if (url.endsWith('/admin/me')) return json(200, setupAdminSession());
        if (url.includes('/admin/businesses')) return json(200, { items: [sampleBusiness], limit: 100, offset: 0, has_more: false });
        return json(200, {});
      });
      vi.stubGlobal('fetch', fetchMock);

      const { container } = render(
        <AdminProvider>
          <LocaleProvider initialLocale="ru">
            <PromotionDialog onClose={vi.fn()} />
          </LocaleProvider>
        </AdminProvider>
      );

      // 1. Dynamic image hint (offer default) + aria-describedby
      const offerHint = screen.getByText(/Карточка акции: рекомендуется 800×600 px \(4:3\)/i);
      expect(offerHint).toBeInTheDocument();
      expect(offerHint).toHaveClass('image-upload-hint');
      expect(container.querySelector('#promo-image')).toHaveAttribute('aria-describedby', 'promo-image-hint');

      // Switching kind changes hint to banner
      await user.selectOptions(await screen.findByLabelText('Где показывать'), 'banner');
      expect(screen.getByText(/Баннер на главной: рекомендуется 1200×500 px \(2\.4:1\)/i)).toBeInTheDocument();

      // 2. Badge and sort order in 2-column row
      const badgeInput = container.querySelector('#promo-badge');
      const sortInput = container.querySelector('#promo-sort');
      expect(badgeInput).toBeInTheDocument();
      expect(sortInput).toBeInTheDocument();

      // Dates in 2-column row with checkboxes "Начать сейчас" and "Бессрочно"
      const startInput = container.querySelector('#promo-start');
      const endInput = container.querySelector('#promo-end');
      expect(startInput).toBeInTheDocument();
      expect(endInput).toBeInTheDocument();
      expect(screen.getByRole('checkbox', { name: /начать сейчас/i })).toBeChecked();
      expect(screen.getByRole('checkbox', { name: /бессрочно/i })).toBeChecked();

      // 3. Mutation form should not have internal overflow scroll
      const form = container.querySelector('.mutation-form');
      expect(form).toBeInTheDocument();
    });

    it('displays image dimensions/format hint in Kazakh', () => {
      const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/admin/auth/refresh')) return json(200, access);
        if (url.endsWith('/admin/me')) return json(200, setupAdminSession());
        return json(200, {});
      });
      vi.stubGlobal('fetch', fetchMock);

      render(
        <AdminProvider>
          <LocaleProvider initialLocale="kk">
            <PromotionDialog onClose={vi.fn()} />
          </LocaleProvider>
        </AdminProvider>
      );

      expect(screen.getByText(/Акция карточкасы: 800×600 px \(4:3\) ұсынылады/i)).toBeInTheDocument();
      expect(screen.getByText('Сұрыптау')).toBeInTheDocument();
    });
  });
});
