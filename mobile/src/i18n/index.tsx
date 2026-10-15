import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import { kz } from './kz';
import { ru, type Dictionary } from './ru';

export type Language = 'ru' | 'kz';
type Key = keyof Dictionary;
const dictionaries: Record<Language, Dictionary> = { ru, kz };

export function translate(language: Language, key: Key, params?: Record<string, string | number>): string {
  const template = dictionaries[language][key] ?? ru[key];
  return params ? template.replace(/\{(\w+)\}/g, (_, name: string) => String(params[name] ?? '')) : template;
}

interface I18n { language: Language; setLanguage: (language: Language) => void; t: (key: Key, params?: Record<string, string | number>) => string }
const Context = createContext<I18n | null>(null);

export function I18nProvider({ children, initial = 'ru' }: { children: ReactNode; initial?: Language }) {
  const [language, setLanguage] = useState<Language>(initial);
  const t = useCallback((key: Key, params?: Record<string, string | number>) => translate(language, key, params), [language]);
  const value = useMemo(() => ({ language, setLanguage, t }), [language, t]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

const fallback: I18n = { language: 'ru', setLanguage: () => {}, t: (key, params) => translate('ru', key, params) };
export function useI18n(): I18n {
  return useContext(Context) ?? fallback;
}
