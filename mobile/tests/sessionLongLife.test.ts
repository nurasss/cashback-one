// The session must live exactly as long as the server lets it (the backend refresh token is long-lived with a sliding window):
// the app has no lifetime of its own, and only a final refusal of the server (401) or an explicit sign out ends it.
import { Session } from '../src/auth/session';
import type { TokenStore } from '../src/storage/secure';
import type { Tokens } from '../src/types/api';
const DAY = 24 * 60 * 60 * 1000;
const saved: Tokens = { access_token: 'access-0', refresh_token: 'refresh-0', expires_in: 900, token_type: 'bearer' };
const rotated = (n: number): Tokens => ({ ...saved, access_token: `access-${n}`, refresh_token: `refresh-${n}` });
const response = (status: number, body: unknown) => ({ status, ok: status < 400, json: async () => body }) as Response;
function fixture(initial: Tokens | null = saved) {
  let persisted: Tokens | null = initial;
  const store: jest.Mocked<TokenStore> = {
    read: jest.fn(async () => persisted),
    write: jest.fn(async (tokens: Tokens) => { persisted = tokens; }),
    clear: jest.fn(async () => { persisted = null; }),
  };
  const fetcher = jest.fn<ReturnType<typeof fetch>, Parameters<typeof fetch>>();
  const cache = jest.fn();
  const create = () => new Session(store, 'https://cloud.example', cache, () => {}, fetcher);
  return { store, fetcher, cache, create, persisted: () => persisted };
}
const refreshBodies = (fetcher: jest.Mock) => fetcher.mock.calls.filter(call => String(call[0]).endsWith('/auth/refresh')).map(call => JSON.parse(String(call[1]?.body)));

describe('the app has no session lifetime of its own', () => {
  afterEach(() => { jest.useRealTimers(); });

  it('tokens saved a year ago are still sent to the server, and a new refresh token replaces them each time (sliding window)', async () => {
    jest.useFakeTimers({ now: new Date('2026-01-01T00:00:00Z'), doNotFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'setImmediate', 'clearImmediate', 'nextTick', 'queueMicrotask'] });
    const f = fixture();
    f.fetcher.mockResolvedValueOnce(response(200, rotated(1))).mockResolvedValueOnce(response(200, []));
    let session = f.create(); await session.bootstrap();
    expect(session.state.status).toBe('authenticated'); expect(f.persisted()).toEqual(rotated(1));
    // 400 days later (more than the old 14 days and more than a year): a new process start with what was saved
    jest.setSystemTime(new Date('2027-02-05T00:00:00Z'));
    f.fetcher.mockResolvedValueOnce(response(200, rotated(2))).mockResolvedValueOnce(response(200, []));
    session = f.create(); await session.bootstrap();
    expect(session.state.status).toBe('authenticated'); expect(f.persisted()).toEqual(rotated(2));
    expect(refreshBodies(f.fetcher)).toEqual([{ refresh_token: 'refresh-0' }, { refresh_token: 'refresh-1' }]);
    expect(f.store.clear).not.toHaveBeenCalled(); expect(f.cache).not.toHaveBeenCalled();
    expect(Date.now() - new Date('2026-01-01T00:00:00Z').getTime()).toBeGreaterThan(365 * DAY);
  });

  it('an expired access token after a long time in the background is renewed with the saved refresh token, the request is repeated once', async () => {
    const f = fixture(); const session = f.create(); await session.accept(saved);
    f.fetcher.mockResolvedValueOnce(response(401, { error: { code: 'TOKEN_EXPIRED' } })).mockResolvedValueOnce(response(200, rotated(1))).mockResolvedValueOnce(response(200, []));
    expect(await session.api.request('/me/cards', { auth: true })).toEqual([]);
    expect(refreshBodies(f.fetcher)).toEqual([{ refresh_token: 'refresh-0' }]);
    expect(f.persisted()).toEqual(rotated(1)); expect(session.state.status).toBe('authenticated');
  });
});

describe.each([500, 502, 503, 504, 429])('server answer %i while refreshing is not a refusal of the session', status => {
  it('bootstrap keeps the saved tokens, shows the retry state and does not sign out', async () => {
    const f = fixture(); const session = f.create();
    f.fetcher.mockResolvedValueOnce(response(status, { error: { code: 'TEMPORARY', message: 'later' } }));
    await session.bootstrap();
    expect(session.state.status).toBe('error');
    expect(f.store.clear).not.toHaveBeenCalled(); expect(f.store.write).not.toHaveBeenCalled(); expect(f.cache).not.toHaveBeenCalled(); expect(f.persisted()).toEqual(saved);
    f.fetcher.mockResolvedValueOnce(response(200, rotated(1))).mockResolvedValueOnce(response(200, []));
    await session.bootstrap(); // the retry button
    expect(session.state.status).toBe('authenticated'); expect(refreshBodies(f.fetcher)).toEqual([{ refresh_token: 'refresh-0' }, { refresh_token: 'refresh-0' }]);
  });

  it('a request that needed a refresh fails with the temporary error, the person stays signed in', async () => {
    const f = fixture(); const session = f.create(); await session.accept(saved);
    f.fetcher.mockResolvedValueOnce(response(401, { error: { code: 'TOKEN_EXPIRED' } })).mockResolvedValueOnce(response(status, { error: { code: 'TEMPORARY' } }));
    await expect(session.api.request('/me/cards', { auth: true })).rejects.toMatchObject({ status });
    expect(session.state.status).toBe('authenticated'); expect(f.store.clear).not.toHaveBeenCalled(); expect(f.persisted()).toEqual(saved);
    expect(f.fetcher).toHaveBeenCalledTimes(2); // the request was not replayed without a new token
  });
});

describe('the only ways out', () => {
  it('the server refusing the refresh token (401) signs out', async () => {
    const f = fixture(); const session = f.create();
    f.fetcher.mockResolvedValueOnce(response(401, { error: { code: 'INVALID_REFRESH_TOKEN' } }));
    await session.bootstrap();
    expect(session.state.status).toBe('anonymous'); expect(f.store.clear).toHaveBeenCalled(); expect(f.persisted()).toBeNull();
  });
  it('an explicit sign out revokes on the server and clears the device', async () => {
    const f = fixture(); const session = f.create(); await session.accept(saved);
    f.fetcher.mockResolvedValue(response(200, { status: 'ok' }));
    await session.logout();
    expect(session.state.status).toBe('anonymous'); expect(f.persisted()).toBeNull();
    expect(f.fetcher.mock.calls[0]?.[0]).toBe('https://cloud.example/auth/logout');
  });
});
