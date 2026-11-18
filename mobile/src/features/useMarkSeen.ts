import { useQueryClient } from '@tanstack/react-query';
import { useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useRef } from 'react';
import { AppState, type ViewabilityConfig, type ViewToken } from 'react-native';
import { keys } from '../api/app';
import { useSession } from '../auth/provider';
import { withClientBusiness } from '../config/client';
import type { Badges, Notifications, NotificationsMarkRead } from '../types/api';
import { notificationEpoch } from './notificationSignals';
import { dismissReadBroadcasts, syncSystemBadge } from './notificationTray';

// When a tab with "new" content is opened, tell the server once and refresh the tab bar badges.
export function useMarkSeen(path: '/me/promotions/seen', hasNew: boolean) {
  const { api } = useSession();
  const query = useQueryClient();
  const sending = useRef(false);
  useFocusEffect(useCallback(() => {
    if (!hasNew || sending.current) return;
    sending.current = true;
    api.request<void>(withClientBusiness(path), { method: 'POST', auth: true })
      .then(() => query.invalidateQueries({ queryKey: keys.badges }))
      .catch(() => { /* Badge stays until the next successful visit. */ })
      .finally(() => { sending.current = false; });
  }, [api, hasNew, path, query]));
}

// ---- Notifications: exact-ID read ------------------------------------------------------------------------------------------
// The server contract (POST /me/notifications/mark-read, same business_id as the list) takes the ids the person really saw.
// Choices made here (not business rules; tuned by hand, change them only together with the tests):
//  * an item counts as seen when it is fully visible or covers at least 20% of the viewport for 800 ms (so tall cards > 2x viewport still count, while a quick fling past marks nothing);
//  * one request carries at most 100 ids, requests go strictly one after another, ids that become visible meanwhile wait;
//  * the legacy endpoint POST /me/notifications/read is never used here, not even after a 404 or without a network.
// FlatList reads viewabilityConfig and the callback once: both must be the same objects on every render.
export const NOTIFICATION_VIEWABILITY: ViewabilityConfig = { viewAreaCoveragePercentThreshold: 20, minimumViewTime: 800 };
export const MARK_READ_BATCH = 100;

type ViewableChange = { viewableItems: ViewToken[]; changed: ViewToken[] };
const tokenId = (token: ViewToken): string | null => {
  const item = token.item as { id?: unknown } | undefined;
  return typeof item?.id === 'string' ? item.id : typeof token.key === 'string' ? token.key : null;
};
const isIdList = (value: unknown): value is string[] => Array.isArray(value) && value.every(v => typeof v === 'string');

// Order of effects after a request: server answer first; only then the list, the tab badge, the launcher badge and the shade,
// and only for the ids the server confirmed (read + already_read). A failed request changes nothing locally and is not repeated
// on its own: the next try comes with a new focus, a return to the app or a newly visible item.
export function useMarkNotificationsRead(data: Notifications | undefined) {
  const { api, session, state } = useSession();
  const query = useQueryClient();
  const dataRef = useRef<Notifications | undefined>(data);
  dataRef.current = data;
  const viewable = useRef(new Set<string>());
  const confirmed = useRef(new Set<string>()); // confirmed read by the server in this session
  const ignored = useRef(new Set<string>());   // the server did not accept them: not asked again until a new focus
  const sending = useRef(false);
  const blocked = useRef(false);
  const focused = useRef(false);
  const appActive = useRef(AppState.currentState !== 'background' && AppState.currentState !== 'inactive');
  const generation = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const pumpRef = useRef<(retry: boolean) => void>(() => {});
  const dismissedKey = useRef('');

  const send = useCallback((batch: string[]) => {
    sending.current = true;
    const myGeneration = generation.current;
    const abort = new AbortController();
    controller.current = abort;
    const startEpoch = notificationEpoch();
    const listAt = query.getQueryState(keys.notifications)?.dataUpdatedAt;
    const badgesAt = query.getQueryState(keys.badges)?.dataUpdatedAt;
    const live = () => myGeneration === generation.current;
    void (async () => {
      try {
        const res = await api.request<NotificationsMarkRead>(withClientBusiness('/me/notifications/mark-read'), { method: 'POST', auth: true, body: { ids: batch }, signal: abort.signal });
        if (!live()) return;
        if (!res || !isIdList(res.read) || !isIdList(res.already_read) || !isIdList(res.ignored) || typeof res.unread_count !== 'number') throw new Error('bad mark-read answer');
        const inBatch = new Set(batch);
        const ok = new Set([...res.read, ...res.already_read].filter(id => inBatch.has(id)));
        for (const id of ok) confirmed.current.add(id);
        for (const id of batch) if (!ok.has(id)) ignored.current.add(id); // ignored (or unanswered) is not read
        // A newer push, or a refetch that finished while the request was running, makes the answer's counter older than the cache.
        const fresh = notificationEpoch() === startEpoch
          && query.getQueryState(keys.notifications)?.dataUpdatedAt === listAt
          && query.getQueryState(keys.badges)?.dataUpdatedAt === badgesAt;
        if (ok.size > 0) {
          query.setQueryData<Notifications>(keys.notifications, old => {
            if (!old) return old;
            const dropped = old.items.filter(item => item.is_unread && ok.has(item.id)).length;
            return { ...old, items: old.items.map(item => (ok.has(item.id) ? { ...item, is_unread: false } : item)), unread_count: Math.max(0, old.unread_count - dropped) };
          });
        }
        if (fresh) query.setQueryData<Badges>(keys.badges, old => (old ? { ...old, notifications_unread: Math.max(0, res.unread_count) } : old));
        // Confirm against the server in any case; when the answer is not fresh its counter is not used at all.
        await Promise.all([query.invalidateQueries({ queryKey: keys.notifications }), query.invalidateQueries({ queryKey: keys.badges })]);
        if (!live()) return;
        const badges = query.getQueryData<Badges>(keys.badges);
        const unread = fresh ? res.unread_count : badges?.notifications_unread; // no badge answer at all: do not invent a zero
        await dismissReadBroadcasts(ok);
        if (unread !== undefined && live()) await syncSystemBadge(unread);
      } catch {
        if (live()) blocked.current = true;
      } finally {
        if (live()) {
          sending.current = false;
          if (!blocked.current) pumpRef.current(false);
        }
      }
    })();
  }, [api, query]);

  const pump = useCallback((retry: boolean) => {
    if (retry) blocked.current = false;
    if (blocked.current || sending.current || !focused.current || !appActive.current) return;
    const current = dataRef.current;
    if (!current) return;
    const unread = new Set(current.items.filter(item => item.is_unread).map(item => item.id));
    const ids = [...viewable.current].filter(id => unread.has(id) && !confirmed.current.has(id) && !ignored.current.has(id));
    if (ids.length === 0) return;
    send(ids.slice(0, MARK_READ_BATCH));
  }, [send]);
  pumpRef.current = pump;

  // The same function for the whole life of the screen (FlatList does not accept a changing callback).
  const onViewableItemsChanged = useRef(({ viewableItems }: ViewableChange) => {
    const next = new Set<string>();
    for (const token of viewableItems) { const id = tokenId(token); if (id) next.add(id); }
    viewable.current = next;
    pumpRef.current(true);
  }).current;

  // A new session, a logout, a session invalidation or leaving the screen drops everything of the old scope, including
  // the effects of a request that is still on its way.
  useEffect(() => {
    const reset = () => {
      generation.current += 1;
      controller.current?.abort();
      controller.current = null;
      sending.current = false;
      blocked.current = false;
      viewable.current = new Set();
      confirmed.current = new Set();
      ignored.current = new Set();
      dismissedKey.current = '';
    };
    const off = [session.registerOnInvalidate(reset), session.registerBeforeLogout(async () => { reset(); })];
    return () => { off.forEach(fn => fn()); reset(); };
  }, [session, state.status]);

  useFocusEffect(useCallback(() => {
    focused.current = true;
    ignored.current = new Set();
    dismissedKey.current = '';
    pumpRef.current(true);
    dismissRef.current();
    return () => { focused.current = false; };
  }, []));

  useEffect(() => {
    const sub = AppState.addEventListener('change', next => {
      appActive.current = next === 'active';
      if (next === 'active') { dismissedKey.current = ''; pumpRef.current(true); dismissRef.current(); }
    });
    return () => sub.remove();
  }, []);

  // Delivered pushes whose list items the server already reports as read (read earlier, on another device, after a cold start)
  // leave the shade too. Only server-reported state is used; unread items and write-off codes stay.
  const dismissServerRead = useCallback(() => {
    const current = dataRef.current;
    if (!current || !focused.current || !appActive.current) return;
    const readIds = new Set(current.items.filter(item => !item.is_unread).map(item => item.id));
    if (readIds.size === 0) return;
    const key = [...readIds].sort().join(',');
    if (key === dismissedKey.current) return; // the same set was handled for this visit
    dismissedKey.current = key;
    void dismissReadBroadcasts(readIds);
  }, []);
  const dismissRef = useRef(dismissServerRead);
  dismissRef.current = dismissServerRead;

  // Fresh data (refetch, push): a newly arrived item that is already on the screen is picked up; a failure is not retried by this.
  useEffect(() => { pumpRef.current(false); dismissRef.current(); }, [data]);
  return { onViewableItemsChanged, viewabilityConfig: NOTIFICATION_VIEWABILITY };
}
