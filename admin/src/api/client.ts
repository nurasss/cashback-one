import { ApiError, errorFromResponse } from './errors';
import { validateRuntimeBaseUrl } from './transport';

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH';
  body?: object;
  authenticated?: boolean;
  retryAuthentication?: boolean;
  signal?: AbortSignal;
}
export interface SessionHooks {
  accessToken(): string | null;
  generation(): number;
  replaceAccessToken(token: string): void;
  clearSession(): void;
  refreshAccess(): Promise<string>;
}

export class AdminApiClient {
  constructor(
    private readonly hooks: SessionHooks,
    private readonly baseUrl: () => string | undefined = () => import.meta.env.VITE_API_BASE_URL,
    private readonly fetcher: typeof fetch = fetch,
    private readonly timeoutMs = 15_000,
  ) {}

  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const generation = this.hooks.generation();
    const sentToken = options.authenticated === false ? null : this.hooks.accessToken();
    try {
      return await this.send<T>(path, options, sentToken, generation);
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 401 || options.retryAuthentication === false) throw error;
      if (generation !== this.hooks.generation()) throw new ApiError('SESSION_CHANGED');
      try {
        let currentToken = this.hooks.accessToken();
        if (sentToken === currentToken || !currentToken) currentToken = await this.hooks.refreshAccess();
        return await this.send<T>(path, options, currentToken, generation);
      } catch (refreshError) {
        if (refreshError instanceof ApiError && refreshError.status === 401 && generation === this.hooks.generation()) {
          this.hooks.clearSession();
        }
        throw refreshError;
      }
    }
  }

  private async send<T>(path: string, options: RequestOptions, token: string | null, generation: number): Promise<T> {
    if (options.authenticated !== false && generation !== this.hooks.generation()) throw new ApiError('SESSION_CHANGED');
    const controller = new AbortController();
    const relayAbort = () => controller.abort();
    options.signal?.addEventListener('abort', relayAbort);
    if (options.signal?.aborted) controller.abort();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const validatedBaseUrl = validateRuntimeBaseUrl(this.baseUrl());
      const response = await this.fetcher(`${validatedBaseUrl}${path}`, {
        method: options.method ?? 'GET',
        credentials: 'include',
        cache: 'no-store',
        headers: {
          Accept: 'application/json',
          'X-Admin-Request': '1',
          ...(options.body ? { 'Content-Type': 'application/json' } : {}),
          ...(token && options.authenticated !== false ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: options.body ? JSON.stringify(options.body) : undefined,
        signal: controller.signal,
      });
      if (options.authenticated !== false && generation !== this.hooks.generation()) throw new ApiError('SESSION_CHANGED');
      if (response.status === 204) return undefined as T;
      let payload: unknown;
      try { payload = await response.json(); }
      catch { throw new ApiError(response.ok ? 'INVALID_RESPONSE' : 'SERVER_UNAVAILABLE', response.status); }
      if (!response.ok) throw errorFromResponse(response.status, payload);
      return payload as T;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw new ApiError(controller.signal.aborted ? 'REQUEST_TIMEOUT' : 'NETWORK_UNAVAILABLE');
    } finally {
      clearTimeout(timeout);
      options.signal?.removeEventListener('abort', relayAbort);
    }
  }
}
