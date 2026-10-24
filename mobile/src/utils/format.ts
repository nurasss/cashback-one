import { translate, type Language } from '../i18n';

export const isBarcode = (value: string): boolean => /^[0-9]{4,13}$/.test(value);

const group = (whole: string) => whole.replace(/\B(?=(\d{3})+(?!\d))/g, ' ');

// Format Decimal text without floating point rounding or precision loss.
export function decimalText(value: string): string {
  const [whole = '', fraction = ''] = value.split('.');
  const trimmed = fraction.replace(/0+$/, '');
  return `${group(whole)}${trimmed ? ',' + trimmed : ''}`;
}

// Points as shown in the design: always two decimals ("0,00", "1 500,50"); truncates, never rounds up.
export function pointsText(value: string | null | undefined): string {
  const [rawWhole = '0', fraction = ''] = (value ?? '0').split('.');
  const negative = rawWhole.startsWith('-');
  const whole = rawWhole.replace('-', '') || '0';
  return `${negative ? '-' : ''}${group(whole)},${(fraction + '00').slice(0, 2)}`;
}

// Whole tenge amount for level progress ("350 000").
export const amountText = (value: string | null | undefined): string => group((value ?? '0').split('.')[0]?.replace('-', '') || '0');

export const percentText = (value: string | null | undefined): string => decimalText(value ?? '0');

export function phoneText(phone: string | null | undefined): string {
  const digits = (phone ?? '').replace(/\D/g, '');
  if (digits.length === 11 && digits.startsWith('7')) return `+7 ${digits.slice(1, 4)} ${digits.slice(4, 7)} ${digits.slice(7, 9)} ${digits.slice(9)}`;
  return phone ?? '';
}

const locale = (language: Language) => (language === 'kz' ? 'kk-KZ' : 'ru-RU');
export const dateText = (value: string | number, language: Language = 'ru') =>
  new Date(value).toLocaleString(locale(language), { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' });
export const dayText = (value: string, language: Language = 'ru') =>
  new Date(value).toLocaleDateString(locale(language), { day: 'numeric', month: 'long', year: 'numeric' });

export function transactionLabel(type: string, language: Language = 'ru'): string {
  return type === 'accrual' ? translate(language, 'accrual') : type === 'redemption' ? translate(language, 'redemption') : type;
}

// Birth date: DD.MM.YYYY in the UI, YYYY-MM-DD on the wire.
export function birthDateToUi(value: string | null | undefined): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value ?? '');
  return match ? `${match[3]}.${match[2]}.${match[1]}` : '';
}
export function birthDateToApi(value: string): string | null | undefined {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const match = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(trimmed);
  if (!match) return undefined;
  const [, day, month, year] = match;
  const date = new Date(`${year}-${month}-${day}T00:00:00Z`);
  if (Number.isNaN(date.getTime()) || date.getUTCDate() !== Number(day)) return undefined;
  return `${year}-${month}-${day}`;
}

export const initials = (first: string | null | undefined, last: string | null | undefined) =>
  `${(first ?? '').trim().charAt(0)}${(last ?? '').trim().charAt(0)}`.toUpperCase();
