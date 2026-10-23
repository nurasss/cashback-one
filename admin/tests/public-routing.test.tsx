import { lazy, Suspense } from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AppRouter, AppRoutes } from '../src/layout/AppRouter';
import { AdminErrorBoundary } from '../src/layout/AdminErrorBoundary';
import { ManagerAccessDialog } from '../src/features/AdminMutations';
import type { ManagerAccessDisclosure } from '../src/api/types';
import AdminRoutes from '../src/layout/AdminRoutes';

const json = (status: number, payload: unknown) =>
  new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

function LocationObserver({ onLocation }: { onLocation: (loc: { pathname: string; search: string; hash: string }) => void }) {
  const location = useLocation();
  onLocation({ pathname: location.pathname, search: location.search, hash: location.hash });
  return null;
}

afterEach(() => {
  cleanup();
  window.history.pushState({}, '', '/');
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe('Public Landing Isolation', () => {
  it('renders landing at / without triggering any API calls, even with missing or invalid API URL', async () => {
    vi.stubEnv('VITE_API_BASE_URL', '');
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    window.history.pushState({}, '', '/');
    render(<AppRouter />);

    // Проверяем главные элементы страницы
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/Бонусная карта в телефоне/i);
    expect(screen.queryByText(/Android, файл APK, версия 1\.0\.3\./i)).not.toBeInTheDocument();
    expect(screen.queryByText('Версии для iPhone пока нет.')).not.toBeInTheDocument();
    expect(
      screen.getAllByText(
        /Баланс обновляется не сразу\. Новые начисления и списания появляются 2 раза в сутки\./i
      ).length
    ).toBeGreaterThanOrEqual(2);

    // Ссылка на скачивание APK
    const downloadLinks = screen.getAllByRole('link', { name: /Скачать для Android/i });
    expect(downloadLinks.length).toBeGreaterThanOrEqual(1);
    for (const link of downloadLinks) {
      expect(link).toHaveAttribute('href', '/app/cashback-one-1.0.3.apk');
    }
    expect(screen.queryByRole('link', { name: 'Конфиденциальность' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Условия' })).not.toBeInTheDocument();

    // Ссылка на вход для бизнеса
    const loginLinks = screen.getAllByRole('link', { name: /Вход для бизнеса/i });
    expect(loginLinks.length).toBeGreaterThanOrEqual(1);
    expect(loginLinks[0]).toHaveAttribute('href', '/admin/login');

    // Ни одного вызова fetch!
    expect(fetchMock).not.toHaveBeenCalled();
    // URL остался /
    expect(window.location.pathname).toBe('/');
  });

  it('keeps public landing independent of broken API / server error', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://invalid-api-that-fails.poscenter.test');
    const fetchMock = vi.fn(async () => json(500, { error: { code: 'INTERNAL_ERROR' } }));
    vi.stubGlobal('fetch', fetchMock);

    window.history.pushState({}, '', '/');
    render(<AppRouter />);

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/Бонусная карта в телефоне/i);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('renders landing at / for authorized visitor without redirecting to /admin', async () => {
    // Авторизованный посетитель тоже видит лендинг на /
    window.history.pushState({}, '', '/');
    render(<AppRouter />);
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/Бонусная карта в телефоне/i);
    expect(window.location.pathname).toBe('/');
  });

  it('keeps unapproved legal drafts unpublished without API calls', () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    const privacyView = render(
      <MemoryRouter initialEntries={['/privacy']}>
        <AppRoutes />
      </MemoryRouter>
    );
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Страница не найдена');
    expect(screen.queryByText(/Категории обрабатываемых данных/i)).not.toBeInTheDocument();
    privacyView.unmount();

    const termsView = render(
      <MemoryRouter initialEntries={['/terms']}>
        <AppRoutes />
      </MemoryRouter>
    );
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Страница не найдена');
    expect(screen.queryByText(/Правила возврата товаров/i)).not.toBeInTheDocument();
    termsView.unmount();

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('switches among all four phone screens via mouse and keyboard without API calls', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    window.history.pushState({}, '', '/');
    render(<AppRouter />);

    const tabHome = screen.getByRole('tab', { name: 'Карта' });
    const tabBarcode = screen.getByRole('tab', { name: 'Штрихкод' });
    const tabHistory = screen.getByRole('tab', { name: 'История' });
    const tabPromotions = screen.getByRole('tab', { name: 'Акции' });

    expect(tabHome).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByText(/Карта и баланс\./i)).toBeInTheDocument();
    expect(screen.getByText(/Данные на экранах — пример/i)).toBeInTheDocument();

    // Переключение кликом на Штрихкод
    await user.click(tabBarcode);
    expect(tabBarcode).toHaveAttribute('aria-selected', 'true');
    expect(tabHome).toHaveAttribute('aria-selected', 'false');
    expect(screen.getByText(/Штрихкод\./i)).toBeInTheDocument();

    // Переключение кликом на Историю
    await user.click(tabHistory);
    expect(tabHistory).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByText(/История операций\./i)).toBeInTheDocument();

    // Переключение кликом на Акции
    await user.click(tabPromotions);
    expect(tabPromotions).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByText(/Акции и сообщения\./i)).toBeInTheDocument();

    // Клавиатурное переключение (ArrowLeft возвращает на Историю)
    await user.keyboard('{ArrowLeft}');
    expect(tabHistory).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByText(/История операций\./i)).toBeInTheDocument();

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('connects all tabs to existing tabpanels via aria-controls and hides inactive panels', async () => {
    const user = userEvent.setup();
    window.history.pushState({}, '', '/');
    render(<AppRouter />);

    const tabs = screen.getAllByRole('tab');
    expect(tabs).toHaveLength(4);

    const panels = screen.getAllByRole('tabpanel', { hidden: true });
    expect(panels).toHaveLength(4);

    // Verify each tab points to an existing panel and labelledby matches tab id
    tabs.forEach((tab) => {
      const controlsId = tab.getAttribute('aria-controls');
      expect(controlsId).toBeTruthy();
      const panel = document.getElementById(controlsId!);
      expect(panel).not.toBeNull();
      expect(panel?.getAttribute('role')).toBe('tabpanel');
      expect(panel?.getAttribute('aria-labelledby')).toBe(tab.getAttribute('id'));
    });

    // Initial state: only panel-home is visible, others are hidden
    const panelHome = document.getElementById('panel-home');
    const panelBarcode = document.getElementById('panel-barcode');
    const panelHistory = document.getElementById('panel-history');
    const panelPromotions = document.getElementById('panel-promotions');

    expect(panelHome).not.toHaveAttribute('hidden');
    expect(panelBarcode).toHaveAttribute('hidden');
    expect(panelHistory).toHaveAttribute('hidden');
    expect(panelPromotions).toHaveAttribute('hidden');

    // Switch to Barcode
    const tabBarcode = screen.getByRole('tab', { name: 'Штрихкод' });
    await user.click(tabBarcode);

    expect(panelHome).toHaveAttribute('hidden');
    expect(panelBarcode).not.toHaveAttribute('hidden');
    expect(panelHistory).toHaveAttribute('hidden');
    expect(panelPromotions).toHaveAttribute('hidden');

    // Switch to History
    const tabHistory = screen.getByRole('tab', { name: 'История' });
    await user.click(tabHistory);

    expect(panelBarcode).toHaveAttribute('hidden');
    expect(panelHistory).not.toHaveAttribute('hidden');
  });

  it('has no false submission form, fake button or draft notes on client page', () => {
    window.history.pushState({}, '', '/');
    render(<AppRouter />);

    // Нет фиктивной кнопки «Обсудить подключение» и ложной отправки
    expect(screen.queryByRole('button', { name: /Обсудить подключение/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('form')).not.toBeInTheDocument();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();

    // Нет служебных пометок и черновиков
    const bodyText = document.body.textContent || '';
    expect(bodyText).not.toMatch(/будет опубликовано/i);
    expect(bodyText).not.toMatch(/будут опубликованы/i);
    expect(bodyText).not.toMatch(/контакт не утверждён/i);
    expect(bodyText).not.toMatch(/записка команде/i);
  });
});

describe('Legacy Redirects with query, hash and trailing slashes', () => {
  it('redirects /login to /admin/login preserving query and hash', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
    vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');
    vi.stubGlobal('fetch', vi.fn(async () => json(401, { error: { code: 'ADMIN_UNAUTHENTICATED' } })));

    const history: Array<{ pathname: string; search: string; hash: string }> = [];
    render(
      <MemoryRouter initialEntries={['/login?return_to=foo#section']}>
        <LocationObserver onLocation={(loc) => { history.push({ ...loc }); }} />
        <AppRoutes />
      </MemoryRouter>
    );

    // Подтверждаем реальный переход с сохранением query и hash
    expect(history).toContainEqual({
      pathname: '/admin/login',
      search: '?return_to=foo',
      hash: '#section',
    });
    await screen.findByRole('heading', { name: 'Вход в систему' });
  });

  it('redirects legacy business path with trailing slash and query to /admin/businesses/:id', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
    vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');
    vi.stubGlobal('fetch', vi.fn(async () => json(401, { error: { code: 'ADMIN_UNAUTHENTICATED' } })));

    const history: Array<{ pathname: string; search: string; hash: string }> = [];
    render(
      <MemoryRouter initialEntries={['/businesses/biz-42/?tab=settings#anchor']}>
        <LocationObserver onLocation={(loc) => { history.push({ ...loc }); }} />
        <AppRoutes />
      </MemoryRouter>
    );

    // Сначала LegacyRedirect направляет на канонический /admin/businesses/biz-42 с query и hash
    expect(history).toContainEqual({
      pathname: '/admin/businesses/biz-42',
      search: '?tab=settings',
      hash: '#anchor',
    });
    // Затем для неавторизованного пользователя RequireAdmin переводит на логин
    await screen.findByRole('heading', { name: 'Вход в систему' });
  });

  it('redirects /operations, /agents, /cards, /audit, /content to /admin/... preserving parameters', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
    vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');
    vi.stubGlobal('fetch', vi.fn(async () => json(401, { error: { code: 'ADMIN_UNAUTHENTICATED' } })));

    const cases = [
      { from: '/operations?page=2&status=success', expected: { pathname: '/admin/operations', search: '?page=2&status=success', hash: '' } },
      { from: '/agents/ag-99?filter=active#logs', expected: { pathname: '/admin/agents/ag-99', search: '?filter=active', hash: '#logs' } },
      { from: '/cards/123456789', expected: { pathname: '/admin/cards/123456789', search: '', hash: '' } },
      { from: '/audit?limit=25', expected: { pathname: '/admin/audit', search: '?limit=25', hash: '' } },
      { from: '/content#news', expected: { pathname: '/admin/content', search: '', hash: '#news' } },
    ];

    for (const item of cases) {
      const history: Array<{ pathname: string; search: string; hash: string }> = [];
      const view = render(
        <MemoryRouter initialEntries={[item.from]}>
          <LocationObserver onLocation={(loc) => { history.push({ ...loc }); }} />
          <AppRoutes />
        </MemoryRouter>
      );
      expect(history).toContainEqual(item.expected);
      view.unmount();
    }
  });
});

describe('AdminErrorBoundary outside lazy chunk', () => {
  it('catches real React.lazy import failure, shows fallback UI, link to home, and triggers page reload', async () => {
    const user = userEvent.setup();
    const reloadSpy = vi.fn();

    // Настоящий React.lazy с отклонённым Promise (имитирует сетевой отказ загрузки JS-чанка)
    const FailingLazyComponent = lazy(() =>
      Promise.reject(new Error('Failed to fetch dynamically imported module: /assets/AdminRoutes.js'))
    );

    render(
      <AdminErrorBoundary onReload={reloadSpy}>
        <Suspense fallback={<div>Загрузка...</div>}>
          <FailingLazyComponent />
        </Suspense>
      </AdminErrorBoundary>
    );

    // Должна отобразиться панель сбоя
    expect(await screen.findByRole('heading', { name: 'Ошибка загрузки кабинета' })).toBeInTheDocument();
    expect(screen.getByText(/Не удалось загрузить модуль управления/i)).toBeInTheDocument();

    // Ссылка на главную
    const homeLink = screen.getByRole('link', { name: 'На главную' });
    expect(homeLink).toHaveAttribute('href', '/');

    // Кнопка восстановления через перезагрузку страницы
    const reloadBtn = screen.getByRole('button', { name: 'Перезагрузить страницу' });
    expect(reloadBtn).toBeInTheDocument();

    // Действие восстановления вызывает перезагрузку документа
    await user.click(reloadBtn);
    expect(reloadSpy).toHaveBeenCalledTimes(1);
  });
});

describe('Both 404 pages', () => {
  it('renders PublicNotFoundPage for unknown public routes without API calls', () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    render(
      <MemoryRouter initialEntries={['/unknown-public-page']}>
        <AppRoutes />
      </MemoryRouter>
    );

    expect(screen.getByText('ОШИБКА 404')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Страница не найдена' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'На главную страницу' })).toHaveAttribute('href', '/');
    expect(screen.getAllByRole('link', { name: 'Вход для бизнеса' })[0]).toHaveAttribute('href', '/admin/login');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('renders AdminNotFoundPage for unknown admin routes when authenticated', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://admin.test');
    vi.stubEnv('VITE_ALLOW_INSECURE_HTTP', '0');

    const fetchMock: typeof fetch = vi.fn(async (input) => {
      const url = String(input);
      if (url.endsWith('/admin/auth/refresh')) {
        return json(200, { access_token: 'fake-token', token_type: 'bearer', expires_in: 900 });
      }
      if (url.endsWith('/admin/me')) {
        return json(200, {
          admin: { id: 'admin-1', login: 'superadmin', role: 'superadmin', business: null },
        });
      }
      return json(404, {});
    });
    vi.stubGlobal('fetch', fetchMock);

    render(
      <MemoryRouter initialEntries={['/admin/non-existent-section']}>
        <Routes>
          <Route path="/admin/*" element={<AdminRoutes />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByRole('heading', { name: 'Страница не найдена' })).toBeInTheDocument();
    expect(screen.getByText(/Запрошенный административный раздел не существует/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Вернуться к обзору' })).toHaveAttribute('href', '/admin');
  });
});

describe('Manager Access Disclosure', () => {
  it('displays and copies identical canonical URL (${origin}/admin/login)', async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', { clipboard: { writeText } });

    const disclosure: ManagerAccessDisclosure = {
      login: 'manager-test',
      password: 'SafePassword123',
      login_url: 'https://backend-unmodified-url.kz',
      one_time: true,
    };

    render(<ManagerAccessDialog disclosure={disclosure} onClose={vi.fn()} />);

    const expectedUrl = `${window.location.origin}/admin/login`;
    const displayedUrl = screen.getByLabelText('Ссылка для входа').textContent;

    expect(displayedUrl).toBe(expectedUrl);

    const copyBtn = screen.getByRole('button', { name: 'Скопировать всё' });
    await user.click(copyBtn);

    expect(writeText).toHaveBeenCalledWith(
      `Ссылка: ${expectedUrl}\nЛогин: manager-test\nПароль: SafePassword123`
    );
  });
});
