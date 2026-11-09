import * as Application from 'expo-application';
import Constants from 'expo-constants';
import { getClientConfig, type ClientConfig } from '../config/client';

// Trusted origin and directory of every published APK and version manifest.
export const UPDATE_BASE_URL = 'https://cashback-qr.poscenter.kz/app/';
// The shared manifest of the general Cashback One app. Clients never fall back to it: each client reads its own file.
export const VERSION_INFO_URL = `${UPDATE_BASE_URL}version.json`;

const VERSION_REGEX = /^\d+\.\d+\.\d+$/;
const APK_NAME_REGEX = /^[a-z0-9]+(-[a-z0-9]+)*$/;
const MANIFEST_FILE_REGEX = /^[a-z0-9]+(-[a-z0-9]+)*\.json$/;

export interface UpdateSource {
  slug: string;
  manifestUrl: string;
  apkName: string;
}

/**
 * Where the current build looks for updates and which APK name it may offer.
 * General app: `version.json` + `cashback-one-X.Y.Z.apk`. Other clients: `<update_manifest>` (default `<slug>-version.json`)
 * + `<apk_name>-X.Y.Z.apk`. Returns null for an invalid client config, which disables update checks instead of guessing.
 */
export function getUpdateSource(client?: ClientConfig): UpdateSource | null {
  let config: ClientConfig;
  try { config = client ?? getClientConfig(); } catch { return null; }
  const apkName = config.apk_name ?? config.slug;
  const manifestFile = config.update_manifest ?? (config.slug === 'cashbackone' ? 'version.json' : `${config.slug}-version.json`);
  if (!APK_NAME_REGEX.test(apkName) || !MANIFEST_FILE_REGEX.test(manifestFile)) return null;
  return { slug: config.slug, manifestUrl: `${UPDATE_BASE_URL}${manifestFile}`, apkName };
}

function downloadUrlRegex(apkName: string): RegExp {
  const escapedBase = UPDATE_BASE_URL.replace(/[.*+?^${}()|[\]\\/]/g, '\\$&');
  return new RegExp(`^${escapedBase}${apkName}-\\d+\\.\\d+\\.\\d+\\.apk$`);
}

export interface VersionInfo {
  latest_version: string;
  latest_version_code: number;
  min_version_code: number;
  download_url: string;
}

export type UpdateDecision = 'none' | 'optional' | 'required';

/**
 * Pure parser for version.json.
 * Returns null if the value is malformed or violates security/integrity constraints.
 */
export function parseVersionInfo(value: unknown, source: UpdateSource | null = getUpdateSource()): VersionInfo | null {
  if (!source) {
    return null;
  }
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null;
  }
  const obj = value as Record<string, unknown>;

  if (typeof obj.latest_version !== 'string' || !VERSION_REGEX.test(obj.latest_version)) {
    return null;
  }

  if (
    typeof obj.latest_version_code !== 'number' ||
    !Number.isInteger(obj.latest_version_code) ||
    obj.latest_version_code <= 0
  ) {
    return null;
  }

  if (
    typeof obj.min_version_code !== 'number' ||
    !Number.isInteger(obj.min_version_code) ||
    obj.min_version_code <= 0
  ) {
    return null;
  }

  if (obj.min_version_code > obj.latest_version_code) {
    return null;
  }

  if (typeof obj.download_url !== 'string' || !downloadUrlRegex(source.apkName).test(obj.download_url)) {
    return null;
  }

  return {
    latest_version: obj.latest_version,
    latest_version_code: obj.latest_version_code,
    min_version_code: obj.min_version_code,
    download_url: obj.download_url,
  };
}

/**
 * Pure decision maker for update prompt based on current and remote versions.
 */
export function updateDecision(
  info: VersionInfo | null,
  currentCode: number | null | undefined,
): UpdateDecision {
  if (!info || typeof currentCode !== 'number' || !Number.isInteger(currentCode) || currentCode <= 0) {
    return 'none';
  }
  if (currentCode < info.min_version_code) {
    return 'required';
  }
  if (currentCode < info.latest_version_code) {
    return 'optional';
  }
  return 'none';
}

function positiveInteger(value: unknown): number | null {
  const number = typeof value === 'string' && /^\d+$/.test(value) ? Number(value) : value;
  return typeof number === 'number' && Number.isInteger(number) && number > 0 ? number : null;
}

/**
 * Reads the current Android versionCode. The installed package's real versionCode (native build, set in build.gradle)
 * wins; the value embedded from app.json (Expo Constants) is the fallback when the native one is unavailable.
 * Returns null if neither is a positive integer.
 */
export function getCurrentVersionCode(): number | null {
  try {
    const native = positiveInteger(Application.nativeBuildVersion);
    if (native !== null) return native;
  } catch {
    // Native module unavailable (web, tests): use the embedded config.
  }
  return positiveInteger(Constants.expoConfig?.android?.versionCode);
}

export type VersionFetchResult = { ok: true; info: VersionInfo } | { ok: false };

/**
 * Fetches this client's manifest from the public website with a 5s timeout and no cache.
 * Distinguishes a failed request or invalid manifest (`ok: false`) from a valid answer, so callers never report
 * "up to date" after an error. Never throws and never logs.
 */
export async function loadVersionInfo(
  fetcher: typeof fetch = fetch,
  source: UpdateSource | null = getUpdateSource(),
): Promise<VersionFetchResult> {
  if (!source) {
    return { ok: false };
  }
  const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
  const timer = controller ? setTimeout(() => controller.abort(), 5000) : null;
  try {
    const res = await fetcher(source.manifestUrl, {
      method: 'GET',
      headers: { 'Cache-Control': 'no-cache' },
      signal: controller?.signal,
    });
    if (!res.ok) {
      return { ok: false };
    }
    const info = parseVersionInfo(await res.json(), source);
    return info ? { ok: true, info } : { ok: false };
  } catch {
    return { ok: false };
  } finally {
    if (timer) {
      clearTimeout(timer);
    }
  }
}

/** Same as `loadVersionInfo`, returning null on any failure. */
export async function fetchVersionInfo(
  fetcher: typeof fetch = fetch,
  source: UpdateSource | null = getUpdateSource(),
): Promise<VersionInfo | null> {
  const result = await loadVersionInfo(fetcher, source);
  return result.ok ? result.info : null;
}
