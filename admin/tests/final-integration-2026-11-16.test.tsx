import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, errorFromResponse, messageForError } from '../src/api/errors';
import type { AuditItem, BusinessDetail, LoyaltyTier } from '../src/api/types';
import { AdminProvider } from '../src/auth/provider';
import { ActiveBusinessProvider } from '../src/context/ActiveBusinessContext';
import { BusinessEditorDialog } from '../src/features/AdminMutations';
import { LocaleProvider } from '../src/i18n/LocaleContext';
import { AuditPage } from '../src/pages/AuditPage';
import { ContentPage } from '../src/pages/ContentPage';
import { StatusesPage } from '../src/pages/StatusesPage';

const access = { access_token: 'fixture-access', token_type: 'bearer', expires_in: 900 };
const businessId = '11111111-1111-1111-1111-111111111111';

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

const baseTiers: LoyaltyTier[] = [
  {
    id: 'tier-1',
    business_id: businessId,
    level: 1,
    priority: 1,
    name_ru: 'Бронза',
    name_kk: 'Қола',
    description_ru: 'Стартовый статус',
    description_kk: 'Бастапқы мәртебе',
    image_url: 'https://cdn.example.test/bronze.webp',
    min_turnover: '0.00',
    max_turnover: '100000.00',
    percent: '1.00',
    is_active: true,
    created_at: '2026-11-01T00:00:00Z',
    updated_at: '2026-11-01T00:00:00Z',
  },
  {
    id: 'tier-2',
    business_id: businessId,
    level: 2,
    priority: 2,
    name_ru: 'Серебро',
    name_kk: 'Күміс',
    description_ru: 'Постоянный покупатель',
    description_kk: 'Тұрақты сатып алушы',
    image_url: null,
    min_turnover: '50000.00', // intersecting legacy state before atomic edit
    max_turnover: null,
    percent: '3.00',
    is_active: false, // inactive row must STILL appear and participate in PUT
    created_at: '2026-11-01T00:00:00Z',
    updated_at: '2026-11-01T00:00:00Z',
  },
];

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

describe('Final Integration Suite: Legacy Tiers, K1 Scale Editor, K5 Audit & K4 Content', () => {
  describe('P3 Narrow Fix: BusinessEditorDialog legacy tiers have no +100000 default and preserve untouched fields', () => {
    it('sets threshold "0" only on first added row, starts row 2 empty "", blocks blank submit, and preserves existing tiers/colors on unrelated edit', async () => {
      const user = userEvent.setup();
      let patchedBodies: Array<Record<string, unknown>> = [];
      const businessWithoutTiers: BusinessDetail = {
        id: businessId,
        name: 'Fresh Biz',
        logo_url: null,
        colors: { primary: '#123456', customExtra: 'preserved' },
        barcode_prefixes: ['77'],
        android_app_id: 'kz.cashbackone.fresh',
        status: 'active',
        loyalty_tiers: null,
        created_at: '2026-11-01T00:00:00Z',
        updated_at: '2026-11-01T00:00:00Z',
        cards_count: 1,
        unblocked_cards_count: 1,
        customers_with_cards_count: 1,
        agents_count: 1,
      };

      setupEnvFetch('superadmin', async (url, init) => {
        if (url.pathname === `/admin/businesses/${businessId}` && init?.method === 'PATCH') {
          const parsed = JSON.parse(String(init.body)) as Record<string, unknown>;
          patchedBodies.push(parsed);
          return json(200, { ...businessWithoutTiers, ...parsed });
        }
        return json(200, []);
      });

      const onSaved = vi.fn();
      const { unmount } = render(
        <QueryClientProvider client={new QueryClient()}>
          <AdminProvider>
            <ActiveBusinessProvider>
              <LocaleProvider initialLocale="ru">
                <BusinessEditorDialog business={businessWithoutTiers} onClose={() => {}} onSaved={onSaved} />
              </LocaleProvider>
            </ActiveBusinessProvider>
          </AdminProvider>
        </QueryClientProvider>
      );

      // Row 1 starts with threshold '0'
      await user.click(await screen.findByRole('button', { name: 'Добавить уровень' }));
      const row1Thresholds = screen.getAllByLabelText('Порог, ₸');
      expect(row1Thresholds).toHaveLength(1);
      expect(row1Thresholds[0]).toHaveValue('0');

      // Row 2 MUST start empty '' (NO 100000)
      await user.click(screen.getByRole('button', { name: 'Добавить уровень' }));
      const twoThresholds = screen.getAllByLabelText('Порог, ₸');
      expect(twoThresholds).toHaveLength(2);
      expect(twoThresholds[1]).toHaveValue('');

      // Save with empty row 2 threshold -> inline error near field, ZERO PATCH sent
      await user.click(screen.getByRole('button', { name: 'Сохранить' }));
      expect(await screen.findByRole('alert')).toHaveTextContent('Укажите порог');
      expect(twoThresholds[1]).toHaveAttribute('aria-invalid', 'true');
      expect(patchedBodies).toHaveLength(0);

      // Fill explicit threshold 200000 and save
      await user.type(twoThresholds[1]!, '200000');
      await user.click(screen.getByRole('button', { name: 'Сохранить' }));
      await waitFor(() => expect(onSaved).toHaveBeenCalledTimes(1));
      expect(patchedBodies[0]?.loyalty_tiers).toEqual([
        { level: 1, name: '', threshold: '0', percent: '0' },
        { level: 2, name: '', threshold: '200000', percent: '0' },
      ]);
      unmount();

      // Re-open with existing tiers + extra color key, change ONLY name -> preserves existing tiers and custom color key
      patchedBodies = [];
      const onSaved2 = vi.fn();
      const existingWithTiers: BusinessDetail = {
        ...businessWithoutTiers,
        loyalty_tiers: [
          { level: 1, name: 'Базовый', threshold: '0', percent: '1' },
          { level: 2, name: 'Про', threshold: '185000', percent: '4' },
        ],
      };
      render(
        <QueryClientProvider client={new QueryClient()}>
          <AdminProvider>
            <ActiveBusinessProvider>
              <LocaleProvider initialLocale="ru">
                <BusinessEditorDialog business={existingWithTiers} onClose={() => {}} onSaved={onSaved2} />
              </LocaleProvider>
            </ActiveBusinessProvider>
          </AdminProvider>
        </QueryClientProvider>
      );
      await screen.findByText('Основные данные');
      const nameInput = document.getElementById('business-name') as HTMLInputElement;
      expect(nameInput).toBeTruthy();
      await user.clear(nameInput);
      await user.type(nameInput, 'Renamed Biz');
      await user.click(screen.getByRole('button', { name: 'Сохранить' }));
      await waitFor(() => expect(onSaved2).toHaveBeenCalledTimes(1));
      expect(patchedBodies[0]).toMatchObject({
        name: 'Renamed Biz',
        colors: { primary: '#123456', customExtra: 'preserved' },
        loyalty_tiers: existingWithTiers.loyalty_tiers,
      });
    }, 15_000);
  });

  describe('K1 Atomic Scale Editor: contract compliance, errors, concurrency, and 404/405 feature detection', () => {
    it('loads scale, avoids auto-shifting neighbors, omits unedited optional fields and forbidden keys, handles changed:false', async () => {
      const user = userEvent.setup();
      const putBodies: unknown[] = [];
      let callCount = 0;

      setupEnvFetch('business_manager', async (url, init) => {
        if (url.pathname === `/admin/businesses/${businessId}/loyalty-tiers`) {
          return json(200, baseTiers);
        }
        if (url.pathname === `/admin/businesses/${businessId}/loyalty-tiers/scale` && (!init?.method || init.method === 'GET')) {
          return json(200, { business_id: businessId, version: 3, tiers: baseTiers });
        }
        if (url.pathname === `/admin/businesses/${businessId}/loyalty-tiers/scale` && init?.method === 'PUT') {
          callCount += 1;
          const body = JSON.parse(String(init.body));
          putBodies.push(body);
          if (callCount === 1) {
            const updated: LoyaltyTier[] = [
              { ...baseTiers[0]!, min_turnover: '0.00', max_turnover: '350000.00', percent: '2.00' },
              { ...baseTiers[1]!, min_turnover: '350000.00', max_turnover: null, percent: '5.00', is_active: true },
            ];
            return json(200, { business_id: businessId, version: 4, changed: true, tiers: updated });
          }
          const updated2: LoyaltyTier[] = [
            { ...baseTiers[0]!, min_turnover: '0.00', max_turnover: '350000.00', percent: '2.00' },
            { ...baseTiers[1]!, min_turnover: '350000.00', max_turnover: null, percent: '5.00', is_active: true },
          ];
          return json(200, { business_id: businessId, version: 4, changed: false, tiers: updated2 });
        }
        return json(404, { detail: 'Not found' });
      });

      render(
        <QueryClientProvider client={new QueryClient()}>
          <AdminProvider>
            <ActiveBusinessProvider>
              <LocaleProvider initialLocale="ru">
                <MemoryRouter>
                  <StatusesPage />
                </MemoryRouter>
              </LocaleProvider>
            </ActiveBusinessProvider>
          </AdminProvider>
        </QueryClientProvider>
      );

      await user.click(await screen.findByRole('button', { name: 'Редактировать шкалу' }));
      expect(await screen.findByText('Версия v3')).toBeInTheDocument();

      // Inactive row #2 MUST also appear in scale editor
      const tier1Card = document.querySelector('[data-scale-tier-id="tier-1"]')!;
      const tier2Card = document.querySelector('[data-scale-tier-id="tier-2"]')!;
      expect(tier1Card).toBeTruthy();
      expect(tier2Card).toBeTruthy();

      // Edit tier 1 max_turnover to 350000 -> tier 2 min_turnover MUST NOT auto-shift (stays 50000.00)
      const tier1Max = document.getElementById('scale-max-tier-1') as HTMLInputElement;
      const tier2Min = document.getElementById('scale-min-tier-2') as HTMLInputElement;
      const tier2Active = document.getElementById('scale-active-tier-2') as HTMLInputElement;
      const tier2Pct = document.getElementById('scale-percent-tier-2') as HTMLInputElement;

      await user.clear(tier1Max);
      await user.type(tier1Max, '350000');
      expect(tier2Min.value).toBe('50000.00'); // no auto-shift!

      // Preview detects overlap before coordinate edit
      expect(screen.getByText(/Предпросмотр итоговой шкалы/)).toBeInTheDocument();

      // Coordinate tier 2 manually and toggle active -> PUT 1
      await user.clear(tier2Min);
      await user.type(tier2Min, '350000');
      await user.clear(tier2Pct);
      await user.type(tier2Pct, '5');
      await user.click(tier2Active);

      await user.click(screen.getByRole('button', { name: 'Сохранить шкалу' }));
      expect(await screen.findByText('Шкала успешно сохранена (актуальная версия: v4).')).toBeInTheDocument();
      expect(screen.getByText('Версия v4')).toBeInTheDocument();

      expect(putBodies[0]).toEqual({
        expected_version: 3,
        tiers: [
          {
            id: 'tier-1',
            min_turnover: '0.00',
            max_turnover: '350000',
            percent: '1.00',
          },
          {
            id: 'tier-2',
            min_turnover: '350000',
            max_turnover: null,
            percent: '5',
            is_active: true,
          },
        ],
      });

      // Verify omitted unedited optional fields & no forbidden fields (level, priority, turnover_period_months)
      const firstPut = putBodies[0] as { tiers: Array<Record<string, unknown>> };
      for (const item of firstPut.tiers) {
        expect(item).not.toHaveProperty('level');
        expect(item).not.toHaveProperty('priority');
        expect(item).not.toHaveProperty('turnover_period_months');
        expect(item).not.toHaveProperty('name_ru');
        expect(item).not.toHaveProperty('name_kk');
        expect(item).not.toHaveProperty('description_ru');
        expect(item).not.toHaveProperty('image_url');
      }
      expect(firstPut.tiers[0]).not.toHaveProperty('is_active');

      // Second save unchanged -> changed: false message, version stays 4
      await user.click(screen.getByRole('button', { name: 'Сохранить шкалу' }));
      expect(await screen.findByText('Изменений не было — версия шкалы осталась прежней (v4).')).toBeInTheDocument();
      expect(screen.getByText('Версия v4')).toBeInTheDocument();
    }, 15_000);

    it('preserves unsaved user edits on 409 LOYALTY_SCALE_VERSION_CONFLICT and reloads only on explicit button click', async () => {
      const user = userEvent.setup();
      let getCount = 0;

      setupEnvFetch('business_manager', async (url, init) => {
        if (url.pathname === `/admin/businesses/${businessId}/loyalty-tiers`) {
          return json(200, baseTiers);
        }
        if (url.pathname === `/admin/businesses/${businessId}/loyalty-tiers/scale` && (!init?.method || init.method === 'GET')) {
          getCount += 1;
          if (getCount === 1) {
            return json(200, { business_id: businessId, version: 1, tiers: baseTiers });
          }
          const serverUpdated: LoyaltyTier[] = [
            { ...baseTiers[0]!, max_turnover: '200000.00', percent: '1.50' },
            { ...baseTiers[1]!, min_turnover: '200000.00', is_active: true },
          ];
          return json(200, { business_id: businessId, version: 5, tiers: serverUpdated });
        }
        if (url.pathname === `/admin/businesses/${businessId}/loyalty-tiers/scale` && init?.method === 'PUT') {
          return json(409, {
            error: {
              code: 'CONFLICT',
              message: 'Version mismatch',
              reason: 'LOYALTY_SCALE_VERSION_CONFLICT',
              current_version: 5,
            },
          });
        }
        return json(404, { detail: 'Not found' });
      });

      render(
        <QueryClientProvider client={new QueryClient()}>
          <AdminProvider>
            <ActiveBusinessProvider>
              <LocaleProvider initialLocale="ru">
                <MemoryRouter>
                  <StatusesPage />
                </MemoryRouter>
              </LocaleProvider>
            </ActiveBusinessProvider>
          </AdminProvider>
        </QueryClientProvider>
      );

      await user.click(await screen.findByRole('button', { name: 'Редактировать шкалу' }));
      await screen.findByText('Версия v1');

      const tier1Max = document.getElementById('scale-max-tier-1') as HTMLInputElement;
      await user.clear(tier1Max);
      await user.type(tier1Max, '275000');

      await user.click(screen.getByRole('button', { name: 'Сохранить шкалу' }));
      const alert = await screen.findByRole('alert');
      expect(alert).toHaveTextContent('актуальная версия: v5');

      // Unsaved input MUST be preserved and NO second automatic GET triggered
      expect(tier1Max.value).toBe('275000');
      expect(getCount).toBe(1);

      // Click explicit "Загрузить актуальную шкалу"
      await user.click(alert.querySelector('button')!);
      await waitFor(() => expect(getCount).toBe(2));
      expect(await screen.findByText('Версия v5')).toBeInTheDocument();
      expect((document.getElementById('scale-max-tier-1') as HTMLInputElement).value).toBe('200000.00');
    });

    it('highlights both conflicting rows/fields on 409 LOYALTY_SCALE_RANGE_OVERLAP and translates all 422/409 reasons in RU & KK', async () => {
      const user = userEvent.setup();
      setupEnvFetch('business_manager', async (url, init) => {
        if (url.pathname === `/admin/businesses/${businessId}/loyalty-tiers`) {
          return json(200, baseTiers);
        }
        if (url.pathname === `/admin/businesses/${businessId}/loyalty-tiers/scale` && (!init?.method || init.method === 'GET')) {
          return json(200, { business_id: businessId, version: 1, tiers: baseTiers });
        }
        if (url.pathname === `/admin/businesses/${businessId}/loyalty-tiers/scale` && init?.method === 'PUT') {
          return json(409, {
            error: {
              code: 'CONFLICT',
              message: 'Ranges overlap',
              reason: 'LOYALTY_SCALE_RANGE_OVERLAP',
              conflicts: [
                {
                  tier_id: 'tier-1',
                  other_tier_id: 'tier-2',
                  levels: [1, 2],
                  fields: ['min_turnover', 'max_turnover'],
                },
              ],
            },
          });
        }
        return json(404, { detail: 'Not found' });
      });

      render(
        <QueryClientProvider client={new QueryClient()}>
          <AdminProvider>
            <ActiveBusinessProvider>
              <LocaleProvider initialLocale="ru">
                <MemoryRouter>
                  <StatusesPage />
                </MemoryRouter>
              </LocaleProvider>
            </ActiveBusinessProvider>
          </AdminProvider>
        </QueryClientProvider>
      );

      await user.click(await screen.findByRole('button', { name: 'Редактировать шкалу' }));
      await screen.findByText('Версия v1');
      await user.click(screen.getByRole('button', { name: 'Сохранить шкалу' }));

      const alert = await screen.findByRole('alert');
      expect(alert).toHaveTextContent('Диапазоны активных уровней пересекаются (#1 ↔ #2)');
      expect(document.querySelector('[data-scale-tier-id="tier-1"]')).toHaveClass('scale-tier-card--conflict');
      expect(document.querySelector('[data-scale-tier-id="tier-2"]')).toHaveClass('scale-tier-card--conflict');
      expect(document.getElementById('scale-max-tier-1')).toHaveAttribute('aria-invalid', 'true');
      expect(document.getElementById('scale-min-tier-2')).toHaveAttribute('aria-invalid', 'true');

      // Direct reason-based translation tests for RU & KK (422 & unknown 409)
      const invalidRangeErr = errorFromResponse(422, {
        error: { code: 'VALIDATION_ERROR', message: 'bad', reason: 'LOYALTY_SCALE_INVALID_RANGE', tier_id: 'tier-1', fields: ['tiers[0].max_turnover'] },
      });
      expect(invalidRangeErr.detail?.fields).toEqual(['max_turnover']);
      expect(messageForError(invalidRangeErr, 'ru')).toContain('Некорректный диапазон оборота');
      expect(messageForError(invalidRangeErr, 'kk')).toContain('Айналым ауқымы қате');

      const incompleteErr = errorFromResponse(422, {
        error: { code: 'VALIDATION_ERROR', message: 'bad', reason: 'LOYALTY_SCALE_INCOMPLETE', tier_ids: ['tier-2'] },
      });
      expect(messageForError(incompleteErr, 'ru')).toContain('все существующие уровни бизнеса');
      expect(messageForError(incompleteErr, 'kk')).toContain('барлық қолданыстағы деңгейлері');

      const unknownTierErr = errorFromResponse(422, {
        error: { code: 'VALIDATION_ERROR', message: 'bad', reason: 'LOYALTY_SCALE_UNKNOWN_TIER', tier_ids: ['tier-x'] },
      });
      expect(messageForError(unknownTierErr, 'ru')).toContain('не найден или больше не относится');
      expect(messageForError(unknownTierErr, 'kk')).toContain('табылмады немесе бұл бизнеске тиесілі емес');

      const duplicateTierErr = errorFromResponse(422, {
        error: { code: 'VALIDATION_ERROR', message: 'bad', reason: 'LOYALTY_SCALE_DUPLICATE_TIER', tier_ids: ['tier-1'] },
      });
      expect(messageForError(duplicateTierErr, 'ru')).toContain('дублирующийся уровень');
      expect(messageForError(duplicateTierErr, 'kk')).toContain('қайталанатын деңгей');

      const unknown409 = errorFromResponse(409, {
        error: { code: 'CONFLICT', message: 'some unknown conflict', reason: 'SOMETHING_NEW' },
      });
      expect(messageForError(unknown409, 'ru')).toBe('Конфликт с уже существующими данными. Проверьте значения и повторите.');
    });

    it('falls back to single-tier legacy mode ONLY on 404/405 and NEVER masks 403/500/network errors', async () => {
      const user = userEvent.setup();
      let scaleStatus = 404;

      setupEnvFetch('business_manager', async url => {
        if (url.pathname === `/admin/businesses/${businessId}/loyalty-tiers`) {
          return json(200, baseTiers);
        }
        if (url.pathname === `/admin/businesses/${businessId}/loyalty-tiers/scale`) {
          if (scaleStatus === 0) throw new TypeError('Network failure');
          return json(scaleStatus, { detail: scaleStatus === 404 ? 'Not Found' : 'Error' });
        }
        return json(404, { detail: 'Not found' });
      });

      const { unmount } = render(
        <QueryClientProvider client={new QueryClient()}>
          <AdminProvider>
            <ActiveBusinessProvider>
              <LocaleProvider initialLocale="ru">
                <MemoryRouter>
                  <StatusesPage />
                </MemoryRouter>
              </LocaleProvider>
            </ActiveBusinessProvider>
          </AdminProvider>
        </QueryClientProvider>
      );

      // 404 -> falls back cleanly with honest unsupported notice and single-tier Edit buttons remaining active
      await user.click(await screen.findByRole('button', { name: 'Редактировать шкалу' }));
      expect(await screen.findByText(/Атомарное редактирование шкалы недоступно/)).toBeInTheDocument();
      expect(screen.getAllByRole('button', { name: 'Изменить' }).length).toBeGreaterThan(0);
      unmount();

      // 500 -> does NOT fall back, shows Server Unavailable error instead
      scaleStatus = 500;
      const qc2 = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      render(
        <QueryClientProvider client={qc2}>
          <AdminProvider>
            <ActiveBusinessProvider>
              <LocaleProvider initialLocale="ru">
                <MemoryRouter>
                  <StatusesPage />
                </MemoryRouter>
              </LocaleProvider>
            </ActiveBusinessProvider>
          </AdminProvider>
        </QueryClientProvider>
      );

      await user.click(await screen.findByRole('button', { name: 'Редактировать шкалу' }));
      expect(await screen.findByText(/Сервис временно недоступен/)).toBeInTheDocument();
      expect(screen.queryByText(/Атомарное редактирование шкалы недоступно/)).not.toBeInTheDocument();

      // Network failure shows Retry button and never falls back to legacy
      scaleStatus = 0;
      await user.click(screen.getByRole('button', { name: 'Закрыть редактор шкалы' }));
      await user.click(screen.getByRole('button', { name: 'Редактировать шкалу' }));
      expect(await screen.findByText(/Нет соединения/)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Повторить' })).toBeInTheDocument();
      expect(screen.queryByText(/Атомарное редактирование шкалы недоступно/)).not.toBeInTheDocument();
    });

    it('validates client decimal precision, negative/exponent rejection, and requires max or "Без предела" before PUT', async () => {
      const user = userEvent.setup();
      let putCalled = false;

      setupEnvFetch('business_manager', async (url, init) => {
        if (url.pathname === `/admin/businesses/${businessId}/loyalty-tiers`) {
          return json(200, baseTiers);
        }
        if (url.pathname === `/admin/businesses/${businessId}/loyalty-tiers/scale` && (!init?.method || init.method === 'GET')) {
          return json(200, { business_id: businessId, version: 1, tiers: baseTiers });
        }
        if (url.pathname === `/admin/businesses/${businessId}/loyalty-tiers/scale` && init?.method === 'PUT') {
          putCalled = true;
          return json(200, { business_id: businessId, version: 2, changed: true, tiers: baseTiers });
        }
        return json(404, { detail: 'Not found' });
      });

      render(
        <QueryClientProvider client={new QueryClient()}>
          <AdminProvider>
            <ActiveBusinessProvider>
              <LocaleProvider initialLocale="ru">
                <MemoryRouter>
                  <StatusesPage />
                </MemoryRouter>
              </LocaleProvider>
            </ActiveBusinessProvider>
          </AdminProvider>
        </QueryClientProvider>
      );

      await user.click(await screen.findByRole('button', { name: 'Редактировать шкалу' }));
      await screen.findByText('Версия v1');

      const tier1Min = document.getElementById('scale-min-tier-1') as HTMLInputElement;
      const tier2Unbounded = document.getElementById('scale-unbounded-tier-2') as HTMLInputElement;
      const tier2Max = document.getElementById('scale-max-tier-2') as HTMLInputElement;

      // Reject >2 decimals via direct change and reject unchecking "Без предела" with empty max
      fireEvent.change(tier1Min, { target: { value: '10.123' } });
      await user.click(tier2Unbounded);
      expect(tier2Max).not.toBeDisabled();

      await user.click(screen.getByRole('button', { name: 'Сохранить шкалу' }));
      expect(await screen.findByText(/не более 2 знаков после запятой/)).toBeInTheDocument();
      expect(screen.getByText(/Укажите максимальный оборот или отметьте «Без предела»/)).toBeInTheDocument();
      expect(putCalled).toBe(false);
    });
  });

  // Draft AuditPage behaviour, not in production 18.11; the draft and these checks live on wip/admin-audit-splash-drafts.
  describe.skip('K5 Audit Alignment: loyalty_scale_updated + safe tier/store projections + null handling', () => {
    const scaleAndPackageAuditRows: AuditItem[] = [
      {
        id: 'audit-scale-1',
        business_id: businessId,
        actor: 'keremet.manager',
        action: 'loyalty_scale_updated',
        entity: 'business_loyalty_scale',
        entity_id: businessId,
        before_state: {
          version: 1,
          tiers: [
            { tier_id: 'tier-1', level: 1, min_turnover: '0.00', max_turnover: '350000.00', percent: '1.00', is_active: true },
            { tier_id: 'tier-2', level: 2, min_turnover: '350000.00', max_turnover: null, percent: '3.00', is_active: true },
          ],
        },
        after_state: {
          version: 2,
          tiers: [
            { tier_id: 'tier-1', level: 1, min_turnover: '0.00', max_turnover: '500000.00', percent: '1.50', is_active: true },
            { tier_id: 'tier-2', level: 2, min_turnover: '500000.00', max_turnover: null, percent: '5.00', is_active: true },
          ],
        },
        created_at: '2026-11-16T09:00:00Z',
      },
      {
        id: 'audit-tier-create',
        business_id: businessId,
        actor: 'keremet.manager',
        action: 'loyalty_tier_created',
        entity: 'business_loyalty_tier',
        entity_id: 'tier-3',
        before_state: null,
        after_state: {
          tier_id: 'tier-secret-uuid-3',
          level: 3,
          name_ru: 'Платина',
          name_kk: 'Платина',
          min_turnover: '700000.00',
          max_turnover: null,
          percent: '5.00',
          is_active: true,
          image_url: 'https://hidden-from-manager.test/x.png',
          description_ru: 'скрытое описание',
        },
        created_at: '2026-11-16T08:00:00Z',
      },
      {
        id: 'audit-store-create',
        business_id: businessId,
        actor: 'keremet.manager',
        action: 'store_created',
        entity: 'business_store',
        entity_id: 'store-1',
        before_state: null,
        after_state: {
          store_id: 'store-secret-uuid-1',
          title_ru: 'Филиал Центр',
          title_kk: 'Орталық филиал',
          address_ru: 'ул. Абая, 10',
          address_kk: 'Абай к-сі, 10',
          sort_order: 1,
          is_active: true,
          phone: '+77001234567',
          map_url: 'https://maps.example.test/1',
        },
        created_at: '2026-11-16T07:00:00Z',
      },
      {
        id: 'audit-old-null',
        business_id: businessId,
        actor: 'keremet.manager',
        action: 'loyalty_scale_updated',
        entity: 'business_loyalty_scale',
        entity_id: businessId,
        before_state: null,
        after_state: null,
        created_at: '2026-11-16T06:00:00Z',
      },
    ];

    it('renders structured loyalty_scale_updated, tier/store whitelists, unbounded "без предела"/"шектеусіз", and honest null without secrets/IDs', async () => {
      setupEnvFetch('business_manager', url => {
        if (url.pathname === '/admin/audit') {
          return json(200, { items: scaleAndPackageAuditRows, limit: 25, offset: 0, has_more: false });
        }
        return json(200, {});
      });

      const { container, unmount } = render(
        <QueryClientProvider client={new QueryClient()}>
          <AdminProvider>
            <LocaleProvider initialLocale="ru">
              <AuditPage />
            </LocaleProvider>
          </AdminProvider>
        </QueryClientProvider>
      );

      expect(await screen.findAllByText('Обновлена шкала статусов лояльности')).toHaveLength(2);
      expect(screen.getAllByText('Шкала статусов').length).toBeGreaterThanOrEqual(2);
      expect(screen.getByText('[0 ₸ – 350 000 ₸) · 1% · Активен')).toBeInTheDocument();
      expect(screen.getByText('[500 000 ₸ – без предела) · 5% · Активен')).toBeInTheDocument();
      expect(screen.getByText('700 000 ₸')).toBeInTheDocument();
      expect(screen.getAllByText('без предела').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('Филиал Центр')).toBeInTheDocument();
      expect(screen.getByText('ул. Абая, 10')).toBeInTheDocument();

      // Both snapshots null: the values were not stored. Do not call that "no details".
      expect(screen.getAllByText('Данные об изменении не сохранялись').length).toBe(2);
      expect(screen.queryByText('Нет подробностей')).not.toBeInTheDocument();

      // Zero leakage of raw JSON, UUIDs, phone, or image/map URLs for business_manager
      const txt = container.textContent ?? '';
      expect(txt).not.toContain('Технические детали');
      expect(txt).not.toContain('tier-secret-uuid-3');
      expect(txt).not.toContain('store-secret-uuid-1');
      expect(txt).not.toContain('+77001234567');
      expect(txt).not.toContain('https://maps.example.test');
      expect(txt).not.toContain('https://hidden-from-manager.test');
      unmount();

      // KK locale verification
      render(
        <QueryClientProvider client={new QueryClient()}>
          <AdminProvider>
            <LocaleProvider initialLocale="kk">
              <AuditPage />
            </LocaleProvider>
          </AdminProvider>
        </QueryClientProvider>
      );
      expect(await screen.findAllByText('Адалдық дәрежелері шкаласы жаңартылды')).toHaveLength(2);
      expect(screen.getByText('[500 000 ₸ – шектеусіз) · 5% · Белсенді')).toBeInTheDocument();
      expect(screen.getAllByText('шектеусіз').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Өзгеріс туралы мәліметтер сақталмаған').length).toBe(2);
      expect(screen.queryByText('Толық мәлімет жоқ')).not.toBeInTheDocument();
    });

    it('never treats missing max_turnover key as null/unbounded in scale or tier audit entries', async () => {
      const partialRows: AuditItem[] = [
        {
          id: 'audit-scale-missing-max',
          business_id: businessId,
          actor: 'keremet.manager',
          action: 'loyalty_scale_updated',
          entity: 'business_loyalty_scale',
          entity_id: businessId,
          before_state: {
            version: 1,
            tiers: [{ tier_id: 'tier-1', level: 1, min_turnover: '0.00', percent: '1.00', is_active: true }],
          },
          after_state: {
            version: 2,
            tiers: [{ tier_id: 'tier-1', level: 1, min_turnover: '0.00', max_turnover: null, percent: '2.00', is_active: true }],
          },
          created_at: '2026-11-16T09:00:00Z',
        },
        {
          id: 'audit-tier-missing-max',
          business_id: businessId,
          actor: 'keremet.manager',
          action: 'loyalty_tier_updated',
          entity: 'business_loyalty_tier',
          entity_id: 'tier-1',
          before_state: { level: 1, name_ru: 'Базовый', min_turnover: '0.00', percent: '1.00' },
          after_state: { level: 1, name_ru: 'Базовый', min_turnover: '0.00', max_turnover: null, percent: '2.00' },
          created_at: '2026-11-16T08:30:00Z',
        },
      ];

      setupEnvFetch('business_manager', url => {
        if (url.pathname === '/admin/audit') {
          return json(200, { items: partialRows, limit: 25, offset: 0, has_more: false });
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

      expect(await screen.findByText('[0 ₸ – —) · 1% · Активен')).toBeInTheDocument();
      expect(screen.getByText('[0 ₸ – без предела) · 2% · Активен')).toBeInTheDocument();
      // Only after_state sides (2 rows) have explicit null -> exact 2 occurrences, never fabricated from absent before_state keys
      expect(screen.getAllByText(/без предела/)).toHaveLength(2);
      expect(container.textContent ?? '').not.toContain('Пусто');
    });
  });

  describe('K4 Full Create -> Edit Promo Lifecycle (Banner & Offer)', () => {
    it('uploads image, creates new banner/offer via POST 201, reopens and updates via PATCH with preserved null vs explicit schedule', async () => {
      const user = userEvent.setup();
      let promos: Array<Record<string, unknown>> = [];
      let uploadedCount = 0;

      setupEnvFetch('business_manager', async (url, init) => {
        if (url.pathname === '/admin/media/images' && init?.method === 'POST') {
          uploadedCount += 1;
          return json(201, {
            url: `https://cdn.example.test/uploaded-${uploadedCount}.webp`,
            width: 800,
            height: 600,
            bytes: 1024,
          });
        }
        if (url.pathname === '/admin/promotions' && (!init?.method || init.method === 'GET')) {
          const kindFilter = url.searchParams.get('kind');
          const items = kindFilter ? promos.filter(p => p.kind === kindFilter) : promos;
          return json(200, { items, limit: 25, offset: 0, has_more: false });
        }
        if (url.pathname === '/admin/promotions' && init?.method === 'POST') {
          const body = JSON.parse(String(init.body)) as Record<string, unknown>;
          const created = {
            id: `promo-${promos.length + 1}`,
            business_id: businessId,
            business_name: 'Keremet',
            created_at: '2026-11-16T10:00:00Z',
            updated_at: '2026-11-16T10:00:00Z',
            ...body,
          };
          promos = [created, ...promos];
          return json(201, created);
        }
        if (url.pathname.startsWith('/admin/promotions/') && init?.method === 'PATCH') {
          const id = url.pathname.split('/').pop()!;
          const body = JSON.parse(String(init.body)) as Record<string, unknown>;
          let updated: Record<string, unknown> | null = null;
          promos = promos.map(p => {
            if (p.id !== id) return p;
            updated = { ...p, ...body };
            return updated;
          });
          return json(200, updated);
        }
        return json(200, []);
      });

      render(
        <QueryClientProvider client={new QueryClient()}>
          <AdminProvider>
            <ActiveBusinessProvider>
              <LocaleProvider initialLocale="ru">
                <MemoryRouter>
                  <ContentPage />
                </MemoryRouter>
              </LocaleProvider>
            </ActiveBusinessProvider>
          </AdminProvider>
        </QueryClientProvider>
      );

      // Create Banner with uploaded image & null starts_at / null ends_at
      await user.click(await screen.findByRole('button', { name: 'Добавить баннер' }));
      await user.type(screen.getByLabelText('Заголовок'), 'Новый зимний баннер');
      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      await user.upload(fileInput, new File(['png'], 'banner.png', { type: 'image/png' }));
      await waitFor(() => expect(screen.getByLabelText('Картинка (HTTPS URL)')).toHaveValue('https://cdn.example.test/uploaded-1.webp'));

      await user.click(screen.getByRole('button', { name: 'Сохранить' }));
      expect(await screen.findByText('Новый зимний баннер')).toBeInTheDocument();
      expect(promos[0]).toMatchObject({
        kind: 'banner',
        title: 'Новый зимний баннер',
        starts_at: null,
        ends_at: null,
        image_url: 'https://cdn.example.test/uploaded-1.webp',
      });

      // Reopen & PATCH title -> keeps starts_at/ends_at null
      await user.click(screen.getByRole('button', { name: 'Изменить' }));
      const titleInput = screen.getByLabelText('Заголовок');
      await user.clear(titleInput);
      await user.type(titleInput, 'Обновлённый зимний баннер');
      await user.click(screen.getByRole('button', { name: 'Сохранить' }));
      expect(await screen.findByText('Обновлённый зимний баннер')).toBeInTheDocument();
      expect(promos[0]).toMatchObject({ starts_at: null, ends_at: null });

      // Ensure ApiError import stays referenced in type-check
      expect(ApiError).toBeDefined();
    }, 15_000);
  });

  describe('StatusesPage role-gated businesses query', () => {
    it('does not request GET /admin/businesses when opened as business_manager while loading own tiers and scale', async () => {
      const user = userEvent.setup();
      const requestedPaths: string[] = [];

      setupEnvFetch('business_manager', url => {
        requestedPaths.push(url.pathname + url.search);
        if (url.pathname === '/admin/businesses') {
          throw new Error('business_manager must not request /admin/businesses');
        }
        if (url.pathname === `/admin/businesses/${businessId}/loyalty-tiers`) {
          return json(200, baseTiers);
        }
        if (url.pathname === `/admin/businesses/${businessId}/loyalty-tiers/scale`) {
          return json(200, { version: 1, tiers: baseTiers });
        }
        return json(200, {});
      });

      render(
        <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
          <AdminProvider>
            <ActiveBusinessProvider>
              <LocaleProvider initialLocale="ru">
                <MemoryRouter>
                  <StatusesPage />
                </MemoryRouter>
              </LocaleProvider>
            </ActiveBusinessProvider>
          </AdminProvider>
        </QueryClientProvider>
      );

      expect(await screen.findByText('Бронза')).toBeInTheDocument();
      await user.click(screen.getByRole('button', { name: 'Редактировать шкалу' }));
      expect(await screen.findByText('Версия v1')).toBeInTheDocument();
      expect(requestedPaths.some(p => p.startsWith('/admin/businesses?'))).toBe(false);
    });

    it('requests GET /admin/businesses as superadmin and switches business tiers', async () => {
      const user = userEvent.setup();
      const biz2Id = '22222222-2222-2222-2222-222222222222';
      const requestedPaths: string[] = [];

      setupEnvFetch('superadmin', url => {
        requestedPaths.push(url.pathname + url.search);
        if (url.pathname === '/admin/businesses') {
          return json(200, {
            items: [
              { id: businessId, name: 'Keremet', logo_url: null, android_app_id: null },
              { id: biz2Id, name: 'Alma', logo_url: null, android_app_id: null },
            ],
            limit: 100,
            offset: 0,
            has_more: false,
          });
        }
        if (url.pathname === `/admin/businesses/${businessId}/loyalty-tiers`) {
          return json(200, baseTiers);
        }
        if (url.pathname === `/admin/businesses/${biz2Id}/loyalty-tiers`) {
          return json(200, [
            {
              ...baseTiers[0],
              id: 'tier-biz2-1',
              business_id: biz2Id,
              name_ru: 'Алма Уровень',
              name_kk: 'Алма Дәреже',
            },
          ]);
        }
        return json(200, {});
      });

      render(
        <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
          <AdminProvider>
            <ActiveBusinessProvider>
              <LocaleProvider initialLocale="ru">
                <MemoryRouter>
                  <StatusesPage />
                </MemoryRouter>
              </LocaleProvider>
            </ActiveBusinessProvider>
          </AdminProvider>
        </QueryClientProvider>
      );

      expect(await screen.findByText('Бронза')).toBeInTheDocument();
      expect(requestedPaths).toContain('/admin/businesses?limit=100&offset=0');

      const select = screen.getByLabelText('Бизнес:');
      await user.selectOptions(select, biz2Id);
      expect(await screen.findByText('Алма Уровень')).toBeInTheDocument();
    });
  });
});
