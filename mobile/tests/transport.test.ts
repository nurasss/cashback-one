import { ApiClient } from '../src/api/client';
import { ApiError } from '../src/api/errors';
import { runtimeTransportPolicy, validateApiBaseUrl, type TransportPolicy } from '../src/api/transport';

const release: TransportPolicy = { development: false, allowInsecureHttp: false };
const development: TransportPolicy = { development: true, allowInsecureHttp: false };
const devHttp: TransportPolicy = { development: true, allowInsecureHttp: true };
const originalDev = __DEV__;
const originalFlag = process.env.EXPO_PUBLIC_ALLOW_INSECURE_HTTP;
afterEach(() => {
  Object.defineProperty(globalThis, '__DEV__', { value: originalDev, configurable: true, writable: true });
  if (originalFlag === undefined) delete process.env.EXPO_PUBLIC_ALLOW_INSECURE_HTTP;
  else process.env.EXPO_PUBLIC_ALLOW_INSECURE_HTTP = originalFlag;
});

it.each([release, development, devHttp])('HTTPS works under every policy %#', policy => {
  expect(validateApiBaseUrl('https://cloud.example/api///', policy)).toBe('https://cloud.example/api');
});
it.each([release, development, { development: false, allowInsecureHttp: true }])('HTTP is denied without BOTH dev mode and opt-in %#', policy => {
  expect(() => validateApiBaseUrl('http://cloud.example', policy)).toThrow('INSECURE_TRANSPORT');
});
it('explicit development HTTP opt-in supports local testing and normalizes the URL', () => {
  expect(validateApiBaseUrl(' http://10.0.2.2:8000/// ', devHttp)).toBe('http://10.0.2.2:8000');
});
it.each(['', '  '])('missing base URL has a safe error %#', raw => {
  expect(() => validateApiBaseUrl(raw, release)).toThrow('CONFIG_MISSING');
});
it.each(['not-a-url', '/relative', '//cloud.example', 'https://', 'https:cloud.example', 'https:\\cloud.example', 'https://bad host', 'https://cloud.example:99999'])('invalid absolute URL is denied %#', raw => {
  expect(() => validateApiBaseUrl(raw, release)).toThrow('INVALID_API_URL');
});
it.each(['ftp://cloud.example', 'file://cloud.example/path', 'ws://cloud.example'])('other protocols are denied even with development allowance %#', raw => {
  expect(() => validateApiBaseUrl(raw, devHttp)).toThrow('INSECURE_TRANSPORT');
});
it.each(['https://user:secret@cloud.example', 'https://cloud.example?secret=value', 'https://cloud.example/#secret', 'https://cloud.example?', 'https://cloud.example#'])('userinfo/query/fragment are denied without leaking them %#', raw => {
  try { validateApiBaseUrl(raw, devHttp); throw new Error('Expected rejection'); }
  catch (error) {
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ code: 'INVALID_API_URL' });
    expect(String(error)).not.toContain(raw);
    expect(JSON.stringify(error)).not.toContain('secret');
  }
});
it.each(['', 'http://cloud.example', 'not-a-url', 'https://cloud.example?secret=value'])('invalid configuration never reaches fetch or sends a Bearer token %#', async raw => {
  Object.defineProperty(globalThis, '__DEV__', { value: false, configurable: true, writable: true });
  process.env.EXPO_PUBLIC_ALLOW_INSECURE_HTTP = '1';
  const fetcher = jest.fn(); const refresh = jest.fn();
  const api = new ApiClient(raw, { access: () => 'private-token', generation: () => 0, refresh, invalidate: async () => {} }, fetcher);
  await expect(api.request('/me/cards', { auth: true })).rejects.toBeInstanceOf(ApiError);
  expect(fetcher).not.toHaveBeenCalled(); expect(refresh).not.toHaveBeenCalled();
});
it('release runtime ignores insecure env opt-in', () => {
  Object.defineProperty(globalThis, '__DEV__', { value: false, configurable: true, writable: true });
  process.env.EXPO_PUBLIC_ALLOW_INSECURE_HTTP = '1';
  expect(runtimeTransportPolicy()).toEqual({ development: false, allowInsecureHttp: false });
  expect(() => validateApiBaseUrl('http://cloud.example')).toThrow('INSECURE_TRANSPORT');
});
it.each([undefined, '0', 'true', 'yes', ' 1 '])('dev runtime rejects non-explicit flag %#', flag => {
  Object.defineProperty(globalThis, '__DEV__', { value: true, configurable: true, writable: true });
  if (flag === undefined) delete process.env.EXPO_PUBLIC_ALLOW_INSECURE_HTTP;
  else process.env.EXPO_PUBLIC_ALLOW_INSECURE_HTTP = flag;
  expect(() => validateApiBaseUrl('http://cloud.example')).toThrow('INSECURE_TRANSPORT');
});
it('dev runtime accepts exactly flag 1', () => {
  Object.defineProperty(globalThis, '__DEV__', { value: true, configurable: true, writable: true });
  process.env.EXPO_PUBLIC_ALLOW_INSECURE_HTTP = '1';
  expect(validateApiBaseUrl('http://cloud.example/')).toBe('http://cloud.example');
});
it('JSON body with phone/OTP or refresh credentials is not transmitted over invalid transport', async () => {
  Object.defineProperty(globalThis, '__DEV__', { value: false, configurable: true, writable: true });
  const fetcher = jest.fn();
  const api = new ApiClient('http://cloud.example', { access: () => null, generation: () => 0, refresh: async () => {}, invalidate: async () => {} }, fetcher);
  await expect(api.request('/auth/sms/verify', { method: 'POST', body: { phone: 'test-fixture', code: 'test-fixture' } })).rejects.toMatchObject({ code: 'INSECURE_TRANSPORT' });
  await expect(api.request('/auth/refresh', { method: 'POST', body: { refresh_token: 'test-fixture' } })).rejects.toMatchObject({ code: 'INSECURE_TRANSPORT' });
  expect(fetcher).not.toHaveBeenCalled();
});
