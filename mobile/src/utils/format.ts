import { translate, type Language } from '../i18n';

export const isBarcode = (value: string): boolean => /^[0-9]{4,13}$/.test(value);

const group = (whole: string) => whole.replace(/\B(?=(\d{3})+(?!\d))/g, ' ');

// Format Decimal text without floating point rounding or precision loss.
export function decimalText(value: string): string {
  const [whole = '', fraction = ''] = value.split('.');
  const trimmed = fraction.replace(/0+$/, '');
  return `${group(whole)}${trimmed ? ',' + trimmed : ''}`;
}

// Points/currency amounts as shown in the design: integer with grouping, truncates towards zero, never shows decimals or "-0".
export function pointsText(value: string | null | undefined): string {
  if (value === null || value === undefined) return '0';
  const str = String(value).trim();
  if (!str) return '0';
  const [rawWhole = '0'] = str.split(/[.,]/);
  const isNegative = rawWhole.startsWith('-');
  const digits = rawWhole.replace('-', '').replace(/^0+(?=\d)/, '') || '0';
  if (digits === '0') return '0';
  return `${isNegative ? '-' : ''}${group(digits)}`;
}

// Whole tenge amount for level progress ("350 000").
export const amountText = (value: string | null | undefined): string => group((value ?? '0').split('.')[0]?.replace('-', '') || '0');

export const percentText = (value: string | null | undefined): string => decimalText(value ?? '0');

export function phoneText(phone: string | null | undefined): string {
  const digits = (phone ?? '').replace(/\D/g, '');
  if (digits.length === 11 && digits.startsWith('7')) return `+7 ${digits.slice(1, 4)} ${digits.slice(4, 7)} ${digits.slice(7, 9)} ${digits.slice(9)}`;
  return phone ?? '';
}

export function phoneInputDigits(raw: string): string {
  const text = (raw ?? '').trim();
  const hasPrefix = /^\+7|^7\s/.test(text);
  let digits = text.replace(/\D/g, '');
  let prefixDiscarded = false;
  if (hasPrefix) {
    digits = digits.replace(/^7/, '');
    prefixDiscarded = true;
  }
  if (!prefixDiscarded && digits.length === 11 && (digits.startsWith('7') || digits.startsWith('8'))) {
    digits = digits.slice(1);
  }
  return digits.slice(0, 10);
}

export function phoneInputText(digits: string): string {
  const d = digits.slice(0, 10);
  let res = '+7';
  if (d.length > 0) res += ` ${d.slice(0, 3)}`;
  if (d.length > 3) res += ` ${d.slice(3, 6)}`;
  if (d.length > 6) res += ` ${d.slice(6, 8)}`;
  if (d.length > 8) res += ` ${d.slice(8, 10)}`;
  return res;
}

export function phoneToApi(digits: string): string {
  return `+7${digits.slice(0, 10)}`;
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

// Mask for the birth date field. Typing and erasing work on the digits (at most 8: day, month and EXACTLY four year digits, so a fifth
// year digit is never kept). A complete date that was pasted in another common layout is read as a date, not as a row of digits:
// 1990-01-15, 15/01/1990, 15-01-1990, 15 01 1990, 5.1.1990, "ДР: 15.01.1990 г." all become 15.01.1990.
export function birthDateInputText(raw: string): string {
  const text = (raw ?? '').slice(0, 64);
  let digits: string;
  const iso = /(?:^|\D)(\d{4})[-./](\d{1,2})[-./](\d{1,2})(?!\d)/.exec(text);
  const dmy = /(?:^|\D)(\d{1,2})[^\d](\d{1,2})[^\d](\d{4})(?!\d)/.exec(text);
  if (iso) digits = `${iso[3]!.padStart(2, '0')}${iso[2]!.padStart(2, '0')}${iso[1]}`;
  else if (dmy) digits = `${dmy[1]!.padStart(2, '0')}${dmy[2]!.padStart(2, '0')}${dmy[3]}`;
  else digits = text.replace(/\D/g, '').slice(0, 8);
  if (digits.length <= 2) return digits;
  if (digits.length <= 4) return `${digits.slice(0, 2)}.${digits.slice(2)}`;
  return `${digits.slice(0, 2)}.${digits.slice(2, 4)}.${digits.slice(4)}`;
}
// The date inside a pasted text as day+month+year digits (DDMMYYYY), or null when the text holds no complete date.
function pastedFullDate(text: string): string | null {
  const iso = /(?:^|\D)(\d{4})[-./](\d{1,2})[-./](\d{1,2})(?!\d)/.exec(text);
  if (iso) return `${iso[3]!.padStart(2, '0')}${iso[2]!.padStart(2, '0')}${iso[1]}`;
  const dmy = /(?:^|\D)(\d{1,2})[^\d](\d{1,2})[^\d](\d{4})(?!\d)/.exec(text);
  return dmy ? `${dmy[1]!.padStart(2, '0')}${dmy[2]!.padStart(2, '0')}${dmy[3]}` : null;
}

const BIRTH_PART_MAX = [2, 2, 4] as const; // day, month, year

// The birth date field's reaction to a change of its text: `previous` is what is shown, `next` is what the input reports.
// A PASTE (two or more characters arrive at once) is read as a date: a complete date in another layout is converted, anything else
// goes through the digit mask. An EDIT (typing one character, Backspace/Delete, replacing a selection with one character) keeps the
// text exactly as the person made it: nothing is padded, shifted or re-masked, so erasing a digit in the middle of 15.01.1990 leaves
// 15.0.1990, and retyping the digit restores 15.01.1990. Backspace on a dot changes nothing. A digit that would make a part longer
// than day 2 / month 2 / year 4 is not accepted, so the year always has at most four digits; only typing at the END moves an overflowing
// digit on into the next part (15 + 0 -> 15.0, 15.01 + 1 -> 15.01.1).
export function birthDateEdit(previous: string, next: string): string {
  const prev = previous ?? '';
  const raw = (next ?? '').slice(0, 64);
  if (raw === '') return '';
  if (raw === prev) return prev;
  let start = 0;
  while (start < prev.length && start < raw.length && prev[start] === raw[start]) start++;
  let end = 0;
  while (end < prev.length - start && end < raw.length - start && prev[prev.length - 1 - end] === raw[raw.length - 1 - end]) end++;
  const inserted = raw.slice(start, raw.length - end);
  const removed = prev.slice(start, prev.length - end);

  if (inserted.length >= 2) { // a paste
    // The whole text is read first: the inserted part is only what differs from the old value, so it can be a cut-off piece of the date
    // (a paste over 15.01.1990 shares its last digit with the old text and the differing part is only 2001-02-2).
    const full = pastedFullDate(raw) ?? pastedFullDate(inserted);
    return birthDateInputText(full ?? raw);
  }

  if (inserted === '' && removed === '.') return prev; // Backspace on a mask dot: nothing is erased
  const clean = raw.replace(/[^\d.]/g, '').replace(/\.{2,}/g, '.');
  const parts = clean.split('.');
  const fits = (list: string[]) => list.length <= 3 && list.every((part, index) => part.length <= BIRTH_PART_MAX[index]!);
  if (fits(parts)) return clean;
  const typedAtEnd = removed === '' && end === 0 && /^\d$/.test(inserted);
  if (typedAtEnd) {
    const last = parts.length - 1;
    const part = parts[last]!;
    if (part.length === BIRTH_PART_MAX[last]! + 1 && last < 2) {
      const moved = [...parts.slice(0, last), part.slice(0, BIRTH_PART_MAX[last]), part.slice(BIRTH_PART_MAX[last])];
      if (fits(moved)) return moved.join('.');
    }
  }
  return prev; // would break the day / month / year lengths: not accepted
}
export type BirthDateProblem = 'invalid' | 'implausible' | 'under18';
// What is wrong with a birth date typed as DD.MM.YYYY, or null when it is acceptable (an empty field is acceptable: the date is optional).
// invalid: not DD.MM.YYYY with a four-digit year, or not a real calendar day; implausible: before 1900 or in the future;
// under18: a real past date, but the person is younger than 18 (the age rule is unchanged).
export function birthDateProblem(uiValue: string, today = new Date()): BirthDateProblem | null {
  const trimmed = (uiValue ?? '').trim();
  if (!trimmed) return null;
  const match = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(trimmed);
  if (!match || birthDateToApi(trimmed) === undefined) return 'invalid';
  const year = Number(match[3]);
  const month = Number(match[2]);
  const day = Number(match[1]);
  const todayYear = today.getFullYear();
  const todayMonth = today.getMonth() + 1;
  const todayDay = today.getDate();
  if (year < 1900 || year > todayYear || (year === todayYear && (month > todayMonth || (month === todayMonth && day > todayDay)))) return 'implausible';
  return isAdultBirthDate(trimmed, today) ? null : 'under18';
}
export function isAdultBirthDate(uiValue: string, today = new Date()): boolean {
  const apiDate = birthDateToApi(uiValue);
  if (!apiDate) return false;
  const match = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(uiValue.trim());
  if (!match) return false;
  const day = Number(match[1]);
  const month = Number(match[2]);
  const year = Number(match[3]);

  if (year < 1900) return false;

  const todayYear = today.getFullYear();
  const todayMonth = today.getMonth() + 1;
  const todayDay = today.getDate();

  if (
    year > todayYear ||
    (year === todayYear && (month > todayMonth || (month === todayMonth && day > todayDay)))
  ) {
    return false;
  }

  let age = todayYear - year;
  if (todayMonth < month || (todayMonth === month && todayDay < day)) {
    age -= 1;
  }
  return age >= 18;
}

export const initials = (first: string | null | undefined, last: string | null | undefined) =>
  `${(first ?? '').trim().charAt(0)}${(last ?? '').trim().charAt(0)}`.toUpperCase();
