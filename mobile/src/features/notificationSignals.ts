// Small in-memory signals between the push listeners (src/features/push.tsx) and the notifications screen.
// Nothing here is persisted and nothing survives a session change (see resetNotificationSignals).

// Counts every event that can make a server answer about "unread" stale: a push arrived, a push was tapped.
let epoch = 0;
export const notificationEpoch = (): number => epoch;
export const bumpNotificationEpoch = (): void => { epoch += 1; };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export const isNotificationId = (value: unknown): value is string => typeof value === 'string' && UUID.test(value);

// The notification the person opened by tapping its push. It only says "show this one"; the item is marked read by the same rule
// as every other item: after it was really on the screen.
let tapTarget: string | null = null;
const listeners = new Set<() => void>();
export const getTapTarget = (): string | null => tapTarget;
export const subscribeTapTarget = (listener: () => void): (() => void) => { listeners.add(listener); return () => { listeners.delete(listener); }; };
export function setTapTarget(id: string | null): void {
  if (tapTarget === id) { if (id !== null) listeners.forEach(l => l()); return; } // a repeated tap re-announces the same target
  tapTarget = id;
  listeners.forEach(l => l());
}

export function resetNotificationSignals(): void {
  tapTarget = null;
  listeners.forEach(l => l());
}
