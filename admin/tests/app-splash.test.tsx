import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AdminProvider } from '../src/auth/provider';
import { ContentPage } from '../src/pages/ContentPage';
import { LocaleProvider } from '../src/i18n/LocaleContext';
import type { BusinessSplashConfig } from '../src/api/types';

const businessId = 'test-biz-uuid';

const initialSplashConfig: BusinessSplashConfig = {
  business_id: businessId,
  enabled: false,
  media_type: null,
  media_url: null,
  width: null,
  height: null,
  duration_seconds: null,
  file_size: null,
  version: null,
};

const activeSplashConfig: BusinessSplashConfig = {
  business_id: businessId,
  enabled: true,
  media_type: 'video',
  media_url: 'https://admin.test/media/splashes/test_vid.mp4',
  width: 1080,
  height: 1920,
  duration_seconds: 4.5,
  file_size: 5242880,
  version: 'v123',
};

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

function setupMocks(config: BusinessSplashConfig = initialSplashConfig) {
  vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
  vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

  let currentConfig = { ...config };
  const putCalls: Partial<BusinessSplashConfig>[] = [];

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? 'GET';

    if (url.endsWith('/admin/auth/refresh')) {
      return json(200, {
        access_token: 'fixture-access',
        token_type: 'bearer',
        expires_in: 900,
      });
    }
    if (url.endsWith('/admin/me')) {
      return json(200, {
        admin: {
          id: 'mgr-id',
          login: 'keremet_mgr',
          role: 'business_manager',
          business: { id: businessId, name: 'Keremet Store', status: 'active' },
        },
        admin_max_stats_period_days: 90,
      });
    }
    if (url.includes('/admin/promotions?')) {
      return json(200, { items: [], limit: 25, offset: 0, has_more: false });
    }
    if (url.includes('/admin/notifications?')) {
      return json(200, { items: [], limit: 25, offset: 0, has_more: false });
    }
    if (url.includes(`/admin/businesses/${businessId}/stores`)) {
      return json(200, []);
    }
    if (url.includes(`/admin/businesses/${businessId}/app-texts`)) {
      return json(200, {
        home_store_note_lead: { ru: '', kk: '' },
        balance_delay_note: { ru: '', kk: '' },
      });
    }
    if (url.includes(`/admin/businesses/${businessId}/splash`)) {
      if (method === 'GET') {
        return json(200, currentConfig);
      }
      if (method === 'PUT') {
        const payload = JSON.parse(String(init?.body));
        putCalls.push(payload);
        currentConfig = {
          ...currentConfig,
          ...payload,
          version: 'updated-v2',
        };
        return json(200, currentConfig);
      }
    }
    if (url.includes('/admin/media/splash') && method === 'POST') {
      return json(200, {
        media_type: 'image',
        url: 'https://admin.test/media/splashes/new_splash.webp',
        width: 1080,
        height: 1920,
        duration_seconds: null,
        bytes: 102400,
      });
    }

    return json(404, { error: { code: 'NOT_FOUND', message: 'Not found' } });
  });

  vi.stubGlobal('fetch', fetchMock);
  return { putCalls, getCurrentConfig: () => currentConfig };
}

describe('BusinessSplashSection in ContentPage', () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it('renders splash tab for manager and shows limits callout', async () => {
    setupMocks(initialSplashConfig);

    render(
      <MemoryRouter initialEntries={['/admin/content']}>
        <LocaleProvider>
          <AdminProvider>
            <Routes>
              <Route path="/admin/content" element={<ContentPage />} />
            </Routes>
          </AdminProvider>
        </LocaleProvider>
      </MemoryRouter>
    );

    const splashTabBtn = await screen.findByTestId('client-tab-splash');
    expect(splashTabBtn).toBeInTheDocument();
    expect(splashTabBtn).toHaveTextContent('Заставка');

    await userEvent.click(splashTabBtn);

    expect(await screen.findByRole('heading', { level: 2, name: 'Заставка приложения' })).toBeInTheDocument();
    expect(screen.getByText(/1080×1920 px \(9:16\).*PNG, JPEG, WebP или GIF до 5 МиБ.*40 Мп.*MP4 \(H\.264, без звука, ≤ 5 с\) до 15 МиБ/i)).toBeInTheDocument();
    expect(screen.getByLabelText('Включить заставку в приложении')).not.toBeChecked();
    expect(screen.getByTestId('splash-upload-btn')).toBeInTheDocument();
  });

  it('displays preview and metadata when splash media is configured', async () => {
    setupMocks(activeSplashConfig);

    render(
      <MemoryRouter initialEntries={['/admin/content']}>
        <LocaleProvider>
          <AdminProvider>
            <Routes>
              <Route path="/admin/content" element={<ContentPage />} />
            </Routes>
          </AdminProvider>
        </LocaleProvider>
      </MemoryRouter>
    );

    const splashTabBtn = await screen.findByTestId('client-tab-splash');
    await userEvent.click(splashTabBtn);

    const toggle = await screen.findByLabelText('Включить заставку в приложении');
    expect(toggle).toBeChecked();

    const preview = await screen.findByTestId('splash-preview');
    expect(preview).toBeInTheDocument();
    expect(screen.getByText('Видео MP4')).toBeInTheDocument();
    expect(screen.getByText('1080 × 1920')).toBeInTheDocument();
    expect(screen.getByText('4.5 сек')).toBeInTheDocument();
    expect(screen.getByText('Видео воспроизводится без звука')).toBeInTheDocument();
  });

  it('validates that enabled splash requires media', async () => {
    setupMocks(initialSplashConfig);

    render(
      <MemoryRouter initialEntries={['/admin/content']}>
        <LocaleProvider>
          <AdminProvider>
            <Routes>
              <Route path="/admin/content" element={<ContentPage />} />
            </Routes>
          </AdminProvider>
        </LocaleProvider>
      </MemoryRouter>
    );

    const splashTabBtn = await screen.findByTestId('client-tab-splash');
    await userEvent.click(splashTabBtn);

    const toggle = await screen.findByLabelText('Включить заставку в приложении');
    await userEvent.click(toggle);
    expect(toggle).toBeChecked();

    const saveBtn = screen.getByRole('button', { name: 'Сохранить' });
    await userEvent.click(saveBtn);

    expect(await screen.findByTestId('splash-error')).toHaveTextContent(
      'Для включения заставки загрузите изображение или видео.'
    );
  });

  it('saves splash disabled successfully', async () => {
    const { putCalls } = setupMocks(activeSplashConfig);

    render(
      <MemoryRouter initialEntries={['/admin/content']}>
        <LocaleProvider>
          <AdminProvider>
            <Routes>
              <Route path="/admin/content" element={<ContentPage />} />
            </Routes>
          </AdminProvider>
        </LocaleProvider>
      </MemoryRouter>
    );

    const splashTabBtn = await screen.findByTestId('client-tab-splash');
    await userEvent.click(splashTabBtn);

    const toggle = await screen.findByLabelText('Включить заставку в приложении');
    expect(toggle).toBeChecked();

    await userEvent.click(toggle);
    expect(toggle).not.toBeChecked();

    const saveBtn = screen.getByRole('button', { name: 'Сохранить' });
    await userEvent.click(saveBtn);

    await waitFor(() => {
      expect(screen.getByTestId('splash-feedback')).toHaveTextContent(
        'Настройки заставки успешно сохранены'
      );
    });

    expect(putCalls.length).toBe(1);
    expect(putCalls[0].enabled).toBe(false);
  });
});
