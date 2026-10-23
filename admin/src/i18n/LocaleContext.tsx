import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { INTL_LOCALE_MAP, type IntlLocale, type SiteLocale } from './types';

export const LOCALE_STORAGE_KEY = 'c1_site_lang';

export function getStoredLocale(): SiteLocale {
  try {
    if (typeof window === 'undefined' || !window.localStorage) {
      return 'ru';
    }
    const val = window.localStorage.getItem(LOCALE_STORAGE_KEY);
    if (val === 'kk' || val === 'ru') {
      return val;
    }
    return 'ru';
  } catch {
    return 'ru';
  }
}

export function setStoredLocale(locale: SiteLocale): void {
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
    }
  } catch {
    // Gracefully ignore storage quota or access errors
  }
}

interface LocaleContextValue {
  locale: SiteLocale;
  setLocale: (next: SiteLocale) => void;
  intlLocale: IntlLocale;
}

const LocaleContext = createContext<LocaleContextValue>({
  locale: 'ru',
  setLocale: () => {},
  intlLocale: 'ru-RU',
});

export function LocaleProvider({
  children,
  initialLocale,
}: {
  children: ReactNode;
  initialLocale?: SiteLocale;
}) {
  const [locale, setLocaleState] = useState<SiteLocale>(() => initialLocale ?? getStoredLocale());

  const setLocale = (next: SiteLocale) => {
    if (next !== 'ru' && next !== 'kk') return;
    setLocaleState(next);
    setStoredLocale(next);
  };

  useEffect(() => {
    if (typeof document !== 'undefined' && document.documentElement) {
      document.documentElement.lang = locale;
    }
  }, [locale]);

  const value: LocaleContextValue = {
    locale,
    setLocale,
    intlLocale: INTL_LOCALE_MAP[locale] ?? 'ru-RU',
  };

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale(): LocaleContextValue {
  return useContext(LocaleContext);
}

export interface LanguageSwitcherProps {
  className?: string;
}

export function LanguageSwitcher({ className = '' }: LanguageSwitcherProps) {
  const { locale, setLocale } = useLocale();

  return (
    <div
      className={`lang-switcher ${className}`.trim()}
      role="group"
      aria-label={locale === 'kk' ? 'Тілді таңдау' : 'Выбор языка'}
    >
      <button
        type="button"
        className={`lang-btn ${locale === 'ru' ? 'lang-btn-active' : ''}`}
        aria-pressed={locale === 'ru'}
        onClick={() => setLocale('ru')}
      >
        RU
      </button>
      <span className="lang-divider" aria-hidden="true">
        /
      </span>
      <button
        type="button"
        className={`lang-btn ${locale === 'kk' ? 'lang-btn-active' : ''}`}
        aria-pressed={locale === 'kk'}
        onClick={() => setLocale('kk')}
      >
        ҚАЗ
      </button>
    </div>
  );
}
