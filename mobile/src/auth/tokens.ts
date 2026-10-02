import { ApiError } from '../api/errors';
import type { Tokens } from '../types/api';
export function parseTokens(value: unknown): Tokens {
  if (typeof value !== 'object' || value === null || !('access_token' in value) || !('refresh_token' in value)
    || !('token_type' in value) || !('expires_in' in value) || typeof value.access_token !== 'string' || !value.access_token
    || typeof value.refresh_token !== 'string' || !value.refresh_token || value.token_type !== 'bearer'
    || typeof value.expires_in !== 'number' || !Number.isFinite(value.expires_in) || value.expires_in <= 0) throw new ApiError('INVALID_RESPONSE');
  return { access_token: value.access_token, refresh_token: value.refresh_token, token_type: value.token_type, expires_in: value.expires_in };
}
