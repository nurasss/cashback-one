import AsyncStorage from '@react-native-async-storage/async-storage';

// Managed launch splash: the public configuration, its validation and its small local cache.
// Contract (backend, published): GET {API}/public/app-splash?app_id=<android_app_id>, no authorization, ETag / 304.
// The cache holds only this tiny JSON per app id (never tokens and never the personal `cashback-one.cache.v1:` cache);
// image bytes are cached by expo-image, a video is streamed and is not stored on the device.

export const SPLASH_CACHE_PREFIX = 'cashback-one.splash.v1:';
export const IMAGE_MAX_BYTES = 5 * 1024 * 1024;
export const VIDEO_MAX_BYTES = 15 * 1024 * 1024;
export const VIDEO_MAX_SECONDS = 5;
export const CONFIG_TIMEOUT_MS = 2000;
export const CACHE_OP_TIMEOUT_MS = 600;

export const TRUSTED_MEDIA_ORIGINS = new Set([
  'https://cashback-qr.poscenter.kz',
  'https://api.cashback-qr.poscenter.kz',
]);

function getTrustedOrigins(): Set<string> {
  const set = new Set(TRUSTED_MEDIA_ORIGINS);
  const base = process.env.EXPO_PUBLIC_API_BASE_URL;
  if (base) {
    const m = /^https:\/\/[a-zA-Z0-9.-]+(?::[0-9]+)?/i.exec(base.trim());
    if (m) set.add(m[0].toLowerCase());
  }
  return set;
}

const STRICT_SPLASH_MEDIA_URL =
  /^(https:\/\/[a-zA-Z0-9.-]+(?::[0-9]+)?)\/media\/splashes\/([0-9a-f]{32})\.(webp|mp4)$/;

export interface Splash {
  mediaType: 'image' | 'video';
  mediaUrl: string;
  width: number;
  height: number;
  durationSeconds: number | null;
  fileSize: number;
  version: string;
  businessId: string | null;
}

export interface SplashExpectation {
  /** The client's own business, when the client config has one: media of another business is never shown. */
  businessId: string | null;
}

const isValidDimension = (value: unknown): value is number =>
  typeof value === 'number' && Number.isInteger(value) && value > 0 && value <= 10_000;

const isValidFileSize = (value: unknown, maxBytes: number): value is number =>
  typeof value === 'number' && Number.isInteger(value) && value > 0 && value <= maxBytes;

// Returns a safe splash, or null for "disabled", an unknown shape, a non-HTTPS or foreign-looking media URL, a wrong
// business, or a file above the limits. Anything unexpected means an ordinary launch, never a guess.
export function parseSplash(raw: unknown, expected: SplashExpectation): Splash | null {
  if (!raw || typeof raw !== 'object') return null;
  const body = raw as Record<string, unknown>;
  if (body.enabled !== true) return null;
  const mediaType = body.media_type;
  const mediaUrl = body.media_url;
  if ((mediaType !== 'image' && mediaType !== 'video') || typeof mediaUrl !== 'string') return null;

  const match = STRICT_SPLASH_MEDIA_URL.exec(mediaUrl);
  if (!match || !match[1] || !match[3]) return null;
  const origin = match[1].toLowerCase();
  if (!getTrustedOrigins().has(origin)) return null;

  const ext = match[3];
  if ((ext === 'mp4') !== (mediaType === 'video')) return null;

  const { width, height, file_size: fileSize, version } = body;
  if (!isValidDimension(width) || !isValidDimension(height)) return null;

  const maxBytes = mediaType === 'video' ? VIDEO_MAX_BYTES : IMAGE_MAX_BYTES;
  if (!isValidFileSize(fileSize, maxBytes)) return null;

  if (typeof version !== 'string' || version.length === 0 || version.length > 128) return null;
  const businessId = typeof body.business_id === 'string' ? body.business_id : null;
  if (expected.businessId && businessId !== expected.businessId) return null;

  let durationSeconds: number | null = null;
  if (mediaType === 'video') {
    const duration = body.duration_seconds;
    if (typeof duration !== 'number' || !Number.isFinite(duration) || duration <= 0 || duration > VIDEO_MAX_SECONDS) return null;
    durationSeconds = duration;
  }
  return { mediaType, mediaUrl, width, height, durationSeconds, fileSize, version, businessId };
}

/**
 * Validates a cached Splash object against client business, size limits, format and origins.
 * Prevents corrupted or foreign cache from being trusted by the player.
 */
export function validateCachedSplash(splash: unknown, expected: SplashExpectation): Splash | null {
  if (!splash || typeof splash !== 'object') return null;
  const s = splash as Record<string, unknown>;
  const mediaType = s.mediaType;
  const mediaUrl = s.mediaUrl;
  if ((mediaType !== 'image' && mediaType !== 'video') || typeof mediaUrl !== 'string') return null;

  const match = STRICT_SPLASH_MEDIA_URL.exec(mediaUrl);
  if (!match || !match[1] || !match[3]) return null;
  const origin = match[1].toLowerCase();
  if (!getTrustedOrigins().has(origin)) return null;

  const ext = match[3];
  if ((ext === 'mp4') !== (mediaType === 'video')) return null;

  const { width, height, fileSize, version } = s;
  if (!isValidDimension(width) || !isValidDimension(height)) return null;

  const maxBytes = mediaType === 'video' ? VIDEO_MAX_BYTES : IMAGE_MAX_BYTES;
  if (!isValidFileSize(fileSize, maxBytes)) return null;

  if (typeof version !== 'string' || version.length === 0 || version.length > 128) return null;
  const businessId = typeof s.businessId === 'string' ? s.businessId : null;
  if (expected.businessId && businessId !== expected.businessId) return null;

  let durationSeconds: number | null = null;
  if (mediaType === 'video') {
    const duration = s.durationSeconds;
    if (typeof duration !== 'number' || !Number.isFinite(duration) || duration <= 0 || duration > VIDEO_MAX_SECONDS) return null;
    durationSeconds = duration;
  }
  return { mediaType, mediaUrl, width, height, durationSeconds, fileSize, version, businessId };
}

interface CacheEntry { appId: string; etag: string | null; checkedAt: number; splash: Splash | null }

export const cacheKey = (appId: string) => `${SPLASH_CACHE_PREFIX}${appId}`;

export async function withTimeout<T>(promise: Promise<T>, timeoutMs: number, fallback: T): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeoutPromise = new Promise<T>(resolve => {
    timer = setTimeout(() => resolve(fallback), timeoutMs);
  });
  try {
    return await Promise.race([promise, timeoutPromise]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

export async function readCache(appId: string, expected?: SplashExpectation): Promise<CacheEntry | null> {
  try {
    const text = await withTimeout(
      AsyncStorage.getItem(cacheKey(appId)),
      CACHE_OP_TIMEOUT_MS,
      null,
    );
    if (!text) return null;
    const entry = JSON.parse(text) as CacheEntry;
    if (!entry || entry.appId !== appId || typeof entry.checkedAt !== 'number') return null;
    if (entry.splash) {
      const valid = validateCachedSplash(entry.splash, expected ?? { businessId: null });
      if (!valid) {
        return { ...entry, splash: null };
      }
      entry.splash = valid;
    }
    return entry;
  } catch {
    return null;
  }
}

export async function writeCache(entry: CacheEntry): Promise<void> {
  try {
    await withTimeout(
      AsyncStorage.setItem(cacheKey(entry.appId), JSON.stringify(entry)),
      CACHE_OP_TIMEOUT_MS,
      undefined,
    );
  } catch {
    /* the cache is optional, never throw */
  }
}

export type FetchOutcome =
  | { kind: 'fresh'; splash: Splash | null; etag: string | null } // splash null: disabled, or a config that failed validation
  | { kind: 'not-modified' }
  | { kind: 'error' };

export async function fetchSplash(appId: string, expected: SplashExpectation, etag: string | null, timeoutMs = CONFIG_TIMEOUT_MS): Promise<FetchOutcome> {
  const base = (process.env.EXPO_PUBLIC_API_BASE_URL ?? '').replace(/\/+$/, '');
  if (!/^https:\/\//i.test(base)) return { kind: 'error' };
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${base}/public/app-splash?app_id=${encodeURIComponent(appId)}`, {
      headers: etag ? { Accept: 'application/json', 'If-None-Match': etag } : { Accept: 'application/json' },
      signal: controller.signal,
    });
    if (response.status === 304) return { kind: 'not-modified' };
    if (!response.ok) return { kind: 'error' };
    const body: unknown = await response.json();
    return { kind: 'fresh', splash: parseSplash(body, expected), etag: response.headers.get('ETag') };
  } catch { return { kind: 'error' }; } finally { clearTimeout(timer); }
}

export interface Resolution {
  splash: Splash | null;
  // True when there is no cached answer at all (first launch): the caller waits for the answer once, within the budget.
  firstCheck: boolean;
}

/**
 * Cache policy:
 *  - answer "enabled" (200): stored with its ETag, shown; "disabled" or invalid: the stored splash is deleted, ordinary launch;
 *  - 304: the stored splash of this app id is shown;
 *  - network error / timeout: the last confirmed splash of this client is shown (never another client's), otherwise ordinary launch;
 *  - a cache that says "disabled" never blocks the launch: the app opens at once and the check runs in the background for the next launch.
 */
export async function resolveSplash(appId: string, expected: SplashExpectation, timeoutMs = CONFIG_TIMEOUT_MS): Promise<Resolution> {
  const cached = await readCache(appId, expected);
  const outcome = await fetchSplash(appId, expected, cached?.splash ? cached.etag : null, timeoutMs);
  if (outcome.kind === 'fresh') {
    await writeCache({ appId, etag: outcome.splash ? outcome.etag : null, checkedAt: Date.now(), splash: outcome.splash });
    return { splash: outcome.splash, firstCheck: cached === null };
  }
  if (outcome.kind === 'not-modified' && cached?.splash) {
    await writeCache({ ...cached, checkedAt: Date.now() });
    return { splash: cached.splash, firstCheck: false };
  }
  if (cached === null) {
    await writeCache({ appId, etag: null, checkedAt: Date.now(), splash: null });
  }
  return { splash: cached?.splash ?? null, firstCheck: cached === null };
}

/** Whether the launch must wait for the answer: yes on the first launch and when a splash is cached (it may have been turned off). */
export async function mustWaitForConfig(appId: string, expected?: SplashExpectation): Promise<boolean> {
  const cached = await readCache(appId, expected);
  return cached === null || cached.splash !== null;
}
