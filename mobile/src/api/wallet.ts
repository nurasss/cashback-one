import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { useSession } from '../auth/provider';
import type { Card, HistoryPage } from '../types/api';
export const walletKey = ['wallet'] as const;
export function useCards() {
  const { api } = useSession();
  return useQuery({ queryKey: [...walletKey, 'cards'], queryFn: ({ signal }) => api.request<Card[]>('/me/cards', { auth: true, signal }) });
}
export function useCard(id: string) {
  const { api } = useSession();
  return useQuery({ queryKey: [...walletKey, 'card', id], queryFn: ({ signal }) => api.request<Card>(`/me/cards/${encodeURIComponent(id)}`, { auth: true, signal }) });
}
export function useHistory(id: string) {
  const { api } = useSession();
  return useInfiniteQuery({ queryKey: [...walletKey, 'history', id], initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => api.request<HistoryPage>(`/me/cards/${encodeURIComponent(id)}/transactions?limit=20${pageParam ? '&cursor=' + encodeURIComponent(pageParam) : ''}`, { auth: true, signal }),
    getNextPageParam: page => page.has_more && page.next_cursor ? page.next_cursor : undefined });
}
