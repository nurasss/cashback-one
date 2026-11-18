import { useSyncExternalStore } from 'react';

// True while the launch splash covers the app (including its short configuration check). The update dialog is a separate
// native window that would appear above the splash, so it waits for this to turn false; a required update is then shown.
let active = false;
const listeners = new Set<() => void>();

export function setSplashActive(next: boolean): void {
  if (active === next) return;
  active = next;
  listeners.forEach(listener => listener());
}

export function isSplashActive(): boolean {
  return active;
}

export function useSplashActive(): boolean {
  return useSyncExternalStore(
    listener => { listeners.add(listener); return () => { listeners.delete(listener); }; },
    () => active,
    () => false,
  );
}
