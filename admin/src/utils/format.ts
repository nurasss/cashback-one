import type { SiteLocale } from '../i18n/types';

export function formatDate(value: string, locale: SiteLocale = 'ru'): string {
  const intlLocale = locale === 'kk' ? 'kk-KZ' : 'ru-RU';
  const d = new Date(value);
  if (isNaN(d.getTime())) return '';
  const astanaDate = new Date(d.getTime() + 5 * 3600 * 1000);
  return new Intl.DateTimeFormat(intlLocale, {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'UTC',
  }).format(astanaDate);
}

export function formatDateOnly(value: string, locale: SiteLocale = 'ru'): string {
  const intlLocale = locale === 'kk' ? 'kk-KZ' : 'ru-RU';
  const d = new Date(value);
  if (isNaN(d.getTime())) return '';
  const astanaDate = new Date(d.getTime() + 5 * 3600 * 1000);
  return new Intl.DateTimeFormat(intlLocale, {
    dateStyle: 'medium',
    timeZone: 'UTC',
  }).format(astanaDate);
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
  const d = new Date(value.getTime() + 5 * 3600 * 1000);
  const year = d.getUTCFullYear();
  const month = String(d.getUTCMonth() + 1).padStart(2, '0');
  const day = String(d.getUTCDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function dayBoundary(day: string, end: boolean): string {
  const parts = day.split('-');
  const year = parseInt(parts[0] ?? '1970', 10);
  const month = parseInt(parts[1] ?? '1', 10);
  const dayNum = parseInt(parts[2] ?? '1', 10);
  if (end) {
    const ms = Date.UTC(year, month - 1, dayNum, 23 - 5, 59, 59, 999);
    return new Date(ms).toISOString();
  }
  const ms = Date.UTC(year, month - 1, dayNum, 0 - 5, 0, 0, 0);
  return new Date(ms).toISOString();
}

export function calendarDaysInclusive(from: string, to: string): number {
  if (!isValidDateOnly(from) || !isValidDateOnly(to) || from > to) return 0;
  const start = Date.parse(`${from}T00:00:00.000Z`);
  const end = Date.parse(`${to}T00:00:00.000Z`);
  return Math.floor((end - start) / 86400_000) + 1;
}

export function shiftAstanaDay(day: string, deltaDays: number): string {
  if (!isValidDateOnly(day)) return day;
  const ms = Date.parse(`${day}T00:00:00.000Z`) + deltaDays * 86400_000;
  const d = new Date(ms);
  const year = d.getUTCFullYear();
  const month = String(d.getUTCMonth() + 1).padStart(2, '0');
  const dayNum = String(d.getUTCDate()).padStart(2, '0');
  return `${year}-${month}-${dayNum}`;
}

export function isoToAstanaDay(value: string | null | undefined): string | null {
  if (!value || typeof value !== 'string') return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) {
    return isValidDateOnly(trimmed) ? trimmed : null;
  }
  const hasTz = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(trimmed);
  const normalized = !hasTz && /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?$/.test(trimmed)
    ? `${trimmed.replace(' ', 'T')}Z`
    : trimmed;
  const d = new Date(normalized);
  if (Number.isNaN(d.getTime())) return null;
  return localDate(d);
}

export function clampDefaultPeriodDays(
  fromDay: string,
  toDay: string,
  minDay: string | null,
  maxDay: string,
): { from: string; to: string } {
  let clampedTo = toDay > maxDay ? maxDay : toDay;
  if (minDay && clampedTo < minDay) {
    clampedTo = minDay;
  }
  let clampedFrom = fromDay > clampedTo ? clampedTo : fromDay;
  if (minDay && clampedFrom < minDay) {
    clampedFrom = minDay;
  }
  if (clampedFrom > clampedTo) {
    clampedFrom = clampedTo;
  }
  return { from: clampedFrom, to: clampedTo };
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

export function isValidDateOnly(val: string): boolean {
  if (!val) return false;
  // Year must be strictly 4 digits (1000-9999), month 01-12, day 01-31
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(val);
  if (!match || !match[1] || !match[2] || !match[3]) return false;
  const year = parseInt(match[1], 10);
  const month = parseInt(match[2], 10);
  const day = parseInt(match[3], 10);

  if (year < 1000 || year > 9999) return false;
  if (month < 1 || month > 12) return false;

  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate();
  if (day < 1 || day > daysInMonth) return false;

  return true;
}

export function isValidAstanaDateTimeLocal(val: string): boolean {
  if (!val) return false;
  // Year must be strictly 4 digits, month 01-12, day 01-31, hour 00-23, min 00-59
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/.exec(val);
  if (!match || !match[1] || !match[2] || !match[3] || !match[4] || !match[5]) return false;
  const year = parseInt(match[1], 10);
  const month = parseInt(match[2], 10);
  const day = parseInt(match[3], 10);
  const hour = parseInt(match[4], 10);
  const min = parseInt(match[5], 10);
  const sec = match[6] ? parseInt(match[6], 10) : 0;

  if (year < 2000 || year > 2100) return false;
  if (month < 1 || month > 12) return false;
  if (hour < 0 || hour > 23 || min < 0 || min > 59 || sec < 0 || sec > 59) return false;

  // Real calendar day check (handling leap years and month lengths)
  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate();
  if (day < 1 || day > daysInMonth) return false;

  return true;
}

export function astanaLocalToUtcIso(localVal: string): string {
  if (!isValidAstanaDateTimeLocal(localVal)) return '';
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

export function utcIsoToAstanaLocal(iso: string | null | undefined): string {
  if (!iso) return '';
  const date = new Date(iso);
  if (isNaN(date.getTime())) return '';
  const astanaMs = date.getTime() + 5 * 3600 * 1000;
  const d = new Date(astanaMs);
  const year = d.getUTCFullYear();
  const month = String(d.getUTCMonth() + 1).padStart(2, '0');
  const day = String(d.getUTCDate()).padStart(2, '0');
  const hour = String(d.getUTCHours()).padStart(2, '0');
  const min = String(d.getUTCMinutes()).padStart(2, '0');
  return `${year}-${month}-${day}T${hour}:${min}`;
}

export function formatAstanaDateTime(value: string | null | undefined): string {
  if (!value) return '';
  const date = new Date(value);
  if (isNaN(date.getTime())) return '';
  const astanaMs = date.getTime() + 5 * 3600 * 1000;
  const d = new Date(astanaMs);
  const day = String(d.getUTCDate()).padStart(2, '0');
  const month = String(d.getUTCMonth() + 1).padStart(2, '0');
  const year = d.getUTCFullYear();
  const hour = String(d.getUTCHours()).padStart(2, '0');
  const minute = String(d.getUTCMinutes()).padStart(2, '0');
  return `${day}.${month}.${year} ${hour}:${minute}`;
}
