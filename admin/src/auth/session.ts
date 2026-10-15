import { AdminApiClient } from '../api/client';
import { ApiError } from '../api/errors';
import type { AdminAccessToken, AdminIdentity, AdminMe } from '../api/types';

export type SessionView =
  | { status: 'loading' | 'authenticating' | 'signing_out' }
  | { status: 'anonymous' }
  | { status: 'authenticated'; admin: AdminIdentity }
  | { status: 'error' | 'logout_error'; error: ApiError };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function parseToken(value: unknown): AdminAccessToken {
  if (!isRecord(value) || typeof value.access_token !== 'string' || !value.access_token
    || value.token_type !== 'bearer' || typeof value.expires_in !== 'number' || value.expires_in <= 0) {
    throw new ApiError('INVALID_RESPONSE');
  }
  return { access_token: value.access_token, token_type: 'bearer', expires_in: value.expires_in };
}

function parseMe(value: unknown): AdminMe {
  if (!isRecord(value) || !isRecord(value.admin)) throw new ApiError('INVALID_RESPONSE');
  const admin = value.admin;
  if (typeof admin.id !== 'string' || typeof admin.login !== 'string'
    || (admin.role !== 'superadmin' && admin.role !== 'business_manager')) throw new ApiError('INVALID_RESPONSE');
  if (admin.role === 'superadmin') {
    if (admin.business !== null) throw new ApiError('INVALID_RESPONSE');
    return { admin: { id: admin.id, login: admin.login, role: admin.role, business: null } };
  }
  if (!isRecord(admin.business) || typeof admin.business.id !== 'string' || typeof admin.business.name !== 'string'
    || typeof admin.business.status !== 'string') throw new ApiError('INVALID_RESPONSE');
  return {
    admin: {
      id: admin.id,
      login: admin.login,
      role: admin.role,
      business: { id: admin.business.id, name: admin.business.name, status: admin.business.status },
    },
  };
}

export class AdminSession {
  // The short-lived access JWT exists only in this object in JavaScript memory.
  private access: string | null = null;
  private epoch = 0;
  private bootstrapFlight: Promise<void> | null = null;
  private refreshFlight: Promise<string> | null = null;
  private listeners = new Set<() => void>();
  private currentView: SessionView = { status: 'loading' };
  readonly api: AdminApiClient;

  constructor(private readonly clearPrivateCache: () => void, baseUrl?: () => string, fetcher?: typeof fetch) {
    this.api = new AdminApiClient({
      accessToken: () => this.access,
      generation: () => this.epoch,
      replaceAccessToken: token => { this.access = token; },
      clearSession: () => this.expireLocally(),
      refreshAccess: () => this.refreshAccess(),
    }, baseUrl, fetcher);
  }

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  };
  snapshot = (): SessionView => this.currentView;

  private publish(view: SessionView): void {
    this.currentView = view;
    for (const listener of this.listeners) listener();
  }

  bootstrap(): Promise<void> {
    if (this.bootstrapFlight) return this.bootstrapFlight;
    const flight = this.restoreSession();
    this.bootstrapFlight = flight;
    void flight.finally(() => { if (this.bootstrapFlight === flight) this.bootstrapFlight = null; }).catch(() => {});
    return flight;
  }

  continueToLogin(): void {
    if (this.currentView.status === 'error') {
      this.epoch++;
      this.access = null;
      this.clearPrivateCache();
      this.publish({ status: 'anonymous' });
    }
  }

  private async restoreSession(): Promise<void> {
    const generation = this.epoch;
    this.publish({ status: 'loading' });
    try {
      await this.refreshAccess();
      const me = parseMe(await this.api.request<unknown>('/admin/me'));
      if (generation === this.epoch) this.publish({ status: 'authenticated', admin: me.admin });
    } catch (error) {
      if (generation !== this.epoch) return;
      if (error instanceof ApiError && error.status === 401) this.publish({ status: 'anonymous' });
      else this.publish({ status: 'error', error: error instanceof ApiError ? error : new ApiError('UNKNOWN_ERROR') });
    }
  }

  private refreshAccess(): Promise<string> {
    if (this.refreshFlight) return this.refreshFlight;
    const generation = this.epoch;
    const flight = (async () => {
      const token = parseToken(await this.api.request<unknown>('/admin/auth/refresh', {
        method: 'POST', body: {}, authenticated: false, retryAuthentication: false,
      }));
      if (generation !== this.epoch) throw new ApiError('SESSION_CHANGED');
      this.access = token.access_token;
      return token.access_token;
    })();
    this.refreshFlight = flight;
    void flight.finally(() => { if (this.refreshFlight === flight) this.refreshFlight = null; }).catch(() => {});
    return flight;
  }

  async login(login: string, password: string): Promise<void> {
    this.publish({ status: 'authenticating' });
    const generation = this.epoch;
    try {
      const token = parseToken(await this.api.request<unknown>('/admin/auth/login', {
        method: 'POST', body: { login, password }, authenticated: false, retryAuthentication: false,
      }));
      if (generation !== this.epoch) throw new ApiError('SESSION_CHANGED');
      this.clearPrivateCache();
      this.access = token.access_token;
      const me = parseMe(await this.api.request<unknown>('/admin/me'));
      if (generation === this.epoch) this.publish({ status: 'authenticated', admin: me.admin });
    } catch (error) {
      if (generation === this.epoch) {
        this.access = null;
        this.clearPrivateCache();
        if (error instanceof ApiError && error.status === 401) this.publish({ status: 'anonymous' });
        else this.publish({ status: 'error', error: error instanceof ApiError ? error : new ApiError('UNKNOWN_ERROR') });
      }
      throw error;
    }
  }

  private expireLocally(): void {
    this.epoch++;
    this.access = null;
    this.clearPrivateCache();
    this.publish({ status: 'anonymous' });
  }

  async logout(): Promise<void> {
    this.publish({ status: 'signing_out' });
    this.epoch++;
    this.access = null;
    this.clearPrivateCache();
    this.refreshFlight = null;
    try {
      await this.api.request('/admin/auth/logout', { method: 'POST', body: {}, authenticated: false, retryAuthentication: false });
      this.publish({ status: 'anonymous' });
    } catch (error) {
      const safe = error instanceof ApiError ? error : new ApiError('UNKNOWN_ERROR');
      // HttpOnly prevents JS from clearing the cookie. Keep private routes locked until retry succeeds.
      this.publish({ status: 'logout_error', error: safe });
    }
  }
}
