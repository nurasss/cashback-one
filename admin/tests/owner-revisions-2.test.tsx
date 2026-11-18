import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AdminProvider } from '../src/auth/provider';
import { ActiveBusinessProvider } from '../src/context/ActiveBusinessContext';
import { LocaleProvider } from '../src/i18n/LocaleContext';
import { publicKk, publicRu } from '../src/i18n/public';
import { ManagerAccessDialog } from '../src/features/AdminMutations';
import { StoreDialog } from '../src/features/BusinessAppContent';
import { Navigation } from '../src/features/Navigation';
import { DashboardPage } from '../src/pages/DashboardPage';
import { LandingPage } from '../src/pages/LandingPage';
import { PromotionDialog } from '../src/pages/ContentPage';
import { TierDialog } from '../src/pages/StatusesPage';
import { NumericInput } from '../src/components/NumericInput';
import { formatDate } from '../src/utils/format';

const access = { access_token: 'fixture-access', token_type: 'bearer', expires_in: 900 };
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
});

describe('Owner revisions 2 (2026-11-11)', () => {
  describe('Point 2: Dashboard period error recovery, Back button, nav reset, and >90-day guard', () => {
    it('blocks periods > admin_max_stats_period_days before request, keeps filters on error, and recovers via Back or active nav click', async () => {
      const user = userEvent.setup();
      vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
      vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

      const dashboardCalls: string[] = [];
      let failNextDashboard = false;
      let failWithNetwork = false;

      const fetchMock: typeof fetch = vi.fn(async input => {
        const url = String(input);
        if (url.endsWith('/admin/auth/refresh')) return json(200, access);
        if (url.endsWith('/admin/me')) {
          return json(200, {
            admin: {
              id: 'super-1',
              login: 'poscenter',
              role: 'superadmin',
              business: null,
            },
            admin_max_stats_period_days: 90,
          });
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
          if (failWithNetwork) {
            throw new TypeError('Failed to fetch');
          }
          if (failNextDashboard) {
            return json(422, { error: { code: 'ADMIN_PERIOD_TOO_LARGE', message: 'Too large' } });
          }
          return json(200, {
            period_from: '2026-10-13T19:00:00Z',
            period_to: '2026-11-11T18:59:59Z',
            period_days: 30,
            businesses_total: 1,
            businesses_active: 1,
            cards_total: 100,
            users_total: 50,
            bound_cards_total: 45,
            unbound_cards_total: 55,
            transactions: 200,
            accrual_count: 150,
            redemption_count: 50,
            accrual_sum: '15000.0000',
            redemption_sum: '5000.0000',
            notifications_sent: 10,
            active_promotions: 2,
            agents: { online: 1, stale: 0, never_connected: 0, error: 0, disabled: 0 },
          });
        }
        return json(404, { error: { code: 'NOT_FOUND' } });
      });
      vi.stubGlobal('fetch', fetchMock);

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

      expect(await screen.findByRole('heading', { name: 'Все бизнесы' })).toBeInTheDocument();
      const initialCalls = dashboardCalls.length;
      expect(initialCalls).toBe(1);

      const fromInput = screen.getByLabelText('С') as HTMLInputElement;
      const toInput = screen.getByLabelText('По') as HTMLInputElement;
      const refreshBtn = screen.getByRole('button', { name: 'Обновить' });
      const workingFrom = fromInput.value;
      const workingTo = toInput.value;

      // 1. Pre-request validation > 90 days keeps Refresh active, shows hint, blocks API call on click
      fireEvent.change(fromInput, { target: { value: '2026-01-01' } });
      fireEvent.change(toInput, { target: { value: '2026-06-01' } });
      expect(screen.getByText('Выберите период не длиннее 90 дней.')).toBeInTheDocument();
      expect(refreshBtn).not.toBeDisabled();
      await user.click(refreshBtn);
      expect(dashboardCalls.length).toBe(initialCalls);

      // 2. Valid range <= 90 days that returns server error keeps filter form on screen, hides Retry for 422, removes Back button under error
      failNextDashboard = true;
      fireEvent.change(fromInput, { target: { value: '2026-10-01' } });
      fireEvent.change(toInput, { target: { value: '2026-10-15' } });
      expect(refreshBtn).not.toBeDisabled();
      await user.click(refreshBtn);

      expect(await screen.findByText('Выберите более короткий период.')).toBeInTheDocument();
      expect(screen.getByLabelText('С')).toBeInTheDocument();
      expect(screen.getByLabelText('Бизнес')).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Повторить' })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Назад' })).not.toBeInTheDocument();

      // 3. User corrects the period and clicks Refresh to update
      failNextDashboard = false;
      fireEvent.change(fromInput, { target: { value: workingFrom } });
      fireEvent.change(toInput, { target: { value: workingTo } });
      await user.click(refreshBtn);
      await waitFor(() => {
        expect(screen.queryByText('Выберите более короткий период.')).not.toBeInTheDocument();
      });
      expect(fromInput.value).toBe(workingFrom);
      expect(toInput.value).toBe(workingTo);

      // 4. Network error shows Retry button, and clicking active nav "Обзор" resets to default period
      failWithNetwork = true;
      fireEvent.change(fromInput, { target: { value: '2026-10-05' } });
      fireEvent.change(toInput, { target: { value: '2026-10-10' } });
      await user.click(refreshBtn);

      expect(await screen.findByRole('button', { name: 'Повторить' })).toBeInTheDocument();
      failWithNetwork = false;
      const overviewNav = screen.getByRole('link', { name: 'Обзор' });
      await user.click(overviewNav);
      await waitFor(() => {
        expect(screen.queryByRole('button', { name: 'Повторить' })).not.toBeInTheDocument();
      });
      expect(fromInput.value).toBe(workingFrom);
      expect(toInput.value).toBe(workingTo);
    });
  });

  describe('Point 3: Astana UTC+5 formatting', () => {
    it('formats timestamps in UTC+5 across midnight boundaries', () => {
      expect(formatDate('2026-11-11T20:30:00Z', 'ru')).toContain('12');
      expect(formatDate('2026-11-11T20:30:00Z', 'ru')).toContain('01:30');
    });
  });

  describe('Point 5: ManagerAccessDialog layout and controls', () => {
    it('renders only top Close button, centers Copy All, and reserves status container', async () => {
      const user = userEvent.setup();
      vi.stubGlobal('navigator', {
        clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
      });

      render(
        <LocaleProvider initialLocale="ru">
          <ManagerAccessDialog
            disclosure={{
              login: 'keremet',
              password: 'SecretPassword123',
              login_url: 'https://cashback-qr.poscenter.kz',
              one_time: true,
            }}
            onClose={vi.fn()}
          />
        </LocaleProvider>,
      );

      const closeButtons = screen.getAllByRole('button', { name: /Закрыть/i });
      expect(closeButtons).toHaveLength(1);
      const copyBtn = screen.getByRole('button', { name: 'Скопировать всё' });
      expect(copyBtn.closest('.manager-access-actions')).not.toBeNull();
      const statusBox = document.querySelector('.manager-access-status');
      expect(statusBox).not.toBeNull();

      await user.click(copyBtn);
      expect(await within(statusBox as HTMLElement).findByText('Скопировано в буфер обмена.')).toBeInTheDocument();
    });
  });

  describe('Point 7: NumericInput and field-level validation', () => {
    it('prevents e, E, +, and - (when allowNegative=false) and blurs on wheel', () => {
      const { getByLabelText } = render(
        <div>
          <label htmlFor="num-pos">Pos</label>
          <NumericInput id="num-pos" />
          <label htmlFor="num-neg">Neg</label>
          <NumericInput id="num-neg" allowNegative decimal />
        </div>,
      );

      const pos = getByLabelText('Pos') as HTMLInputElement;
      const neg = getByLabelText('Neg') as HTMLInputElement;
      expect(pos).toHaveAttribute('inputmode', 'numeric');
      expect(neg).toHaveAttribute('inputmode', 'decimal');

      for (const key of ['e', 'E', '+', '-']) {
        const ev = new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true });
        pos.dispatchEvent(ev);
        expect(ev.defaultPrevented).toBe(true);
      }

      const minusAllowed = new KeyboardEvent('keydown', { key: '-', bubbles: true, cancelable: true });
      neg.dispatchEvent(minusAllowed);
      expect(minusAllowed.defaultPrevented).toBe(false);

      pos.focus();
      expect(document.activeElement).toBe(pos);
      fireEvent.wheel(pos);
      expect(document.activeElement).not.toBe(pos);
    });

    it('renders field-level errors next to inputs in TierDialog, PromotionDialog, and StoreDialog', async () => {
      const user = userEvent.setup();
      vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
      vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');
      vi.stubGlobal('fetch', vi.fn(async () => json(200, access)));

      const { unmount } = render(
        <LocaleProvider initialLocale="ru">
          <AdminProvider>
            <TierDialog businessId="biz-1" onClose={vi.fn()} onSaved={vi.fn()} />
          </AdminProvider>
        </LocaleProvider>,
      );

      await user.type(screen.getByLabelText(/Название статуса \(RU\)|Название \(русский\)/i), 'Золотой');
      await user.type(screen.getByLabelText(/Дәреже атауы \(RU\)|Атауы \(KK\)|Название.*KK|Дәреже|Название \(қазақша\)/i), 'Алтын');
      const levelInput = screen.getByLabelText(/Номер уровня/i);
      await user.clear(levelInput);
      await user.type(levelInput, '0');
      await user.click(screen.getByRole('button', { name: 'Сохранить' }));
      expect(levelInput).toHaveAttribute('aria-invalid', 'true');
      expect(screen.getByText('Укажите положительный номер уровня')).toBeInTheDocument();
      unmount();

      const { unmount: unmountPromo } = render(
        <LocaleProvider initialLocale="ru">
          <AdminProvider>
            <PromotionDialog onClose={vi.fn()} />
          </AdminProvider>
        </LocaleProvider>,
      );
      await user.type(screen.getByLabelText('Заголовок'), 'Акция');
      await user.type(screen.getByLabelText('Описание'), 'Описание акции');
      await user.click(screen.getByRole('checkbox', { name: /начать сейчас/i }));
      await user.click(screen.getByRole('checkbox', { name: /бессрочно/i }));
      const startInput = screen.getByLabelText('Начало показа');
      const endInput = screen.getByLabelText('Конец показа');
      fireEvent.change(startInput, { target: { value: '2026-12-10T12:00' } });
      fireEvent.change(endInput, { target: { value: '2026-12-09T12:00' } });
      await user.click(screen.getByRole('button', { name: 'Сохранить' }));
      expect(endInput).toHaveAttribute('aria-invalid', 'true');
      expect(screen.getByText('Конец показа должен быть строго позже начала.')).toBeInTheDocument();
      unmountPromo();

      render(
        <LocaleProvider initialLocale="ru">
          <AdminProvider>
            <StoreDialog businessId="biz-1" onClose={vi.fn()} onSaved={vi.fn()} />
          </AdminProvider>
        </LocaleProvider>,
      );
      await user.type(screen.getByLabelText('Название (RU)'), 'Магазин');
      await user.type(screen.getByLabelText('Название (KK)'), 'Дүкен');
      await user.type(screen.getByLabelText('Адрес (RU)'), 'ул. Абая 1');
      await user.type(screen.getByLabelText('Адрес (KK)'), 'Абай к-сі 1');
      const sortInput = screen.getByLabelText('Порядок сортировки');
      await user.clear(sortInput);
      await user.type(sortInput, '5000');
      await user.click(screen.getByRole('button', { name: 'Сохранить' }));
      expect(sortInput).toHaveAttribute('aria-invalid', 'true');
    });
  });

  describe('Points 9 & 10: Landing header and bonus wording without балл/ұпай', () => {
    it('removes the header outline business button while keeping nav and hero business links in RU and KK', () => {
      const { container } = render(
        <LocaleProvider initialLocale="ru">
          <LandingPage />
        </LocaleProvider>,
      );

      expect(container.querySelector('.landing-header-biz-btn')).toBeNull();
      expect(screen.getByRole('navigation', { name: publicRu.header.navAria })).toHaveTextContent('Для бизнеса');
      expect(screen.getByRole('link', { name: 'Вход для бизнеса' })).toHaveAttribute('href', '/admin/login');
      expect(screen.getByRole('link', { name: /Для бизнеса →/ })).toHaveAttribute('href', '#business');
      expect(container.textContent).not.toMatch(/iPhone/i);

      cleanup();
      const { container: kkContainer } = render(
        <LocaleProvider initialLocale="kk">
          <LandingPage />
        </LocaleProvider>,
      );
      expect(kkContainer.querySelector('.landing-header-biz-btn')).toBeNull();
      expect(screen.getByRole('link', { name: 'Бизнеске кіру' })).toHaveAttribute('href', '/admin/login');
      expect(screen.getByRole('link', { name: /Бизнес үшін →/ })).toHaveAttribute('href', '#business');
      expect(kkContainer.textContent).not.toMatch(/iPhone/i);
    });

    it('has no балл, ұпай, or iPhone mention in publicRu, publicKk, or admin/index.html', () => {
      const ruText = JSON.stringify(publicRu);
      const kkText = JSON.stringify(publicKk);
      const indexHtml = readFileSync(resolve(__dirname, '../index.html'), 'utf-8');

      expect(ruText).not.toMatch(/балл|iPhone/i);
      expect(kkText).not.toMatch(/балл|балдар|ұпай|iPhone/i);
      expect(indexHtml).not.toMatch(/балл|ұпай|iPhone/i);
      expect(publicRu.bonus.pointsText1).toBe(
        'Правила начисления, списания и использования бонусов / скидок определяет магазин.',
      );
    });
  });
});
