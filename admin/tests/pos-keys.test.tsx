import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { BusinessDetail, PosKey, PosKeyDisclosure } from '../src/api/types';
import { AdminProvider } from '../src/auth/provider';
import { PosKeyCreateDialog, PosKeyDialog, PosKeyRevokeDialog } from '../src/features/BusinessPosKeys';
import { LocaleProvider } from '../src/i18n/LocaleContext';
import { BusinessDetailPage } from '../src/pages/BusinessesPage';

const access = { access_token: 'fixture-access', token_type: 'bearer', expires_in: 900 };
const businessId = 'fixture-biz-id';

const business: BusinessDetail = {
  id: businessId,
  name: 'Супермаркет «Керемет»',
  logo_url: null,
  colors: null,
  barcode_prefixes: ['10'],
  status: 'active',
  created_at: '2026-10-01T00:00:00Z',
  updated_at: '2026-10-01T00:00:00Z',
  cards_count: 10,
  unblocked_cards_count: 10,
  customers_with_cards_count: 8,
  agents_count: 1,
};

const fixturePosKeys: PosKey[] = [
  {
    id: 'pos-key-1',
    business_id: businessId,
    name: 'Касса 1 (Основная)',
    created_at: '2026-11-01T10:00:00Z',
    last_used_at: '2026-11-04T09:30:00Z',
    revoked_at: null,
    status: 'active',
  },
  {
    id: 'pos-key-2',
    business_id: businessId,
    name: 'Касса 2 (Резервная)',
    created_at: '2026-10-15T12:00:00Z',
    last_used_at: null,
    revoked_at: '2026-10-20T15:00:00Z',
    status: 'revoked',
  },
];

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

function adminResponse(role: 'superadmin' | 'business_manager') {
  return {
    admin: {
      id: 'fixture-admin-id',
      login: `fixture.${role}`,
      role,
      business: role === 'business_manager' ? { id: businessId, name: business.name, status: 'active' } : null,
    },
  };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe('PosKeyDialog (Disclosure modal)', () => {
  it('renders one-time key disclosure, copy button and warning hint', async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', {
      clipboard: { writeText },
    });

    const disclosure: PosKeyDisclosure = {
      pos_key: {
        id: 'pos-key-123',
        business_id: businessId,
        name: 'Касса 1',
        created_at: '2026-11-04T12:00:00Z',
        last_used_at: null,
        revoked_at: null,
        status: 'active',
      },
      api_key: 'pos_live_secret_key_1234567890abcdef1234567890',
    };

    const onClose = vi.fn();

    render(
      <LocaleProvider initialLocale="ru">
        <PosKeyDialog disclosure={disclosure} onClose={onClose} />
      </LocaleProvider>
    );

    expect(screen.getByRole('heading', { name: 'Ключ кассы создан' })).toBeInTheDocument();
    expect(screen.getByText('pos_live_secret_key_1234567890abcdef1234567890')).toBeInTheDocument();
    expect(screen.getByText('Введите ключ в настройках Cash на этой кассе.')).toBeInTheDocument();
    expect(screen.getByText(/Ключ показан один раз/)).toBeInTheDocument();

    const copyBtn = screen.getByRole('button', { name: 'Скопировать' });
    await user.click(copyBtn);

    expect(writeText).toHaveBeenCalledWith('pos_live_secret_key_1234567890abcdef1234567890');
    expect(screen.getByRole('status')).toHaveTextContent('Ключ скопирован в буфер обмена');

    const closeBtn = screen.getByRole('button', { name: 'Закрыть' });
    await user.click(closeBtn);
    expect(onClose).toHaveBeenCalled();
  });
});

describe('PosKeyCreateDialog & PosKeyRevokeDialog', () => {
  it('validates empty name and calls API on create', async () => {
    const user = userEvent.setup();
    vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
    vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

    let postedBody: unknown = null;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/admin/auth/refresh')) return json(200, access);
      if (url.endsWith('/admin/me')) return json(200, adminResponse('superadmin'));
      if (url.endsWith(`/admin/businesses/${businessId}/pos-keys`)) {
        postedBody = JSON.parse(String(init?.body));
        return json(201, {
          pos_key: {
            id: 'pos-new',
            business_id: businessId,
            name: 'Касса Экспресс',
            created_at: '2026-11-04T12:00:00Z',
            last_used_at: null,
            revoked_at: null,
            status: 'active',
          },
          api_key: 'pos_live_secret_express_9876543210',
        });
      }
      return json(404, { error: { code: 'NOT_FOUND', message: 'Not found' } });
    });
    vi.stubGlobal('fetch', fetchMock);

    const onClose = vi.fn();
    const onCreated = vi.fn();

    render(
      <AdminProvider>
        <LocaleProvider initialLocale="ru">
          <PosKeyCreateDialog businessId={businessId} onClose={onClose} onCreated={onCreated} />
        </LocaleProvider>
      </AdminProvider>
    );

    // Click submit with empty name
    const submitBtn = screen.getByRole('button', { name: 'Создать ключ' });
    await user.click(submitBtn);

    expect(screen.getByRole('alert')).toHaveTextContent('Введите название кассы');

    // Fill in name and submit
    const input = screen.getByPlaceholderText('например, Касса 1');
    await user.type(input, 'Касса Экспресс');
    await user.click(submitBtn);

    await waitFor(() => {
      expect(onCreated).toHaveBeenCalledWith(
        expect.objectContaining({
          api_key: 'pos_live_secret_express_9876543210',
          pos_key: expect.objectContaining({
            name: 'Касса Экспресс',
          }),
        })
      );
    });
    expect(postedBody).toEqual({ name: 'Касса Экспресс' });
  });

  it('submits revoke request and invokes onRevoked', async () => {
    const user = userEvent.setup();
    vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
    vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

    let revokedKeyId = '';
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/admin/auth/refresh')) return json(200, access);
      if (url.endsWith('/admin/me')) return json(200, adminResponse('superadmin'));
      if (url.endsWith('/admin/pos-keys/pos-key-1/revoke')) {
        revokedKeyId = 'pos-key-1';
        return json(200, {
          id: 'pos-key-1',
          business_id: businessId,
          name: 'Касса 1 (Основная)',
          created_at: '2026-11-01T10:00:00Z',
          last_used_at: '2026-11-04T09:30:00Z',
          revoked_at: '2026-11-04T12:00:00Z',
          status: 'revoked',
        });
      }
      return json(404, { error: { code: 'NOT_FOUND', message: 'Not found' } });
    });
    vi.stubGlobal('fetch', fetchMock);

    const onClose = vi.fn();
    const onRevoked = vi.fn();

    render(
      <AdminProvider>
        <LocaleProvider initialLocale="ru">
          <PosKeyRevokeDialog
            posKey={fixturePosKeys[0]}
            onClose={onClose}
            onRevoked={onRevoked}
          />
        </LocaleProvider>
      </AdminProvider>
    );

    expect(screen.getByRole('heading', { name: 'Отозвать' })).toBeInTheDocument();
    expect(screen.getByText(/«Касса 1 \(Основная\)»/)).toBeInTheDocument();

    const revokeBtn = screen.getByRole('button', { name: 'Отозвать' });
    await user.click(revokeBtn);

    await waitFor(() => {
      expect(onRevoked).toHaveBeenCalled();
    });
    expect(revokedKeyId).toBe('pos-key-1');
  });
});

describe('BusinessPosKeys list and role visibility in BusinessDetailPage', () => {
  function renderBusinessDetailPage(role: 'superadmin' | 'business_manager', locale: 'ru' | 'kk' = 'ru') {
    vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
    vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/admin/auth/refresh')) return json(200, access);
      if (url.endsWith('/admin/me')) return json(200, adminResponse(role));
      if (url.endsWith(`/admin/businesses/${businessId}/pos-keys`)) {
        return json(200, fixturePosKeys);
      }
      if (url.endsWith(`/admin/businesses/${businessId}/app-content`)) {
        return json(200, { stores: [], texts: {} });
      }
      if (url.endsWith(`/admin/businesses/${businessId}`)) {
        return json(200, business);
      }
      return json(404, { error: { code: 'NOT_FOUND', message: 'Not found' } });
    });
    vi.stubGlobal('fetch', fetchMock);

    return render(
      <MemoryRouter initialEntries={[`/admin/businesses/${businessId}`]}>
        <AdminProvider>
          <LocaleProvider initialLocale={locale}>
            <Routes>
              <Route path="/admin/businesses/:businessId" element={<BusinessDetailPage />} />
            </Routes>
          </LocaleProvider>
        </AdminProvider>
      </MemoryRouter>
    );
  }

  it('shows POS keys block for superadmin with keys, actions and statuses', async () => {
    renderBusinessDetailPage('superadmin', 'ru');

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 2, name: 'Кассы' })).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: 'Добавить кассу' })).toBeInTheDocument();

    // Check key names once loaded
    await waitFor(() => {
      expect(screen.getAllByText('Касса 1 (Основная)').length).toBeGreaterThan(0);
    });
    expect(screen.getAllByText('Касса 2 (Резервная)').length).toBeGreaterThan(0);

    // Check status pills
    expect(screen.getAllByText('Активен').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Отозван').length).toBeGreaterThan(0);

    // Active key has revoke buttons (both table and card view)
    const revokeButtons = screen.getAllByRole('button', { name: 'Отозвать' });
    expect(revokeButtons.length).toBeGreaterThan(0);
  });

  it('renders POS keys block in Kazakh correctly', async () => {
    renderBusinessDetailPage('superadmin', 'kk');

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 2, name: 'Кассалар' })).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: 'Касса қосу' })).toBeInTheDocument();
  });

  it('hides POS keys block for business_manager', async () => {
    renderBusinessDetailPage('business_manager', 'ru');

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 1, name: 'Супермаркет «Керемет»' })).toBeInTheDocument();
    });

    expect(screen.queryByRole('heading', { level: 2, name: 'Кассы' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Добавить кассу' })).toBeNull();
  });
});
