import type { SiteLocale } from '../i18n/types';

export function formatDate(value: string, locale: SiteLocale = 'ru'): string {
  const intlLocale = locale === 'kk' ? 'kk-KZ' : 'ru-RU';
  return new Intl.DateTimeFormat(intlLocale, {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'UTC',
  }).format(new Date(value));
}

export function formatDateOnly(value: string, locale: SiteLocale = 'ru'): string {
  const intlLocale = locale === 'kk' ? 'kk-KZ' : 'ru-RU';
  return new Intl.DateTimeFormat(intlLocale, {
    dateStyle: 'medium',
    timeZone: 'UTC',
  }).format(new Date(value));
}

export function formatNumber(value: number, locale: SiteLocale = 'ru'): string {
  const intlLocale = locale === 'kk' ? 'kk-KZ' : 'ru-RU';
  return new Intl.NumberFormat(intlLocale).format(value);
}

export function formatBalance(value: string): string {
  const [integer = '0', fraction = ''] = value.split('.');
  const normalizedFraction = fraction.replace(/0+$/, '');
  return `${integer.replace(/\B(?=(\d{3})+(?!\d))/g, ' ')}${normalizedFraction ? `,${normalizedFraction}` : ''}`;
}

export function localDate(value: Date): string {
  const date = new Date(value.getTime() - value.getTimezoneOffset() * 60_000);
  return date.toISOString().slice(0, 10);
}

export function dayBoundary(day: string, end: boolean): string {
  const date = new Date(`${day}T00:00:00`);
  if (end) date.setDate(date.getDate() + 1);
  if (end) date.setMilliseconds(date.getMilliseconds() - 1);
  return date.toISOString();
}
