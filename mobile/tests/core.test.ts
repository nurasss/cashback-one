import * as SecureStore from 'expo-secure-store';
import { tokenStore, deviceId } from '../src/storage/secure';
import { ApiClient } from '../src/api/client';
import { normalizeApiError } from '../src/api/errors';
import { isBarcode, decimalText, transactionLabel, pointsText, amountText, phoneText, phoneInputDigits, phoneInputText, phoneToApi, birthDateToApi, birthDateToUi, birthDateEdit, birthDateInputText, birthDateProblem, isAdultBirthDate, initials } from '../src/utils/format';
import { translate } from '../src/i18n';
import { isQrToken } from '../src/features/DynamicQr';
const tokens = { access_token: 'a', refresh_token: 'r', token_type: 'bearer', expires_in: 900 };
beforeEach(() => jest.clearAllMocks());
it('SecureStore persists both tokens as one atomic item and clears it', async () => {
  await tokenStore.write(tokens); expect(SecureStore.setItemAsync).toHaveBeenCalledWith('cashback-one.session.v1', JSON.stringify(tokens), expect.any(Object));
  jest.mocked(SecureStore.getItemAsync).mockResolvedValue(JSON.stringify(tokens)); expect(await tokenStore.read()).toEqual(tokens);
  await tokenStore.clear(); expect(SecureStore.deleteItemAsync).toHaveBeenCalledWith('cashback-one.session.v1', expect.any(Object));
});
it('invalid stored DTO is deleted', async () => {
  jest.mocked(SecureStore.getItemAsync).mockResolvedValue('{"access_token":"a"}'); expect(await tokenStore.read()).toBeNull(); expect(SecureStore.deleteItemAsync).toHaveBeenCalled();
});
it('installation identifier persists independently of logout', async () => {
  jest.mocked(SecureStore.getItemAsync).mockResolvedValue(null); expect(await deviceId()).toBe('installation-id');
  expect(SecureStore.setItemAsync).toHaveBeenCalledWith('cashback-one.device.v1', 'installation-id', expect.any(Object));
});
it.each(['0001', '0000', '012345', '12345678901', '0123456789012', '9999999999999'])('accepts exact barcode %s', value => { expect(isBarcode(value)).toBe(true); });
it.each(['123', '12', '12345678901234', '1234567890123456', '01234567890a2', ' 0123456789012', 'https://0123456789012'])('rejects invalid barcode %s', value => { expect(isBarcode(value)).toBe(false); });
it('Decimal formatting does not lose numeric precision', () => { expect(decimalText('99999999999999.9999')).toBe('99 999 999 999 999,9999'); expect(decimalText('50.0000')).toBe('50'); });
it('only documented transaction types have business labels', () => { expect(transactionLabel('accrual')).toBe('Начисление'); expect(transactionLabel('redemption')).toBe('Списание'); expect(transactionLabel('adjustment')).toBe('adjustment'); });
it('normalizes machine error without leaking server PII', () => {
  const error = normalizeApiError(422, { error: { code: 'VALIDATION_ERROR', message: '+7701 secret otp 123456', detail: 'pii' } });
  expect(error.code).toBe('VALIDATION_ERROR'); expect(JSON.stringify(error)).not.toContain('123456'); expect(error.message).toBe('VALIDATION_ERROR');
});
it('safe business selection discards unrelated fields', () => {
  expect(normalizeApiError(409, { error: { code: 'BUSINESS_SELECTION_REQUIRED', businesses: [{ id: 'b', name: 'Shop', phone: 'pii' }] } }).businesses).toEqual([{ id: 'b', name: 'Shop' }]);
});
it('malformed server error is normalized', () => { expect(normalizeApiError(503, '<html>').code).toBe('SERVER_UNAVAILABLE'); });
it('client timeout aborts request with a safe error', async () => {
  const fetcher: typeof fetch = async (_url, options) => new Promise((_resolve, reject) => options?.signal?.addEventListener('abort', () => reject(new Error('aborted'))));
  const api = new ApiClient('https://cloud.example', { access: () => null, generation: () => 0, refresh: async () => {}, invalidate: async () => {} }, fetcher, 5);
  await expect(api.request('/auth/challenge')).rejects.toMatchObject({ code: 'REQUEST_TIMEOUT' });
});
it('204 delete response does not attempt JSON parsing', async () => {
  const json = jest.fn(); const api = new ApiClient('https://cloud.example', { access: () => 'a', generation: () => 0, refresh: async () => {}, invalidate: async () => {} }, async () => ({ status: 204, ok: true, json }) as unknown as Response);
  await expect(api.request('/me/cards/id', { auth: true, method: 'DELETE' })).resolves.toBeUndefined(); expect(json).not.toHaveBeenCalled();
});
it('malformed SecureStore JSON is deleted without retaining its contents', async () => {
  jest.mocked(SecureStore.getItemAsync).mockResolvedValue('invalid-json'); expect(await tokenStore.read()).toBeNull(); expect(SecureStore.deleteItemAsync).toHaveBeenCalled();
});

it('points truncate decimals to zero and avoid -0 for remainders less than 1', () => {
  expect(pointsText('0')).toBe('0');
  expect(pointsText('0.99')).toBe('0');
  expect(pointsText('-0.99')).toBe('0');
  expect(pointsText('1234.56')).toBe('1 234');
  expect(pointsText('-1234.56')).toBe('-1 234');
  expect(pointsText('99999999999999999999.88')).toBe('99 999 999 999 999 999 999');
  expect(pointsText(null)).toBe('0');
  expect(amountText('350000.0000')).toBe('350 000');
});
it('formats Kazakhstan phone like the design', () => { expect(phoneText('+77058344326')).toBe('+7 705 834 43 26'); expect(phoneText('+4915112345678')).toBe('+4915112345678'); });
it('converts birth date between UI and API formats and rejects impossible dates', () => {
  expect(birthDateToUi('1990-01-31')).toBe('31.01.1990'); expect(birthDateToApi('31.01.1990')).toBe('1990-01-31');
  expect(birthDateToApi('')).toBeNull(); expect(birthDateToApi('31.02.1990')).toBeUndefined(); expect(birthDateToApi('1990-01-31')).toBeUndefined();
  expect(initials(' айгерим', 'серикова')).toBe('АС');
});
it('Kazakh dictionary interpolates and covers every key', () => {
  expect(translate('kz', 'tabNotifications')).toBe('Хабарламалар');
  expect(translate('ru', 'dontMiss', { percent: '12' })).toBe('Не упустите до 12% бонусов');
  expect(translate('kz', 'untilStatus', { level: 2 })).toContain('2');
});
it('only server-signed dynamic QR tokens are rendered', () => {
  expect(isQrToken('C1' + 'A'.repeat(48))).toBe(true);
  for (const bad of ['0123456789012', 'C1' + 'A'.repeat(47), 'c1' + 'a'.repeat(48), 'C1' + '0'.repeat(48)]) expect(isQrToken(bad)).toBe(false);
});

it('handles all 4 phone insertion formats, erase to empty, +7 non-erasable, and non-7 first digit', () => {
  // 4 insertion formats: +77011234567, 87011234567, 77011234567, 7011234567
  expect(phoneInputDigits('+77011234567')).toBe('7011234567');
  expect(phoneInputDigits('87011234567')).toBe('7011234567');
  expect(phoneInputDigits('77011234567')).toBe('7011234567');
  expect(phoneInputDigits('7011234567')).toBe('7011234567');
  expect(phoneInputDigits('+7 701 123 45 67')).toBe('7011234567');
  expect(phoneInputDigits('+7 701 123 45 678')).toBe('7011234567');
  expect(phoneInputDigits('+ 701')).toBe('701');
  expect(phoneInputDigits('7 701')).toBe('701');

  // Erase to empty:
  expect(phoneInputDigits('+7')).toBe('');
  expect(phoneInputDigits('+')).toBe('');
  expect(phoneInputDigits('')).toBe('');

  // +7 never erased in formatted text:
  expect(phoneInputText('')).toBe('+7');
  expect(phoneInputText(phoneInputDigits(''))).toBe('+7');
  expect(phoneInputText(phoneInputDigits('+'))).toBe('+7');

  // Incremental input does not add trailing separator:
  expect(phoneInputText('7')).toBe('+7 7');
  expect(phoneInputText('701')).toBe('+7 701');
  expect(phoneInputText('7011')).toBe('+7 701 1');
  expect(phoneInputText('701123')).toBe('+7 701 123');
  expect(phoneInputText('7011234567')).toBe('+7 701 123 45 67');

  // First digit not 7:
  const non7 = phoneInputDigits('6011234567');
  expect(non7).toBe('6011234567');
  expect(non7.startsWith('7')).toBe(false);

  // phoneToApi format:
  expect(phoneToApi('7011234567')).toBe('+77011234567');
});

it('birthDateInputText formats mask on typing and erasing, isAdultBirthDate tests calendar boundaries and leap year', () => {
  // Mask on typing and erasing:
  expect(birthDateInputText('19')).toBe('19');
  expect(birthDateInputText('191')).toBe('19.1');
  expect(birthDateInputText('19111990')).toBe('19.11.1990');
  // Backspace (erasing):
  expect(birthDateInputText('19.')).toBe('19');
  expect(birthDateInputText('19.11.')).toBe('19.11');

  // 31.02 invalid date:
  expect(isAdultBirthDate('31.02.1990')).toBe(false);

  // Calendar 18 years boundary:
  const refDate = new Date('2026-11-01T12:00:00Z');
  // Exactly 18 years today:
  expect(isAdultBirthDate('01.11.2008', refDate)).toBe(true);
  // 18 years tomorrow (currently 17):
  expect(isAdultBirthDate('02.11.2008', refDate)).toBe(false);

  // 29 February leap year: born 29.02.2004
  const feb28_2022 = new Date('2022-02-28T12:00:00Z');
  const mar01_2022 = new Date('2022-03-01T12:00:00Z');
  const feb29_2024 = new Date('2024-02-29T12:00:00Z');
  expect(isAdultBirthDate('29.02.2004', feb28_2022)).toBe(false);
  expect(isAdultBirthDate('29.02.2004', mar01_2022)).toBe(true);
  expect(isAdultBirthDate('29.02.2004', feb29_2024)).toBe(true);
});

it('birthDateProblem: invalid / implausible / under18 / acceptable (the 18+ rule is unchanged)', () => {
  const today = new Date(2026, 10, 11); // 11 Nov 2026
  expect(birthDateProblem('', today)).toBeNull();
  expect(birthDateProblem('   ', today)).toBeNull();
  expect(birthDateProblem('15.01.1990', today)).toBeNull();
  expect(birthDateProblem('11.11.2008', today)).toBeNull();       // exactly 18 today
  expect(birthDateProblem('12.11.2008', today)).toBe('under18');   // one day short
  expect(birthDateProblem('01.01.2020', today)).toBe('under18');
  expect(birthDateProblem('31.02.1990', today)).toBe('invalid');
  expect(birthDateProblem('15.13.1990', today)).toBe('invalid');
  expect(birthDateProblem('1.1.1990', today)).toBe('invalid');     // not DD.MM.YYYY
  expect(birthDateProblem('15.01.90', today)).toBe('invalid');     // two-digit year
  expect(birthDateProblem('15.01.19900', today)).toBe('invalid');  // five-digit year
  expect(birthDateProblem('15.01.0099', today)).toBe('implausible');
  expect(birthDateProblem('31.12.1899', today)).toBe('implausible');
  expect(birthDateProblem('12.11.2026', today)).toBe('implausible'); // tomorrow
  expect(birthDateProblem('01.01.2030', today)).toBe('implausible');
  expect(birthDateProblem('29.02.2000', today)).toBeNull();
  expect(birthDateProblem('29.02.1900', today)).toBe('invalid');   // 1900 is not a leap year
});

it('birthDateInputText reads a pasted date in common layouts and never keeps a fifth year digit', () => {
  expect(birthDateInputText('1990-01-15')).toBe('15.01.1990');
  expect(birthDateInputText('15/01/1990')).toBe('15.01.1990');
  expect(birthDateInputText('5.1.1990')).toBe('05.01.1990');
  expect(birthDateInputText('Дата: 15.01.1990 г.')).toBe('15.01.1990');
  expect(birthDateInputText('15.01.19905')).toBe('15.01.1990');
  expect(birthDateInputText('150119901234')).toBe('15.01.1990');
  expect(birthDateInputText(`${'9'.repeat(5000)}`)).toBe('99.99.9999');
  expect(birthDateInputText('')).toBe('');
});

describe('birthDateEdit: editing the current value is separate from pasting a date', () => {
  // [previous, what the input reports after the change, what must be shown]
  it.each([
    // typing at the end builds the mask
    ['', '1', '1'], ['1', '15', '15'], ['15', '150', '15.0'], ['15.0', '15.01', '15.01'], ['15.01', '15.011', '15.01.1'],
    ['15.01.1', '15.01.19', '15.01.19'], ['15.01.199', '15.01.1990', '15.01.1990'],
    // Backspace / Delete of a digit in the middle changes only that digit: nothing is padded, shifted or re-masked
    ['15.01.1990', '1.01.1990', '1.01.1990'],       // a day digit
    ['15.01.1990', '5.01.1990', '5.01.1990'],
    ['15.01.1990', '15.0.1990', '15.0.1990'],       // a month digit (the old behaviour padded this to 15.00.1990)
    ['15.01.1990', '15.1.1990', '15.1.1990'],
    ['15.01.1990', '15.01.190', '15.01.190'],       // a year digit
    ['15.01.1990', '15.01.199', '15.01.199'],
    // retyping the digit puts it back
    ['1.01.1990', '15.01.1990', '15.01.1990'],
    ['15.0.1990', '15.01.1990', '15.01.1990'],
    ['15.01.190', '15.01.1990', '15.01.1990'],
    // Backspace on a mask dot erases nothing
    ['15.01.1990', '1501.1990', '15.01.1990'],
    ['15.01.1990', '15.011990', '15.01.1990'],
    // selecting a part and typing one character replaces just that part
    ['15.01.1990', '15.1.1990', '15.1.1990'],
    ['15.01.1990', '15.01.2', '15.01.2'],
    ['15.01.1990', '3', '3'],
    // clearing
    ['15.01.1990', '', ''], ['15.0', '', ''],
    // a digit that would make a part too long is not accepted: the year keeps four digits
    ['15.01.1990', '15.01.19905', '15.01.1990'],
    ['15.01.1990', '15.01.19990', '15.01.1990'],
    ['15.01.1990', '151.01.1990', '15.01.1990'],
    ['15.01.1990', '15.011.1990', '15.01.1990'],
    ['15.01.1990', '15.01.1990.', '15.01.1990'],
    // letters and other characters are ignored
    ['15', '15a', '15'],
  ])('%j -> %j shows %j', (previous, next, expected) => {
    expect(birthDateEdit(previous, next)).toBe(expected);
  });

  it.each([
    // a paste of a complete date: ISO and DD.MM.YYYY (also over the existing value), other layouts
    ['', '1990-01-15', '15.01.1990'],
    ['', '15.01.1990', '15.01.1990'],
    ['15.01.1990', '20.02.2001', '20.02.2001'],
    ['15.01.1990', '2001-02-20', '20.02.2001'],
    ['', '15/01/1990', '15.01.1990'],
    ['', '5.1.1990', '05.01.1990'],
    ['', 'Дата: 15.01.1990 г.', '15.01.1990'],
    // digits only, or a longer row of digits: the mask keeps exactly four year digits
    ['', '15011990', '15.01.1990'],
    ['', '15.01.19905', '15.01.1990'],
    ['', '15011990123456', '15.01.1990'],
  ])('paste over %j: %j becomes %j', (previous, pasted, expected) => {
    expect(birthDateEdit(previous, pasted)).toBe(expected);
  });
});
