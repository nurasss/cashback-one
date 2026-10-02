import { ApiError } from './errors';

export interface TransportPolicy {
  development: boolean;
  allowInsecureHttp: boolean;
}

// Expo replaces __DEV__ with false in release bundles. A public env flag alone
// never authorizes cleartext transport, regardless of NODE_ENV or build config.
export function runtimeTransportPolicy(): TransportPolicy {
  const development = typeof __DEV__ !== 'undefined' && __DEV__ === true;
  return {
    development,
    allowInsecureHttp: development && process.env.EXPO_PUBLIC_ALLOW_INSECURE_HTTP === '1',
  };
}

export function validateApiBaseUrl(raw: string, policy: TransportPolicy = runtimeTransportPolicy()): string {
  const value = raw.trim();
  if (!value) throw new ApiError('CONFIG_MISSING');

  let url: URL;
  try {
    // Require an explicit absolute authority; do not repair scheme-relative or
    // backslash URLs. Query/fragment/userinfo are never valid API configuration.
    if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(value) || /[\s\\]/.test(value)) throw new Error();
    url = new URL(value);
    if (!url.hostname || url.username || url.password || url.search || url.hash || value.includes('?') || value.includes('#')) throw new Error();
  } catch {
    // Do not retain the parser exception, raw URL, credentials or query.
    throw new ApiError('INVALID_API_URL');
  }

  if (url.protocol === 'http:') {
    if (policy.development !== true || policy.allowInsecureHttp !== true) throw new ApiError('INSECURE_TRANSPORT');
  } else if (url.protocol !== 'https:') {
    throw new ApiError('INSECURE_TRANSPORT');
  }
  return url.toString().replace(/\/+$/, '');
}
