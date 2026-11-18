import { expect, it, vi } from 'vitest';
import { AdminSession } from '../src/auth/session';

const me = { admin: { id: 'fixture-id', login: 'fixture.admin', role: 'superadmin', business: null }, admin_max_stats_period_days: 90 };
const token = { access_token: 'fixture-transient-access', token_type: 'bearer', expires_in: 900 };
const json = (status: number, data: unknown) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });

it('holds the loading state until HttpOnly cookie refresh and GET /admin/me finish', async () => {
  let resolveRefresh: ((response: Response) => void) | undefined;
  const fetcher: typeof fetch = vi.fn(async url => String(url).endsWith('/admin/auth/refresh')
    ? await new Promise<Response>(resolve => { resolveRefresh = resolve; })
    : json(200, me));
  const session = new AdminSession(() => {}, () => 'https://admin.test', fetcher);
  const boot = session.bootstrap();
  expect(session.snapshot()).toEqual({ status: 'loading' });
  resolveRefresh?.(json(200, token));
  await boot;
  expect(session.snapshot()).toMatchObject({ status: 'authenticated', admin: { login: 'fixture.admin' } });
});

it('coalesces concurrent 401s into one refresh and retries with the rotated access token', async () => {
  let rejected = 0;
  let rotations = 0;
  const fetcher: typeof fetch = vi.fn(async (url, init) => {
    const value = String(url);
    if (value.endsWith('/admin/auth/login')) return json(200, token);
    if (value.endsWith('/admin/me')) return json(200, me);
    if (value.endsWith('/admin/auth/refresh')) {
      rotations += 1;
      return json(200, { ...token, access_token: 'fixture-rotated-access' });
    }
    if (rejected < 2) { rejected += 1; return json(401, { error: { code: 'ADMIN_UNAUTHENTICATED' } }); }
    expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer fixture-rotated-access');
    return json(200, { items: [] });
  });
  const session = new AdminSession(() => {}, () => 'https://admin.test', fetcher);
  await session.login('fixture.admin', 'fixture-test-password');
  const before = rotations;
  await Promise.all([
    session.api.request('/admin/dashboard'),
    session.api.request('/admin/dashboard'),
  ]);
  expect(rotations - before).toBe(1);
});

it('clears the access token and authenticated cache when refresh is rejected', async () => {
  const clear = vi.fn();
  const fetcher: typeof fetch = vi.fn(async url => {
    if (String(url).endsWith('/admin/auth/login')) return json(200, token);
    if (String(url).endsWith('/admin/me')) return json(200, me);
    if (String(url).endsWith('/admin/auth/refresh')) return json(401, { error: { code: 'ADMIN_UNAUTHENTICATED' } });
    return json(401, { error: { code: 'ADMIN_UNAUTHENTICATED' } });
  });
  const session = new AdminSession(clear, () => 'https://admin.test', fetcher);
  await session.login('fixture.admin', 'fixture-test-password');
  await expect(session.api.request('/admin/dashboard')).rejects.toMatchObject({ status: 401 });
  expect(session.snapshot()).toEqual({ status: 'anonymous' });
  expect(clear).toHaveBeenCalled();
});

it('clears memory credentials and the private cache after server logout', async () => {
  const clear = vi.fn();
  const fetcher: typeof fetch = vi.fn(async url => String(url).endsWith('/admin/auth/login')
    ? json(200, token)
    : String(url).endsWith('/admin/me') ? json(200, me) : json(200, { status: 'ok' }));
  const session = new AdminSession(clear, () => 'https://admin.test', fetcher);
  await session.login('fixture.admin', 'fixture-test-password');
  await session.logout();
  expect(session.snapshot()).toEqual({ status: 'anonymous' });
  expect(clear).toHaveBeenCalled();
  const revoke = vi.mocked(fetcher).mock.calls.find(([url]) => String(url).endsWith('/admin/auth/logout'));
  expect(revoke?.[1]?.credentials).toBe('include');
  expect(new Headers(revoke?.[1]?.headers).has('Authorization')).toBe(false);
});

it('keeps protected routes locked when remote logout cannot revoke the HttpOnly cookie', async () => {
  const fetcher: typeof fetch = vi.fn(async url => String(url).endsWith('/admin/auth/login')
    ? json(200, token)
    : String(url).endsWith('/admin/me') ? json(200, me) : Promise.reject(new TypeError('offline test fixture')));
  const session = new AdminSession(() => {}, () => 'https://admin.test', fetcher);
  await session.login('fixture.admin', 'fixture-test-password');
  await session.logout();
  expect(session.snapshot()).toMatchObject({ status: 'logout_error' });
});

it('sets adminStatsUnlimitedPeriod=true when /admin/me returns admin_stats_unlimited_period=true', async () => {
  const unlimitedMe = {
    admin: { id: 'fixture-id', login: 'fixture.admin', role: 'superadmin', business: null },
    admin_stats_unlimited_period: true,
    admin_max_stats_period_days: 90,
  };
  const fetcher: typeof fetch = vi.fn(async url => String(url).endsWith('/admin/auth/login')
    ? json(200, token)
    : String(url).endsWith('/admin/me') ? json(200, unlimitedMe) : json(404, {}));
  const session = new AdminSession(() => {}, () => 'https://admin.test', fetcher);
  await session.login('fixture.admin', 'fixture-test-password');
  expect(session.snapshot()).toEqual({
    status: 'authenticated',
    admin: unlimitedMe.admin,
    adminMaxStatsPeriodDays: 90,
    adminStatsUnlimitedPeriod: true,
  });
});

it('defaults adminStatsUnlimitedPeriod=false when /admin/me omits admin_stats_unlimited_period (legacy backend)', async () => {
  const legacyMe = {
    admin: { id: 'fixture-id', login: 'fixture.admin', role: 'superadmin', business: null },
    admin_max_stats_period_days: 90,
  };
  const fetcher: typeof fetch = vi.fn(async url => String(url).endsWith('/admin/auth/login')
    ? json(200, token)
    : String(url).endsWith('/admin/me') ? json(200, legacyMe) : json(404, {}));
  const session = new AdminSession(() => {}, () => 'https://admin.test', fetcher);
  await session.login('fixture.admin', 'fixture-test-password');
  expect(session.snapshot()).toEqual({
    status: 'authenticated',
    admin: legacyMe.admin,
    adminMaxStatsPeriodDays: 90,
    adminStatsUnlimitedPeriod: false,
  });
});

it('sets adminStatsUnlimitedPeriod=false when /admin/me explicitly provides admin_stats_unlimited_period=false', async () => {
  const falseMe = {
    admin: { id: 'fixture-id', login: 'fixture.admin', role: 'superadmin', business: null },
    admin_stats_unlimited_period: false,
    admin_max_stats_period_days: 90,
  };
  const fetcher: typeof fetch = vi.fn(async url => String(url).endsWith('/admin/auth/login')
    ? json(200, token)
    : String(url).endsWith('/admin/me') ? json(200, falseMe) : json(404, {}));
  const session = new AdminSession(() => {}, () => 'https://admin.test', fetcher);
  await session.login('fixture.admin', 'fixture-test-password');
  expect(session.snapshot()).toEqual({
    status: 'authenticated',
    admin: falseMe.admin,
    adminMaxStatsPeriodDays: 90,
    adminStatsUnlimitedPeriod: false,
  });
});

it('rejects invalid non-boolean admin_stats_unlimited_period (e.g. string "true" or "false")', async () => {
  for (const invalidValue of ['true', 'false', 1, 0, {}, []]) {
    const badMe = {
      admin: { id: 'fixture-id', login: 'fixture.admin', role: 'superadmin', business: null },
      admin_stats_unlimited_period: invalidValue,
      admin_max_stats_period_days: 90,
    };
    const fetcher: typeof fetch = vi.fn(async url => String(url).endsWith('/admin/auth/login')
      ? json(200, token)
      : String(url).endsWith('/admin/me') ? json(200, badMe) : json(404, {}));
    const session = new AdminSession(() => {}, () => 'https://admin.test', fetcher);
    await expect(session.login('fixture.admin', 'fixture-test-password')).rejects.toMatchObject({
      code: 'INVALID_RESPONSE',
    });
    expect(session.snapshot()).toMatchObject({
      status: 'error',
      error: expect.objectContaining({ code: 'INVALID_RESPONSE' }),
    });
  }
});

it('sets adminStatsUnlimitedPeriod cleanly during bootstrap() for both new and legacy /admin/me', async () => {
  const unlimitedFetcher: typeof fetch = vi.fn(async url => String(url).endsWith('/admin/auth/refresh')
    ? json(200, token)
    : json(200, { ...me, admin_stats_unlimited_period: true }));
  const sessionNew = new AdminSession(() => {}, () => 'https://admin.test', unlimitedFetcher);
  await sessionNew.bootstrap();
  expect(sessionNew.snapshot()).toMatchObject({
    status: 'authenticated',
    adminMaxStatsPeriodDays: 90,
    adminStatsUnlimitedPeriod: true,
  });

  const legacyFetcher: typeof fetch = vi.fn(async url => String(url).endsWith('/admin/auth/refresh')
    ? json(200, token)
    : json(200, me));
  const sessionLegacy = new AdminSession(() => {}, () => 'https://admin.test', legacyFetcher);
  await sessionLegacy.bootstrap();
  expect(sessionLegacy.snapshot()).toMatchObject({
    status: 'authenticated',
    adminMaxStatsPeriodDays: 90,
    adminStatsUnlimitedPeriod: false,
  });
});
