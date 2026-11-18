import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
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
  home_text: {
    ru: 'Добро пожаловать в супермаркет «КеремЕт»!',
    kk: '«КеремЕт» супермаркетіне қош келдіңіз!',
  },
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

  let currentStore: BusinessStore = { ...store };

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
        admin_max_stats_period_days: 90,
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
    if (url.includes(`/admin/businesses/${businessId}/stores/resolve-coordinates`)) {
      const body = typeof init?.body === 'string' ? JSON.parse(init.body) : {};
      const query = String(body.query || '');
      if (query.includes('2gis.kz') || query.includes('go.2gis.com')) {
        return json(200, {
          status: 'found',
          latitude: 43.238949,
          longitude: 76.889709,
          resolved_address: 'Координаты из метки 2ГИС',
        });
      }
      if (query === 'Абая 10') {
        return json(200, {
          status: 'ambiguous',
          message: 'Найдено несколько похожих адресов:',
          candidates: [
            { address: 'г. Алматы, пр. Абая, 10', latitude: 43.2401, longitude: 76.9205 },
            { address: 'г. Астана, ул. Абая, 10', latitude: 51.1501, longitude: 71.4305 },
          ],
        });
      }
      if (query.includes('Несуществующий')) {
        return json(200, {
          status: 'not_found',
          message: 'По указанному адресу объектов в Казахстане не найдено.',
        });
      }
      return json(200, {
        status: 'found',
        latitude: 51.13245,
        longitude: 71.46821,
        resolved_address: 'г. Астана, ул. Достык, 5',
      });
    }
    if (url.includes(`/admin/businesses/${businessId}/stores`)) {
      if (method === 'GET') {
        return json(200, [currentStore]);
      }
      if (method === 'POST') {
        return json(201, { ...store, id: 'new-store-id' });
      }
      if (method === 'PATCH') {
        const patchData = typeof init?.body === 'string' ? JSON.parse(init.body) : {};
        currentStore = { ...currentStore, ...patchData };
        return json(200, currentStore);
      }
      if (method === 'DELETE') {
        return new Response(null, { status: 204 });
      }
    }
    if (url.includes(`/admin/businesses/${businessId}/splash`)) {
      return json(200, { splash: null });
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
  renderAppContent('business_manager');

  const storesTab = await screen.findByRole('tab', { name: 'Магазины' });
  expect(storesTab).toBeInTheDocument();
  fireEvent.click(storesTab);

  expect(screen.queryByLabelText('Бизнес')).not.toBeInTheDocument();

  expect(await screen.findByText('Супермаркет «КеремЕт»')).toBeInTheDocument();
  expect(screen.getByText('проспект Тауелсиздик, 4')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Открыть на карте' })).toHaveAttribute(
    'href',
    'https://2gis.kz/astana/firm/70000001103172202'
  );

  const textsTab = screen.getByRole('tab', { name: 'Тексты' });
  fireEvent.click(textsTab);

  expect(await screen.findByDisplayValue('Баллы начисляются после смены')).toBeInTheDocument();
  expect(screen.queryByText('Текст на главной')).not.toBeInTheDocument();
  expect(document.getElementById('text-home-ru')).not.toBeInTheDocument();
  expect(document.getElementById('text-home-kk')).not.toBeInTheDocument();
  expect(document.querySelector('.home-text-preview-box')).not.toBeInTheDocument();
}, 15000);

it('validates store form and creates a store through the typed API', async () => {
  const fetchMock = renderAppContent('business_manager');

  fireEvent.click(await screen.findByRole('tab', { name: 'Магазины' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Добавить магазин' }));

  const dialog = await screen.findByRole('dialog');
  expect(within(dialog).getByText('Новый магазин')).toBeInTheDocument();

  // Invalid map url check
  fireEvent.change(within(dialog).getByLabelText('Название (RU)'), { target: { value: 'Новый Филиал' } });
  fireEvent.change(within(dialog).getByLabelText('Название (KK)'), { target: { value: 'Жаңа филиал' } });
  fireEvent.change(within(dialog).getByLabelText('Адрес (RU)'), { target: { value: 'ул. Сыганак, 1' } });
  fireEvent.change(within(dialog).getByLabelText('Адрес (KK)'), { target: { value: 'Сығанақ к-сі, 1' } });
  fireEvent.change(within(dialog).getByLabelText(/Ссылка на карту/i), {
    target: { value: 'http://insecure-site.kz' },
  });

  fireEvent.click(within(dialog).getByRole('button', { name: 'Сохранить' }));
  expect(
    await within(dialog).findByText(
      'Ссылка должна начинаться с https:// и содержать корректный адрес сайта'
    )
  ).toBeInTheDocument();

  // Fix URL and submit
  const mapInput = within(dialog).getByLabelText(/Ссылка на карту/i);
  fireEvent.change(mapInput, { target: { value: 'https://2gis.kz/astana/firm/12345' } });

  fireEvent.click(within(dialog).getByRole('button', { name: 'Сохранить' }));
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
  const confirmMock = vi.fn(() => true);
  vi.stubGlobal('confirm', confirmMock);

  const fetchMock = renderAppContent('business_manager');
  fireEvent.click(await screen.findByRole('tab', { name: 'Магазины' }));
  await screen.findByText('Супермаркет «КеремЕт»');

  fireEvent.click(screen.getByRole('button', { name: 'Удалить' }));

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

it('updates app texts in RU and KK while omitting hidden home_text to preserve stored value', async () => {
  const fetchMock = renderAppContent('business_manager');

  fireEvent.click(await screen.findByRole('tab', { name: 'Тексты' }));
  const delayRuInput = await screen.findByDisplayValue('Баллы начисляются после смены');

  fireEvent.change(delayRuInput, { target: { value: 'Новый текст задержки (RU)' } });
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить тексты' }));

  await waitFor(() => {
    const putCall = vi
      .mocked(fetchMock)
      .mock.calls.find(
        ([url, init]) =>
          String(url).endsWith(`/admin/businesses/${businessId}/app-texts`) &&
          init?.method === 'PUT'
      );
    expect(putCall).toBeDefined();
    const sent = JSON.parse(String(putCall?.[1]?.body)) as Record<string, unknown>;
    expect(sent).not.toHaveProperty('home_text');
    expect(sent).toMatchObject({
      balance_delay_note: {
        ru: 'Новый текст задержки (RU)',
        kk: 'Ұпайлар ауысымнан кейін есептеледі',
      },
    });
  });

  expect(await screen.findByText('Тексты успешно сохранены')).toBeInTheDocument();
});

it('superadmin sees business picker on app tab and prompt when unselected', async () => {
  renderAppContent('superadmin');

  fireEvent.click(await screen.findByRole('tab', { name: 'Магазины и инфо' }));
  expect(screen.getByLabelText('Бизнес')).toBeInTheDocument();
  expect(
    screen.getByText('Выберите бизнес для настройки магазинов и текстов приложения.')
  ).toBeInTheDocument();

  // Select business
  fireEvent.change(screen.getByLabelText('Бизнес'), { target: { value: businessId } });
  expect(await screen.findByText('Супермаркет «КеремЕт»')).toBeInTheDocument();
});

it('renders in Kazakh locale with proper translations', async () => {
  renderAppContent('business_manager', 'kk');

  const storesTab = await screen.findByRole('tab', { name: 'Дүкендер' });
  expect(storesTab).toBeInTheDocument();
  const textsTab = await screen.findByRole('tab', { name: 'Мәтіндер' });
  expect(textsTab).toBeInTheDocument();
});

it('manager edits store map url and coordinates, saves, and reopens modal seeing saved values', async () => {
  renderAppContent('business_manager');

  fireEvent.click(await screen.findByRole('tab', { name: 'Магазины' }));
  expect(await screen.findByText('Супермаркет «КеремЕт»')).toBeInTheDocument();

  // Open edit modal
  fireEvent.click(screen.getByRole('button', { name: 'Изменить' }));
  const dialog = await screen.findByRole('dialog');
  expect(within(dialog).getByText('Изменить магазин')).toBeInTheDocument();

  const mapInput = within(dialog).getByLabelText(/Ссылка на карту/i);
  const latInput = within(dialog).getByLabelText(/Широта/i);
  const lonInput = within(dialog).getByLabelText(/Долгота/i);

  fireEvent.change(mapInput, { target: { value: 'https://2gis.kz/astana/firm/70000001103172202' } });
  fireEvent.change(latInput, { target: { value: '51.13245' } });
  fireEvent.change(lonInput, { target: { value: '71.46821' } });

  const form = dialog.querySelector('form')!;
  fireEvent.submit(form);
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());

  // Verify coordinates are displayed in table
  expect(await screen.findByText(/51\.13245, 71\.46821/)).toBeInTheDocument();

  // Reopen modal to verify saved values persist in form
  fireEvent.click(screen.getByRole('button', { name: 'Изменить' }));
  const reopenedDialog = await screen.findByRole('dialog');

  expect(within(reopenedDialog).getByLabelText(/Ссылка на карту/i)).toHaveValue(
    'https://2gis.kz/astana/firm/70000001103172202'
  );
  expect(within(reopenedDialog).getByLabelText(/Широта/i)).toHaveValue(51.13245);
  expect(within(reopenedDialog).getByLabelText(/Долгота/i)).toHaveValue(71.46821);
}, 15000);

it('auto-resolves coordinates from 2GIS link, displays badge and populates coordinates', async () => {
  renderAppContent('business_manager');

  fireEvent.click(await screen.findByRole('tab', { name: 'Магазины' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Добавить магазин' }));
  const dialog = await screen.findByRole('dialog');

  const mapInput = within(dialog).getByLabelText(/Ссылка на карту/i);
  fireEvent.change(mapInput, {
    target: { value: 'https://2gis.kz/almaty/firm/70000001018042456?m=76.889709%2C43.238949%2F16' },
  });

  // Click auto-resolve
  fireEvent.click(within(dialog).getByRole('button', { name: 'Определить точку' }));

  // Verify coordinates are detected and badge is displayed
  expect(await within(dialog).findByText(/Точка определена/)).toBeInTheDocument();
  expect(within(dialog).getByText(/43\.238949, 76\.889709/)).toBeInTheDocument();

  // Verify input fields
  expect(within(dialog).getByLabelText(/Широта/i)).toHaveValue(43.238949);
  expect(within(dialog).getByLabelText(/Долгота/i)).toHaveValue(76.889709);

  // Verify "Проверить на карте" link is rendered
  expect(within(dialog).getByRole('link', { name: /Проверить на карте/i })).toHaveAttribute(
    'href',
    'https://maps.google.com/?q=43.238949,76.889709'
  );

  // Click clear coordinates
  fireEvent.click(within(dialog).getByRole('button', { name: 'Очистить точку' }));
  expect(within(dialog).getByLabelText(/Широта/i)).toHaveValue(null);
  expect(within(dialog).getByLabelText(/Долгота/i)).toHaveValue(null);
  expect(within(dialog).queryByText(/Точка определена/)).not.toBeInTheDocument();
});

it('auto-resolves ambiguous address, displays candidates, and sets selected point', async () => {
  renderAppContent('business_manager');

  fireEvent.click(await screen.findByRole('tab', { name: 'Магазины' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Добавить магазин' }));
  const dialog = await screen.findByRole('dialog');

  const addrInput = within(dialog).getByLabelText(/Адрес \(RU\)/i);
  fireEvent.change(addrInput, { target: { value: 'Абая 10' } });

  // Click auto-resolve
  fireEvent.click(within(dialog).getByRole('button', { name: 'Определить точку' }));

  // Ambiguous prompt and candidates
  expect(await within(dialog).findByText(/Найдено несколько адресов, выберите подходящий:/)).toBeInTheDocument();
  expect(within(dialog).getByText(/г\. Алматы, пр\. Абая, 10/)).toBeInTheDocument();
  expect(within(dialog).getByText(/г\. Астана, ул\. Абая, 10/)).toBeInTheDocument();

  // Pick first candidate
  const selectBtns = within(dialog).getAllByRole('button', { name: 'Выбрать' });
  fireEvent.click(selectBtns[0]);

  // Verify selected coordinates are populated and candidates list is closed
  expect(await within(dialog).findByText(/Точка определена/)).toBeInTheDocument();
  expect(within(dialog).getByLabelText(/Широта/i)).toHaveValue(43.2401);
  expect(within(dialog).getByLabelText(/Долгота/i)).toHaveValue(76.9205);
  expect(within(dialog).queryByText(/Найдено несколько адресов/)).not.toBeInTheDocument();
});

it('handles not-found coordinate resolution gracefully without erasing existing input', async () => {
  renderAppContent('business_manager');

  fireEvent.click(await screen.findByRole('tab', { name: 'Магазины' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Добавить магазин' }));
  const dialog = await screen.findByRole('dialog');

  const addrInput = within(dialog).getByLabelText(/Адрес \(RU\)/i);
  fireEvent.change(addrInput, { target: { value: 'Несуществующий переулок 99999' } });

  // Manually pre-set coordinates
  const latInput = within(dialog).getByLabelText(/Широта/i);
  const lonInput = within(dialog).getByLabelText(/Долгота/i);
  fireEvent.change(latInput, { target: { value: '43.111' } });
  fireEvent.change(lonInput, { target: { value: '76.222' } });

  // Click auto-resolve
  fireEvent.click(within(dialog).getByRole('button', { name: 'Определить точку' }));

  // Error is shown
  expect(await within(dialog).findByText('По указанному адресу объектов в Казахстане не найдено.')).toBeInTheDocument();

  // Coordinates are NOT erased or set to 0/0
  expect(latInput).toHaveValue(43.111);
  expect(lonInput).toHaveValue(76.222);
});
