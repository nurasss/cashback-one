import Constants from 'expo-constants';

export const VERSION_INFO_URL = 'https://cashback-qr.poscenter.kz/app/version.json';

const VERSION_REGEX = /^\d+\.\d+\.\d+$/;
const DOWNLOAD_URL_REGEX = /^https:\/\/cashback-qr\.poscenter\.kz\/app\/cashback-one-\d+\.\d+\.\d+\.apk$/;

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
export function parseVersionInfo(value: unknown): VersionInfo | null {
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

  if (typeof obj.download_url !== 'string' || !DOWNLOAD_URL_REGEX.test(obj.download_url)) {
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

/**
 * Reads the current Android versionCode from Expo Constants.
 * Returns null if not configured or not a positive integer.
 */
export function getCurrentVersionCode(): number | null {
  const code = Constants.expoConfig?.android?.versionCode;
  return typeof code === 'number' && Number.isInteger(code) && code > 0 ? code : null;
}

/**
 * Fetches version.json from the public website with a 5s timeout and no cache.
 * Any network, HTTP, or parsing error returns null without logging or throwing.
 */
export async function fetchVersionInfo(
  fetcher: typeof fetch = fetch,
): Promise<VersionInfo | null> {
  const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
  const timer = controller ? setTimeout(() => controller.abort(), 5000) : null;
  try {
    const res = await fetcher(VERSION_INFO_URL, {
      method: 'GET',
      headers: { 'Cache-Control': 'no-cache' },
      signal: controller?.signal,
    });
    if (!res.ok) {
      return null;
    }
    const data = await res.json();
    return parseVersionInfo(data);
  } catch {
    return null;
  } finally {
    if (timer) {
      clearTimeout(timer);
    }
  }
}
