import { afterEach, expect, it, vi } from 'vitest';
import { AdminApiClient } from '../src/api/client';

afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

// Real browsers throw "Illegal invocation" when fetch is called with a foreign `this`
// (for example as a method of the API client). Mocked fetchers never reveal this.
it('calls the platform fetch without binding it to the client object', async () => {
  vi.stubGlobal('fetch', function strictFetch(this: unknown) {
    if (this !== undefined && this !== globalThis) throw new TypeError('Illegal invocation');
    return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
  });
  const client = new AdminApiClient({
    accessToken: () => null, generation: () => 0, replaceAccessToken: () => {}, clearSession: () => {}, refreshAccess: async () => 'x',
  }, () => 'https://api.example.test');
  await expect(client.request('/admin/me', { authenticated: false })).resolves.toEqual({ ok: true });
});
