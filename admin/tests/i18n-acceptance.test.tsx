import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../src/api/errors';
import { LanguageSwitcher, LocaleProvider, LOCALE_STORAGE_KEY } from '../src/i18n/LocaleContext';
import { getPublicTranslations } from '../src/i18n/public';
import { getAdminTranslations } from '../src/i18n/admin';
import { AdminErrorBoundary } from '../src/layout/AdminErrorBoundary';
import { LandingPage } from '../src/pages/LandingPage';
import { LoginPage } from '../src/pages/LoginPage';

const { login } = vi.hoisted(() => ({ login: vi.fn() }));
vi.mock('../src/auth/provider', () => ({
  useAdminSession: () => ({ session: { login }, view: { status: 'anonymous' } }),
}));

afterEach(() => {
  cleanup();
  window.localStorage.removeItem(LOCALE_STORAGE_KEY);
  document.documentElement.lang = 'ru';
  vi.restoreAllMocks();
  login.mockReset();
});

function BrokenModule(): never {
  throw new Error('Synthetic chunk failure: must never be displayed');
}

describe('Independent localization acceptance', () => {
  it.each([false, true])('switches the real error screen in both directions (storage denied: %s)', blocked => {
    const storage = Object.getOwnPropertyDescriptor(window, 'localStorage')!;
    if (blocked) {
      Object.defineProperty(window, 'localStorage', {
        configurable: true,
        get() { throw new DOMException('Access denied', 'SecurityError'); },
      });
    }
    const reload = vi.fn();
    vi.spyOn(console, 'error').mockImplementation(() => {});
    try {
      render(
        <LocaleProvider initialLocale="ru">
          <AdminErrorBoundary onReload={reload}><BrokenModule /></AdminErrorBoundary>
        </LocaleProvider>,
      );
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(getPublicTranslations('ru').adminChunkError.title);
      fireEvent.click(screen.getByRole('button', { name: 'ҚАЗ' }));
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(getPublicTranslations('kk').adminChunkError.title);
      expect(document.documentElement.lang).toBe('kk');
      fireEvent.click(screen.getByRole('button', { name: 'RU' }));
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(getPublicTranslations('ru').adminChunkError.title);
      expect(screen.queryByText(/Synthetic chunk failure/)).not.toBeInTheDocument();
      fireEvent.click(screen.getByRole('button', { name: getPublicTranslations('ru').adminChunkError.reloadBtn }));
      expect(reload).toHaveBeenCalledTimes(1);
    } finally {
      Object.defineProperty(window, 'localStorage', storage);
    }
  });

  it('preserves actual login/password fields and location, and translates an existing login error', async () => {
    function Location() {
      const location = useLocation();
      return <output data-testid="location">{location.pathname + location.search + location.hash}</output>;
    }
    login.mockRejectedValue(new ApiError('INVALID_CREDENTIALS', 401));
    render(
      <MemoryRouter initialEntries={['/admin/login?from=acceptance#entry']}>
        <LocaleProvider initialLocale="ru"><LoginPage /><Location /></LocaleProvider>
      </MemoryRouter>,
    );
    const username = screen.getByLabelText(getAdminTranslations('ru').login.loginLabel);
    const password = screen.getByLabelText(getAdminTranslations('ru').login.passwordLabel);
    fireEvent.change(username, { target: { value: 'fixture-user' } });
    fireEvent.change(password, { target: { value: 'synthetic-password' } });
    fireEvent.click(screen.getByRole('button', { name: 'ҚАЗ' }));
    expect(screen.getByLabelText(getAdminTranslations('kk').login.loginLabel)).toBe(username);
    expect(screen.getByLabelText(getAdminTranslations('kk').login.passwordLabel)).toBe(password);
    expect(username).toHaveValue('fixture-user');
    expect(password).toHaveValue('synthetic-password');
    expect(login).not.toHaveBeenCalled();
    expect(screen.getByTestId('location')).toHaveTextContent('/admin/login?from=acceptance#entry');
    fireEvent.submit(screen.getByRole('form'));
    expect(await screen.findByRole('alert')).toHaveTextContent(getAdminTranslations('kk').errors.INVALID_CREDENTIALS);
    expect(password).toHaveValue('');
    fireEvent.click(screen.getByRole('button', { name: 'RU' }));
    expect(screen.getByRole('alert')).toHaveTextContent(getAdminTranslations('ru').errors.INVALID_CREDENTIALS);
    expect(username).toHaveValue('fixture-user');
    expect(login).toHaveBeenCalledTimes(1);
  });

  it.each(['ru', 'kk'] as const)('renders the latest approved balance and points copy in %s', locale => {
    const t = getPublicTranslations(locale);
    render(<LocaleProvider initialLocale={locale}><LandingPage /><LanguageSwitcher /></LocaleProvider>);
    const bonus = screen.getByRole('region', { name: t.bonus.title });
    expect(within(bonus).getByText(t.bonus.lead)).toBeInTheDocument();
    for (const text of [t.bonus.pointsText1, t.bonus.pointsText2, t.bonus.pointsText3]) {
      expect(within(bonus).getByText(text)).toBeInTheDocument();
    }
    expect(screen.getAllByText(t.bonus.lead)).toHaveLength(2);
    expect(bonus.querySelector('.landing-bonus-explanation')).toBeNull();
    if (locale === 'ru') {
      expect(t.bonus.lead).toBe('Баланс обновляется не сразу. Новые начисления и списания появляются 2 раза в сутки.');
      expect([t.bonus.pointsText1, t.bonus.pointsText2, t.bonus.pointsText3].join(' ')).toBe(
        'Правила начисления, списания и использования баллов / скидок определяет магазин. Приложение не изменяет их количество или правила списания. По всем вопросам применения скидок / баллов обращайтесь в магазин.',
      );
    } else {
      expect(t.bonus.lead).toContain('тәулігіне 2 рет');
      expect(t.bonus.pointsText1).toContain('жеңілдіктерді');
    }
    expect(screen.queryByText(/когда магазин передаст данные/)).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: t.hero.downloadBtn })).toHaveAttribute('href', '/app/cashback-one-1.0.8.apk');
  });
});
