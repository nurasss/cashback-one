import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { AuditItem, Business, LoyaltyTier } from '../src/api/types';
import { AdminProvider } from '../src/auth/provider';
import { AgentCreateDialog } from '../src/features/AdminMutations';
import { BusinessSplashSection, StoreDialog } from '../src/features/BusinessAppContent';
import { LocaleProvider } from '../src/i18n/LocaleContext';
import { AuditPage } from '../src/pages/AuditPage';
import { ContentPage, NotificationDialog, PromotionDialog } from '../src/pages/ContentPage';
import { DashboardPage } from '../src/pages/DashboardPage';
import { NotificationsPage } from '../src/pages/NotificationsPage';
import { OperationsPage } from '../src/pages/OperationsPage';
import { StatusesPage, TierDialog } from '../src/pages/StatusesPage';

const access = { access_token: 'fixture-access', token_type: 'bearer', expires_in: 900 };
const primaryBusinessId = '11111111-1111-1111-1111-111111111111';

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

function makeBusinesses(count: number): Business[] {
  return Array.from({ length: count }, (_, idx) => {
    const num = String(idx + 1).padStart(3, '0');
    return {
      id: idx === 0 ? primaryBusinessId : `biz-${num}`,
      name: `Biz ${num}`,
      logo_url: null,
      colors: null,
      barcode_prefixes: [],
      android_app_id: null,
      status: 'active',
      created_at: '2026-11-01T00:00:00Z',
      updated_at: '2026-11-01T00:00:00Z',
    };
  });
}

function makeScaleTiers(
  count: number,
  options?: {
    offsetMin?: number;
    pctBonus?: number;
    inactiveLevels?: number[];
    omitMaxOnLevels?: number[];
  }
) {
  const inactiveSet = new Set(options?.inactiveLevels ?? []);
  const omitMaxSet = new Set(options?.omitMaxOnLevels ?? []);
  const offsetMin = options?.offsetMin ?? 0;
  const pctBonus = options?.pctBonus ?? 0;
  return Array.from({ length: count }, (_, idx) => {
    const level = idx + 1;
    const min = idx * 10000 + offsetMin;
    const max = level === count ? null : (idx + 1) * 10000 + offsetMin;
    const base: Record<string, unknown> = {
      tier_id: `tier-secret-uuid-${level}`,
      level,
      min_turnover: String(min),
      percent: String(level + pctBonus),
      is_active: !inactiveSet.has(level),
    };
    if (!omitMaxSet.has(level)) {
      base.max_turnover = max === null ? null : String(max);
    }
    return base;
  });
}

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
            business: role === 'business_manager'
              ? { id: primaryBusinessId, name: 'Keremet', status: 'active' }
              : null,
          },
          admin_stats_unlimited_period: true,
          admin_max_stats_period_days: 3650,
        });
      }
      return handler(url, init);
    })
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  window.localStorage.clear();
});

describe('Admin Audit UI Rework (2026-11-16)', () => {
  describe('1. K5: AuditPage completeness beyond 8 items (27 & 100 tiers, first/last/all, alignment, fields, isolation)', () => {
    it('expands all 27 changed tiers synchronously on ДО/ПОСЛЕ in RU & KK without leaking UUIDs or raw JSON', async () => {
      const user = userEvent.setup();
      const scale27Row: AuditItem = {
        id: 'audit-scale-27',
        business_id: primaryBusinessId,
        actor: 'keremet.manager',
        action: 'loyalty_scale_updated',
        entity: 'business_loyalty_scale',
        before_state: {
          version: 1,
          tiers: makeScaleTiers(27, { inactiveLevels: [26] }),
        },
        after_state: {
          version: 2,
          tiers: makeScaleTiers(27, { offsetMin: 500, pctBonus: 1, inactiveLevels: [25] }),
        },
        created_at: '2026-11-16T10:00:00Z',
      };

      setupEnvFetch('business_manager', url => {
        if (url.pathname === '/admin/audit') {
          return json(200, { items: [scale27Row], limit: 25, offset: 0, has_more: false });
        }
        return json(200, {});
      });

      const { container, unmount } = render(
        <AdminProvider>
          <LocaleProvider initialLocale="ru">
            <AuditPage />
          </LocaleProvider>
        </AdminProvider>
      );

      expect(await screen.findByText('Обновлена шкала статусов лояльности')).toBeInTheDocument();
      // Initially capped at 8 rows with explicit hidden count 19 of 27
      expect(screen.getAllByText('Скрыто ещё 19 из 27')).toHaveLength(2);
      expect(screen.queryByText('#27:')).not.toBeInTheDocument();
      expect(screen.queryByText('#9:')).not.toBeInTheDocument();

      // Click expand button in ДО -> expands BOTH ДО and ПОСЛЕ
      const expandButtons = screen.getAllByRole('button', { name: 'Показать все (27)' });
      expect(expandButtons).toHaveLength(2);
      await user.click(expandButtons[0]!);

      expect(screen.getAllByText('#1:')).toHaveLength(2);
      expect(screen.getAllByText('#9:')).toHaveLength(2);
      expect(screen.getAllByText('#25:')).toHaveLength(2);
      expect(screen.getAllByText('#26:')).toHaveLength(2);
      expect(screen.getAllByText('#27:')).toHaveLength(2);
      // Numbers before/after, inactive, unbounded null
      expect(screen.getByText('[250 000 ₸ – 260 000 ₸) · 26% · Скрыт')).toBeInTheDocument();
      expect(screen.getByText('[240 500 ₸ – 250 500 ₸) · 26% · Скрыт')).toBeInTheDocument();
      expect(screen.getByText('[260 000 ₸ – без предела) · 27% · Активен')).toBeInTheDocument();
      expect(screen.getByText('[260 500 ₸ – без предела) · 28% · Активен')).toBeInTheDocument();

      // Zero leakage of raw JSON or tier UUIDs to business_manager
      const txt = container.textContent ?? '';
      expect(txt).not.toContain('tier-secret-uuid');
      expect(txt).not.toContain('Технические детали');

      // Collapse works symmetrically
      const collapseButtons = screen.getAllByRole('button', { name: 'Свернуть подробности' });
      expect(collapseButtons).toHaveLength(2);
      await user.click(collapseButtons[1]!);
      expect(screen.queryByText('#27:')).not.toBeInTheDocument();
      unmount();

      // KK locale verification
      render(
        <AdminProvider>
          <LocaleProvider initialLocale="kk">
            <AuditPage />
          </LocaleProvider>
        </AdminProvider>
      );
      expect(await screen.findByText('Адалдық дәрежелері шкаласы жаңартылды')).toBeInTheDocument();
      expect(screen.getAllByText('Тағы 19 жасырылды (барлығы 27)')).toHaveLength(2);
      const kkExpand = screen.getAllByRole('button', { name: 'Барлығын көрсету (27)' });
      await user.click(kkExpand[0]!);
      expect(screen.getByText('[250 000 ₸ – 260 000 ₸) · 26% · Жасырын')).toBeInTheDocument();
      expect(screen.getByText('[260 500 ₸ – шектеусіз) · 28% · Белсенді')).toBeInTheDocument();
      expect(screen.getAllByRole('button', { name: 'Мәліметті жию' })).toHaveLength(2);
    });

    it('handles 100 levels (all changed, first-only, last-only) without truncation or raw JSON', async () => {
      const user = userEvent.setup();
      const before100All = makeScaleTiers(100);
      const after100All = makeScaleTiers(100, { pctBonus: 1, inactiveLevels: [99] });

      const after100FirstOnly = makeScaleTiers(100);
      after100FirstOnly[0] = { ...after100FirstOnly[0]!, percent: '9' };

      const after100LastOnly = makeScaleTiers(100);
      after100LastOnly[99] = { ...after100LastOnly[99]!, percent: '99', max_turnover: null };

      const rows: AuditItem[] = [
        {
          id: 'scale-100-all',
          business_id: primaryBusinessId,
          actor: 'keremet.manager',
          action: 'loyalty_scale_updated',
          entity: 'business_loyalty_scale',
          before_state: { version: 10, tiers: before100All },
          after_state: { version: 11, tiers: after100All },
          created_at: '2026-11-16T10:03:00Z',
        },
        {
          id: 'scale-100-first',
          business_id: primaryBusinessId,
          actor: 'keremet.manager',
          action: 'loyalty_scale_updated',
          entity: 'business_loyalty_scale',
          before_state: { version: 11, tiers: before100All },
          after_state: { version: 12, tiers: after100FirstOnly },
          created_at: '2026-11-16T10:02:00Z',
        },
        {
          id: 'scale-100-last',
          business_id: primaryBusinessId,
          actor: 'keremet.manager',
          action: 'loyalty_scale_updated',
          entity: 'business_loyalty_scale',
          before_state: { version: 12, tiers: before100All },
          after_state: { version: 13, tiers: after100LastOnly },
          created_at: '2026-11-16T10:01:00Z',
        },
      ];

      setupEnvFetch('business_manager', url => {
        if (url.pathname === '/admin/audit') {
          return json(200, { items: rows, limit: 25, offset: 0, has_more: false });
        }
        return json(200, {});
      });

      const { container } = render(
        <AdminProvider>
          <LocaleProvider initialLocale="ru">
            <AuditPage />
          </LocaleProvider>
        </AdminProvider>
      );

      expect(await screen.findAllByText('Скрыто ещё 92 из 100')).toHaveLength(2);
      // First-only & last-only rows already show #100 and #1 without needing expand
      expect(screen.getAllByText('#100:')).toHaveLength(2);
      expect(screen.getByText('[990 000 ₸ – без предела) · 99% · Активен')).toBeInTheDocument();

      // Expand the 100-tier event
      await user.click(screen.getAllByRole('button', { name: 'Показать все (100)' })[0]!);
      expect(screen.getAllByText('#99:')).toHaveLength(2);
      expect(screen.getAllByText('#100:')).toHaveLength(4);
      expect(screen.getByText('[980 000 ₸ – 990 000 ₸) · 100% · Скрыт')).toBeInTheDocument();
      expect(container.textContent ?? '').not.toContain('tier-secret-uuid');
    });

    it('keeps ДО and ПОСЛЕ aligned when tiers differ (4 vs 5, missing max_turnover, missing before_state)', async () => {
      const user = userEvent.setup();
      const tiers5 = makeScaleTiers(5);
      const tiers4 = tiers5.slice(0, 4);

      const beforeMissingMax = makeScaleTiers(10, { omitMaxOnLevels: [9, 10] });
      const afterExplicitNullMax = makeScaleTiers(10, { pctBonus: 1 });
      afterExplicitNullMax[8] = { ...afterExplicitNullMax[8]!, max_turnover: null };

      const rows: AuditItem[] = [
        {
          id: 'asym-5-vs-4',
          business_id: primaryBusinessId,
          actor: 'keremet.manager',
          action: 'loyalty_scale_updated',
          entity: 'business_loyalty_scale',
          before_state: { version: 1, tiers: tiers5 },
          after_state: { version: 2, tiers: tiers4 },
          created_at: '2026-11-16T10:03:00Z',
        },
        {
          id: 'missing-max-10',
          business_id: primaryBusinessId,
          actor: 'keremet.manager',
          action: 'loyalty_scale_updated',
          entity: 'business_loyalty_scale',
          before_state: { version: 3, tiers: beforeMissingMax },
          after_state: { version: 4, tiers: afterExplicitNullMax },
          created_at: '2026-11-16T10:02:00Z',
        },
        {
          id: 'null-before-12',
          business_id: primaryBusinessId,
          actor: 'keremet.manager',
          action: 'loyalty_scale_updated',
          entity: 'business_loyalty_scale',
          before_state: null,
          after_state: { version: 5, tiers: makeScaleTiers(12) },
          created_at: '2026-11-16T10:01:00Z',
        },
      ];

      setupEnvFetch('business_manager', url => {
        if (url.pathname === '/admin/audit') {
          return json(200, { items: rows, limit: 25, offset: 0, has_more: false });
        }
        return json(200, {});
      });

      const { container } = render(
        <AdminProvider>
          <LocaleProvider initialLocale="ru">
            <AuditPage />
          </LocaleProvider>
        </AdminProvider>
      );

      await screen.findByText('v1');
      const tableRows = container.querySelectorAll('tbody tr');
      expect(tableRows).toHaveLength(3);

      // Row 1 (5 vs 4): both ДО and ПОСЛЕ align strictly on #5 (NOT #5 in ДО vs #1..#4 in ПОСЛЕ!)
      const row1Cells = tableRows[0]!.querySelectorAll('td');
      expect(row1Cells[4]!.textContent).toContain('#5:');
      expect(row1Cells[4]!.textContent).not.toContain('#1:');
      expect(row1Cells[5]!.textContent).toContain('#5:');
      expect(row1Cells[5]!.textContent).toContain('—');
      expect(row1Cells[5]!.textContent).not.toContain('#1:');

      // Row 2 (10 tiers with omitted max_turnover before -> explicit null after): expand and verify honest — vs без предела
      await user.click(within(tableRows[1]! as HTMLElement).getAllByRole('button', { name: 'Показать все (10)' })[0]!);
      const row2Cells = tableRows[1]!.querySelectorAll('td');
      expect(within(row2Cells[4]! as HTMLElement).getByText('[80 000 ₸ – —) · 9% · Активен')).toBeInTheDocument();
      expect(within(row2Cells[5]! as HTMLElement).getByText('[80 000 ₸ – без предела) · 10% · Активен')).toBeInTheDocument();
      expect(row2Cells[4]!.textContent).not.toContain('без предела');

      // Row 3 (null before_state + 12 tiers after): before stays honest Нет подробностей, after expands to 12
      const row3Cells = tableRows[2]!.querySelectorAll('td');
      expect(row3Cells[4]!.textContent).toBe('Нет подробностей');
      await user.click(within(row3Cells[5]! as HTMLElement).getByRole('button', { name: 'Показать все (12)' }));
      expect(row3Cells[5]!.textContent).toContain('#12:');
    });

    it('renders all >8 changed whitelisted fields in getDiffKeys while preserving whitelist and secret scrubbing', async () => {
      const user = userEvent.setup();
      const row12Fields: AuditItem = {
        id: 'audit-12-fields',
        business_id: primaryBusinessId,
        actor: 'keremet.manager',
        action: 'business_updated',
        entity: 'business',
        before_state: {
          title_ru: 'Заг-1-old',
          title_kk: 'ЗагKK-old',
          subtitle_ru: 'Подз-old',
          subtitle_kk: 'ПодзKK-old',
          kind: 'offer',
          is_active: true,
          sort_order: 1,
          percent: '1',
          about_ru: 'О нас old',
          about_kk: 'Біз туралы old',
          support_phone: '+77001110001',
          support_whatsapp: '+77001110002',
          unknown_internal_flag: 'secret-leak-old',
          api_key_hash: 'deadbeef1',
        },
        after_state: {
          title_ru: 'Заг-1-new',
          title_kk: 'ЗагKK-new',
          subtitle_ru: 'Подз-new',
          subtitle_kk: 'ПодзKK-new',
          kind: 'banner',
          is_active: false,
          sort_order: 9,
          percent: '5',
          about_ru: 'О нас new',
          about_kk: 'Біз туралы new',
          support_phone: '+77002220001',
          support_whatsapp: '+77002220002',
          unknown_internal_flag: 'secret-leak-new',
          password_token: '[REDACTED]',
        },
        created_at: '2026-11-16T10:00:00Z',
      };

      setupEnvFetch('business_manager', url => {
        if (url.pathname === '/admin/audit') {
          return json(200, { items: [row12Fields], limit: 25, offset: 0, has_more: false });
        }
        return json(200, {});
      });

      const { container } = render(
        <AdminProvider>
          <LocaleProvider initialLocale="ru">
            <AuditPage />
          </LocaleProvider>
        </AdminProvider>
      );

      expect(await screen.findAllByText('Скрыто ещё 4 из 12')).toHaveLength(2);
      expect(screen.queryByText('+77002220002')).not.toBeInTheDocument();

      await user.click(screen.getAllByRole('button', { name: 'Показать все (12)' })[0]!);
      expect(screen.getByText('+77001110002')).toBeInTheDocument();
      expect(screen.getByText('+77002220002')).toBeInTheDocument();
      expect(screen.getByText('О нас new')).toBeInTheDocument();

      const text = container.textContent ?? '';
      expect(text).not.toContain('unknown_internal_flag');
      expect(text).not.toContain('secret-leak');
      expect(text).not.toContain('deadbeef1');
      expect(text).not.toContain('[REDACTED]');
    });

    it('does not break outer Показать ещё or Pagination when expanding details of one audit row', async () => {
      const user = userEvent.setup();
      const rowsPage1: AuditItem[] = Array.from({ length: 12 }, (_, idx) => ({
        id: `audit-ev-${idx + 1}`,
        business_id: primaryBusinessId,
        actor: 'keremet.manager',
        action: idx === 0 ? 'loyalty_scale_updated' : 'store_updated',
        entity: idx === 0 ? 'business_loyalty_scale' : 'business_store',
        before_state: idx === 0
          ? { version: 1, tiers: makeScaleTiers(27) }
          : { title_ru: `Магазин old ${idx + 1}` },
        after_state: idx === 0
          ? { version: 2, tiers: makeScaleTiers(27, { pctBonus: 1 }) }
          : { title_ru: `Магазин new ${idx + 1}` },
        created_at: `2026-11-16T10:${String(59 - idx).padStart(2, '0')}:00Z`,
      }));
      const rowsPage2: AuditItem[] = [
        {
          id: 'audit-ev-page2',
          business_id: primaryBusinessId,
          actor: 'keremet.manager',
          action: 'store_created',
          entity: 'business_store',
          before_state: null,
          after_state: { title_ru: 'Магазин стр 2' },
          created_at: '2026-11-16T09:00:00Z',
        },
      ];

      setupEnvFetch('business_manager', url => {
        if (url.pathname === '/admin/audit') {
          const offset = Number(url.searchParams.get('offset') ?? 0);
          return json(200, {
            items: offset === 0 ? rowsPage1 : rowsPage2,
            limit: 25,
            offset,
            has_more: offset === 0,
          });
        }
        return json(200, {});
      });

      const { container } = render(
        <AdminProvider>
          <LocaleProvider initialLocale="ru">
            <AuditPage />
          </LocaleProvider>
        </AdminProvider>
      );

      await screen.findByText('Магазин new 2');
      // Initially compact table shows 7 events and outer Показать ещё
      expect(container.querySelectorAll('tbody tr')).toHaveLength(7);
      expect(screen.getByRole('button', { name: 'Показать ещё' })).toBeInTheDocument();

      // Expand row 1's 27 tiers
      await user.click(screen.getAllByRole('button', { name: 'Показать все (27)' })[0]!);
      expect(screen.getAllByText('#27:')).toHaveLength(2);
      // Outer table still compacted at 7 events and outer Показать ещё still works
      expect(container.querySelectorAll('tbody tr')).toHaveLength(7);
      await user.click(screen.getByRole('button', { name: 'Показать ещё' }));
      expect(container.querySelectorAll('tbody tr')).toHaveLength(12);
      expect(screen.getByText('Магазин new 12')).toBeInTheDocument();
      // Row 1 remained expanded!
      expect(screen.getAllByText('#27:')).toHaveLength(2);

      // Navigate to outer page 2 cleanly
      await user.click(screen.getByRole('button', { name: 'Далее' }));
      expect(await screen.findByText('Магазин стр 2')).toBeInTheDocument();
    });
  });

  describe('2. П6: All business selectors load all pages (101 & 205 businesses, errors, selection preservation, manager isolation)', () => {
    function setupPagedBusinessesFetch(
      allBusinesses: Business[],
      options?: {
        overlapPage2?: boolean;
        failOffset?: number;
        failLoopPage?: boolean;
        onBusinessRequest?: (offset: number) => void;
      }
    ) {
      let failedOnce = false;
      const requestedUrls: string[] = [];

      setupEnvFetch('superadmin', url => {
        if (url.pathname === '/admin/businesses') {
          const limit = Number(url.searchParams.get('limit') ?? 25);
          const offset = Number(url.searchParams.get('offset') ?? 0);
          requestedUrls.push(`${url.pathname}?limit=${limit}&offset=${offset}`);
          options?.onBusinessRequest?.(offset);

          if (options?.failOffset !== undefined && offset === options.failOffset && !failedOnce) {
            failedOnce = true;
            return json(500, { error: { code: 'SERVER_UNAVAILABLE' } });
          }
          if (options?.failLoopPage && offset > 0) {
            return json(200, {
              items: allBusinesses.slice(0, limit),
              limit,
              offset,
              has_more: true,
            });
          }

          let slice = allBusinesses.slice(offset, offset + limit);
          let hasMore = offset + limit < allBusinesses.length;
          if (options?.overlapPage2 && allBusinesses.length > 100) {
            if (offset === 100) {
              // Simulate concurrent update shifting item #100 onto page 2 while keeping page size = 100
              slice = allBusinesses.slice(99, 199);
              hasMore = true;
            } else if (offset === 200) {
              slice = allBusinesses.slice(199);
              hasMore = false;
            }
          }
          return json(200, { items: slice, limit, offset, has_more: hasMore });
        }
        if (url.pathname === '/admin/dashboard') {
          return json(200, {
            business_id: null,
            business_name: null,
            period_from: '2026-10-18T00:00:00Z',
            period_to: '2026-11-16T23:59:59Z',
            period_days: 30,
            customers_with_business_cards: 1,
            cards: 1,
            unblocked_cards: 1,
            transactions: 1,
            agents: { online: 1, stale: 0, never_connected: 0, error: 0, disabled: 0 },
          });
        }
        if (url.pathname.endsWith('/loyalty-tiers')) {
          return json(200, []);
        }
        return json(200, { items: [], limit: 25, offset: 0, has_more: false });
      });

      return requestedUrls;
    }

    it('loads 205 businesses across Dashboard, Operations, Statuses, Notifications, Content/BusinessPicker, PromotionDialog, NotificationDialog with 0 duplicates and preserves selection', async () => {
      const user = userEvent.setup();
      const biz205 = makeBusinesses(205);
      const requestedUrls = setupPagedBusinessesFetch(biz205, { overlapPage2: true });

      const checkSelectHasAll205 = async (select: HTMLSelectElement, hasAllOption: boolean) => {
        await waitFor(() => {
          expect(select.querySelectorAll('option')).toHaveLength(hasAllOption ? 206 : 205);
        });
        const values = Array.from(select.querySelectorAll('option')).map(o => o.getAttribute('value'));
        const nonEmpty = values.filter(Boolean);
        expect(new Set(nonEmpty).size).toBe(205);
        expect(nonEmpty).toContain('biz-101');
        expect(nonEmpty).toContain('biz-150');
        expect(nonEmpty).toContain('biz-205');
      };

      // 1. DashboardPage
      const d1 = render(
        <AdminProvider>
          <MemoryRouter>
            <LocaleProvider initialLocale="ru">
              <DashboardPage />
            </LocaleProvider>
          </MemoryRouter>
        </AdminProvider>
      );
      const dashSelect = (await screen.findByLabelText('Бизнес')) as HTMLSelectElement;
      await checkSelectHasAll205(dashSelect, true);
      expect(dashSelect.value).toBe(''); // Все бизнесы preserved
      await user.selectOptions(dashSelect, 'biz-205');
      expect(dashSelect.value).toBe('biz-205');
      d1.unmount();

      // Verify offset=0 was called once per fresh AdminProvider, never looped
      expect(requestedUrls.filter(u => u === '/admin/businesses?limit=100&offset=0')).toHaveLength(1);
      expect(requestedUrls.filter(u => u === '/admin/businesses?limit=100&offset=100')).toHaveLength(1);
      expect(requestedUrls.filter(u => u === '/admin/businesses?limit=100&offset=200')).toHaveLength(1);

      // 2. OperationsPage
      const d2 = render(
        <AdminProvider>
          <MemoryRouter>
            <LocaleProvider initialLocale="ru">
              <OperationsPage />
            </LocaleProvider>
          </MemoryRouter>
        </AdminProvider>
      );
      const opsSelect = (await screen.findByLabelText('Бизнес поиска')) as HTMLSelectElement;
      await checkSelectHasAll205(opsSelect, true);
      await user.selectOptions(opsSelect, 'biz-150');
      expect(opsSelect.value).toBe('biz-150');
      d2.unmount();

      // 3. StatusesPage
      const d3 = render(
        <AdminProvider>
          <MemoryRouter>
            <LocaleProvider initialLocale="ru">
              <StatusesPage />
            </LocaleProvider>
          </MemoryRouter>
        </AdminProvider>
      );
      const statusSelect = (await screen.findByLabelText('Бизнес:')) as HTMLSelectElement;
      await checkSelectHasAll205(statusSelect, false);
      await user.selectOptions(statusSelect, 'biz-205');
      expect(statusSelect.value).toBe('biz-205');
      d3.unmount();

      // 4. NotificationsPage + NotificationDialog BusinessPicker
      const d4 = render(
        <AdminProvider>
          <MemoryRouter>
            <LocaleProvider initialLocale="ru">
              <NotificationsPage />
            </LocaleProvider>
          </MemoryRouter>
        </AdminProvider>
      );
      const noticeFilterSelect = (await screen.findByLabelText('Бизнес')) as HTMLSelectElement;
      await checkSelectHasAll205(noticeFilterSelect, true);
      await user.click(screen.getByRole('button', { name: 'Создать рассылку' }));
      const noteDialogSelect = (await within(await screen.findByRole('dialog')).findByLabelText('Кому')) as HTMLSelectElement;
      await checkSelectHasAll205(noteDialogSelect, true);
      await user.selectOptions(noteDialogSelect, 'biz-205');
      expect(noteDialogSelect.value).toBe('biz-205');
      d4.unmount();

      // 5. ContentPage filter + PromotionDialog BusinessPicker
      const d5 = render(
        <AdminProvider>
          <MemoryRouter>
            <LocaleProvider initialLocale="ru">
              <ContentPage />
            </LocaleProvider>
          </MemoryRouter>
        </AdminProvider>
      );
      const contentFilterSelect = (await screen.findByLabelText('Бизнес')) as HTMLSelectElement;
      await checkSelectHasAll205(contentFilterSelect, true);
      await user.click(screen.getByRole('button', { name: 'Добавить акцию' }));
      const promoDialogSelect = (await within(await screen.findByRole('dialog')).findByLabelText('Для кого')) as HTMLSelectElement;
      await checkSelectHasAll205(promoDialogSelect, true);
      await user.selectOptions(promoDialogSelect, 'biz-101');
      expect(promoDialogSelect.value).toBe('biz-101');
      d5.unmount();

      // Across all 5 screens (including multi-consumer NotificationsPage+Dialog and ContentPage+Picker+Dialog),
      // each offset is fetched once per fresh QueryClient without duplicate or competing requests.
      expect(requestedUrls.filter(u => u === '/admin/businesses?limit=100&offset=0')).toHaveLength(5);
      expect(requestedUrls.filter(u => u === '/admin/businesses?limit=100&offset=100')).toHaveLength(5);
      expect(requestedUrls.filter(u => u === '/admin/businesses?limit=100&offset=200')).toHaveLength(5);
    });

    it('reaches business #101 across 101 businesses and reaches #205 in AgentCreateDialog', async () => {
      const user = userEvent.setup();
      setupPagedBusinessesFetch(makeBusinesses(101));

      const d1 = render(
        <AdminProvider>
          <MemoryRouter>
            <LocaleProvider initialLocale="ru">
              <DashboardPage />
            </LocaleProvider>
          </MemoryRouter>
        </AdminProvider>
      );
      const select101 = (await screen.findByLabelText('Бизнес')) as HTMLSelectElement;
      await waitFor(() => expect(select101.querySelectorAll('option')).toHaveLength(102));
      await user.selectOptions(select101, 'biz-101');
      expect(select101.value).toBe('biz-101');
      d1.unmount();

      // AgentCreateDialog across 3 pages (205 businesses)
      setupPagedBusinessesFetch(makeBusinesses(205));
      render(
        <AdminProvider>
          <LocaleProvider initialLocale="ru">
            <AgentCreateDialog onClose={() => {}} onCreated={() => {}} />
          </LocaleProvider>
        </AdminProvider>
      );
      expect(await screen.findByRole('option', { name: 'Biz 001' })).toBeInTheDocument();
      await user.click(screen.getByRole('button', { name: 'Следующие бизнесы' }));
      expect(await screen.findByRole('option', { name: 'Biz 150' })).toBeInTheDocument();
      await user.click(screen.getByRole('button', { name: 'Следующие бизнесы' }));
      expect(await screen.findByRole('option', { name: 'Biz 205' })).toBeInTheDocument();
      await user.selectOptions(screen.getByLabelText('Бизнес'), 'biz-205');
      expect((screen.getByLabelText('Бизнес') as HTMLSelectElement).value).toBe('biz-205');
    });

    it('reports incomplete list error on page 2 failure without silent truncation or resetting selection, and retries page 2 without re-looping page 1', async () => {
      const user = userEvent.setup();
      const biz205 = makeBusinesses(205);
      const requestedOffsets: number[] = [];

      setupPagedBusinessesFetch(biz205, {
        failOffset: 100,
        onBusinessRequest: offset => requestedOffsets.push(offset),
      });

      render(
        <AdminProvider>
          <MemoryRouter>
            <LocaleProvider initialLocale="ru">
              <DashboardPage />
            </LocaleProvider>
          </MemoryRouter>
        </AdminProvider>
      );

      // Page 1 loads (100 items), Page 2 fails (500)
      const alert = await screen.findByRole('alert');
      expect(alert).toHaveTextContent('Загружена только часть списка (100)');
      const select = screen.getByLabelText('Бизнес') as HTMLSelectElement;
      await user.selectOptions(select, 'biz-042');
      expect(select.value).toBe('biz-042');

      // Did not spin on offset=0
      expect(requestedOffsets.filter(o => o === 0)).toHaveLength(1);
      expect(requestedOffsets.filter(o => o === 100)).toHaveLength(1);

      // Retry resumes from offset=100, completes to 205, and keeps selected biz-042
      await user.click(within(alert).getByRole('button', { name: 'Повторить' }));
      await waitFor(() => expect(select.querySelectorAll('option')).toHaveLength(206));
      expect(select.value).toBe('biz-042');
      expect(screen.queryByText(/Загружена только часть списка/)).not.toBeInTheDocument();
      expect(requestedOffsets.filter(o => o === 0)).toHaveLength(1);
      expect(requestedOffsets.filter(o => o === 200)).toHaveLength(1);
    });

    it('stops and flags error instead of looping if server repeats identical page 1 with has_more=true', async () => {
      const biz205 = makeBusinesses(205);
      const requestedOffsets: number[] = [];

      setupPagedBusinessesFetch(biz205, {
        failLoopPage: true,
        onBusinessRequest: offset => requestedOffsets.push(offset),
      });

      render(
        <AdminProvider>
          <MemoryRouter>
            <LocaleProvider initialLocale="ru">
              <NotificationsPage />
            </LocaleProvider>
          </MemoryRouter>
        </AdminProvider>
      );

      const alert = await screen.findByRole('alert');
      expect(alert).toHaveTextContent('Загружена только часть списка (100)');
      expect(requestedOffsets).toEqual([0, 100]);
    });

    it('never requests /admin/businesses as business_manager across all pages', async () => {
      const requestedPaths: string[] = [];
      setupEnvFetch('business_manager', url => {
        requestedPaths.push(url.pathname);
        if (url.pathname === '/admin/businesses') {
          throw new Error('business_manager must not call /admin/businesses');
        }
        if (url.pathname === '/admin/dashboard') {
          return json(200, {
            business_id: primaryBusinessId,
            business_name: 'Keremet',
            period_from: '2026-10-18T00:00:00Z',
            period_to: '2026-11-16T23:59:59Z',
            period_days: 30,
            customers_with_business_cards: 1,
            cards: 1,
            unblocked_cards: 1,
            transactions: 1,
            agents: { online: 1, stale: 0, never_connected: 0, error: 0, disabled: 0 },
          });
        }
        if (url.pathname.endsWith('/loyalty-tiers')) return json(200, []);
        return json(200, { items: [], limit: 25, offset: 0, has_more: false });
      });

      const pages = [
        <DashboardPage key="d" />,
        <OperationsPage key="o" />,
        <StatusesPage key="s" />,
        <NotificationsPage key="n" />,
        <ContentPage key="c" />,
      ];
      for (const page of pages) {
        const view = render(
          <AdminProvider>
            <MemoryRouter>
              <LocaleProvider initialLocale="ru">{page}</LocaleProvider>
            </MemoryRouter>
          </AdminProvider>
        );
        await waitFor(() => expect(requestedPaths.length).toBeGreaterThan(0));
        expect(requestedPaths).not.toContain('/admin/businesses');
        view.unmount();
      }
    });
  });

  describe('3. K3: Verified boolean control & radio registry (labels, keyboard, absence of #note-send-push, payload values)', () => {
    it('NotificationDialog has NO #note-send-push, supports radio labels/keyboard, and always sends send_push:true', async () => {
      const user = userEvent.setup();
      const postBodies: Array<Record<string, unknown>> = [];

      setupEnvFetch('business_manager', async (url, init) => {
        if (url.pathname === '/admin/notifications' && init?.method === 'POST') {
          const body = JSON.parse(String(init.body)) as Record<string, unknown>;
          postBodies.push(body);
          return json(201, {
            id: 'note-1',
            business_id: primaryBusinessId,
            user_id: null,
            kind: 'info',
            title: body.title,
            body: body.body,
            created_at: '2026-11-16T10:00:00Z',
            scheduled_at: body.scheduled_at ?? null,
          });
        }
        return json(200, {});
      });

      const onClose = vi.fn();
      render(
        <AdminProvider>
          <LocaleProvider initialLocale="ru">
            <NotificationDialog onClose={onClose} />
          </LocaleProvider>
        </AdminProvider>
      );

      await screen.findByLabelText('Заголовок');
      expect(document.getElementById('note-send-push')).toBeNull();
      expect(document.querySelectorAll('input[type="checkbox"]')).toHaveLength(0);

      const radioNow = screen.getByLabelText('Сейчас') as HTMLInputElement;
      const radioScheduled = screen.getByLabelText('В указанное время') as HTMLInputElement;
      expect(radioNow.checked).toBe(true);
      expect(radioScheduled.checked).toBe(false);

      // Keyboard Space + label click on radios
      radioScheduled.focus();
      await user.keyboard(' ');
      expect(radioScheduled.checked).toBe(true);
      expect(screen.getByLabelText('Дата и время (время Астаны)')).toBeInTheDocument();

      await user.click(screen.getByText('Сейчас'));
      expect(radioNow.checked).toBe(true);

      await user.type(screen.getByLabelText('Заголовок'), 'Тест push');
      await user.type(screen.getByLabelText('Текст'), 'Сообщение');
      await user.click(screen.getByRole('button', { name: 'Отправить' }));

      await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
      expect(postBodies[0]).toEqual({
        title: 'Тест push',
        body: 'Сообщение',
        send_push: true,
      });
    });

    it('verifies PromotionDialog, TierDialog, ScaleEditorSection, StoreDialog, and BusinessSplashSection checkboxes (IDs, labels, keyboard, payloads)', async () => {
      const user = userEvent.setup();
      const sentPayloads: Record<string, unknown> = {};
      const sampleTiers: LoyaltyTier[] = [
        {
          id: 't1',
          business_id: primaryBusinessId,
          level: 1,
          priority: 1,
          name_ru: 'Старт',
          name_kk: 'Бастау',
          description_ru: null,
          description_kk: null,
          image_url: null,
          min_turnover: '0.00',
          max_turnover: '100000.00',
          percent: '1.00',
          is_active: true,
          created_at: '2026-11-01T00:00:00Z',
          updated_at: '2026-11-01T00:00:00Z',
        },
      ];

      setupEnvFetch('business_manager', async (url, init) => {
        const method = init?.method ?? 'GET';
        if (url.pathname === '/admin/promotions' && method === 'POST') {
          sentPayloads.promo = JSON.parse(String(init?.body));
          return json(201, { id: 'p1', ...(sentPayloads.promo as object) });
        }
        if (url.pathname === `/admin/businesses/${primaryBusinessId}/loyalty-tiers` && method === 'POST') {
          sentPayloads.tier = JSON.parse(String(init?.body));
          return json(201, { id: 't2', ...(sentPayloads.tier as object) });
        }
        if (url.pathname === `/admin/businesses/${primaryBusinessId}/loyalty-tiers` && method === 'GET') {
          return json(200, sampleTiers);
        }
        if (url.pathname === `/admin/businesses/${primaryBusinessId}/loyalty-tiers/scale` && method === 'GET') {
          return json(200, { business_id: primaryBusinessId, version: 1, tiers: sampleTiers });
        }
        if (url.pathname === `/admin/businesses/${primaryBusinessId}/loyalty-tiers/scale` && method === 'PUT') {
          sentPayloads.scale = JSON.parse(String(init?.body));
          return json(200, { business_id: primaryBusinessId, version: 2, changed: true, tiers: sampleTiers });
        }
        if (url.pathname === `/admin/businesses/${primaryBusinessId}/stores` && method === 'POST') {
          sentPayloads.store = JSON.parse(String(init?.body));
          return json(201, { id: 's1', ...(sentPayloads.store as object) });
        }
        if (url.pathname === `/admin/businesses/${primaryBusinessId}/splash` && method === 'GET') {
          return json(200, {
            business_id: primaryBusinessId,
            enabled: false,
            media_type: 'image',
            media_url: 'https://cdn.example.test/splash.webp',
            width: 1080,
            height: 1920,
            duration_seconds: null,
            file_size: 1024,
            version: 'v1',
          });
        }
        if (url.pathname === `/admin/businesses/${primaryBusinessId}/splash` && method === 'PUT') {
          sentPayloads.splash = JSON.parse(String(init?.body));
          return json(200, { business_id: primaryBusinessId, ...(sentPayloads.splash as object) });
        }
        return json(200, {});
      });

      // 1. PromotionDialog: #promo-start-now, #promo-end-now, #promo-active
      const vPromo = render(
        <AdminProvider>
          <LocaleProvider initialLocale="ru">
            <PromotionDialog defaultKind="offer" onClose={() => {}} />
          </LocaleProvider>
        </AdminProvider>
      );
      const startNow = await screen.findByLabelText('Начать сейчас');
      const endNow = screen.getByLabelText('Бессрочно');
      const promoActive = screen.getByLabelText('Показывать в приложении');
      expect(startNow).toHaveAttribute('id', 'promo-start-now');
      expect(endNow).toHaveAttribute('id', 'promo-end-now');
      expect(promoActive).toHaveAttribute('id', 'promo-active');
      promoActive.focus();
      await user.keyboard(' '); // Space toggles #promo-active OFF
      expect(promoActive).not.toBeChecked();
      await user.type(screen.getByLabelText('Заголовок'), 'Акция К3');
      await user.click(screen.getByRole('button', { name: 'Сохранить' }));
      await waitFor(() => expect(sentPayloads.promo).toBeDefined());
      expect(sentPayloads.promo).toMatchObject({ starts_at: null, ends_at: null, is_active: false });
      vPromo.unmount();

      // 2. TierDialog: #tier-is-active
      const vTier = render(
        <AdminProvider>
          <LocaleProvider initialLocale="ru">
            <TierDialog businessId={primaryBusinessId} onClose={() => {}} onSaved={() => {}} />
          </LocaleProvider>
        </AdminProvider>
      );
      const tierActive = await screen.findByLabelText('Показывать статус в приложении');
      expect(tierActive).toHaveAttribute('id', 'tier-is-active');
      tierActive.focus();
      await user.keyboard(' ');
      expect(tierActive).not.toBeChecked();
      await user.type(screen.getByLabelText('Название (русский)'), 'Базовый');
      await user.type(screen.getByLabelText('Название (қазақша)'), 'Базалық');
      await user.click(screen.getByRole('button', { name: 'Сохранить' }));
      await waitFor(() => expect(sentPayloads.tier).toBeDefined());
      expect(sentPayloads.tier).toMatchObject({ is_active: false });
      vTier.unmount();

      // 3. ScaleEditorSection: #scale-active-t1, #scale-unbounded-t1
      const vScale = render(
        <AdminProvider>
          <MemoryRouter>
            <LocaleProvider initialLocale="ru">
              <StatusesPage />
            </LocaleProvider>
          </MemoryRouter>
        </AdminProvider>
      );
      await user.click(await screen.findByRole('button', { name: 'Редактировать шкалу' }));
      const scaleActive = await screen.findByLabelText('Показывать статус в приложении');
      const scaleUnbounded = screen.getByLabelText('Без предела');
      expect(scaleActive).toHaveAttribute('id', 'scale-active-t1');
      expect(scaleUnbounded).toHaveAttribute('id', 'scale-unbounded-t1');
      scaleActive.focus();
      await user.keyboard(' ');
      scaleUnbounded.focus();
      await user.keyboard(' ');
      expect(scaleActive).not.toBeChecked();
      expect(scaleUnbounded).toBeChecked();
      expect(document.getElementById('scale-max-t1')).toBeDisabled();
      await user.click(screen.getByRole('button', { name: 'Сохранить шкалу' }));
      await waitFor(() => expect(sentPayloads.scale).toBeDefined());
      expect(sentPayloads.scale).toMatchObject({
        tiers: [{ id: 't1', max_turnover: null, is_active: false }],
      });
      vScale.unmount();

      // 4. StoreDialog: #store-is-active
      const vStore = render(
        <AdminProvider>
          <LocaleProvider initialLocale="ru">
            <StoreDialog businessId={primaryBusinessId} onClose={() => {}} onSaved={() => {}} />
          </LocaleProvider>
        </AdminProvider>
      );
      const storeActive = await screen.findByLabelText('Магазин активен (отображается в приложении)');
      expect(storeActive).toHaveAttribute('id', 'store-is-active');
      storeActive.focus();
      await user.keyboard(' ');
      expect(storeActive).not.toBeChecked();
      await user.type(screen.getByLabelText('Название (RU)'), 'Филиал');
      await user.type(screen.getByLabelText('Название (KK)'), 'Филиал KK');
      await user.type(screen.getByLabelText('Адрес (RU)'), 'Абая 1');
      await user.type(screen.getByLabelText('Адрес (KK)'), 'Абай 1');
      await user.click(screen.getByRole('button', { name: 'Сохранить' }));
      await waitFor(() => expect(sentPayloads.store).toBeDefined());
      expect(sentPayloads.store).toMatchObject({ is_active: false });
      vStore.unmount();

      // 5. BusinessSplashSection: #splash-enabled-toggle
      const vSplash = render(
        <AdminProvider>
          <LocaleProvider initialLocale="ru">
            <BusinessSplashSection businessId={primaryBusinessId} />
          </LocaleProvider>
        </AdminProvider>
      );
      const splashToggle = await screen.findByLabelText('Включить заставку в приложении');
      expect(splashToggle).toHaveAttribute('id', 'splash-enabled-toggle');
      expect(splashToggle).not.toBeChecked();
      splashToggle.focus();
      await user.keyboard(' ');
      expect(splashToggle).toBeChecked();
      await user.click(screen.getByRole('button', { name: 'Сохранить' }));
      await waitFor(() => expect(sentPayloads.splash).toBeDefined());
      expect(sentPayloads.splash).toMatchObject({ enabled: true });
      await waitFor(() => expect(splashToggle).toBeEnabled());
      fireEvent.click(splashToggle);
      expect(splashToggle).not.toBeChecked();
      vSplash.unmount();
    });
  });
});
