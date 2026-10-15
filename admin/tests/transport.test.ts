import { afterEach, expect, it, vi } from 'vitest';
import { ApiError } from '../src/api/errors';
import { validateApiBaseUrl } from '../src/api/transport';
import { AdminApiClient, type SessionHooks } from '../src/api/client';

afterEach(() => vi.unstubAllEnvs());
const production = { development: false, allowInsecureHttp: true };
const development = { development: true, allowInsecureHttp: false };
const optedInDev = { development: true, allowInsecureHttp: true };

it.each([production, development, optedInDev])('accepts and normalizes HTTPS %#', policy => {
  expect(validateApiBaseUrl('https://admin.example.test/api///', policy)).toBe('https://admin.example.test/api');
});
it('rejects HTTP without the explicit development opt-in', () => {
  expect(() => validateApiBaseUrl('http://10.0.0.25:8000', development)).toThrow('INSECURE_TRANSPORT');
  expect(() => validateApiBaseUrl('http://api.test', { development: false, allowInsecureHttp: false })).toThrow('INSECURE_TRANSPORT');
});
it('allows explicitly opted-in dev LAN HTTP', () => {
  expect(validateApiBaseUrl('http://192.168.1.25:8000///', optedInDev)).toBe('http://192.168.1.25:8000');
});
it.each([undefined, '', '   '])('rejects missing base URLs %#', value => {
  expect(() => validateApiBaseUrl(value, production)).toThrow('CONFIG_MISSING');
});
it.each(['relative', '/admin', '//admin.test', 'https:', 'https://', 'https://has space.test', 'https://admin.test:99999'])('rejects malformed absolute URLs %#', value => {
  expect(() => validateApiBaseUrl(value, production)).toThrow('INVALID_API_URL');
});
it.each(['ftp://admin.test', 'file:///tmp/file', 'ws://admin.test'])('rejects unsupported URL schemes %#', value => {
  expect(() => validateApiBaseUrl(value, optedInDev)).toThrow(/INVALID_API_URL|INSECURE_TRANSPORT/);
});
it.each(['https://name:secret@admin.test', 'https://admin.test?token=private', 'https://admin.test#secret'])('rejects credentials and URL parameters without retaining them %#', value => {
  try { validateApiBaseUrl(value, optedInDev); throw new Error('Expected an invalid URL'); }
  catch (error) {
    expect(error).toBeInstanceOf(ApiError);
    expect(String(error)).not.toContain(value);
    expect(JSON.stringify(error)).not.toContain('secret');
    expect(JSON.stringify(error)).not.toContain('private');
  }
});
it('never sends a Bearer token or PII body when production HTTP is rejected', async () => {
  const fetcher = vi.fn();
  const hooks: SessionHooks = { accessToken: () => 'fixture-access', generation: () => 0, replaceAccessToken: () => {}, clearSession: () => {}, refreshAccess: async () => 'unused' };
  const api = new AdminApiClient(hooks, () => 'http://api.test', fetcher);
  await expect(api.request('/admin/me')).rejects.toMatchObject({ code: 'INSECURE_TRANSPORT' });
  await expect(api.request('/admin/users/search', { method: 'POST', authenticated: false, body: { phone: 'fixture-phone' } }))
    .rejects.toMatchObject({ code: 'INSECURE_TRANSPORT' });
  expect(fetcher).not.toHaveBeenCalled();
});
it('puts phone search in the JSON body and sends credentials plus CSRF protection', async () => {
  const fetcher: typeof fetch = vi.fn(async () => new Response('{"items":[]}', { status: 200 }));
  const hooks: SessionHooks = { accessToken: () => 'fixture-access', generation: () => 0, replaceAccessToken: () => {}, clearSession: () => {}, refreshAccess: async () => 'unused' };
  const api = new AdminApiClient(hooks, () => 'https://admin.test', fetcher);
  await api.request('/admin/users/search?limit=25&offset=0', { method: 'POST', body: { phone: 'fixture-phone' } });
  const [url, init] = vi.mocked(fetcher).mock.calls[0]!;
  expect(String(url)).not.toContain('fixture-phone');
  expect(init?.body).toContain('fixture-phone');
  expect(init?.credentials).toBe('include');
  expect(new Headers(init?.headers).get('X-Admin-Request')).toBe('1');
});
it('guards the Admin SPA session source from persistent browser token storage', async () => {
  const fs = await import('node:fs');
  const source = fs.readFileSync(`${process.cwd()}/src/auth/session.ts`, 'utf8');
  expect(source).not.toMatch(/\b(?:localStorage|sessionStorage|indexedDB)\b/i);
});
