import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { LoyaltyTier } from '../src/api/types';
import { AdminProvider } from '../src/auth/provider';
import { LocaleProvider } from '../src/i18n/LocaleContext';
import { adminRu } from '../src/i18n/admin';
import { StatusesPage, TierDialog } from '../src/pages/StatusesPage';

interface TierPayload {
  level?: number;
  priority?: unknown;
  name_ru?: string;
  name_kk?: string;
  [key: string]: unknown;
}

const access = { access_token: 'fixture-access', token_type: 'bearer', expires_in: 900 };
const businessId = 'fixture-biz-1';

const sampleTiers: LoyaltyTier[] = [
  {
    id: 'tier-1',
    business_id: businessId,
    level: 1,
    priority: 10, // non-matching priority
    name_ru: 'Базовый',
    name_kk: 'Базалық',
    description_ru: 'Стартовый уровень',
    description_kk: 'Бастапқы деңгей',
    image_url: null,
    turnover_period_months: 6,
    min_turnover: '0.00',
    max_turnover: '50000.00',
    percent: '2.00',
    is_active: true,
    created_at: '2026-11-01T00:00:00Z',
    updated_at: '2026-11-01T00:00:00Z',
  },
  {
    id: 'tier-2',
    business_id: businessId,
    level: 2,
    priority: 2, // smaller priority than tier-1
    name_ru: 'Серебряный',
    name_kk: 'Күміс',
    description_ru: 'Для постоянных гостей',
    description_kk: 'Тұрақты қонақтарға',
    image_url: null,
    turnover_period_months: 6,
    min_turnover: '50000.00',
    max_turnover: '150000.00',
    percent: '3.50',
    is_active: true,
    created_at: '2026-11-01T00:00:00Z',
    updated_at: '2026-11-01T00:00:00Z',
  },
  {
    id: 'tier-3',
    business_id: businessId,
    level: 3,
    priority: 5,
    name_ru: 'Золотой',
    name_kk: 'Алтын',
    description_ru: 'VIP привилегии',
    description_kk: 'VIP артықшылықтары',
    image_url: null,
    turnover_period_months: 6,
    min_turnover: '150000.00',
    max_turnover: null,
    percent: '5.00',
    is_active: true,
    created_at: '2026-11-01T00:00:00Z',
    updated_at: '2026-11-01T00:00:00Z',
  },
];

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

function setup() {
  vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
  vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });

  return {
    queryClient,
    render: (ui: React.ReactElement) =>
      render(
        <MemoryRouter>
          <QueryClientProvider client={queryClient}>
            <LocaleProvider initialLocale="ru">
              <AdminProvider initialTokens={access}>{ui}</AdminProvider>
            </LocaleProvider>
          </QueryClientProvider>
        </MemoryRouter>
      ),
  };
}

describe('StatusesPage and TierDialog without Priority field', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('TierDialog does NOT render priority input, label, or hint', () => {
    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/admin/me')) {
        return Promise.resolve(
          json(200, {
            admin: {
              id: 'adm-1',
              login: 'manager',
              role: 'business_manager',
              business: { id: businessId, name: 'Керемет', status: 'active' },
            },
            admin_max_stats_period_days: 90,
          })
        );
      }
      return Promise.resolve(json(404, { detail: 'Not found' }));
    });
    vi.stubGlobal('fetch', fetchMock);

    const { render: renderWithCtx } = setup();
    renderWithCtx(
      <TierDialog
        businessId={businessId}
        onClose={() => {}}
        onSaved={() => {}}
      />
    );

    // Level field is present
    expect(screen.getByLabelText(adminRu.statuses.fieldLevel)).toBeInTheDocument();
    expect(screen.getByLabelText(adminRu.statuses.fieldLevel)).toHaveValue(1);

    // Priority field is completely absent from form
    expect(screen.queryByLabelText(/приоритет/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/басымдық/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/чем больше число, тем выше приоритет/i)).not.toBeInTheDocument();
    expect(document.getElementById('tier-priority')).toBeNull();
  });

  it('TierDialog creates a new status sending payload without priority field', async () => {
    const user = userEvent.setup();
    let createRequestBody: TierPayload | null = null;

    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/admin/me')) {
        return Promise.resolve(
          json(200, {
            admin: {
              id: 'adm-1',
              login: 'manager',
              role: 'business_manager',
              business: { id: businessId, name: 'Керемет', status: 'active' },
            },
            admin_max_stats_period_days: 90,
          })
        );
      }
      if (url.includes(`/admin/businesses/${businessId}/loyalty-tiers`) && init?.method === 'POST') {
        createRequestBody = JSON.parse(String(init.body));
        return Promise.resolve(
          json(201, {
            id: 'tier-new',
            business_id: businessId,
            ...createRequestBody,
            priority: createRequestBody.level,
            created_at: '2026-11-10T00:00:00Z',
            updated_at: '2026-11-10T00:00:00Z',
          })
        );
      }
      return Promise.resolve(json(404, { detail: 'Not found' }));
    });
    vi.stubGlobal('fetch', fetchMock);

    const onSaved = vi.fn();
    const onClose = vi.fn();
    const { render: renderWithCtx } = setup();
    renderWithCtx(
      <TierDialog
        businessId={businessId}
        onClose={onClose}
        onSaved={onSaved}
      />
    );

    // Fill in required fields
    const titleRuInput = screen.getByLabelText(adminRu.statuses.fieldTitleRu);
    const titleKkInput = screen.getByLabelText(adminRu.statuses.fieldTitleKk);
    await user.type(titleRuInput, 'Новый статус');
    await user.type(titleKkInput, 'Жаңа дәреже');

    const saveBtn = screen.getByRole('button', { name: adminRu.statuses.saveBtn });
    await user.click(saveBtn);

    await waitFor(() => {
      expect(createRequestBody).not.toBeNull();
    });

    expect(createRequestBody.level).toBe(1);
    expect(createRequestBody.priority).toBeUndefined();
    expect(createRequestBody.name_ru).toBe('Новый статус');
    expect(createRequestBody.name_kk).toBe('Жаңа дәреже');
    expect(onSaved).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  }, 20000);

  it('TierDialog edits an existing status without priority field in payload', async () => {
    const user = userEvent.setup();
    let updateRequestBody: TierPayload | null = null;

    const existingTier = sampleTiers[0]; // level=1, priority=10

    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/admin/me')) {
        return Promise.resolve(
          json(200, {
            admin: {
              id: 'adm-1',
              login: 'manager',
              role: 'business_manager',
              business: { id: businessId, name: 'Керемет', status: 'active' },
            },
            admin_max_stats_period_days: 90,
          })
        );
      }
      if (url.includes(`/admin/businesses/${businessId}/loyalty-tiers/${existingTier.id}`) && init?.method === 'PATCH') {
        updateRequestBody = JSON.parse(String(init.body));
        return Promise.resolve(
          json(200, {
            ...existingTier,
            ...updateRequestBody,
            updated_at: '2026-11-10T01:00:00Z',
          })
        );
      }
      return Promise.resolve(json(404, { detail: 'Not found' }));
    });
    vi.stubGlobal('fetch', fetchMock);

    const onSaved = vi.fn();
    const onClose = vi.fn();
    const { render: renderWithCtx } = setup();
    renderWithCtx(
      <TierDialog
        businessId={businessId}
        tier={existingTier}
        onClose={onClose}
        onSaved={onSaved}
      />
    );

    // Form loads existing values
    expect(screen.getByLabelText(adminRu.statuses.fieldLevel)).toHaveValue(1);
    expect(screen.getByLabelText(adminRu.statuses.fieldTitleRu)).toHaveValue('Базовый');
    expect(screen.queryByLabelText(/приоритет/i)).not.toBeInTheDocument();

    // Edit level and title using fireEvent for clean numeric assignment
    const levelInput = screen.getByLabelText(adminRu.statuses.fieldLevel);
    fireEvent.change(levelInput, { target: { value: '4' } });

    const titleRuInput = screen.getByLabelText(adminRu.statuses.fieldTitleRu);
    await user.clear(titleRuInput);
    await user.type(titleRuInput, 'Базовый Плюс');

    const saveBtn = screen.getByRole('button', { name: adminRu.statuses.saveBtn });
    await user.click(saveBtn);

    await waitFor(() => {
      expect(updateRequestBody).not.toBeNull();
    });

    expect(updateRequestBody.level).toBe(4);
    expect(updateRequestBody.priority).toBeUndefined();
    expect(updateRequestBody.name_ru).toBe('Базовый Плюс');
    expect(onSaved).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  }, 20000);

  it('StatusesPage renders tiers sorted strictly by level ASC despite non-matching priorities', async () => {
    // Pass tiers in disordered/priority order: Tier 2 (priority 2), Tier 3 (priority 5), Tier 1 (priority 10)
    const disorderedTiers = [sampleTiers[1], sampleTiers[2], sampleTiers[0]];

    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/admin/auth/refresh')) {
        return Promise.resolve(json(200, access));
      }
      if (url.includes('/admin/me')) {
        return Promise.resolve(
          json(200, {
            admin: {
              id: 'adm-1',
              login: 'manager',
              role: 'business_manager',
              business: { id: businessId, name: 'Керемет', status: 'active' },
            },
            admin_max_stats_period_days: 90,
          })
        );
      }
      if (url.includes(`/admin/businesses/${businessId}/loyalty-tiers`)) {
        return Promise.resolve(json(200, disorderedTiers));
      }
      return Promise.resolve(json(404, { detail: 'Not found' }));
    });
    vi.stubGlobal('fetch', fetchMock);

    const { render: renderWithCtx } = setup();
    renderWithCtx(<StatusesPage />);

    // Wait for tiers to render
    await screen.findByText('Базовый', {}, { timeout: 10000 });
    await screen.findByText('Серебряный', {}, { timeout: 10000 });
    await screen.findByText('Золотой', {}, { timeout: 10000 });

    // Verify table header does NOT have Priority column
    expect(screen.queryByText(adminRu.statuses.colPriority)).not.toBeInTheDocument();

    // Verify order in table rows: #1 Базовый, then #2 Серебряный, then #3 Золотой
    const rows = screen.getAllByRole('row');
    // Row 0 is the table header
    expect(rows[1]).toHaveTextContent('#1');
    expect(rows[1]).toHaveTextContent('Базовый');

    expect(rows[2]).toHaveTextContent('#2');
    expect(rows[2]).toHaveTextContent('Серебряный');

    expect(rows[3]).toHaveTextContent('#3');
    expect(rows[3]).toHaveTextContent('Золотой');
  }, 20000);
});
