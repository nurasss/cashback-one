import { ApiError, normalizeApiError } from './errors';
import { validateApiBaseUrl } from './transport';
export interface AuthHooks { access(): string | null; generation(): number; refresh(): Promise<void>; invalidate(): Promise<void> }
interface RequestOptions { method?: 'GET' | 'POST' | 'DELETE'; body?: object; headers?: Record<string, string>; auth?: boolean; signal?: AbortSignal }
export class ApiClient {
  constructor(private readonly baseUrl: string, private readonly hooks: AuthHooks, private readonly fetcher: typeof fetch = fetch, private readonly timeoutMs = 15000) {}
  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const generation = this.hooks.generation();
    const usedToken = this.hooks.access();
    if (options.auth && !usedToken) throw new ApiError('UNAUTHORIZED', 401);
    try { return await this.send<T>(path, options, usedToken, generation); }
    catch (error) {
      if (!(error instanceof ApiError) || error.status !== 401 || !options.auth) throw error;
      if (generation !== this.hooks.generation()) throw new ApiError('SESSION_CHANGED');
      if (usedToken === this.hooks.access()) await this.hooks.refresh();
      try { return await this.send<T>(path, options, this.hooks.access(), generation); }
      catch (retryError) {
        if (retryError instanceof ApiError && retryError.status === 401 && generation === this.hooks.generation()) await this.hooks.invalidate();
        throw retryError;
      }
    }
  }
  private async send<T>(path: string, options: RequestOptions, access: string | null, generation: number): Promise<T> {
    if (options.auth && generation !== this.hooks.generation()) throw new ApiError('SESSION_CHANGED');
    const baseUrl = validateApiBaseUrl(this.baseUrl);
    const controller = new AbortController();
    const abort = () => controller.abort();
    options.signal?.addEventListener('abort', abort);
    if (options.signal?.aborted) controller.abort();
    const timer = setTimeout(abort, this.timeoutMs);
    try {
      const response = await this.fetcher(`${baseUrl}${path}`, {
        method: options.method ?? 'GET',
        headers: { Accept: 'application/json', ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...options.headers,
          ...(options.auth && access ? { Authorization: `Bearer ${access}` } : {}) },
        body: options.body ? JSON.stringify(options.body) : undefined, signal: controller.signal,
      });
      if (options.auth && generation !== this.hooks.generation()) throw new ApiError('SESSION_CHANGED');
      if (response.status === 204) return undefined as T;
      let payload: unknown;
      try { payload = await response.json(); }
      catch { throw new ApiError(controller.signal.aborted ? 'REQUEST_TIMEOUT' : response.ok ? 'INVALID_RESPONSE' : 'SERVER_UNAVAILABLE', response.status); }
      if (!response.ok) throw normalizeApiError(response.status, payload);
      return payload as T;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw new ApiError(controller.signal.aborted ? 'REQUEST_TIMEOUT' : 'NETWORK_UNAVAILABLE');
    } finally { clearTimeout(timer); options.signal?.removeEventListener('abort', abort); }
  }
}
