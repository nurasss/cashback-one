import { ApiError } from './errors';

export interface TransportOptions { development: boolean; allowInsecureHttp: boolean }

export function validateApiBaseUrl(value: string | undefined, options: TransportOptions): string {
  const input = value?.trim() ?? '';
  if (!input) throw new ApiError('CONFIG_MISSING');
  if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(input) || /[\s\\]/.test(input)) throw new ApiError('INVALID_API_URL');
  let url: URL;
  try { url = new URL(input); } catch { throw new ApiError('INVALID_API_URL'); }
  if (!url.hostname || url.username || url.password || url.search || url.hash || input.includes('?') || input.includes('#')) {
    throw new ApiError('INVALID_API_URL');
  }
  if (url.protocol === 'https:') return url.toString().replace(/\/+$/, '');
  if (url.protocol === 'http:' && options.development && options.allowInsecureHttp) {
    return url.toString().replace(/\/+$/, '');
  }
  throw new ApiError(url.protocol === 'http:' ? 'INSECURE_TRANSPORT' : 'INVALID_API_URL');
}

export function configuredApiBaseUrl(): string {
  const development = import.meta.env.DEV === true;
  return validateApiBaseUrl(import.meta.env.VITE_API_BASE_URL, {
    development,
    allowInsecureHttp: development && import.meta.env.VITE_ALLOW_INSECURE_HTTP === '1',
  });
}

export function validateRuntimeBaseUrl(value: string | undefined): string {
  const development = import.meta.env.DEV === true;
  return validateApiBaseUrl(value, {
    development,
    allowInsecureHttp: development && import.meta.env.VITE_ALLOW_INSECURE_HTTP === '1',
  });
}
