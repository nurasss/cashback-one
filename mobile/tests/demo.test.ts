import { createDemoApi, DEMO_ENABLED, demoTokens } from '../src/demo/mockApi';
import { isQrToken } from '../src/features/DynamicQr';
import { parseTokens } from '../src/auth/tokens';

const call = async (api: ReturnType<typeof createDemoApi>, path: string, init?: RequestInit) => api(`https://demo.invalid${path}`, init);

it('demo mode is off unless the build flag is set', () => { expect(DEMO_ENABLED).toBe(false); });

it('demo API serves tokens, a card with a level, history filters and a rotating valid QR', async () => {
  const api = createDemoApi();
  expect(() => parseTokens(demoTokens)).not.toThrow();
  expect(await (await call(api, '/auth/refresh', { method: 'POST' })).json()).toEqual(demoTokens);
  const [card] = await (await call(api, '/me/cards')).json();
  expect(card.tier.next_level).toBe(2);
  expect(card.tier.levels.map((l: { percent: string }) => Number(l.percent))).toEqual([3, 5, 8, 12]);
  const accruals = await (await call(api, `/me/cards/${card.id}/transactions?limit=20&type=accrual`)).json();
  expect(accruals.items.length).toBeGreaterThan(0);
  expect(accruals.items.every((t: { type: string }) => t.type === 'accrual')).toBe(true);
  const first = await (await call(api, `/me/cards/${card.id}/qr`)).json();
  const second = await (await call(api, `/me/cards/${card.id}/qr`)).json();
  expect(isQrToken(first.token)).toBe(true);
  expect(first.token).not.toBe(second.token);
});

it('demo badges clear after opening promotions and reading notifications; profile edits persist in memory', async () => {
  const api = createDemoApi();
  expect(await (await call(api, '/me/badges')).json()).toEqual({ promotions_new: true, notifications_unread: 4 });
  expect((await call(api, '/me/promotions/seen', { method: 'POST' })).status).toBe(204);
  expect((await call(api, '/me/notifications/read', { method: 'POST' })).status).toBe(204);
  expect(await (await call(api, '/me/badges')).json()).toEqual({ promotions_new: false, notifications_unread: 0 });
  const saved = await (await call(api, '/me/profile', { method: 'PATCH', body: JSON.stringify({ first_name: 'Айгерим' }) })).json();
  expect(saved.first_name).toBe('Айгерим');
  expect((await (await call(api, '/me/profile')).json()).first_name).toBe('Айгерим');
  expect((await call(api, '/me/promotions/nope')).status).toBe(404);
});
