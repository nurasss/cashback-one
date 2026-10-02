import * as SecureStore from 'expo-secure-store';
import { tokenStore, deviceId } from '../src/storage/secure';
import { ApiClient } from '../src/api/client';
import { normalizeApiError } from '../src/api/errors';
import { isBarcode, qrPayload, decimalText, transactionLabel } from '../src/utils/format';
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
it.each(['0123456789012', '0000000000000', '9999999999999'])('QR preserves exact barcode %s', value => { expect(isBarcode(value)).toBe(true); expect(qrPayload(value)).toBe(value); });
it.each(['123', '12345678901234', '01234567890a2', ' 0123456789012', 'https://0123456789012'])('rejects invalid barcode %s', value => { expect(isBarcode(value)).toBe(false); expect(() => qrPayload(value)).toThrow(); });
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
