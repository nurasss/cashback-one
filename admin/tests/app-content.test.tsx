import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { AdminProvider } from '../src/auth/provider';
import { ContentPage } from '../src/pages/ContentPage';
import { LocaleProvider } from '../src/i18n/LocaleContext';
import type { AppTexts, BusinessStore } from '../src/api/types';

const businessId = 'fixture-business-id';
const store: BusinessStore = {
  id: 'fixture-store-id',
  business_id: businessId,
  title_ru: 'Супермаркет «КеремЕт»',
  title_kk: '«КеремЕт» супермаркеті',
  address_ru: 'проспект Тауелсиздик, 4',
  address_kk: 'Тәуелсіздік даңғылы, 4',
  map_url: 'https://2gis.kz/astana/firm/70000001103172202',
  sort_order: 1,
  is_active: true,
  created_at: '2026-10-01T00:00:00Z',
  updated_at: '2026-10-01T00:00:00Z',
};

const appTexts: AppTexts = {
  home_store_note_lead: {
    ru: 'Вы можете потратить эти баллы в супермаркете «КеремЕт»:',
    kk: 'Сіз бұл ұпайларды «КеремЕт» супермаркетінде жұмсай аласыз:',
  },
  balance_delay_note: {
    ru: 'Баллы начисляются после смены',
    kk: 'Ұпайлар ауысымнан кейін есептеледі',
  },
};

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

function renderAppContent(role: 'superadmin' | 'business_manager', initialLocale: 'ru' | 'kk' = 'ru') {
  vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
  vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

  const fetchMock: typeof fetch = vi.fn(async (input, init) => {
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
          id: 'a',
          login: 'fixture',
          role,
          business:
            role === 'business_manager'
              ? { id: businessId, name: 'Fixture Market', status: 'active' }
              : null,
        },
      });
    }
    if (url.includes('/admin/businesses?')) {
      return json(200, {
        items: [{ id: businessId, name: 'Fixture Market' }],
        limit: 100,
        offset: 0,
        has_more: false,
      });
    }
    if (url.includes('/admin/promotions?')) {
      return json(200, { items: [], limit: 25, offset: 0, has_more: false });
    }
    if (url.includes('/admin/notifications?')) {
      return json(200, { items: [], limit: 25, offset: 0, has_more: false });
    }
    if (url.includes(`/admin/businesses/${businessId}/stores`)) {
      if (method === 'GET') {
        return json(200, [store]);
      }
      if (method === 'POST') {
        return json(201, { ...store, id: 'new-store-id' });
      }
      if (method === 'PATCH') {
        return json(200, { ...store, title_ru: 'Обновленное название' });
      }
      if (method === 'DELETE') {
        return new Response(null, { status: 204 });
      }
    }
    if (url.includes(`/admin/businesses/${businessId}/app-texts`)) {
      if (method === 'GET') {
        return json(200, appTexts);
      }
      if (method === 'PUT') {
        return json(200, appTexts);
      }
    }

    return json(404, { error: { code: 'ADMIN_RESOURCE_NOT_FOUND' } });
  });

  vi.stubGlobal('fetch', fetchMock);

  render(
    <AdminProvider>
      <LocaleProvider initialLocale={initialLocale}>
        <MemoryRouter>
          <Routes>
            <Route path="/" element={<ContentPage />} />
          </Routes>
        </MemoryRouter>
      </LocaleProvider>
    </AdminProvider>
  );

  return fetchMock;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

it('manager accesses App tab without business picker and sees stores and texts', async () => {
  const user = userEvent.setup();
  renderAppContent('business_manager');

  // Verify tab is present and click it
  const appTab = await screen.findByRole('tab', { name: 'Магазины и инфо' });
  expect(appTab).toBeInTheDocument();
  await user.click(appTab);

  // Business selector must NOT be visible for a manager
  expect(screen.queryByLabelText('Бизнес')).not.toBeInTheDocument();

  // Store information is displayed
  expect(await screen.findByText('Супермаркет «КеремЕт»')).toBeInTheDocument();
  expect(screen.getByText('проспект Тауелсиздик, 4')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Открыть на карте' })).toHaveAttribute(
    'href',
    'https://2gis.kz/astana/firm/70000001103172202'
  );

  // App texts are populated
  const leadInput = screen.getByDisplayValue(
    'Вы можете потратить эти баллы в супермаркете «КеремЕт»:'
  );
  expect(leadInput).toBeInTheDocument();
});

it('validates store form and creates a store through the typed API', async () => {
  const user = userEvent.setup();
  const fetchMock = renderAppContent('business_manager');

  await user.click(await screen.findByRole('tab', { name: 'Магазины и инфо' }));
  await user.click(await screen.findByRole('button', { name: 'Добавить магазин' }));

  const dialog = await screen.findByRole('dialog');
  expect(within(dialog).getByText('Новый магазин')).toBeInTheDocument();

  // Invalid map url check
  await user.type(within(dialog).getByLabelText('Название (RU)'), 'Новый Филиал');
  await user.type(within(dialog).getByLabelText('Название (KK)'), 'Жаңа филиал');
  await user.type(within(dialog).getByLabelText('Адрес (RU)'), 'ул. Сыганак, 1');
  await user.type(within(dialog).getByLabelText('Адрес (KK)'), 'Сығанақ к-сі, 1');
  await user.type(
    within(dialog).getByLabelText(/Ссылка на карту/i),
    'http://insecure-site.kz'
  );

  await user.click(within(dialog).getByRole('button', { name: 'Сохранить' }));
  expect(
    await within(dialog).findByText(
      'Ссылка должна начинаться с https:// и содержать корректный адрес сайта'
    )
  ).toBeInTheDocument();

  // Fix URL and submit
  const mapInput = within(dialog).getByLabelText(/Ссылка на карту/i);
  await user.clear(mapInput);
  await user.type(mapInput, 'https://2gis.kz/astana/firm/12345');

  await user.click(within(dialog).getByRole('button', { name: 'Сохранить' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());

  const postCall = vi
    .mocked(fetchMock)
    .mock.calls.find(
      ([url, init]) =>
        String(url).endsWith(`/admin/businesses/${businessId}/stores`) &&
        init?.method === 'POST'
    );
  expect(postCall).toBeDefined();
  expect(JSON.parse(String(postCall?.[1]?.body))).toMatchObject({
    title_ru: 'Новый Филиал',
    title_kk: 'Жаңа филиал',
    address_ru: 'ул. Сыганак, 1',
    address_kk: 'Сығанақ к-сі, 1',
    map_url: 'https://2gis.kz/astana/firm/12345',
    is_active: true,
  });
});

it('deletes store with user confirmation', async () => {
  const user = userEvent.setup();
  const confirmMock = vi.fn(() => true);
  vi.stubGlobal('confirm', confirmMock);

  const fetchMock = renderAppContent('business_manager');
  await user.click(await screen.findByRole('tab', { name: 'Магазины и инфо' }));
  await screen.findByText('Супермаркет «КеремЕт»');

  await user.click(screen.getByRole('button', { name: 'Удалить' }));

  expect(confirmMock).toHaveBeenCalledWith('Удалить магазин «Супермаркет «КеремЕт»»?');
  await waitFor(() => {
    const deleteCall = vi
      .mocked(fetchMock)
      .mock.calls.find(
        ([url, init]) =>
          String(url).includes(`/admin/businesses/${businessId}/stores/${store.id}`) &&
          init?.method === 'DELETE'
      );
    expect(deleteCall).toBeDefined();
  });
});

it('updates app texts in RU and KK', async () => {
  const user = userEvent.setup();
  const fetchMock = renderAppContent('business_manager');

  await user.click(await screen.findByRole('tab', { name: 'Магазины и инфо' }));
  const leadRuInput = await screen.findByDisplayValue(
    'Вы можете потратить эти баллы в супермаркете «КеремЕт»:'
  );

  await user.clear(leadRuInput);
  await user.type(leadRuInput, 'Новый текст на главной (RU)');

  await user.click(screen.getByRole('button', { name: 'Сохранить тексты' }));

  await waitFor(() => {
    const putCall = vi
      .mocked(fetchMock)
      .mock.calls.find(
        ([url, init]) =>
          String(url).endsWith(`/admin/businesses/${businessId}/app-texts`) &&
          init?.method === 'PUT'
      );
    expect(putCall).toBeDefined();
    expect(JSON.parse(String(putCall?.[1]?.body))).toMatchObject({
      home_store_note_lead: {
        ru: 'Новый текст на главной (RU)',
        kk: 'Сіз бұл ұпайларды «КеремЕт» супермаркетінде жұмсай аласыз:',
      },
    });
  });

  expect(await screen.findByText('Тексты успешно сохранены')).toBeInTheDocument();
});

it('superadmin sees business picker on app tab and prompt when unselected', async () => {
  const user = userEvent.setup();
  renderAppContent('superadmin');

  await user.click(await screen.findByRole('tab', { name: 'Магазины и инфо' }));
  expect(screen.getByLabelText('Бизнес')).toBeInTheDocument();
  expect(
    screen.getByText('Выберите бизнес для настройки магазинов и текстов приложения.')
  ).toBeInTheDocument();

  // Select business
  await user.selectOptions(screen.getByLabelText('Бизнес'), businessId);
  expect(await screen.findByText('Супермаркет «КеремЕт»')).toBeInTheDocument();
});

it('renders in Kazakh locale with proper translations', async () => {
  renderAppContent('business_manager', 'kk');

  const appTab = await screen.findByRole('tab', { name: 'Дүкендер мен мәтіндер' });
  expect(appTab).toBeInTheDocument();
});
