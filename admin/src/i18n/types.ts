export type SiteLocale = 'ru' | 'kk';
export type IntlLocale = 'ru-RU' | 'kk-KZ';

export const SUPPORTED_LOCALES: readonly SiteLocale[] = ['ru', 'kk'] as const;

export const INTL_LOCALE_MAP: Record<SiteLocale, IntlLocale> = {
  ru: 'ru-RU',
  kk: 'kk-KZ',
};
