import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

type TrayNotification = { request?: { identifier?: string; content?: { data?: unknown } } };

// The server sends only two push kinds (backend push_service / pos_service):
//   { type: 'broadcast', notification_id }       - a broadcast that is also an item of the notifications list;
//   { type: 'redemption_code', redemption_id }   - a write-off code the cashier is waiting for.
export interface PushPayload { type?: string; notification_id?: string; redemption_id?: string }

export function pushPayload(notification: TrayNotification | null | undefined): PushPayload {
  const raw = notification?.request?.content?.data;
  if (!raw || typeof raw !== 'object') return {};
  let data = raw as Record<string, unknown>;
  if (typeof data.dataString === 'string') {
    try {
      const parsed: unknown = JSON.parse(data.dataString);
      if (parsed && typeof parsed === 'object') data = parsed as Record<string, unknown>;
    } catch { /* keep the object as it is */ }
  }
  const text = (value: unknown) => (typeof value === 'string' ? value : undefined);
  return { type: text(data.type), notification_id: text(data.notification_id), redemption_id: text(data.redemption_id) };
}

// Removes from the phone's notification shade only the delivered broadcasts whose list items the person has just seen and the
// server has marked read. Anything else stays: write-off codes, a push that arrived after the list was fetched (its id is not in
// `readIds`), pushes of other businesses/users (their ids are not in this person's list), notifications of other apps.
// Returns the number of removed notifications; never throws.
export async function dismissReadBroadcasts(readIds: ReadonlySet<string>): Promise<number> {
  if (Platform.OS === 'web' || readIds.size === 0) return 0;
  if (typeof Notifications.getPresentedNotificationsAsync !== 'function' || typeof Notifications.dismissNotificationAsync !== 'function') return 0;
  let removed = 0;
  try {
    const presented = (await Notifications.getPresentedNotificationsAsync()) as TrayNotification[];
    for (const item of presented) {
      const payload = pushPayload(item);
      const identifier = item.request?.identifier;
      if (payload.type !== 'broadcast' || !payload.notification_id || !readIds.has(payload.notification_id) || !identifier) continue;
      try {
        await Notifications.dismissNotificationAsync(identifier);
        removed += 1;
      } catch { /* one stuck notification must not stop the rest */ }
    }
  } catch { /* the tray is a convenience; the server state is what counts */ }
  return removed;
}

// The launcher badge follows the server's unread count (not every Android launcher supports it: the call then resolves false).
export async function syncSystemBadge(unread: number): Promise<void> {
  if (Platform.OS === 'web' || typeof Notifications.setBadgeCountAsync !== 'function') return;
  try {
    await Notifications.setBadgeCountAsync(Math.max(0, Math.floor(unread) || 0));
  } catch { /* unsupported launcher */ }
}
