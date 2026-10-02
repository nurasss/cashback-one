import { ApiError } from '../api/errors';
import { ru } from '../i18n/ru';
export const isBarcode = (value: string): boolean => /^[0-9]{13}$/.test(value);
export function qrPayload(barcode: string): string {
  if (!isBarcode(barcode)) throw new ApiError('VALIDATION_ERROR');
  return barcode;
}
// Format Decimal text without floating point rounding or precision loss.
export function decimalText(value: string): string {
  const [whole = '', fraction = ''] = value.split('.');
  const trimmed = fraction.replace(/0+$/, '');
  return `${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ' ')}${trimmed ? ',' + trimmed : ''}`;
}
export const dateText = (value: string | number) => new Date(value).toLocaleString('ru-RU');
export function transactionLabel(type: string): string {
  return type === 'accrual' ? ru.accrual : type === 'redemption' ? ru.redemption : type;
}
