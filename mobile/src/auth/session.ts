import { ApiClient } from '../api/client';
import { ApiError } from '../api/errors';
import { parseTokens } from './tokens';
import type { TokenStore } from '../storage/secure';
import type { Tokens } from '../types/api';
export type SessionState = { status: 'loading' | 'anonymous' | 'authenticated' | 'signing-out' | 'error'; error?: ApiError; cleanupRequired?: boolean };
export class Session {
  private tokens: Tokens | null = null;
  private epoch = 0;
  private refreshing: Promise<void> | null = null;
  private bootstrapping: Promise<void> | null = null;
  private writes: Promise<void> = Promise.resolve();
  private listeners = new Set<() => void>();
  state: SessionState = { status: 'loading' };
  readonly api: ApiClient;
  constructor(private readonly store: TokenStore, baseUrl: string, private readonly clearCache: () => void, private readonly onRefresh: () => void = () => {}, fetcher?: typeof fetch) {
    this.api = new ApiClient(baseUrl, { access: () => this.tokens?.access_token ?? null, generation: () => this.epoch,
      refresh: () => this.refresh(), invalidate: () => this.invalidate() }, fetcher);
  }
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; };
  snapshot = () => this.state;
  private publish(state: SessionState) { this.state = state; this.listeners.forEach(listener => listener()); }
  private persist(operation: () => Promise<void>) {
    const next = this.writes.catch(() => {}).then(operation); this.writes = next; return next;
  }
  bootstrap(): Promise<void> {
    if (this.bootstrapping) return this.bootstrapping;
    const work = this.performBootstrap();
    this.bootstrapping = work;
    void work.finally(() => { if (this.bootstrapping === work) this.bootstrapping = null; }).catch(() => {});
    return work;
  }
  private async performBootstrap() {
    const epoch = this.epoch;
    this.publish({ status: 'loading' });
    try {
      const saved = await this.store.read();
      if (epoch !== this.epoch) return;
      this.tokens = saved;
      if (!saved) { this.publish({ status: 'anonymous' }); return; }
      await this.refresh();
      // Refresh does not check a deleted user in the current backend.
      await this.api.request('/me/cards', { auth: true });
      if (epoch === this.epoch) this.publish({ status: 'authenticated' });
    } catch (error) {
      if (epoch !== this.epoch) return;
      this.publish({ status: 'error', error: error instanceof ApiError ? error : new ApiError('UNKNOWN_ERROR') });
    }
  }
  async accept(tokens: Tokens) {
    const epoch = this.epoch;
    tokens = parseTokens(tokens);
    await this.persist(() => this.store.write(tokens));
    if (epoch !== this.epoch) throw new ApiError('SESSION_CHANGED');
    this.clearCache(); this.tokens = tokens; this.publish({ status: 'authenticated' });
  }
  refresh(): Promise<void> {
    if (this.refreshing) return this.refreshing;
    const epoch = this.epoch;
    const refresh = this.tokens?.refresh_token;
    if (!refresh) return Promise.reject(new ApiError('UNAUTHORIZED', 401));
    const promise = (async () => {
      try {
        const tokens = parseTokens(await this.api.request<unknown>('/auth/refresh', { method: 'POST', body: { refresh_token: refresh } }));
        if (epoch !== this.epoch) throw new ApiError('SESSION_CHANGED');
        await this.persist(() => this.store.write(tokens));
        if (epoch !== this.epoch) throw new ApiError('SESSION_CHANGED');
        this.tokens = tokens; this.onRefresh();
      } catch (error) {
        if (epoch === this.epoch && error instanceof ApiError && (error.status === 401 || error.code === 'SECURE_STORAGE_UNAVAILABLE' || error.code === 'INVALID_RESPONSE')) await this.invalidate();
        throw error;
      }
    })();
    this.refreshing = promise;
    void promise.finally(() => { if (this.refreshing === promise) this.refreshing = null; }).catch(() => {});
    return promise;
  }
  async invalidate() {
    this.epoch++; this.tokens = null; this.refreshing = null; this.clearCache();
    try { await this.persist(() => this.store.clear()); this.publish({ status: 'anonymous' }); }
    catch { this.publish({ status: 'error', error: new ApiError('SECURE_STORAGE_UNAVAILABLE'), cleanupRequired: true }); }
  }
  async logout() {
    this.publish({ status: 'signing-out' });
    try { await this.refreshing; } catch { /* Local cleanup below is unconditional. */ }
    const refresh = this.tokens?.refresh_token;
    this.epoch++; this.tokens = null; this.clearCache();
    let revokeFailed = false;
    try { if (refresh) await this.api.request('/auth/logout', { method: 'POST', body: { refresh_token: refresh } }); }
    catch { revokeFailed = true; }
    finally { await this.invalidate(); }
    return revokeFailed;
  }
}
