import { useQuery } from '@tanstack/react-query';
import { useSession } from '../auth/provider';
import type { Badges, CardQr, Notifications, Profile, Promotion, Promotions } from '../types/api';

export const appKey = ['app'] as const;
export const keys = {
  profile: [...appKey, 'profile'] as const,
  promotions: [...appKey, 'promotions'] as const,
  promotion: (id: string) => [...appKey, 'promotion', id] as const,
  notifications: [...appKey, 'notifications'] as const,
  badges: [...appKey, 'badges'] as const,
  qr: (cardId: string) => [...appKey, 'qr', cardId] as const,
};

export function useProfile() {
  const { api } = useSession();
  return useQuery({ queryKey: keys.profile, queryFn: ({ signal }) => api.request<Profile>('/me/profile', { auth: true, signal }) });
}
export function usePromotions() {
  const { api } = useSession();
  return useQuery({ queryKey: keys.promotions, queryFn: ({ signal }) => api.request<Promotions>('/me/promotions', { auth: true, signal }) });
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
