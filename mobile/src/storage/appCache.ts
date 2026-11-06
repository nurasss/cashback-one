import AsyncStorage from '@react-native-async-storage/async-storage';
import { getClientConfig } from '../config/client';
import type { AppContent, Promotions } from '../types/api';

const CACHE_PREFIX = 'cashback-one.cache.v1:';

export interface CachedEntry<T> {
  data: T;
  etag: string | null;
  cachedAt: number;
}

const memoryCache = new Map<string, CachedEntry<unknown>>();
let cacheGeneration = 0;
let initPromise: Promise<void> | null = null;

export function decodeJwtSub(token: string | null | undefined): string | null {
  if (!token || typeof token !== 'string') return null;
  const parts = token.split('.');
  const rawB64 = parts[1];
  if (!rawB64) return null;
  try {
    const b64 = rawB64.replace(/-/g, '+').replace(/_/g, '/');
    const padded = b64.padEnd(b64.length + ((4 - (b64.length % 4)) % 4), '=');
    let binary = '';
    if (typeof globalThis.atob === 'function') {
      binary = globalThis.atob(padded);
    } else if (typeof Buffer !== 'undefined') {
      binary = Buffer.from(padded, 'base64').toString('binary');
    } else {
      return null;
    }
    const decoded = decodeURIComponent(
      binary
        .split('')
        .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join(''),
    );
    const payload = JSON.parse(decoded) as { sub?: string };
    return typeof payload.sub === 'string' ? payload.sub : null;
  } catch {
    return null;
  }
}

export function getAppContentCacheKey(userId: string, businessId: string): string {
  return `${CACHE_PREFIX}user:${userId}:business:${businessId}:app-content`;
}

export function getPromotionsCacheKey(userId: string, businessId?: string | null): string {
  let b = businessId;
  if (b === undefined) {
    try {
      b = getClientConfig().business_id;
    } catch {
      b = null;
    }
  }
  return b ? `${CACHE_PREFIX}user:${userId}:business:${b}:promotions` : `${CACHE_PREFIX}user:${userId}:promotions`;
}

export function initAppCache(): Promise<void> {
  if (initPromise) return initPromise;
  const currentGen = cacheGeneration;
  initPromise = (async () => {
    try {
      const keys = await AsyncStorage.getAllKeys();
      if (currentGen !== cacheGeneration) return;
      const cacheKeys = keys.filter(k => k.startsWith(CACHE_PREFIX));
      if (cacheKeys.length > 0) {
        const pairs = await AsyncStorage.multiGet(cacheKeys);
        if (currentGen !== cacheGeneration) return;
        for (const [key, value] of pairs) {
          if (currentGen !== cacheGeneration) return;
          if (value) {
            try {
              const parsed = JSON.parse(value) as CachedEntry<unknown>;
              const existing = memoryCache.get(key);
              if (!existing || existing.cachedAt <= parsed.cachedAt) {
                memoryCache.set(key, parsed);
              }
            } catch {
              // Ignore corrupt entry
            }
          }
        }
      }
    } catch {
      // Storage unavailable fallback
    }
  })();
  return initPromise;
}

// Automatically start cache initialization
void initAppCache();

export function getCachedAppContent(userId: string, businessId: string): CachedEntry<AppContent> | null {
  const key = getAppContentCacheKey(userId, businessId);
  return (memoryCache.get(key) as CachedEntry<AppContent> | undefined) ?? null;
}

export function setCachedAppContent(
  userId: string,
  businessId: string,
  data: AppContent,
  etag: string | null,
  cachedAt: number = Date.now(),
): void {
  const key = getAppContentCacheKey(userId, businessId);
  const entry: CachedEntry<AppContent> = { data, etag, cachedAt };
  memoryCache.set(key, entry as CachedEntry<unknown>);
  void AsyncStorage.setItem(key, JSON.stringify(entry)).catch(() => {});
}

export function getCachedPromotions(userId: string): CachedEntry<Promotions> | null {
  const key = getPromotionsCacheKey(userId);
  return (memoryCache.get(key) as CachedEntry<Promotions> | undefined) ?? null;
}

export function setCachedPromotions(
  userId: string,
  data: Promotions,
  etag: string | null,
  cachedAt: number = Date.now(),
): void {
  const key = getPromotionsCacheKey(userId);
  const entry: CachedEntry<Promotions> = { data, etag, cachedAt };
  memoryCache.set(key, entry as CachedEntry<unknown>);
  void AsyncStorage.setItem(key, JSON.stringify(entry)).catch(() => {});
}

export async function clearAppCache(): Promise<void> {
  const inFlight = initPromise;
  cacheGeneration++;
  memoryCache.clear();
  if (inFlight) {
    try {
      await inFlight;
    } catch {
      // Ignore
    }
  }
  memoryCache.clear();
  initPromise = null;
  try {
    const keys = await AsyncStorage.getAllKeys();
    const cacheKeys = keys.filter(k => k.startsWith(CACHE_PREFIX));
    if (cacheKeys.length > 0) {
      await AsyncStorage.multiRemove(cacheKeys);
    }
  } catch {
    // Ignore error
  }
}
