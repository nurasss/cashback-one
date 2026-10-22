import { ApiError } from '../src/api/errors';
import { Session } from '../src/auth/session';
import type { TokenStore } from '../src/storage/secure';
import type { Tokens } from '../src/types/api';
const old: Tokens = { access_token: 'access-old', refresh_token: 'refresh-old', expires_in: 900, token_type: 'bearer' };
const fresh: Tokens = { ...old, access_token: 'access-new', refresh_token: 'refresh-new' };
const response = (status: number, body: unknown) => ({ status, ok: status < 400, json: async () => body }) as Response;
function fixture(saved: Tokens | null = old) {
  const store: jest.Mocked<TokenStore> = { read: jest.fn().mockResolvedValue(saved), write: jest.fn().mockResolvedValue(undefined), clear: jest.fn().mockResolvedValue(undefined) };
  const fetcher = jest.fn<ReturnType<typeof fetch>, Parameters<typeof fetch>>();
  const cache = jest.fn(); const refreshed = jest.fn();
  const session = new Session(store, 'https://cloud.example', cache, refreshed, fetcher);
  return { session, store, fetcher, cache, refreshed };
}
it('bootstrap without credentials becomes anonymous without a request', async () => {
  const f = fixture(null); await f.session.bootstrap(); expect(f.session.state.status).toBe('anonymous'); expect(f.fetcher).not.toHaveBeenCalled();
});
it('bootstrap remains loading until rotated tokens are persisted and wallet identity validated', async () => {
  const f = fixture(); let finish: ((r: Response) => void) | undefined;
  f.fetcher.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; })).mockResolvedValueOnce(response(200, []));
  const work = f.session.bootstrap(); await Promise.resolve(); expect(f.session.state.status).toBe('loading');
  finish?.(response(200, fresh)); await work;
  expect(f.store.write).toHaveBeenCalledWith(fresh); expect(f.session.state.status).toBe('authenticated');
  expect(f.fetcher.mock.calls[1]?.[1]?.headers).toMatchObject({ Authorization: 'Bearer access-new' });
});
it('bootstrap revoked refresh clears credentials and cache', async () => {
  const f = fixture(); f.fetcher.mockResolvedValue(response(401, { error: { code: 'INVALID_REFRESH_TOKEN' } }));
  await f.session.bootstrap(); expect(f.store.clear).toHaveBeenCalled(); expect(f.cache).toHaveBeenCalled(); expect(f.session.state.status).toBe('anonymous');
});
it('temporary bootstrap outage preserves credentials and offers an error state', async () => {
  const f = fixture(); f.fetcher.mockRejectedValue(new TypeError('offline'));
  await f.session.bootstrap(); expect(f.session.state.status).toBe('error'); expect(f.store.clear).not.toHaveBeenCalled();
});
it('401 refreshes once and retries with fresh Bearer header', async () => {
  const f = fixture(); await f.session.accept(old);
  f.fetcher.mockResolvedValueOnce(response(401, { error: { code: 'TOKEN_EXPIRED' } })).mockResolvedValueOnce(response(200, fresh)).mockResolvedValueOnce(response(200, []));
  expect(await f.session.api.request('/me/cards', { auth: true })).toEqual([]);
  expect(f.fetcher.mock.calls.map(call => call[0])).toEqual(['https://cloud.example/me/cards', 'https://cloud.example/auth/refresh', 'https://cloud.example/me/cards']);
  expect(f.fetcher.mock.calls[0]?.[1]?.headers).toMatchObject({ Authorization: 'Bearer access-old' });
  expect(f.fetcher.mock.calls[2]?.[1]?.headers).toMatchObject({ Authorization: 'Bearer access-new' });
  expect(f.refreshed).toHaveBeenCalledTimes(1);
});
it('concurrent 401 responses share one rotation', async () => {
  const f = fixture(); await f.session.accept(old);
  f.fetcher.mockImplementation(async (url, options) => {
    if (String(url).endsWith('/auth/refresh')) return response(200, fresh);
    return (options?.headers as Record<string, string>).Authorization === 'Bearer access-old' ? response(401, { error: { code: 'TOKEN_EXPIRED' } }) : response(200, []);
  });
  await Promise.all([f.session.api.request('/me/cards', { auth: true }), f.session.api.request('/me/cards', { auth: true })]);
  expect(f.fetcher.mock.calls.filter(call => String(call[0]).endsWith('/auth/refresh'))).toHaveLength(1);
});
it('refresh failure logs out and does not retry the wallet', async () => {
  const f = fixture(); await f.session.accept(old);
  f.fetcher.mockResolvedValueOnce(response(401, { error: { code: 'TOKEN_EXPIRED' } })).mockResolvedValueOnce(response(401, { error: { code: 'INVALID_REFRESH_TOKEN' } }));
  await expect(f.session.api.request('/me/cards', { auth: true })).rejects.toMatchObject({ code: 'INVALID_REFRESH_TOKEN' });
  expect(f.session.state.status).toBe('anonymous'); expect(f.store.clear).toHaveBeenCalled(); expect(f.fetcher).toHaveBeenCalledTimes(2);
});
it('second 401 after rotation invalidates the session', async () => {
  const f = fixture(); await f.session.accept(old);
  f.fetcher.mockResolvedValueOnce(response(401, { error: { code: 'TOKEN_EXPIRED' } })).mockResolvedValueOnce(response(200, fresh)).mockResolvedValueOnce(response(401, { error: { code: 'USER_NOT_FOUND' } }));
  await expect(f.session.api.request('/me/cards', { auth: true })).rejects.toMatchObject({ code: 'USER_NOT_FOUND' }); expect(f.session.state.status).toBe('anonymous');
});
it('logout calls revoke and clears local tokens and cache', async () => {
  const f = fixture(); await f.session.accept(old); f.fetcher.mockResolvedValue(response(200, { status: 'ok' }));
  expect(await f.session.logout()).toBe(false); expect(f.fetcher.mock.calls[0]?.[1]?.body).toBe(JSON.stringify({ refresh_token: old.refresh_token }));
  expect(f.store.clear).toHaveBeenCalled(); expect(f.session.state.status).toBe('anonymous'); expect(f.cache).toHaveBeenCalled();
});
it('network logout failure still removes local credentials', async () => {
  const f = fixture(); await f.session.accept(old); f.fetcher.mockRejectedValue(new TypeError('offline'));
  expect(await f.session.logout()).toBe(true); expect(f.store.clear).toHaveBeenCalled(); expect(f.session.state.status).toBe('anonymous');
});
it('response from a previous session cannot repopulate authenticated cache', async () => {
  const f = fixture(); await f.session.accept(old); let finish: ((r: Response) => void) | undefined;
  f.fetcher.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
  const request = f.session.api.request('/me/cards', { auth: true }); await f.session.invalidate(); finish?.(response(200, []));
  await expect(request).rejects.toMatchObject({ code: 'SESSION_CHANGED' });
});
it('storage write failure during refresh invalidates the credentials', async () => {
  const f = fixture(); await f.session.accept(old);
  f.store.write.mockRejectedValue(new ApiError('SECURE_STORAGE_UNAVAILABLE')); f.fetcher.mockResolvedValue(response(200, fresh));
  await expect(f.session.refresh()).rejects.toMatchObject({ code: 'SECURE_STORAGE_UNAVAILABLE' }); expect(f.session.state.status).toBe('anonymous');
});
it('concurrent bootstrap calls share one secure read and refresh exchange', async () => {
  const f = fixture(); f.fetcher.mockResolvedValueOnce(response(200, fresh)).mockResolvedValueOnce(response(200, []));
  await Promise.all([f.session.bootstrap(), f.session.bootstrap()]); expect(f.store.read).toHaveBeenCalledTimes(1); expect(f.fetcher).toHaveBeenCalledTimes(2);
});
it('SecureStore deletion failure locks protected UI and permits cleanup retry', async () => {
  const f = fixture(); await f.session.accept(old); f.fetcher.mockResolvedValue(response(200, { status: 'ok' }));
  f.store.clear.mockRejectedValueOnce(new ApiError('SECURE_STORAGE_UNAVAILABLE'));
  await f.session.logout(); expect(f.session.state).toMatchObject({ status: 'error', cleanupRequired: true });
  await f.session.invalidate(); expect(f.session.state.status).toBe('anonymous');
});
it('malformed rotated token response invalidates unusable credentials', async () => {
  const f = fixture(); await f.session.accept(old); f.fetcher.mockResolvedValue(response(200, { access_token: 'a' }));
  await expect(f.session.refresh()).rejects.toMatchObject({ code: 'INVALID_RESPONSE' }); expect(f.store.clear).toHaveBeenCalled(); expect(f.session.state.status).toBe('anonymous');
});

// --- Refresh failures that are not an authoritative answer from the backend must keep the saved credentials. ---
const html200 = () => ({ status: 200, ok: true, json: async () => { throw new SyntaxError('Unexpected token <'); } }) as unknown as Response;
const refreshCalls = (f: ReturnType<typeof fixture>) => f.fetcher.mock.calls.filter(call => String(call[0]).endsWith('/auth/refresh'));
it('non-JSON 200 on bootstrap refresh keeps saved tokens, reports an error and does not sign in', async () => {
  const f = fixture(); f.fetcher.mockResolvedValue(html200());
  await f.session.bootstrap();
  expect(f.session.state).toMatchObject({ status: 'error', error: { code: 'RESPONSE_UNREADABLE' } });
  expect(f.store.clear).not.toHaveBeenCalled(); expect(f.store.write).not.toHaveBeenCalled(); expect(f.cache).not.toHaveBeenCalled();
  expect(refreshCalls(f)).toHaveLength(1); // no automatic retry of the POST
});
it('retry after a non-JSON refresh reuses the still-saved refresh token and then signs in', async () => {
  const f = fixture(); f.fetcher.mockResolvedValueOnce(html200());
  await f.session.bootstrap(); expect(f.session.state.status).toBe('error');
  f.fetcher.mockResolvedValueOnce(response(200, fresh)).mockResolvedValueOnce(response(200, []));
  await f.session.bootstrap();
  expect(f.session.state.status).toBe('authenticated');
  expect(refreshCalls(f)).toHaveLength(2);
  for (const call of refreshCalls(f)) expect(call[1]?.body).toBe(JSON.stringify({ refresh_token: old.refresh_token }));
  expect(f.store.write).toHaveBeenCalledWith(fresh); expect(f.store.clear).not.toHaveBeenCalled();
});
it('network failure during refresh keeps tokens and the signed-in state', async () => {
  const f = fixture(); await f.session.accept(old); f.store.write.mockClear(); f.fetcher.mockRejectedValue(new TypeError('offline'));
  await expect(f.session.refresh()).rejects.toMatchObject({ code: 'NETWORK_UNAVAILABLE' });
  expect(f.store.clear).not.toHaveBeenCalled(); expect(f.store.write).not.toHaveBeenCalled(); expect(f.session.state.status).toBe('authenticated');
  f.fetcher.mockResolvedValueOnce(response(200, fresh)); await f.session.refresh();
  expect(f.store.write).toHaveBeenCalledWith(fresh); expect(f.fetcher.mock.calls.at(-1)?.[1]?.body).toBe(JSON.stringify({ refresh_token: old.refresh_token }));
});
it('refresh timeout keeps tokens', async () => {
  jest.useFakeTimers();
  try {
    const f = fixture(); await f.session.accept(old);
    f.fetcher.mockImplementation((_url, init) => new Promise((_resolve, reject) => { init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError'))); }));
    const attempt = expect(f.session.refresh()).rejects.toMatchObject({ code: 'REQUEST_TIMEOUT' });
    await jest.advanceTimersByTimeAsync(15_001); await attempt;
    expect(f.store.clear).not.toHaveBeenCalled(); expect(f.session.state.status).toBe('authenticated');
  } finally { jest.useRealTimers(); }
});
it('401 followed by a non-JSON refresh does not log out and does not replay the request', async () => {
  const f = fixture(); await f.session.accept(old);
  f.fetcher.mockResolvedValueOnce(response(401, { error: { code: 'TOKEN_EXPIRED' } })).mockResolvedValueOnce(html200());
  await expect(f.session.api.request('/me/cards', { auth: true })).rejects.toMatchObject({ code: 'RESPONSE_UNREADABLE' });
  expect(f.session.state.status).toBe('authenticated'); expect(f.store.clear).not.toHaveBeenCalled(); expect(f.fetcher).toHaveBeenCalledTimes(2);
  // The next request can still recover with the same refresh token.
  f.fetcher.mockResolvedValueOnce(response(401, { error: { code: 'TOKEN_EXPIRED' } })).mockResolvedValueOnce(response(200, fresh)).mockResolvedValueOnce(response(200, []));
  expect(await f.session.api.request('/me/cards', { auth: true })).toEqual([]);
  expect(refreshCalls(f).at(-1)?.[1]?.body).toBe(JSON.stringify({ refresh_token: old.refresh_token }));
});
it('a later 401 on refresh after a non-JSON answer still invalidates the session', async () => {
  const f = fixture(); await f.session.accept(old);
  f.fetcher.mockResolvedValueOnce(html200());
  await expect(f.session.refresh()).rejects.toMatchObject({ code: 'RESPONSE_UNREADABLE' }); expect(f.session.state.status).toBe('authenticated');
  f.fetcher.mockResolvedValueOnce(response(401, { error: { code: 'INVALID_REFRESH_TOKEN' } }));
  await expect(f.session.refresh()).rejects.toMatchObject({ code: 'INVALID_REFRESH_TOKEN' });
  expect(f.store.clear).toHaveBeenCalled(); expect(f.session.state.status).toBe('anonymous');
});
it.each([[{}], [[]], [null], [{ access_token: 'a', refresh_token: 'r', token_type: 'bearer', expires_in: 0 }]])('parsed JSON %j with unusable tokens still invalidates', async body => {
  const f = fixture(); await f.session.accept(old); f.fetcher.mockResolvedValue(response(200, body));
  await expect(f.session.refresh()).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  expect(f.store.clear).toHaveBeenCalled(); expect(f.session.state.status).toBe('anonymous');
});
it('concurrent callers share one failed non-JSON refresh without clearing tokens', async () => {
  const f = fixture(); await f.session.accept(old); f.fetcher.mockResolvedValue(html200());
  const results = await Promise.allSettled([f.session.refresh(), f.session.refresh()]);
  expect(results.map(r => r.status)).toEqual(['rejected', 'rejected']); expect(refreshCalls(f)).toHaveLength(1); expect(f.store.clear).not.toHaveBeenCalled();
});
