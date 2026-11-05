import { useQuery } from '@tanstack/react-query';
import { useSession } from '../auth/provider';
import { ApiError } from './errors';
import type { ApiClient } from './client';
import { getCachedAppContent, getCachedPromotions, initAppCache, setCachedAppContent, setCachedPromotions } from '../storage/appCache';
import type { AppContent, Badges, CardQr, Notifications, Profile, Promotion, Promotions, WalletAvailability, WalletLinkResponse } from '../types/api';

export const appKey = ['app'] as const;
export const keys = {
  profile: [...appKey, 'profile'] as const,
  promotions: [...appKey, 'promotions'] as const,
  promotion: (id: string) => [...appKey, 'promotion', id] as const,
  appContent: (businessId?: string) => [...appKey, 'appContent', businessId ?? ''] as const,
  notifications: [...appKey, 'notifications'] as const,
  badges: [...appKey, 'badges'] as const,
  qr: (cardId: string) => [...appKey, 'qr', cardId] as const,
  wallet: [...appKey, 'wallet'] as const,
};

export async function fetchPromotionsWithCache(
  api: ApiClient | { request: ApiClient['request']; requestWithMeta?: ApiClient['requestWithMeta'] },
  userId: string,
  signal?: AbortSignal,
): Promise<Promotions> {
  await initAppCache();
  const cached = getCachedPromotions(userId);
  const headers: Record<string, string> = {};
  if (cached?.etag) {
    headers['If-None-Match'] = cached.etag;
  }
  try {
    if (typeof api.requestWithMeta === 'function') {
      const res = await api.requestWithMeta<Promotions>('/me/promotions', {
        auth: true,
        headers,
        signal,
      });
      if (res.status === 304) {
        return cached ? cached.data : { banners: [], offers: [], has_new: false };
      }
      if (res.data) {
        setCachedPromotions(userId, res.data, res.etag);
        return res.data;
      }
      return cached ? cached.data : { banners: [], offers: [], has_new: false };
    }
    const data = await api.request<Promotions>('/me/promotions', {
      auth: true,
      headers,
      signal,
    });
    if (data) {
      setCachedPromotions(userId, data, null);
      return data;
    }
    return cached ? cached.data : { banners: [], offers: [], has_new: false };
  } catch (error) {
    if (cached) {
      return cached.data;
    }
    throw error;
  }
}

export async function fetchAppContentWithCache(
  api: ApiClient | { request: ApiClient['request']; requestWithMeta?: ApiClient['requestWithMeta'] },
  userId: string,
  businessId: string,
  signal?: AbortSignal,
): Promise<AppContent | null> {
  await initAppCache();
  const cached = getCachedAppContent(userId, businessId);
  const headers: Record<string, string> = {};
  if (cached?.etag) {
    headers['If-None-Match'] = cached.etag;
  }
  try {
    if (typeof api.requestWithMeta === 'function') {
      const res = await api.requestWithMeta<AppContent>(`/me/app-content?business_id=${encodeURIComponent(businessId)}`, {
        auth: true,
        headers,
        signal,
      });
      if (res.status === 304) {
        return cached ? cached.data : null;
      }
      if (res.data) {
        setCachedAppContent(userId, businessId, res.data, res.etag);
        return res.data;
      }
      return cached ? cached.data : null;
    }
    const data = await api.request<AppContent>(`/me/app-content?business_id=${encodeURIComponent(businessId)}`, {
      auth: true,
      headers,
      signal,
    });
    if (data) {
      setCachedAppContent(userId, businessId, data, null);
      return data;
    }
    return cached ? cached.data : null;
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.code === 'CUSTOMER_RESOURCE_NOT_FOUND')) {
      return null;
    }
    if (cached) {
      return cached.data;
    }
    throw error;
  }
}

export function useProfile() {
  const { api } = useSession();
  return useQuery({ queryKey: keys.profile, queryFn: ({ signal }) => api.request<Profile>('/me/profile', { auth: true, signal }) });
}
export function usePromotions() {
  const { api, session } = useSession();
  const userId = session.getUserId?.() ?? 'anonymous';
  return useQuery({
    queryKey: keys.promotions,
    initialData: () => getCachedPromotions(userId)?.data,
    queryFn: ({ signal }) => fetchPromotionsWithCache(api, userId, signal),
  });
}
export function useAppContent(businessId: string | undefined) {
  const { api, session } = useSession();
  const userId = session.getUserId?.() ?? 'anonymous';
  return useQuery<AppContent | null>({
    queryKey: keys.appContent(businessId),
    enabled: !!businessId,
    initialData: () => (businessId ? getCachedAppContent(userId, businessId)?.data : undefined),
    queryFn: ({ signal }) => (businessId ? fetchAppContentWithCache(api, userId, businessId, signal) : null),
  });
}
export function usePromotion(id: string) {
  const { api } = useSession();
  return useQuery({ queryKey: keys.promotion(id), queryFn: ({ signal }) => api.request<Promotion>(`/me/promotions/${encodeURIComponent(id)}`, { auth: true, signal }) });
}
export function useNotifications() {
  const { api } = useSession();
  return useQuery({ queryKey: keys.notifications, queryFn: ({ signal }) => api.request<Notifications>('/me/notifications', { auth: true, signal }) });
}
// Badges drive the tab bar dots; poll gently while the app is in the foreground.
export function useBadges() {
  const { api } = useSession();
  return useQuery({ queryKey: keys.badges, refetchInterval: 60_000, staleTime: 15_000,
    queryFn: ({ signal }) => api.request<Badges>('/me/badges', { auth: true, signal }) });
}
// Dynamic QR: the token lives ttl_seconds on the server; refresh at half-life so the code never expires on screen.
export function useCardQr(cardId: string | undefined) {
  const { api } = useSession();
  return useQuery<CardQr>({ queryKey: keys.qr(cardId ?? ''), enabled: !!cardId, staleTime: 0, gcTime: 0,
    refetchInterval: query => Math.max(5_000, ((query.state.data?.ttl_seconds ?? 60) * 1000) / 2),
    refetchIntervalInBackground: false,
    queryFn: ({ signal }) => api.request<CardQr>(`/me/cards/${encodeURIComponent(cardId ?? '')}/qr`, { auth: true, signal }) });
}

export function useWalletAvailability(options?: { enabled?: boolean }) {
  const { api } = useSession();
  return useQuery<WalletAvailability>({
    queryKey: keys.wallet,
    staleTime: 60_000,
    queryFn: ({ signal }) => api.request<WalletAvailability>('/me/wallet', { auth: true, signal }),
    enabled: options?.enabled,
  });
}

type RequestCaller = {
  request: <T>(
    path: string,
    options?: { method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'; body?: object | FormData; headers?: Record<string, string>; auth?: boolean; signal?: AbortSignal },
  ) => Promise<T>;
};

export async function uploadAvatar(api: RequestCaller, uri: string): Promise<Profile> {
  const form = new FormData();
  form.append('file', {
    uri,
    name: 'avatar.jpg',
    type: 'image/jpeg',
  } as unknown as Blob);
  return api.request<Profile>('/me/avatar', {
    method: 'POST',
    auth: true,
    body: form,
  });
}

export async function deleteAvatar(api: RequestCaller): Promise<Profile> {
  return api.request<Profile>('/me/avatar', {
    method: 'DELETE',
    auth: true,
  });
}

export async function requestWalletLink(
  api: RequestCaller,
  cardId: string,
  platform: 'apple' | 'google',
): Promise<WalletLinkResponse> {
  return api.request<WalletLinkResponse>(`/me/cards/${encodeURIComponent(cardId)}/wallet`, {
    method: 'POST',
    auth: true,
    body: { platform },
  });
}

export function useRequestWalletLink() {
  const { api } = useSession();
  return (cardId: string, platform: 'apple' | 'google') => requestWalletLink(api, cardId, platform);
}
