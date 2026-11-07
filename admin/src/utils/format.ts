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

export function formatAstanaSchedule(value: string): string {
  const date = new Date(value);
  if (isNaN(date.getTime())) return '';
  const astanaMs = date.getTime() + 5 * 3600 * 1000;
  const d = new Date(astanaMs);
  const day = String(d.getUTCDate()).padStart(2, '0');
  const month = String(d.getUTCMonth() + 1).padStart(2, '0');
  const hour = String(d.getUTCHours()).padStart(2, '0');
  const minute = String(d.getUTCMinutes()).padStart(2, '0');
  return `${day}.${month} ${hour}:${minute}`;
}

export function astanaLocalToUtcIso(localVal: string): string {
  const [datePart, timePart] = localVal.split('T');
  if (!datePart || !timePart) return '';
  const [yearStr, monthStr, dayStr] = datePart.split('-');
  const [hourStr, minStr] = timePart.split(':');
  if (!yearStr || !monthStr || !dayStr || !hourStr || !minStr) return '';
  const year = parseInt(yearStr, 10);
  const month = parseInt(monthStr, 10);
  const day = parseInt(dayStr, 10);
  const hour = parseInt(hourStr, 10);
  const min = parseInt(minStr, 10);
  const utcMs = Date.UTC(year, month - 1, day, hour - 5, min, 0, 0);
  return new Date(utcMs).toISOString();
}

export function getAstanaNowLocal(): string {
  const now = new Date();
  const astanaMs = now.getTime() + 5 * 3600 * 1000;
  const d = new Date(astanaMs);
  const year = d.getUTCFullYear();
  const month = String(d.getUTCMonth() + 1).padStart(2, '0');
  const day = String(d.getUTCDate()).padStart(2, '0');
  const hour = String(d.getUTCHours()).padStart(2, '0');
  const min = String(d.getUTCMinutes()).padStart(2, '0');
  return `${year}-${month}-${day}T${hour}:${min}`;
}
