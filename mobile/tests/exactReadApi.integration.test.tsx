/**
 * Integration of the mobile read flow with the REAL candidate backend (not mocks): real ApiClient, real fetch, real
 * react-query cache, real useNotifications + useMarkNotificationsRead. Needs a running local server; skipped without it.
 *   EXACT_READ_ACCOUNTS=<json written by exact-ids-recheck1/integration/serve.py> EXPO_PUBLIC_ALLOW_INSECURE_HTTP=1 npx jest tests/exactReadApi.integration.test.tsx
 * Native pieces (shade, launcher badge) are the mocked expo-notifications of tests/setup.ts: this proves the HTTP contract,
 * not the Android shade.
 */
import fs from 'fs';
import { act, renderHook, waitFor } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { ApiClient } from '../src/api/client';
import { keys, useNotifications } from '../src/api/app';
import { useMarkNotificationsRead } from '../src/features/useMarkSeen';
import type { Notifications as NotificationsData } from '../src/types/api';

const accountsFile = process.env.EXACT_READ_ACCOUNTS;
const maybe = accountsFile ? describe : describe.skip;

type Accounts = { base_url: string; businesses: Record<string, string>; notifications: Record<string, string>; accounts: Record<string, { token: string; phone: string }> };
const world: Accounts = accountsFile ? JSON.parse(fs.readFileSync(accountsFile, 'utf8')) as Accounts : { base_url: '', businesses: {}, notifications: {}, accounts: {} };

let mockBusiness = '';
let mockApi: ApiClient;
const mockSession = { registerOnInvalidate: () => () => undefined, registerBeforeLogout: () => () => undefined };
const mockValue = { get api() { return mockApi; }, session: mockSession, state: { status: 'authenticated' } };
jest.mock('../src/auth/provider', () => ({ useSession: () => mockValue }));
jest.mock('../src/config/client', () => ({ withClientBusiness: (path: string) => `${path}${path.includes('?') ? '&' : '?'}business_id=${mockBusiness}` }));
jest.mock('expo-router', () => {
  const React = jest.requireActual<typeof import('react')>('react');
  return { useFocusEffect: (effect: () => void | (() => void)) => { React.useEffect(effect, [effect]); } };
});

const urls: string[] = [];
let failNext = false;
function clientFor(user: string): ApiClient {
  const token = world.accounts[user]?.token ?? '';
  const fetcher: typeof fetch = async (input, init) => {
    urls.push(`${init?.method ?? 'GET'} ${String(input).replace(world.base_url, '')}`);
    if (failNext && String(input).includes('mark-read')) { failNext = false; throw new TypeError('Network request failed'); }
    return fetch(input, init);
  };
  return new ApiClient(world.base_url, { access: () => token, generation: () => 1, refresh: async () => undefined, invalidate: async () => undefined }, fetcher);
}
const http = async (path: string, init?: RequestInit) => (await fetch(`${world.base_url}${path}`, init)).json() as Promise<Record<string, unknown>>;
const listFor = async (user: string, biz: string) => clientFor(user).request<NotificationsData>(`/me/notifications?business_id=${world.businesses[biz]}`, { auth: true });
const unread = (data: NotificationsData) => data.items.filter(i => i.is_unread).map(i => i.title).sort();

const clients: QueryClient[] = [];
function mount(user: string, biz: string) {
  mockApi = clientFor(user);
  mockBusiness = world.businesses[biz] ?? '';
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
  clients.push(client);
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  const hook = renderHook(() => { const q = useNotifications(); return { q, mark: useMarkNotificationsRead(q.data) }; }, { wrapper });
  return { client, ...hook };
}
const seeing = (hook: ReturnType<typeof mount>, ids: string[]) => act(async () => {
  hook.result.current.mark.onViewableItemsChanged({ viewableItems: ids.map((id, index) => ({ item: { id }, key: id, index, isViewable: true })), changed: [] });
});
afterAll(() => { clients.forEach(c => c.clear()); });

maybe('mobile read flow against the real candidate backend', () => {
  it('real list, only the seen items are marked by id (real POST /me/notifications/mark-read), other business/user untouched, legacy never called', async () => {
    const hook = mount('u1', 'A');
    await waitFor(() => expect(hook.result.current.q.data?.items.length).toBeGreaterThan(0));
    const before = hook.result.current.q.data as NotificationsData;
    expect(before.items.map(i => i.title).sort()).toEqual(['Акция A1', 'Акция A2', 'Акция A3', 'Акция A4', 'Акция A5']);
    expect(unread(before)).toHaveLength(5);
    const a1 = before.items.find(i => i.title === 'Акция A1')?.id;
    const a2 = before.items.find(i => i.title === 'Акция A2')?.id;
    if (!a1 || !a2) {
      throw new Error('Test fixture missing expected notification IDs for Акция A1 / Акция A2');
    }
    await seeing(hook, [a1, a2]);
    await waitFor(() => expect(unread(hook.result.current.q.data as NotificationsData)).toEqual(['Акция A3', 'Акция A4', 'Акция A5']));
    expect(hook.result.current.q.data?.unread_count).toBe(3);
    expect(urls.filter(u => u.includes('mark-read'))).toEqual([`POST /me/notifications/mark-read?business_id=${world.businesses.A}`]);
    expect(urls.some(u => /\/me\/notifications\/read(\?|$)/.test(u))).toBe(false);
    // the server really holds these two receipts, the baseline did not move
    const state = await http('/__harness/receipts');
    expect(state.count).toBe(2);
    expect(Object.values(state.baseline as Record<string, unknown>).every(v => v === null)).toBe(true);
    // the other business of the same user and the other user are untouched
    expect(unread(await listFor('u1', 'B'))).toEqual(['Акция B1', 'Акция B2', 'Акция B3']);
    expect(unread(await listFor('u2', 'A'))).toEqual(['Акция A1', 'Акция A2', 'Акция A3', 'Акция A4', 'Акция A5', 'Личное для u2']);
    // badges agree with the list in the same business scope
    const badges = await clientFor('u1').request<{ notifications_unread: number }>(`/me/badges?business_id=${world.businesses.A}`, { auth: true });
    expect(badges.notifications_unread).toBe(3);
  });

  it('a new arrival that was never on the screen stays unread on the server; once seen it is marked; a repeated id is already_read, a foreign id is ignored', async () => {
    const hook = mount('u1', 'A');
    await waitFor(() => expect(hook.result.current.q.data).toBeTruthy());
    await seeing(hook, []);
    await http('/__harness/arrive?title=%D0%9D%D0%BE%D0%B2%D0%B0%D1%8F', { method: 'POST' });
    await act(async () => { await hook.client.invalidateQueries({ queryKey: keys.notifications }); });
    await waitFor(() => expect(hook.result.current.q.data?.items.some(i => i.title === 'Новая')).toBe(true));
    const fresh = hook.result.current.q.data?.items.find(i => i.title === 'Новая');
    expect(fresh?.is_unread).toBe(true);
    expect(unread(await listFor('u1', 'A'))).toContain('Новая'); // server-side: not marked just because the list was fetched
    const callsBefore = urls.filter(u => u.includes('mark-read')).length;
    await seeing(hook, [fresh?.id as string]);
    await waitFor(() => expect(urls.filter(u => u.includes('mark-read')).length).toBe(callsBefore + 1));
    await waitFor(() => expect(unread(hook.result.current.q.data as NotificationsData)).not.toContain('Новая'));
    // raw contract: repeated id -> already_read; another user's personal id -> ignored; 4 keys only
    const raw = await fetch(`${world.base_url}/me/notifications/mark-read?business_id=${world.businesses.A}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${world.accounts.u1?.token}` },
      body: JSON.stringify({ ids: [fresh?.id, world.notifications.p2] }),
    });
    const body = await raw.json() as Record<string, unknown>;
    expect(Object.keys(body).sort()).toEqual(['already_read', 'ignored', 'read', 'unread_count']);
    expect(body.already_read).toEqual([fresh?.id]);
    expect(body.ignored).toEqual([world.notifications.p2]);
    expect(body.read).toEqual([]);
  });

  it('a failed request (network) keeps everything unread locally and on the server; no legacy fallback; the next trigger succeeds', async () => {
    const hook = mount('u1', 'B');
    await waitFor(() => expect(hook.result.current.q.data?.items.length).toBe(3));
    const b1 = hook.result.current.q.data?.items[0]?.id as string;
    urls.length = 0;
    failNext = true;
    await seeing(hook, [b1]);
    await waitFor(() => expect(urls.filter(u => u.includes('mark-read'))).toHaveLength(1));
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 50)); });
    expect(urls.filter(u => u.includes('mark-read'))).toHaveLength(1);
    expect(urls.some(u => /\/me\/notifications\/read(\?|$)/.test(u))).toBe(false);
    expect(unread(await listFor('u1', 'B'))).toHaveLength(3);
    expect(hook.result.current.q.data?.items.find(i => i.id === b1)?.is_unread).toBe(true);
    await seeing(hook, [b1]); // the person scrolls again: a new action retries
    await waitFor(() => expect(urls.filter(u => u.includes('mark-read'))).toHaveLength(2));
    await waitFor(() => expect(unread(hook.result.current.q.data as NotificationsData)).toHaveLength(2));
    expect(unread(await listFor('u1', 'B'))).toHaveLength(2);
  });
});
