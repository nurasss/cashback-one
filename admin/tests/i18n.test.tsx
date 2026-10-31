import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { publicRu, publicKk } from '../src/i18n/public';
import { adminRu, adminKk } from '../src/i18n/admin';
import {
  LOCALE_STORAGE_KEY,
  getStoredLocale,
  setStoredLocale,
  LocaleProvider,
  useLocale,
  LanguageSwitcher,
} from '../src/i18n/LocaleContext';
import { formatDate, formatDateOnly, formatNumber } from '../src/utils/format';
import { ApiError, messageForError } from '../src/api/errors';
import { AppRouter } from '../src/layout/AppRouter';

function getDeepKeys(obj: Record<string, unknown>, prefix = ''): string[] {
  let keys: string[] = [];
  for (const [k, v] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object') {
      keys = keys.concat(getDeepKeys(v as Record<string, unknown>, fullKey));
    } else {
      keys.push(fullKey);
    }
  }
  return keys.sort();
}

afterEach(() => {
  cleanup();
  window.history.pushState({}, '', '/');
  try {
    window.localStorage.clear();
  } catch {
    // ignore
  }
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe('1. Dictionary Key Parity and Structure', () => {
  it('publicRu and publicKk have 100% matching translation keys', () => {
    const ruKeys = getDeepKeys(publicRu as unknown as Record<string, unknown>);
    const kkKeys = getDeepKeys(publicKk as unknown as Record<string, unknown>);
    expect(ruKeys).toEqual(kkKeys);
    expect(ruKeys.length).toBeGreaterThan(40);
  });

  it('adminRu and adminKk have 100% matching translation keys', () => {
    const ruKeys = getDeepKeys(adminRu as unknown as Record<string, unknown>);
    const kkKeys = getDeepKeys(adminKk as unknown as Record<string, unknown>);
    expect(ruKeys).toEqual(kkKeys);
    expect(ruKeys.length).toBeGreaterThan(150);
  });

  it('contains expected Kazakh specific letters in KK dictionaries', () => {
    const allKkPublic = JSON.stringify(publicKk);
    const allKkAdmin = JSON.stringify(adminKk);
    const kazakhGlyphs = /[әғқңөұүһіӘҒҚҢӨҰҮҺІ]/;
    expect(kazakhGlyphs.test(allKkPublic)).toBe(true);
    expect(kazakhGlyphs.test(allKkAdmin)).toBe(true);
  });
});

describe('2. Storage and Fallback Resilience', () => {
  it('defaults to ru when localStorage is empty', () => {
    window.localStorage.removeItem(LOCALE_STORAGE_KEY);
    expect(getStoredLocale()).toBe('ru');
  });

  it('reads stored kk locale correctly', () => {
    setStoredLocale('kk');
    expect(getStoredLocale()).toBe('kk');
  });

  it('safely falls back to ru on invalid or corrupted values', () => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, 'kz');
    expect(getStoredLocale()).toBe('ru');

    window.localStorage.setItem(LOCALE_STORAGE_KEY, 'en');
    expect(getStoredLocale()).toBe('ru');

    window.localStorage.setItem(LOCALE_STORAGE_KEY, '{"bad": 1}');
    expect(getStoredLocale()).toBe('ru');

    window.localStorage.setItem(LOCALE_STORAGE_KEY, '');
    expect(getStoredLocale()).toBe('ru');
  });

  it('survives throwing localStorage (e.g. disabled cookies/strict privacy)', () => {
    const original = Object.getOwnPropertyDescriptor(window, 'localStorage')!;
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      get() { throw new DOMException('Access denied', 'SecurityError'); },
    });
    try {
      expect(getStoredLocale()).toBe('ru');
      expect(() => setStoredLocale('kk')).not.toThrow();
    } finally {
      Object.defineProperty(window, 'localStorage', original);
    }
  });

  it('syncs document.documentElement.lang with chosen locale', () => {
    function TestComp() {
      const { locale, setLocale } = useLocale();
      return (
        <div>
          <span data-testid="cur">{locale}</span>
          <button type="button" onClick={() => setLocale('kk')}>Switch KK</button>
          <button type="button" onClick={() => setLocale('ru')}>Switch RU</button>
        </div>
      );
    }

    render(
      <LocaleProvider initialLocale="ru">
        <TestComp />
      </LocaleProvider>
    );

    expect(document.documentElement.lang).toBe('ru');
    expect(screen.getByTestId('cur')).toHaveTextContent('ru');

    fireEvent.click(screen.getByRole('button', { name: 'Switch KK' }));
    expect(document.documentElement.lang).toBe('kk');
    expect(screen.getByTestId('cur')).toHaveTextContent('kk');

    fireEvent.click(screen.getByRole('button', { name: 'Switch RU' }));
    expect(document.documentElement.lang).toBe('ru');
    expect(screen.getByTestId('cur')).toHaveTextContent('ru');
  });
});

describe('3. Formatting and Error Messages in RU and KK', () => {
  const testIso = '2026-10-23T12:30:00Z';

  it('formats dates in ru and kk locales', () => {
    const formattedRu = formatDate(testIso, 'ru');
    const formattedKk = formatDate(testIso, 'kk');
    expect(formattedRu).toBeDefined();
    expect(formattedKk).toBeDefined();
    expect(formattedRu).toContain('2026');
    expect(formattedKk).toContain('2026');
  });

  it('formats date only in ru and kk locales', () => {
    const dRu = formatDateOnly(testIso, 'ru');
    const dKk = formatDateOnly(testIso, 'kk');
    expect(dRu).toBeDefined();
    expect(dKk).toBeDefined();
    expect(dRu).toContain('2026');
    expect(dKk).toContain('2026');
  });

  it('formats numbers according to locale conventions', () => {
    const nRu = formatNumber(1000000, 'ru');
    const nKk = formatNumber(1000000, 'kk');
    expect(nRu).toBeDefined();
    expect(nKk).toBeDefined();
  });

  it('translates ApiError codes into both RU and KK safe messages', () => {
    const errCreds = new ApiError('INVALID_CREDENTIALS', 401);
    expect(messageForError(errCreds, 'ru')).toBe('Неверный логин или пароль.');
    expect(messageForError(errCreds, 'kk')).toBe('Қате логин немесе құпиясөз.');

    const errUnknown = new ApiError('SOMETHING_STRANGE_FROM_SERVER', 500);
    expect(messageForError(errUnknown, 'ru')).toBe('Произошла ошибка. Повторите запрос.');
    expect(messageForError(errUnknown, 'kk')).toBe('Қате орын алды. Қайталап көріңіз.');
  });
});

describe('4. Public Landing Localization & State Invariants', () => {
  it('renders Landing in Russian with correct hero and constraints', () => {
    setStoredLocale('ru');
    render(<AppRouter />);

    // Заголовок первого экрана
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/Бонусная карта в[\s\u00A0]телефоне/);

    // Под кнопками hero удалены обе подписи
    expect(screen.queryByText(/Android, файл APK, версия 1\.0\.3\./i)).not.toBeInTheDocument();
    expect(screen.queryByText('Версии для iPhone пока нет.')).not.toBeInTheDocument();

    // Основная APK-ссылка
    const apkLinks = screen.getAllByRole('link', { name: /Скачать для Android/i });
    expect(apkLinks.length).toBeGreaterThan(0);
    for (const link of apkLinks) {
      expect(link).toHaveAttribute('href', '/app/cashback-one-1.0.8.apk');
    }

    // Утверждённое пояснение про задержку баланса
    expect(
      screen.getAllByText(
        /Баланс обновляется не сразу\. Новые начисления и списания появляются 2 раза в сутки\./i
      ).length
    ).toBeGreaterThanOrEqual(1);

    // Кнопка входа в админку видна
    expect(screen.getByRole('link', { name: 'Вход для бизнеса' })).toHaveAttribute('href', '/admin/login');
  });

  it('renders Landing in Kazakh when toggled via switcher', async () => {
    const user = userEvent.setup();
    setStoredLocale('ru');
    render(<AppRouter />);

    // Исходно на русском
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/Бонусная карта в[\s\u00A0]телефоне/);

    // Находим кнопку ҚАЗ в переключателе
    const kkButton = screen.getByRole('button', { name: 'ҚАЗ' });
    await user.click(kkButton);

    // Проверяем смену заголовка на казахский
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Бонустық карта телефоныңызда');

    // Под кнопками hero удалены обе подписи на обоих языках
    expect(screen.queryByText(/Android, файл APK, версия 1\.0\.3\./i)).not.toBeInTheDocument();
    expect(screen.queryByText('Версии для iPhone пока нет.')).not.toBeInTheDocument();
    expect(screen.queryByText('Әзірше iPhone нұсқасы жоқ.')).not.toBeInTheDocument();

    // Ссылка на APK остаётся 1.0.8
    const kkApkLinks = screen.getAllByRole('link', { name: /Android үшін жүктеп алу/i });
    expect(kkApkLinks.length).toBeGreaterThan(0);
    for (const link of kkApkLinks) {
      expect(link).toHaveAttribute('href', '/app/cashback-one-1.0.8.apk');
    }

    // Утверждённое пояснение на казахском
    expect(
      screen.getAllByText(
        /Баланс бірден жаңартылмайды\. Жаңа есептеулер мен есептен шығарулар тәулігіне 2 рет көрсетіледі\./i
      ).length
    ).toBeGreaterThanOrEqual(1);

    // Ссылка для бизнеса переведена
    expect(screen.getByRole('link', { name: 'Бизнеске кіру' })).toHaveAttribute('href', '/admin/login');

    // document.documentElement.lang обновился
    expect(document.documentElement.lang).toBe('kk');
    expect(window.localStorage.getItem(LOCALE_STORAGE_KEY)).toBe('kk');
  });

  it('preserves form input values across language toggle', async () => {
    const user = userEvent.setup();

    function FormWithLang() {
      return (
        <div>
          <LanguageSwitcher />
          <label htmlFor="test-input">Test Field</label>
          <input id="test-input" defaultValue="user-typed-content" />
        </div>
      );
    }

    render(
      <LocaleProvider initialLocale="ru">
        <FormWithLang />
      </LocaleProvider>
    );

    const input = screen.getByLabelText('Test Field');
    await user.clear(input);
    await user.type(input, 'my-preserved-value');
    expect(input).toHaveValue('my-preserved-value');

    // Переключаем язык на ҚАЗ
    const kkBtn = screen.getByRole('button', { name: 'ҚАЗ' });
    await user.click(kkBtn);

    // Значение инпута сохранилось
    expect(screen.getByLabelText('Test Field')).toHaveValue('my-preserved-value');

    // Переключаем обратно на RU
    const ruBtn = screen.getByRole('button', { name: 'RU' });
    await user.click(ruBtn);
    expect(screen.getByLabelText('Test Field')).toHaveValue('my-preserved-value');
  });
});
