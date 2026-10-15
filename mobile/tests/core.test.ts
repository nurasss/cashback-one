import * as SecureStore from 'expo-secure-store';
import { tokenStore, deviceId } from '../src/storage/secure';
import { ApiClient } from '../src/api/client';
import { normalizeApiError } from '../src/api/errors';
import { isBarcode, decimalText, transactionLabel, pointsText, amountText, phoneText, birthDateToApi, birthDateToUi, initials } from '../src/utils/format';
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
it.each(['0123456789012', '0000000000000', '9999999999999'])('accepts exact barcode %s', value => { expect(isBarcode(value)).toBe(true); });
it.each(['123', '12345678901234', '01234567890a2', ' 0123456789012', 'https://0123456789012'])('rejects invalid barcode %s', value => { expect(isBarcode(value)).toBe(false); });
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

it('points always show two decimals without rounding up', () => {
  expect(pointsText('0')).toBe('0,00'); expect(pointsText('1500.5000')).toBe('1 500,50'); expect(pointsText('99.9999')).toBe('99,99');
  expect(pointsText(null)).toBe('0,00'); expect(amountText('350000.0000')).toBe('350 000');
});
it('formats Kazakhstan phone like the design', () => { expect(phoneText('+77058344326')).toBe('+7 705 834 43 26'); expect(phoneText('+4915112345678')).toBe('+4915112345678'); });
it('converts birth date between UI and API formats and rejects impossible dates', () => {
  expect(birthDateToUi('1990-01-31')).toBe('31.01.1990'); expect(birthDateToApi('31.01.1990')).toBe('1990-01-31');
  expect(birthDateToApi('')).toBeNull(); expect(birthDateToApi('31.02.1990')).toBeUndefined(); expect(birthDateToApi('1990-01-31')).toBeUndefined();
  expect(initials(' айгерим', 'серикова')).toBe('АС');
});
it('Kazakh dictionary interpolates and covers every key', () => {
  expect(translate('kz', 'tabNotifications')).toBe('Хабарламалар');
  expect(translate('ru', 'dontMiss', { percent: '12' })).toBe('Не упустите до 12% баллов');
  expect(translate('kz', 'untilStatus', { level: 2 })).toContain('2');
});
it('only server-signed dynamic QR tokens are rendered', () => {
  expect(isQrToken('C1' + 'A'.repeat(48))).toBe(true);
  for (const bad of ['0123456789012', 'C1' + 'A'.repeat(47), 'c1' + 'a'.repeat(48), 'C1' + '0'.repeat(48)]) expect(isQrToken(bad)).toBe(false);
});
