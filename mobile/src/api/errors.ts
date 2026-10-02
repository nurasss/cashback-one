import type { BusinessChoice } from '../types/api';
// Do not retain server message/body: validation messages may contain PII or OTP.
export class ApiError extends Error {
  constructor(readonly code: string, readonly status = 0, readonly businesses: BusinessChoice[] = []) { super(code); this.name = 'ApiError'; }
}
const record = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null;
export function normalizeApiError(status: number, payload: unknown): ApiError {
  const error = record(payload) && record(payload.error) ? payload.error : undefined;
  const code = error && typeof error.code === 'string' && /^[A-Z_]{1,64}$/.test(error.code)
    ? error.code : status >= 500 ? 'SERVER_UNAVAILABLE' : 'UNKNOWN_ERROR';
  const businesses: BusinessChoice[] = [];
  if (code === 'BUSINESS_SELECTION_REQUIRED' && error && Array.isArray(error.businesses)) {
    for (const item of error.businesses) {
      if (record(item) && typeof item.id === 'string' && typeof item.name === 'string') businesses.push({ id: item.id, name: item.name });
    }
  }
  return new ApiError(code, status, businesses);
}
