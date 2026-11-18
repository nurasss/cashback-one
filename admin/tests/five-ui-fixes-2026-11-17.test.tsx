import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AdminProvider } from '../src/auth/provider';
import { ActiveBusinessProvider } from '../src/context/ActiveBusinessContext';
import { BusinessTextsSection } from '../src/features/BusinessAppContent';
import { Navigation } from '../src/features/Navigation';
import { LocaleProvider } from '../src/i18n/LocaleContext';
import { PromotionDialog } from '../src/pages/ContentPage';
import { DashboardPage } from '../src/pages/DashboardPage';
import { CardDetailPage } from '../src/pages/OperationsPage';
import { TierDialog } from '../src/pages/StatusesPage';
import type { Promotion } from '../src/api/types';

const access = { access_token: 'fixture-access', token_type: 'bearer', expires_in: 900 };
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

const RU_PERIOD_ERROR =
  'Ошибка в указанном периоде: дата начала должна быть не позже даты окончания, а обе даты — не позже сегодняшнего дня по Астане.';
const KK_PERIOD_ERROR =
  'Көрсетілген кезеңде қате бар: басталу күні аяқталу күнінен кеш болмауы, ал екі күн де Астана уақыты бойынша бүгіннен кеш болмауы тиіс.';

afterEach(() => {
  vi.useRealTimers();
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe('Five UI fixes (2026-11-17)', () => {
  describe('Fix 1: DashboardPage period bounds, midnight rollover, and single error', () => {
    it.each(['ru', 'kk'] as const)(
      'keeps the default, rejects future dates and accepts periods before registration (%s)',
      async locale => {
        // 2026-11-17T10:00:00+05:00 -> 2026-11-17T05:00:00Z
        vi.useFakeTimers({ toFake: ['Date'] });
        vi.setSystemTime(new Date('2026-11-17T05:00:00.000Z'));

        const user = userEvent.setup();
        vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
        vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

        const dashboardQueries: string[] = [];
        vi.stubGlobal(
          'fetch',
          vi.fn(async (input: RequestInfo | URL) => {
            const url = String(input);
            if (url.endsWith('/admin/auth/refresh')) return json(200, access);
            if (url.endsWith('/admin/me')) {
              return json(200, {
                admin: {
                  id: 'mgr-1',
                  login: 'amber.mgr',
                  role: 'business_manager',
                  business: {
                    id: 'biz-new',
                    name: 'Amber Fresh',
                    status: 'active',
                    logo_url: null,
                    android_app_id: null,
                    created_at: '2026-11-15T10:00:00Z',
                  },
                },
                admin_max_stats_period_days: 90,
                admin_stats_unlimited_period: true,
              });
            }
            if (url.includes('/admin/dashboard')) {
              dashboardQueries.push(url);
              return json(200, {
                business_id: 'biz-new',
                business_name: 'Amber Fresh',
                period_from: '2026-11-15T00:00:00+05:00',
                period_to: '2026-11-17T23:59:59+05:00',
                period_days: 3,
                customers_with_business_cards: 5,
                cards: 12,
                unblocked_cards: 12,
                transactions: 24,
                agents: { online: 1, stale: 0, never_connected: 0, error: 0, disabled: 0 },
              });
            }
            return json(404, { error: { code: 'NOT_FOUND' } });
          }),
        );

        render(
          <LocaleProvider initialLocale={locale}>
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

        const fromLabel = locale === 'ru' ? 'С' : 'Бастап';
        const toLabel = locale === 'ru' ? 'По' : 'Дейін';
        const refreshLabel = locale === 'ru' ? 'Обновить' : 'Жаңарту';
        const expectedErr = locale === 'ru' ? RU_PERIOD_ERROR : KK_PERIOD_ERROR;

        const fromInput = (await screen.findByLabelText(fromLabel)) as HTMLInputElement;
        const toInput = screen.getByLabelText(toLabel) as HTMLInputElement;
        const refreshBtn = screen.getByRole('button', { name: refreshLabel });

        // Initial default range automatically clamped to registration day (2026-11-15..2026-11-17)
        await waitFor(() => expect(dashboardQueries).toHaveLength(1));
        expect(fromInput.value).toBe('2026-11-15');
        expect(toInput.value).toBe('2026-11-17');
        expect(fromInput.min).toBe('1000-01-01');
        expect(toInput.max).toBe('2026-11-17');

        // Future year 2098 -> single error inside filter panel, invalid input highlighted, no Back button, Refresh remains active but blocks query
        fireEvent.change(toInput, { target: { value: '2098-01-01' } });
        expect(screen.getAllByText(expectedErr)).toHaveLength(1);
        expect(screen.getByRole('alert')).toHaveTextContent(expectedErr);
        expect(toInput).toHaveAttribute('aria-invalid', 'true');
        expect(toInput).toHaveAttribute('aria-describedby', 'dashboard-period-error');
        expect(screen.queryByRole('button', { name: locale === 'ru' ? 'Назад' : 'Артқа' })).not.toBeInTheDocument();
        expect(refreshBtn).not.toBeDisabled();
        await user.click(refreshBtn);
        expect(dashboardQueries).toHaveLength(1);

        // Tomorrow's "from" date (2026-11-18) -> blocked with bounds message, Refresh active but blocks query
        fireEvent.change(toInput, { target: { value: '2026-11-17' } });
        fireEvent.change(fromInput, { target: { value: '2026-11-18' } });
        expect(screen.getAllByText(expectedErr)).toHaveLength(1);
        expect(fromInput).toHaveAttribute('aria-invalid', 'true');
        expect(screen.queryByRole('button', { name: locale === 'ru' ? 'Назад' : 'Артқа' })).not.toBeInTheDocument();
        expect(refreshBtn).not.toBeDisabled();
        await user.click(refreshBtn);
        expect(dashboardQueries).toHaveLength(1);

        // A single day entirely before registration is valid.
        fireEvent.change(fromInput, { target: { value: '1970-01-01' } });
        fireEvent.change(toInput, { target: { value: '1970-01-01' } });
        expect(screen.queryByRole('alert')).not.toBeInTheDocument();
        expect(toInput.min).toBe('1970-01-01');
        await user.click(refreshBtn);
        await waitFor(() => expect(dashboardQueries).toHaveLength(2));
        expect(new URL(dashboardQueries[1]).searchParams.get('from')).toBe('1969-12-31T19:00:00.000Z');
        expect(new URL(dashboardQueries[1]).searchParams.get('to')).toBe('1970-01-01T18:59:59.999Z');

        fireEvent.change(fromInput, { target: { value: '2026-01-01' } });
        fireEvent.change(toInput, { target: { value: '2026-11-17' } });
        expect(screen.queryByRole('alert')).not.toBeInTheDocument();
        await user.click(refreshBtn);
        await waitFor(() => expect(dashboardQueries).toHaveLength(3));
        expect(dashboardQueries[2]).toContain('from=2025-12-31T19%3A00%3A00.000Z');

        // "from" > "to" -> blocked with periodInvalid
        fireEvent.change(fromInput, { target: { value: '2026-11-17' } });
        fireEvent.change(toInput, { target: { value: '2026-11-16' } });
        expect(screen.getByRole('alert')).toBeInTheDocument();
        await user.click(refreshBtn);
        expect(dashboardQueries).toHaveLength(3);

        // Both inclusive boundaries + internal single-day range succeed
        fireEvent.change(fromInput, { target: { value: '2026-11-15' } });
        fireEvent.change(toInput, { target: { value: '2026-11-17' } });
        expect(screen.queryByRole('alert')).not.toBeInTheDocument();
        expect(refreshBtn).not.toBeDisabled();
        await user.click(refreshBtn);
        await waitFor(() => expect(dashboardQueries).toHaveLength(4));

        fireEvent.change(fromInput, { target: { value: '2026-11-16' } });
        fireEvent.change(toInput, { target: { value: '2026-11-16' } });
        await user.click(refreshBtn);
        await waitFor(() => expect(dashboardQueries).toHaveLength(5));
      },
    );

    it('handles superadmin All businesses, business switch clamping, midnight UTC+5 rollover, and server 422 without duplicate notices', async () => {
      // 2026-11-17 23:55 UTC+5 = 2026-11-17T18:55:00Z
      vi.useFakeTimers({ toFake: ['Date'] });
      vi.setSystemTime(new Date('2026-11-17T18:55:00.000Z'));

      const user = userEvent.setup();
      vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
      vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

      const dashboardQueries: string[] = [];
      let returnServer422 = false;

      vi.stubGlobal(
        'fetch',
        vi.fn(async (input: RequestInfo | URL) => {
          const url = String(input);
          if (url.endsWith('/admin/auth/refresh')) return json(200, access);
          if (url.endsWith('/admin/me')) {
            return json(200, {
              admin: { id: 'super-1', login: 'super', role: 'superadmin', business: null },
              admin_max_stats_period_days: 90,
              admin_stats_unlimited_period: true,
            });
          }
          if (url.includes('/admin/businesses?')) {
            return json(200, {
              items: [
                {
                  id: 'biz-old',
                  name: 'Old Co',
                  status: 'active',
                  logo_url: null,
                  android_app_id: null,
                  barcode_prefixes: ['20'],
                  created_at: '2022-05-10T03:00:00Z',
                },
                {
                  id: 'biz-new',
                  name: 'New Co',
                  status: 'active',
                  logo_url: null,
                  android_app_id: null,
                  barcode_prefixes: ['21'],
                  created_at: '2026-11-15T10:00:00Z',
                },
              ],
              limit: 25,
              offset: 0,
              has_more: false,
            });
          }
          if (url.includes('/admin/dashboard')) {
            dashboardQueries.push(url);
            if (returnServer422) {
              return json(422, {
                error: {
                  code: 'ADMIN_INVALID_PERIOD',
                  message: 'Invalid period bounds',
                  reason: 'period_out_of_bounds',
                  period_min: '2026-11-15',
                  period_max: '2026-11-17',
                },
              });
            }
            return json(200, {
              business_id: null,
              business_name: null,
              period_from: '2026-10-19T00:00:00+05:00',
              period_to: '2026-11-17T23:59:59+05:00',
              period_days: 30,
              customers_with_business_cards: 100,
              cards: 200,
              unblocked_cards: 190,
              transactions: 500,
              agents: { online: 2, stale: 0, never_connected: 0, error: 0, disabled: 0 },
            });
          }
          return json(404, { error: { code: 'NOT_FOUND' } });
        }),
      );

      render(
        <LocaleProvider initialLocale="ru">
          <AdminProvider>
            <ActiveBusinessProvider>
              <MemoryRouter initialEntries={['/admin']}>
                <Navigation role="superadmin" />
                <Routes>
                  <Route path="/admin" element={<DashboardPage />} />
                </Routes>
              </MemoryRouter>
            </ActiveBusinessProvider>
          </AdminProvider>
        </LocaleProvider>,
      );

      await screen.findByRole('heading', { name: 'Все бизнесы' });
      const fromInput = screen.getByLabelText('С') as HTMLInputElement;
      const toInput = screen.getByLabelText('По') as HTMLInputElement;
      const bizSelect = screen.getByLabelText('Бизнес') as HTMLSelectElement;
      const refreshBtn = screen.getByRole('button', { name: 'Обновить' });

      await waitFor(() => expect(screen.getByRole('option', { name: 'New Co' })).toBeInTheDocument());

      // Switching untouched default to New Co clamps from to 2026-11-15
      await user.selectOptions(bizSelect, 'biz-new');
      expect(fromInput.value).toBe('2026-11-15');
      expect(toInput.value).toBe('2026-11-17');

      // Explicit long historical range for All businesses succeeds without duration/lower cap
      await user.selectOptions(bizSelect, '');
      fireEvent.change(fromInput, { target: { value: '2020-01-01' } });
      fireEvent.change(toInput, { target: { value: '2026-11-17' } });
      expect(refreshBtn).not.toBeDisabled();
      await user.click(refreshBtn);
      await waitFor(() => expect(dashboardQueries).toHaveLength(2));

      // Switching to New Co after explicit user input keeps explicit early from (2020-01-01) and allows Refresh
      await user.selectOptions(bizSelect, 'biz-new');
      expect(fromInput.value).toBe('2020-01-01');
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
      expect(refreshBtn).not.toBeDisabled();
      await user.click(refreshBtn);
      await waitFor(() => expect(dashboardQueries).toHaveLength(3));

      // Tomorrow's "from" date (2026-11-18) shows error, no Back button, blocks query
      fireEvent.change(fromInput, { target: { value: '2026-11-18' } });
      expect(screen.getAllByText(RU_PERIOD_ERROR)).toHaveLength(1);
      expect(screen.queryByRole('button', { name: 'Назад' })).not.toBeInTheDocument();
      expect(refreshBtn).not.toBeDisabled();
      await user.click(refreshBtn);
      expect(dashboardQueries).toHaveLength(3); // query blocked on future date

      // User fixes invalid date to 2026-11-15 -> error clears and Refresh updates dashboard
      fireEvent.change(fromInput, { target: { value: '2026-11-15' } });
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
      expect(refreshBtn).not.toBeDisabled();
      await user.click(refreshBtn);
      await waitFor(() => expect(dashboardQueries).toHaveLength(4));

      // Cross UTC+5 midnight to 2026-11-18 00:05 UTC+5 (2026-11-17T19:05:00Z)
      vi.setSystemTime(new Date('2026-11-17T19:05:00.000Z'));
      fireEvent.focus(toInput);
      fireEvent.change(toInput, { target: { value: '2026-11-18' } });
      expect(screen.queryByText(RU_PERIOD_ERROR)).not.toBeInTheDocument();
      expect(refreshBtn).not.toBeDisabled();

      // Server 422 ADMIN_INVALID_PERIOD renders ONLY ONCE inside .dashboard-period-hint-row (no duplicate ErrorNotice)
      returnServer422 = true;
      await user.click(refreshBtn);
      await waitFor(() => expect(screen.getAllByText(RU_PERIOD_ERROR)).toHaveLength(1));
      expect(document.querySelector('.dashboard-period-error')).not.toBeInTheDocument();
      expect(document.querySelector('.dashboard-period-hint-row')).toHaveTextContent(RU_PERIOD_ERROR);
      expect(screen.getByLabelText('С')).toBeInTheDocument();
    });
  });

  describe('Fix 2: StatusesPage TierDialog single error alert + field highlights', () => {
    it.each(['ru', 'kk'] as const)(
      'renders one alert directly under the active erroneous field without a top duplicate for turnover_overlap, level_exists, and multi-field errors (%s)',
      async locale => {
        const user = userEvent.setup();
        vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
        vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

        let serverMode: 'overlap' | 'level_exists' | 'multi_field' | 'ok' = 'overlap';
        vi.stubGlobal(
          'fetch',
          vi.fn(async (input: RequestInfo | URL) => {
            const url = String(input);
            if (url.endsWith('/admin/auth/refresh')) return json(200, access);
            if (url.endsWith('/admin/me')) {
              return json(200, {
                admin: { id: 'adm-1', login: 'mgr', role: 'business_manager', business: { id: 'b1', name: 'M', status: 'active', logo_url: null } },
                admin_max_stats_period_days: 90,
              });
            }
            if (url.includes('/loyalty-tiers')) {
              if (serverMode === 'overlap') {
                return json(409, {
                  error: {
                    code: 'CONFLICT',
                    message: 'Turnover range overlaps with tier [100000.00; ∞)',
                    reason: 'LOYALTY_TIER_RANGE_OVERLAP',
                  },
                });
              }
              if (serverMode === 'level_exists') {
                return json(409, {
                  error: {
                    code: 'CONFLICT',
                    message: 'Tier with level 1 already exists',
                  },
                });
              }
              if (serverMode === 'multi_field') {
                return json(422, {
                  error: {
                    code: 'VALIDATION_ERROR',
                    message: 'Invalid tier bounds',
                    fields: ['min_turnover', 'percent'],
                  },
                });
              }
              return json(201, {
                id: 't-new',
                business_id: 'b1',
                level: 2,
                name_ru: 'Серебро',
                name_kk: 'Күміс',
                description_ru: null,
                description_kk: null,
                min_turnover: '100000.00',
                max_turnover: '199999.99',
                percent: '5.00',
                image_url: null,
                is_active: true,
                created_at: '2026-11-17T00:00:00Z',
                updated_at: '2026-11-17T00:00:00Z',
              });
            }
            return json(404, { error: { code: 'NOT_FOUND' } });
          }),
        );

        const onSaved = vi.fn();
        const onClose = vi.fn();
        render(
          <LocaleProvider initialLocale={locale}>
            <AdminProvider>
              <TierDialog businessId="b1" onClose={onClose} onSaved={onSaved} />
            </AdminProvider>
          </LocaleProvider>,
        );

        const saveBtn = screen.getByRole('button', { name: locale === 'ru' ? 'Сохранить' : 'Сақтау' });
        const levelInput = document.getElementById('tier-level') as HTMLInputElement;
        const percentInput = document.getElementById('tier-percent') as HTMLInputElement;
        const minInput = document.getElementById('tier-min') as HTMLInputElement;
        const maxInput = document.getElementById('tier-max') as HTMLInputElement;
        const titleKkInput = document.getElementById('tier-title-kk') as HTMLInputElement;
        const titleRuInput = document.getElementById('tier-title-ru') as HTMLInputElement;

        fireEvent.change(titleKkInput, { target: { value: 'Күміс' } });
        fireEvent.change(titleRuInput, { target: { value: 'Серебро' } });
        fireEvent.change(minInput, { target: { value: '50000' } });
        fireEvent.change(maxInput, { target: { value: '150000' } });
        await user.click(saveBtn);

        const maxErr = await screen.findByRole('alert');
        expect(maxErr).toHaveAttribute('id', 'tier-max-error');
        expect(document.getElementById('tier-form-error')).toBeNull();
        expect(document.getElementById('tier-min-error')).toBeNull();
        const overlapRegex =
          locale === 'ru'
            ? /Диапазон оборота пересекается/
            : /Айналым ауқымы/;
        expect(screen.getAllByText(overlapRegex)).toHaveLength(1);
        expect(minInput).toHaveAttribute('aria-invalid', 'true');
        expect(minInput).toHaveAttribute('aria-describedby', 'tier-max-error');
        expect(maxInput).toHaveAttribute('aria-invalid', 'true');
        expect(maxInput).toHaveAttribute('aria-describedby', 'tier-max-error');
        expect(maxErr.closest('label')).toBe(maxInput.closest('label'));

        // Independent client-side field errors still appear alongside clearing stale server overlap highlights on resubmit
        fireEvent.change(percentInput, { target: { value: '150' } });
        await user.click(saveBtn);
        expect(screen.queryByText(overlapRegex)).not.toBeInTheDocument();
        expect(document.getElementById('tier-form-error')).toBeNull();
        expect(minInput).toHaveAttribute('aria-invalid', 'false');
        expect(maxInput).toHaveAttribute('aria-invalid', 'false');
        expect(percentInput).toHaveAttribute('aria-invalid', 'true');
        expect(percentInput).toHaveAttribute('aria-describedby', 'tier-percent-error');
        expect(document.getElementById('tier-percent-error')).toHaveAttribute('role', 'alert');

        // level_exists -> single alert under #tier-level only
        fireEvent.change(percentInput, { target: { value: '5' } });
        serverMode = 'level_exists';
        await user.click(saveBtn);
        const levelErr = await screen.findByRole('alert');
        expect(levelErr).toHaveAttribute('id', 'tier-level-error');
        expect(levelErr.closest('label')).toBe(levelInput.closest('label'));
        expect(document.getElementById('tier-form-error')).toBeNull();
        const levelErrRegex = locale === 'ru' ? /с таким номером уровня уже существует/ : /Мұндай деңгей нөмірі бар дәреже бұрыннан бар/;
        expect(screen.getAllByText(levelErrRegex)).toHaveLength(1);
        expect(levelInput).toHaveAttribute('aria-invalid', 'true');
        expect(levelInput).toHaveAttribute('aria-describedby', 'tier-level-error');

        // multi_field ['min_turnover', 'percent'] -> single alert under last edited of those two (percentInput)
        serverMode = 'multi_field';
        await user.click(saveBtn);
        const multiErr = await screen.findByRole('alert');
        expect(multiErr).toHaveAttribute('id', 'tier-percent-error');
        expect(document.getElementById('tier-form-error')).toBeNull();
        expect(minInput).toHaveAttribute('aria-invalid', 'true');
        expect(percentInput).toHaveAttribute('aria-invalid', 'true');
        expect(minInput).toHaveAttribute('aria-describedby', 'tier-percent-error');
        expect(percentInput).toHaveAttribute('aria-describedby', 'tier-percent-error');

        // Clean save clears everything
        serverMode = 'ok';
        await user.click(saveBtn);
        await waitFor(() => expect(onSaved).toHaveBeenCalledTimes(1));
      },
    );

    it('tracks last edited erroneous min vs max across focus shifts and Save focus steal, falls back deterministically to first erroneous field, and clears stale state on edit', async () => {
      const user = userEvent.setup();
      vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
      vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

      let serverMode: 'overlap' | 'turnover_order' | 'percent_error' | 'network_error' | 'limit_reached' = 'overlap';
      vi.stubGlobal(
        'fetch',
        vi.fn(async (input: RequestInfo | URL) => {
          const url = String(input);
          if (url.endsWith('/admin/auth/refresh')) return json(200, access);
          if (url.endsWith('/admin/me')) {
            return json(200, {
              admin: { id: 'adm-1', login: 'mgr', role: 'business_manager', business: { id: 'b1', name: 'M', status: 'active', logo_url: null } },
              admin_max_stats_period_days: 90,
            });
          }
          if (url.includes('/loyalty-tiers')) {
            if (serverMode === 'overlap') {
              return json(409, {
                error: {
                  code: 'CONFLICT',
                  message: 'Turnover range overlaps with tier [100000.00; 200000.00)',
                  reason: 'LOYALTY_TIER_RANGE_OVERLAP',
                  fields: ['min_turnover', 'max_turnover'],
                },
              });
            }
            if (serverMode === 'turnover_order') {
              return json(422, {
                error: {
                  code: 'VALIDATION_ERROR',
                  message: 'max_turnover must be greater than min_turnover',
                  fields: ['min_turnover', 'max_turnover'],
                },
              });
            }
            if (serverMode === 'percent_error') {
              return json(422, {
                error: {
                  code: 'VALIDATION_ERROR',
                  message: 'percent out of range',
                  fields: ['percent'],
                },
              });
            }
            if (serverMode === 'limit_reached') {
              return json(409, {
                error: {
                  code: 'CONFLICT',
                  message: 'Maximum active tiers limit reached',
                  reason: 'LOYALTY_TIERS_LIMIT_REACHED',
                },
              });
            }
            throw new TypeError('Failed to fetch');
          }
          return json(404, { error: { code: 'NOT_FOUND' } });
        }),
      );

      render(
        <LocaleProvider initialLocale="ru">
          <AdminProvider>
            <TierDialog
              businessId="b1"
              tier={{
                id: 't1',
                business_id: 'b1',
                level: 2,
                priority: 2,
                name_ru: 'Серебро',
                name_kk: 'Күміс',
                description_ru: null,
                description_kk: null,
                min_turnover: 100000,
                max_turnover: 200000,
                percent: 5,
                image_url: null,
                is_active: true,
              }}
              onClose={vi.fn()}
              onSaved={vi.fn()}
            />
          </AdminProvider>
        </LocaleProvider>,
      );

      const saveBtn = screen.getByRole('button', { name: 'Сохранить' });
      const levelInput = document.getElementById('tier-level') as HTMLInputElement;
      const percentInput = document.getElementById('tier-percent') as HTMLInputElement;
      const minInput = document.getElementById('tier-min') as HTMLInputElement;
      const maxInput = document.getElementById('tier-max') as HTMLInputElement;
      const titleRuInput = document.getElementById('tier-title-ru') as HTMLInputElement;

      // 1. No turnover field edited yet -> deterministic fallback to first erroneous field (tier-min-error)
      await user.click(saveBtn);
      let alert = await screen.findByRole('alert');
      expect(alert).toHaveAttribute('id', 'tier-min-error');
      expect(document.getElementById('tier-max-error')).toBeNull();
      expect(document.getElementById('tier-form-error')).toBeNull();
      expect(minInput).toHaveAttribute('aria-invalid', 'true');
      expect(minInput).toHaveAttribute('aria-describedby', 'tier-min-error');
      expect(maxInput).toHaveAttribute('aria-invalid', 'true');
      expect(maxInput).toHaveAttribute('aria-describedby', 'tier-min-error');

      // 2. Edit max -> clears stale joint overlap error on both fields immediately
      fireEvent.change(maxInput, { target: { value: '250000' } });
      expect(screen.queryByRole('alert')).toBeNull();
      expect(minInput).toHaveAttribute('aria-invalid', 'false');
      expect(maxInput).toHaveAttribute('aria-invalid', 'false');
      expect(minInput).not.toHaveAttribute('aria-describedby');
      expect(maxInput).not.toHaveAttribute('aria-describedby');

      // 3. Edit min last, then move focus/edit a NON-erroneous field (percentInput), then click Save (steals focus):
      //    last edited ERRONEOUS field must still be minInput, NOT percentInput!
      fireEvent.change(minInput, { target: { value: '90000' } });
      await user.click(percentInput);
      fireEvent.change(percentInput, { target: { value: '6' } });
      await user.click(saveBtn);
      alert = await screen.findByRole('alert');
      expect(alert).toHaveAttribute('id', 'tier-min-error');
      expect(document.getElementById('tier-percent-error')).toBeNull();
      expect(minInput).toHaveAttribute('aria-describedby', 'tier-min-error');
      expect(maxInput).toHaveAttribute('aria-describedby', 'tier-min-error');

      // 4. Client-side turnover_order (max <= min) when max was edited last -> highlights both, message under max
      fireEvent.change(maxInput, { target: { value: '50000' } });
      await user.click(saveBtn);
      alert = await screen.findByRole('alert');
      expect(alert).toHaveAttribute('id', 'tier-max-error');
      expect(minInput).toHaveAttribute('aria-invalid', 'true');
      expect(maxInput).toHaveAttribute('aria-invalid', 'true');
      expect(minInput).toHaveAttribute('aria-describedby', 'tier-max-error');
      expect(maxInput).toHaveAttribute('aria-describedby', 'tier-max-error');
      expect(document.getElementById('tier-form-error')).toBeNull();

      // 5. Server-side turnover_order -> also anchors on last edited min/max (min here)
      fireEvent.change(maxInput, { target: { value: '260000' } });
      fireEvent.change(minInput, { target: { value: '120000' } });
      serverMode = 'turnover_order';
      await user.click(saveBtn);
      alert = await screen.findByRole('alert');
      expect(alert).toHaveAttribute('id', 'tier-min-error');
      expect(minInput).toHaveAttribute('aria-invalid', 'true');
      expect(maxInput).toHaveAttribute('aria-invalid', 'true');

      // 6. Server-side percent error -> under #tier-percent only
      fireEvent.change(minInput, { target: { value: '100000' } });
      serverMode = 'percent_error';
      await user.click(saveBtn);
      alert = await screen.findByRole('alert');
      expect(alert).toHaveAttribute('id', 'tier-percent-error');
      expect(percentInput).toHaveAttribute('aria-invalid', 'true');
      expect(minInput).toHaveAttribute('aria-invalid', 'false');
      expect(maxInput).toHaveAttribute('aria-invalid', 'false');

      // 7. Independent client errors on multiple fields must all remain visible without hiding each other
      fireEvent.change(levelInput, { target: { value: '0' } });
      fireEvent.change(percentInput, { target: { value: '101' } });
      fireEvent.change(titleRuInput, { target: { value: '' } });
      await user.click(saveBtn);
      expect(document.getElementById('tier-form-error')).toBeNull();
      expect(document.getElementById('tier-level-error')).toHaveAttribute('role', 'alert');
      expect(document.getElementById('tier-percent-error')).toHaveAttribute('role', 'alert');
      expect(document.getElementById('tier-title-ru-error')).toHaveAttribute('role', 'alert');
      expect(levelInput).toHaveAttribute('aria-invalid', 'true');
      expect(percentInput).toHaveAttribute('aria-invalid', 'true');
      expect(titleRuInput).toHaveAttribute('aria-invalid', 'true');

      // Restore valid values and test non-field server/network errors -> #tier-form-error only, NO field highlighted
      fireEvent.change(levelInput, { target: { value: '2' } });
      fireEvent.change(percentInput, { target: { value: '5' } });
      fireEvent.change(titleRuInput, { target: { value: 'Серебро' } });

      serverMode = 'limit_reached';
      await user.click(saveBtn);
      alert = await screen.findByRole('alert');
      expect(alert).toHaveAttribute('id', 'tier-form-error');
      expect(levelInput).toHaveAttribute('aria-invalid', 'false');
      expect(percentInput).toHaveAttribute('aria-invalid', 'false');
      expect(minInput).toHaveAttribute('aria-invalid', 'false');
      expect(maxInput).toHaveAttribute('aria-invalid', 'false');
      expect(titleRuInput).toHaveAttribute('aria-invalid', 'false');

      serverMode = 'network_error';
      await user.click(saveBtn);
      alert = await screen.findByRole('alert');
      expect(alert).toHaveAttribute('id', 'tier-form-error');
      expect(levelInput).toHaveAttribute('aria-invalid', 'false');
      expect(percentInput).toHaveAttribute('aria-invalid', 'false');
      expect(minInput).toHaveAttribute('aria-invalid', 'false');
      expect(maxInput).toHaveAttribute('aria-invalid', 'false');
    });
  });

  describe('Fix 3: ContentPage Start Now live UTC+5 display in offers and banners', () => {
    it.each(['offer', 'banner'] as const)(
      'shows live UTC+5 datetime when Start Now is active, refreshes on re-toggle after clock advance, preserves manual date, and submits starts_at=null (%s)',
      async kind => {
        // 2026-11-17 15:10 UTC+5 -> 2026-11-17T10:10:00Z
        vi.useFakeTimers({ toFake: ['Date'] });
        vi.setSystemTime(new Date('2026-11-17T10:10:00.000Z'));

        const user = userEvent.setup();
        vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
        vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

        const sentBodies: Record<string, unknown>[] = [];
        vi.stubGlobal(
          'fetch',
          vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
            const url = String(input);
            if (url.endsWith('/admin/auth/refresh')) return json(200, access);
            if (url.endsWith('/admin/me')) {
              return json(200, {
                admin: { id: 'adm-1', login: 'mgr', role: 'business_manager', business: { id: 'b1', name: 'M', status: 'active', logo_url: null } },
                admin_max_stats_period_days: 90,
              });
            }
            if (url.includes('/admin/promotions')) {
              sentBodies.push(JSON.parse(String(init?.body)) as Record<string, unknown>);
              return json(201, {
                id: 'promo-1',
                business_id: 'b1',
                business_name: 'M',
                kind,
                title: 'Test Promo',
                subtitle: null,
                badge: null,
                body: null,
                image_url: null,
                starts_at: null,
                ends_at: null,
                sort_order: 0,
                is_active: true,
                created_at: '2026-11-17T10:10:00Z',
                updated_at: '2026-11-17T10:10:00Z',
              });
            }
            return json(404, { error: { code: 'NOT_FOUND' } });
          }),
        );

        const onClose = vi.fn();
        // 1. Create dialog starts with Start Now checked -> displays current UTC+5 datetime
        const { unmount } = render(
          <LocaleProvider initialLocale="ru">
            <AdminProvider>
              <PromotionDialog defaultKind={kind} onClose={onClose} />
            </AdminProvider>
          </LocaleProvider>,
        );

        const titleInput = await screen.findByLabelText('Заголовок');
        const startInput = document.getElementById('promo-start') as HTMLInputElement;
        const startNowBox = document.getElementById('promo-start-now') as HTMLInputElement;
        expect(startNowBox.checked).toBe(true);
        expect(startInput.value).toBe('2026-11-17T15:10');

        // Toggle OFF -> manual input; enter manual date; toggle ON -> shows fresh UTC+5 time; toggle OFF -> restores manual date
        await user.click(startNowBox);
        expect(startNowBox.checked).toBe(false);
        fireEvent.change(startInput, { target: { value: '2026-12-01T14:30' } });

        // Advance clock by 5 minutes -> 15:15 UTC+5 -> toggling Start Now ON shows 15:15, not 15:10!
        vi.setSystemTime(new Date('2026-11-17T10:15:00.000Z'));
        await user.click(startNowBox);
        expect(startNowBox.checked).toBe(true);
        expect(startInput.value).toBe('2026-11-17T15:15');

        await user.click(startNowBox);
        expect(startInput.value).toBe('2026-12-01T14:30');

        // Wait past initial display time, toggle ON -> must submit starts_at: null with no past-date error
        vi.setSystemTime(new Date('2026-11-17T19:05:00.000Z')); // cross midnight -> 2026-11-18 00:05 UTC+5
        await user.click(startNowBox);
        expect(startInput.value).toBe('2026-11-18T00:05');

        fireEvent.change(titleInput, { target: { value: `Immediate ${kind}` } });
        await user.click(screen.getByRole('button', { name: 'Сохранить' }));
        await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
        expect(sentBodies[0]).toMatchObject({ kind, starts_at: null, ends_at: null });

        unmount();

        // 2. Edit existing item that already has starts_at=null -> opens with Start Now checked & current UTC+5 datetime visible
        const existingImmediate: Promotion = {
          id: 'promo-existing',
          business_id: 'b1',
          business_name: 'M',
          kind,
          title: 'Existing',
          subtitle: null,
          badge: null,
          body: null,
          image_url: null,
          starts_at: null,
          ends_at: null,
          sort_order: 1,
          is_active: true,
          created_at: '2026-11-16T00:00:00Z',
          updated_at: '2026-11-16T00:00:00Z',
        };
        render(
          <LocaleProvider initialLocale="kk">
            <AdminProvider>
              <PromotionDialog promotion={existingImmediate} onClose={onClose} />
            </AdminProvider>
          </LocaleProvider>,
        );
        const editStartInput = (await screen.findByDisplayValue('2026-11-18T00:05')) as HTMLInputElement;
        expect(editStartInput.id).toBe('promo-start');
        expect((document.getElementById('promo-start-now') as HTMLInputElement).checked).toBe(true);
      },
    );
  });

  describe('Fix 4: OperationsPage CardDetailPage hides binding and hidden rows cleanly', () => {
    it.each([
      ['business_manager', 'ru'],
      ['business_manager', 'kk'],
      ['superadmin', 'ru'],
      ['superadmin', 'kk'],
    ] as const)('hides bind_method, bound_at, hidden_at rows while keeping card details and actions (%s, %s)', async (role, locale) => {
      vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
      vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

      vi.stubGlobal(
        'fetch',
        vi.fn(async (input: RequestInfo | URL) => {
          const url = String(input);
          if (url.endsWith('/admin/auth/refresh')) return json(200, access);
          if (url.endsWith('/admin/me')) {
            return json(200, {
              admin: {
                id: 'adm-1',
                login: role,
                role,
                business: role === 'business_manager' ? { id: 'b1', name: 'M', status: 'active', logo_url: null } : null,
              },
              admin_max_stats_period_days: 90,
            });
          }
          if (url.includes('/transactions')) {
            return json(200, { items: [], limit: 25, offset: 0, has_more: false });
          }
          if (url.includes('/admin/cards/')) {
            return json(200, {
              id: 'c-1',
              business_id: 'b1',
              business_name: 'M',
              barcode: '0000000000999',
              balance: '250.0000',
              is_blocked: false,
              phone_masked: '+7 777 ••• 8899',
              full_name: 'Card Owner',
              owner_language: 'ru',
              bind_method: 'phone_otp',
              bound_at: '2026-11-10T10:00:00Z',
              hidden_at: '2026-11-11T10:00:00Z',
              updated_at: '2026-11-17T08:00:00Z',
            });
          }
          return json(404, { error: { code: 'NOT_FOUND' } });
        }),
      );

      render(
        <LocaleProvider initialLocale={locale}>
          <AdminProvider>
            <ActiveBusinessProvider>
              <MemoryRouter initialEntries={['/admin/cards/c-1']}>
                <Routes>
                  <Route path="/admin/cards/:cardId" element={<CardDetailPage />} />
                </Routes>
              </MemoryRouter>
            </ActiveBusinessProvider>
          </AdminProvider>
        </LocaleProvider>,
      );

      expect(await screen.findByText('0000000000999')).toBeInTheDocument();
      expect(screen.getByText('Card Owner')).toBeInTheDocument();

      // Forbidden visible labels in both RU & KK
      for (const hiddenLabel of [
        'Тип привязки',
        'Дата привязки',
        'Скрыта клиентом',
        'Байланыс түрі',
        'Байланыстыру күні',
        'Клиент жасырған',
      ]) {
        expect(screen.queryByText(hiddenLabel)).not.toBeInTheDocument();
      }
      expect(screen.queryByText('phone_otp')).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: locale === 'ru' ? 'Отвязать карту' : 'Карта байланысын ажырату' })).toBeEnabled();
    });
  });

  describe('Fix 5: BusinessTextsSection hides home_text editor/preview and preserves stored home_text on save', () => {
    it.each([
      ['business_manager', 'ru'],
      ['superadmin', 'kk'],
    ] as const)(
      'renders only balance_delay_note, hides home_text & preview, and omits home_text from PUT body (%s, %s)',
      async (role, locale) => {
        const user = userEvent.setup();
        vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
        vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

        const storedTexts = {
          home_text: { ru: 'Скрытый текст RU', kk: 'Жасырын мәтін KK' },
          home_store_note_lead: { ru: 'Ведущая строка RU', kk: 'Кіріспе KK' },
          balance_delay_note: { ru: 'Исходная задержка RU', kk: 'Бастапқы кідіріс KK' },
        };
        const putBodies: Record<string, unknown>[] = [];

        vi.stubGlobal(
          'fetch',
          vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
            const url = String(input);
            if (url.endsWith('/admin/auth/refresh')) return json(200, access);
            if (url.endsWith('/admin/me')) {
              return json(200, {
                admin: {
                  id: 'adm-1',
                  login: role,
                  role,
                  business: role === 'business_manager' ? { id: 'b1', name: 'M', status: 'active', logo_url: null } : null,
                },
                admin_max_stats_period_days: 90,
              });
            }
            if (url.endsWith('/admin/businesses/b1/app-texts')) {
              if (init?.method === 'PUT') {
                const payload = JSON.parse(String(init.body)) as Record<string, unknown>;
                putBodies.push(payload);
                // Simulate backend merge: stored home_text stays intact when omitted from PUT
                return json(200, {
                  ...storedTexts,
                  ...payload,
                });
              }
              return json(200, storedTexts);
            }
            return json(404, { error: { code: 'NOT_FOUND' } });
          }),
        );

        render(
          <LocaleProvider initialLocale={locale}>
            <AdminProvider>
              <BusinessTextsSection businessId="b1" />
            </AdminProvider>
          </LocaleProvider>,
        );

        const delayRu = (await screen.findByDisplayValue('Исходная задержка RU')) as HTMLTextAreaElement;
        expect(document.getElementById('text-home-ru')).not.toBeInTheDocument();
        expect(document.getElementById('text-home-kk')).not.toBeInTheDocument();
        expect(document.querySelector('.home-text-preview-box')).not.toBeInTheDocument();
        expect(screen.queryByText('Текст на главной')).not.toBeInTheDocument();
        expect(screen.queryByText('Басты беттегі мәтін')).not.toBeInTheDocument();
        expect(screen.queryByText('Скрытый текст RU')).not.toBeInTheDocument();
        expect(screen.queryByText('Жасырын мәтін KK')).not.toBeInTheDocument();

        fireEvent.change(delayRu, { target: { value: 'Обновлённая задержка RU' } });
        await user.click(
          screen.getByRole('button', { name: locale === 'ru' ? 'Сохранить тексты' : 'Мәтіндерді сақтау' }),
        );

        await waitFor(() => expect(putBodies).toHaveLength(1));
        expect(putBodies[0]).not.toHaveProperty('home_text');
        expect(putBodies[0]).toEqual({
          home_store_note_lead: storedTexts.home_store_note_lead,
          balance_delay_note: { ru: 'Обновлённая задержка RU', kk: 'Бастапқы кідіріс KK' },
        });
      },
    );
  });
});
