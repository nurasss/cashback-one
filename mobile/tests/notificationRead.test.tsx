import { act, renderHook, waitFor } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { AppState } from 'react-native';
import * as Notifications from 'expo-notifications';
import { keys } from '../src/api/app';
import { dismissReadBroadcasts, pushPayload, syncSystemBadge } from '../src/features/notificationTray';
import { MARK_READ_BATCH, NOTIFICATION_VIEWABILITY, useMarkNotificationsRead } from '../src/features/useMarkSeen';
import { bumpNotificationEpoch } from '../src/features/notificationSignals';
import type { AppNotification, Badges, Notifications as NotificationsData } from '../src/types/api';

const mockRequest = jest.fn();
let mockFocused = true;
let mockBusiness: string | null = null;

// The session objects must be the same on every render, as in the app.
const mockInvalidateHooks: (() => void)[] = [];
const mockSession = { registerOnInvalidate: (hook: () => void) => { mockInvalidateHooks.push(hook); return () => undefined; }, registerBeforeLogout: () => () => undefined };
const mockSessionValue = { api: { request: mockRequest }, session: mockSession, state: { status: 'authenticated' } };
jest.mock('../src/auth/provider', () => ({ useSession: () => mockSessionValue }));
jest.mock('../src/config/client', () => ({
  withClientBusiness: (path: string) => (mockBusiness ? `${path}?business_id=${mockBusiness}` : path),
}));
jest.mock('expo-router', () => {
  const React = jest.requireActual<typeof import('react')>('react');
  return { useFocusEffect: (effect: () => void | (() => void)) => { React.useEffect(() => (mockFocused ? effect() : undefined), [effect]); } };
});

const presented = Notifications.getPresentedNotificationsAsync as jest.Mock;
const dismiss = Notifications.dismissNotificationAsync as jest.Mock;
const setBadge = Notifications.setBadgeCountAsync as jest.Mock;

const item = (id: string, unread = true): AppNotification => ({ id, kind: 'broadcast', title: `t${id}`, body: `b${id}`, created_at: '2026-11-17T00:00:00Z', is_unread: unread });
const list = (...items: AppNotification[]): NotificationsData => ({ items, unread_count: items.filter(i => i.is_unread).length });
const tray = (identifier: string, data: Record<string, unknown>) => ({ request: { identifier, content: { data } } });
const MARK = '/me/notifications/mark-read';
const LEGACY = '/me/notifications/read';

const clients: QueryClient[] = [];
function setup(initial: NotificationsData | undefined, badges: Badges | null = { promotions_new: false, notifications_unread: 2 }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
  clients.push(client);
  if (badges) client.setQueryData<Badges>(keys.badges, badges);
  if (initial) client.setQueryData<NotificationsData>(keys.notifications, initial);
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  const hook = renderHook(({ data }: { data: NotificationsData | undefined }) => useMarkNotificationsRead(data), { wrapper, initialProps: { data: initial } });
  return { client, ...hook };
}
type Hook = ReturnType<typeof setup>;
const markCalls = () => mockRequest.mock.calls.filter(call => String(call[0]).startsWith(MARK));
const markIds = () => markCalls().map(call => (call[1] as { body: { ids: string[] } }).body.ids);
const legacyCalls = () => mockRequest.mock.calls.filter(call => String(call[0]).split('?')[0] === LEGACY);
const tokens = (ids: string[]) => ids.map((id, index) => ({ item: { id }, key: id, index, isViewable: true }));
// What FlatList reports when these items are really on the screen.
const see = (hook: Hook, ids: string[]) => act(async () => { hook.result.current.onViewableItemsChanged({ viewableItems: tokens(ids), changed: [] }); });
const flush = () => act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });
const okAnswer = (ids: string[], unread = 0) => ({ read: ids, already_read: [], ignored: [], unread_count: unread });
const cachedList = (hook: Hook) => hook.client.getQueryData<NotificationsData>(keys.notifications);
const cachedBadge = (hook: Hook) => hook.client.getQueryData<Badges>(keys.badges)?.notifications_unread;
let mockAppState: typeof AppState.currentState = 'active';

beforeEach(() => {
  jest.clearAllMocks();
  mockRequest.mockReset();
  mockRequest.mockImplementation(async (_path: string, options: { body: { ids: string[] } }) => okAnswer(options.body.ids));
  mockInvalidateHooks.length = 0;
  mockAppState = 'active';
  Object.defineProperty(AppState, 'currentState', { configurable: true, get: () => mockAppState });
  mockFocused = true;
  mockBusiness = null;
  presented.mockResolvedValue([]);
});
afterEach(() => { jest.restoreAllMocks(); clients.forEach(c => c.clear()); clients.length = 0; });

describe('pushPayload: what the phone gets from the server push', () => {
  it('reads broadcast and redemption payloads, tolerates dataString and junk', () => {
    expect(pushPayload(tray('a', { type: 'broadcast', notification_id: 'n1' }))).toMatchObject({ type: 'broadcast', notification_id: 'n1' });
    expect(pushPayload(tray('a', { type: 'redemption_code', redemption_id: 'r1' }))).toMatchObject({ type: 'redemption_code', redemption_id: 'r1' });
    expect(pushPayload(tray('a', { dataString: JSON.stringify({ type: 'broadcast', notification_id: 'n2' }) }))).toMatchObject({ notification_id: 'n2' });
    expect(pushPayload(tray('a', { dataString: '{not json', type: 'broadcast', notification_id: 7 }))).toEqual({ type: 'broadcast', notification_id: undefined, redemption_id: undefined });
    expect(pushPayload(null)).toEqual({});
    expect(pushPayload({ request: { content: {} } })).toEqual({});
  });
});

describe('dismissReadBroadcasts: only the pushes the person has read', () => {
  it('removes a listed broadcast; keeps codes, unlisted broadcasts, unknown payloads', async () => {
    presented.mockResolvedValue([
      tray('t-read', { type: 'broadcast', notification_id: 'n1' }),
      tray('t-other-business', { type: 'broadcast', notification_id: 'zzz' }),
      tray('t-code', { type: 'redemption_code', redemption_id: 'n1' }), // same id value, still a code: stays
      tray('t-unknown', {}),
      { request: { content: { data: { type: 'broadcast', notification_id: 'n1' } } } }, // no identifier: nothing to dismiss
    ]);
    await expect(dismissReadBroadcasts(new Set(['n1']))).resolves.toBe(1);
    expect(dismiss).toHaveBeenCalledTimes(1);
    expect(dismiss).toHaveBeenCalledWith('t-read');
  });

  it('does nothing for an empty set, and never throws when the tray or one dismissal fails', async () => {
    await expect(dismissReadBroadcasts(new Set())).resolves.toBe(0);
    expect(presented).not.toHaveBeenCalled();
    presented.mockRejectedValueOnce(new Error('tray'));
    await expect(dismissReadBroadcasts(new Set(['n1']))).resolves.toBe(0);
    presented.mockResolvedValueOnce([tray('a', { type: 'broadcast', notification_id: 'n1' }), tray('b', { type: 'broadcast', notification_id: 'n2' })]);
    dismiss.mockRejectedValueOnce(new Error('stuck'));
    await expect(dismissReadBroadcasts(new Set(['n1', 'n2']))).resolves.toBe(1);
    expect(dismiss).toHaveBeenLastCalledWith('b');
  });

  it('syncSystemBadge writes a non-negative integer and survives an unsupported launcher', async () => {
    await syncSystemBadge(3.7);
    expect(setBadge).toHaveBeenLastCalledWith(3);
    await syncSystemBadge(-4);
    expect(setBadge).toHaveBeenLastCalledWith(0);
    setBadge.mockRejectedValueOnce(new Error('no launcher'));
    await expect(syncSystemBadge(1)).resolves.toBeUndefined();
  });
});


describe('useMarkNotificationsRead: exact ids of what was really seen', () => {
  it('uses stable viewability objects and the agreed thresholds (FlatList cannot change them on the fly)', () => {
    const hook = setup(list(item('a')));
    const first = hook.result.current;
    hook.rerender({ data: list(item('a'), item('b')) });
    expect(hook.result.current.onViewableItemsChanged).toBe(first.onViewableItemsChanged);
    expect(hook.result.current.viewabilityConfig).toBe(first.viewabilityConfig);
    expect(NOTIFICATION_VIEWABILITY).toEqual({ viewAreaCoveragePercentThreshold: 20, minimumViewTime: 800 });
  });

  it('viewability threshold marks a tall card (> 2x viewport height) as viewable while ignoring a tiny 5% peek', () => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const ViewabilityHelper = require('react-native/node_modules/@react-native/virtualized-lists/Lists/ViewabilityHelper').default;
    const helper = new ViewabilityHelper(NOTIFICATION_VIEWABILITY);
    const viewportHeight = 600;
    const getCellMetrics = (index: number) => {
      if (index === 0) return { length: 1500, offset: 0, index: 0, inLayout: true }; // 2.5x viewport height
      return { length: 120, offset: 1500, index: 1, inLayout: true };
    };
    // Scrolled near the top: tall card covers 100% of viewport (600px), second item is offscreen
    const indices = helper.computeViewableItems({ data: ['tall', 'short'], getItemCount: () => 2 }, 0, viewportHeight, { getCellMetrics });
    expect(indices).toContain(0);
    // Scrolled so short card peeks only 30px (5% of 600px viewport): still not viewable
    const peekIndices = helper.computeViewableItems({ data: ['tall', 'short'], getItemCount: () => 2 }, 930, viewportHeight, { getCellMetrics });
    expect(peekIndices).toContain(0);
    expect(peekIndices).not.toContain(1);
  });

  it('opening the list sends nothing; only the items that were viewable are sent, never the whole page', async () => {
    const hook = setup(list(item('a'), item('b'), item('c'), item('old', false)));
    await flush();
    expect(markCalls()).toHaveLength(0);
    await see(hook, ['a', 'old']); // "old" is already read: it is not asked again
    await waitFor(() => expect(markIds()).toEqual([['a']]));
    expect(markCalls()[0][0]).toBe(MARK);
    expect(markCalls()[0][1]).toMatchObject({ method: 'POST', auth: true, body: { ids: ['a'] } });
    await flush();
    expect(cachedList(hook)?.items.map(i => [i.id, i.is_unread])).toEqual([['a', false], ['b', true], ['c', true], ['old', false]]);
    expect(cachedList(hook)?.unread_count).toBe(2);
    expect(legacyCalls()).toHaveLength(0);
  });

  it('an item that scrolls into view later is sent later, and a new unread item that arrives is not marked until it is viewable', async () => {
    const hook = setup(list(item('a'), item('b')));
    await see(hook, ['a']);
    await waitFor(() => expect(markIds()).toEqual([['a']]));
    hook.rerender({ data: list(item('fresh'), item('a', false), item('b')) }); // a push arrived and was fetched
    await flush();
    expect(markIds()).toEqual([['a']]); // the new item is in the list but not looked at
    await see(hook, ['fresh', 'a']);
    await waitFor(() => expect(markIds()).toEqual([['a'], ['fresh']]));
    await see(hook, ['b']);
    await waitFor(() => expect(markIds()).toEqual([['a'], ['fresh'], ['b']]));
  });

  it('keeps the business scope of the list request (same business_id), no legacy endpoint', async () => {
    mockBusiness = 'biz-keremet';
    const hook = setup(list(item('a')));
    await see(hook, ['a']);
    await waitFor(() => expect(markCalls()).toHaveLength(1));
    expect(markCalls()[0][0]).toBe(`${MARK}?business_id=biz-keremet`);
    expect(legacyCalls()).toHaveLength(0);
  });

  it('the server answer is applied exactly: read and already_read lose the dot; ignored stays unread and is not asked again', async () => {
    mockRequest.mockResolvedValueOnce({ read: ['r'], already_read: ['d'], ignored: ['x'], unread_count: 1 });
    presented.mockResolvedValue([
      tray('t-r', { type: 'broadcast', notification_id: 'r' }),
      tray('t-d', { type: 'broadcast', notification_id: 'd' }),
      tray('t-x', { type: 'broadcast', notification_id: 'x' }),
      tray('t-code', { type: 'redemption_code', redemption_id: 'r' }),
      tray('t-new', { type: 'broadcast', notification_id: 'brand-new-push' }),
    ]);
    const hook = setup(list(item('r'), item('d'), item('x')));
    await see(hook, ['r', 'd', 'x']);
    await waitFor(() => expect(dismiss).toHaveBeenCalledTimes(2));
    expect(dismiss.mock.calls.map(c => c[0]).sort()).toEqual(['t-d', 't-r']);
    expect(cachedList(hook)?.items.map(i => [i.id, i.is_unread])).toEqual([['r', false], ['d', false], ['x', true]]);
    expect(cachedBadge(hook)).toBe(1);
    await waitFor(() => expect(setBadge).toHaveBeenCalledWith(1));
    await see(hook, ['x', 'r']); // x is looked at again in the same visit: not resent
    await flush();
    expect(markIds()).toEqual([['r', 'd', 'x']]);
  });

  it('more than 100 viewable ids go in batches of at most 100, strictly one after another, nothing lost', async () => {
    const ids = Array.from({ length: 250 }, (_, i) => `id${i}`);
    let inFlight = 0; let maxInFlight = 0;
    mockRequest.mockImplementation(async (_p: string, options: { body: { ids: string[] } }) => {
      inFlight += 1; maxInFlight = Math.max(maxInFlight, inFlight);
      await new Promise(resolve => setTimeout(resolve, 5));
      inFlight -= 1;
      return okAnswer(options.body.ids);
    });
    const hook = setup(list(...ids.map(id => item(id))));
    await see(hook, ids);
    await waitFor(() => expect(markIds()).toHaveLength(3), { timeout: 2000 });
    expect(markIds().map(b => b.length)).toEqual([MARK_READ_BATCH, MARK_READ_BATCH, 50]);
    expect(markIds().flat()).toEqual(ids);
    expect(maxInFlight).toBe(1);
  });

  it('ids that become visible while a request runs wait for it and go in the next one', async () => {
    const finish: (() => void)[] = [];
    mockRequest.mockImplementation((_p: string, options: { body: { ids: string[] } }) => new Promise(resolve => { finish.push(() => resolve(okAnswer(options.body.ids))); }));
    const hook = setup(list(item('a'), item('b')));
    await see(hook, ['a']);
    await waitFor(() => expect(markIds()).toEqual([['a']]));
    await see(hook, ['a', 'b']);
    expect(markIds()).toEqual([['a']]); // no parallel request
    await act(async () => { finish[0]?.(); });
    await waitFor(() => expect(markIds()).toEqual([['a'], ['b']]));
    await act(async () => { finish[1]?.(); });
  });

  it.each([
    ['a network error', () => Promise.reject(new TypeError('Network request failed'))],
    ['404 (server without the endpoint)', () => Promise.reject(Object.assign(new Error('NOT_FOUND'), { status: 404 }))],
    ['a malformed answer', () => Promise.resolve({ read: 'a' })],
    ['an empty answer', () => Promise.resolve(undefined)],
  ])('%s: no fallback to the legacy endpoint, nothing changes locally, no automatic retry', async (_name, answer) => {
    mockRequest.mockImplementation(answer);
    presented.mockResolvedValue([tray('t1', { type: 'broadcast', notification_id: 'a' })]);
    const hook = setup(list(item('a')));
    const invalidate = jest.spyOn(hook.client, 'invalidateQueries');
    await see(hook, ['a']);
    await waitFor(() => expect(markCalls()).toHaveLength(1));
    await flush(); await flush();
    hook.rerender({ data: list(item('a')) }); // fresh data alone does not start a loop
    await flush();
    expect(markCalls()).toHaveLength(1);
    expect(legacyCalls()).toHaveLength(0);
    expect(invalidate).not.toHaveBeenCalled();
    expect(dismiss).not.toHaveBeenCalled();
    expect(setBadge).not.toHaveBeenCalled();
    expect(cachedList(hook)?.items[0]?.is_unread).toBe(true);
    expect(cachedBadge(hook)).toBe(2);
  });

  it('after a failure the next try comes with the return to the foreground, and with a focus; then it succeeds', async () => {
    let emit: (state: string) => void = () => undefined;
    jest.spyOn(AppState, 'addEventListener').mockImplementation(((type: string, listener: (state: string) => void) => {
      if (type === 'change') emit = listener;
      return { remove: jest.fn() };
    }) as unknown as typeof AppState.addEventListener);
    mockRequest.mockRejectedValueOnce(new Error('offline'));
    presented.mockResolvedValue([tray('t1', { type: 'broadcast', notification_id: 'a' })]);
    const hook = setup(list(item('a')));
    await see(hook, ['a']);
    await waitFor(() => expect(markCalls()).toHaveLength(1));
    await flush();
    await act(async () => { emit('background'); });
    await act(async () => { emit('active'); });
    await waitFor(() => expect(markCalls()).toHaveLength(2));
    await waitFor(() => expect(dismiss).toHaveBeenCalledWith('t1'));
    expect(markIds()).toEqual([['a'], ['a']]);
  });

  it('a new viewable action after a failure is also a retry (a new focus is the same trigger)', async () => {
    mockRequest.mockRejectedValueOnce(new Error('500'));
    const hook = setup(list(item('a'), item('b')));
    await see(hook, ['a']);
    await waitFor(() => expect(markCalls()).toHaveLength(1));
    await flush();
    await see(hook, ['a', 'b']);
    await waitFor(() => expect(markIds()).toEqual([['a'], ['a', 'b']]));
  });

  it('nothing is sent while the screen is not focused or the app is in the background', async () => {
    mockFocused = false;
    const hidden = setup(list(item('a')));
    await see(hidden, ['a']);
    await flush();
    expect(markCalls()).toHaveLength(0);
    mockFocused = true;
    mockAppState = 'background';
    const bg = setup(list(item('b')));
    await see(bg, ['b']);
    await flush();
    expect(markCalls()).toHaveLength(0);
  });

  it('a push that arrives while the request runs: the old unread_count is not written into the badge; the shade is cleaned only for the confirmed id', async () => {
    let finish: () => void = () => undefined;
    mockRequest.mockImplementation(() => new Promise(resolve => { finish = () => resolve(okAnswer(['a'], 0)); }));
    presented.mockResolvedValue([tray('t-a', { type: 'broadcast', notification_id: 'a' }), tray('t-new', { type: 'broadcast', notification_id: 'pushed' })]);
    const hook = setup(list(item('a')), { promotions_new: false, notifications_unread: 1 });
    jest.spyOn(hook.client, 'invalidateQueries').mockImplementation(async filters => {
      // the refetch brings the truth: the pushed one is unread too
      if (JSON.stringify(filters?.queryKey) === JSON.stringify(keys.badges)) hook.client.setQueryData<Badges>(keys.badges, { promotions_new: false, notifications_unread: 1 });
    });
    await see(hook, ['a']);
    await waitFor(() => expect(markCalls()).toHaveLength(1));
    act(() => { bumpNotificationEpoch(); }); // push received
    await act(async () => { finish(); });
    await waitFor(() => expect(dismiss).toHaveBeenCalledTimes(1));
    expect(dismiss).toHaveBeenCalledWith('t-a');
    expect(setBadge).toHaveBeenCalledWith(1); // the refetched value, not the stale 0 of the answer
    expect(setBadge).not.toHaveBeenCalledWith(0);
    expect(cachedBadge(hook)).toBe(1);
  });

  it('a refetch that finishes during the request also makes the answer counter unusable', async () => {
    let finish: () => void = () => undefined;
    mockRequest.mockImplementation(() => new Promise(resolve => { finish = () => resolve(okAnswer(['a'], 0)); }));
    const now = jest.spyOn(Date, 'now');
    now.mockReturnValue(1_000_000);
    const hook = setup(list(item('a'), item('b')), { promotions_new: false, notifications_unread: 2 });
    await see(hook, ['a']);
    await waitFor(() => expect(markCalls()).toHaveLength(1));
    now.mockReturnValue(1_000_500);
    act(() => { hook.client.setQueryData<Badges>(keys.badges, { promotions_new: false, notifications_unread: 3 }); }); // newer server data
    await act(async () => { finish(); });
    await waitFor(() => expect(setBadge).toHaveBeenCalled());
    expect(cachedBadge(hook)).toBe(3); // not overwritten by the answer's 0
    expect(setBadge).toHaveBeenLastCalledWith(3);
  });

  it('a fresh answer writes its counter into the tab badge and the launcher badge', async () => {
    mockRequest.mockResolvedValueOnce(okAnswer(['a'], 4));
    const hook = setup(list(item('a')), { promotions_new: false, notifications_unread: 5 });
    await see(hook, ['a']);
    await waitFor(() => expect(setBadge).toHaveBeenCalledWith(4));
    expect(cachedBadge(hook)).toBe(4);
  });

  it('without any badges answer in the cache an outdated answer is not turned into a launcher badge, and no badge entry is invented', async () => {
    let finish: () => void = () => undefined;
    mockRequest.mockImplementation(() => new Promise(resolve => { finish = () => resolve(okAnswer(['a'], 0)); }));
    presented.mockResolvedValue([tray('t-a', { type: 'broadcast', notification_id: 'a' })]);
    const hook = setup(list(item('a')), null);
    jest.spyOn(hook.client, 'invalidateQueries').mockResolvedValue(undefined);
    await see(hook, ['a']);
    await waitFor(() => expect(markCalls()).toHaveLength(1));
    act(() => { bumpNotificationEpoch(); }); // a push arrived: the answer's counter is old, and there is no badges answer to use
    await act(async () => { finish(); });
    await waitFor(() => expect(dismiss).toHaveBeenCalledWith('t-a'));
    await flush();
    expect(setBadge).not.toHaveBeenCalled();
    expect(hook.client.getQueryData(keys.badges)).toBeUndefined();
  });

  it('a session change during the request drops its local effects: no cache write, no shade, no badge', async () => {
    let finish: () => void = () => undefined;
    mockRequest.mockImplementation(() => new Promise(resolve => { finish = () => resolve(okAnswer(['a'], 0)); }));
    presented.mockResolvedValue([tray('t-a', { type: 'broadcast', notification_id: 'a' })]);
    const hook = setup(list(item('a')));
    await see(hook, ['a']);
    await waitFor(() => expect(markCalls()).toHaveLength(1));
    const afterSwitch = cachedList(hook);
    act(() => { mockInvalidateHooks.forEach(h => h()); }); // session invalidated / user switched
    await act(async () => { finish(); });
    await flush();
    expect(cachedList(hook)).toBe(afterSwitch);
    expect(dismiss).not.toHaveBeenCalled();
    expect(setBadge).not.toHaveBeenCalled();
  });

  it('after a session change ids seen under the old session are not sent for the new one', async () => {
    const hook = setup(list(item('a')));
    await see(hook, ['a']);
    await waitFor(() => expect(markCalls()).toHaveLength(1));
    act(() => { mockInvalidateHooks.forEach(h => h()); });
    hook.rerender({ data: list(item('a')) });
    await flush();
    expect(markCalls()).toHaveLength(1);
  });

  it('unmounting during the request causes no update and no shade/badge effect', async () => {
    const errors = jest.spyOn(console, 'error').mockImplementation(() => undefined);
    let finish: () => void = () => undefined;
    mockRequest.mockImplementationOnce(() => new Promise(resolve => { finish = () => resolve(okAnswer(['a'])); }));
    presented.mockResolvedValue([tray('t-a', { type: 'broadcast', notification_id: 'a' })]);
    const hook = setup(list(item('a')));
    await see(hook, ['a']);
    await waitFor(() => expect(markCalls()).toHaveLength(1));
    const signal = (markCalls()[0][1] as { signal: AbortSignal }).signal;
    hook.unmount();
    expect(signal.aborted).toBe(true);
    await act(async () => { finish(); });
    await flush();
    expect(errors).not.toHaveBeenCalled();
    expect(dismiss).not.toHaveBeenCalled();
    expect(setBadge).not.toHaveBeenCalled();
  });

  it('broadcasts the server already reports as read leave the shade when the list loads (cold start); unread ones and codes stay', async () => {
    presented.mockResolvedValue([
      tray('t-read', { type: 'broadcast', notification_id: 'was-read' }),
      tray('t-unread', { type: 'broadcast', notification_id: 'still-unread' }),
      tray('t-code', { type: 'redemption_code', redemption_id: 'was-read' }),
    ]);
    setup(list(item('was-read', false), item('still-unread', true)));
    await waitFor(() => expect(dismiss).toHaveBeenCalledTimes(1));
    expect(dismiss).toHaveBeenCalledWith('t-read');
    expect(markCalls()).toHaveLength(0);
  });
});
