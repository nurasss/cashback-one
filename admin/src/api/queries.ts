import { useQuery } from '@tanstack/react-query';
import { useAdminSession } from '../auth/provider';
import type {
  Agent, AdminUser, AdminUserDetail, AuditItem, Business, BusinessDetail, Card, CardDetail, Dashboard, Page, PageQuery,
} from './types';

export const privateKey = ['admin'] as const;

export function useDashboard(filters: { business_id?: string; from?: string; to?: string }, enabled = true) {
  const { session } = useAdminSession();
  const params = new URLSearchParams();
  if (filters.business_id) params.set('business_id', filters.business_id);
  if (filters.from) params.set('from', filters.from);
  if (filters.to) params.set('to', filters.to);
  const query = params.size ? `?${params}` : '';
  return useQuery({ queryKey: [...privateKey, 'dashboard', filters], enabled, queryFn: ({ signal }) => session.api.request<Dashboard>(`/admin/dashboard${query}`, { signal }) });
}

export function useBusinesses(page: PageQuery = { limit: 25, offset: 0 }, enabled = true) {
  const { session } = useAdminSession();
  return useQuery({ queryKey: [...privateKey, 'businesses', page], enabled, queryFn: ({ signal }) => session.api.request<Page<Business>>(`/admin/businesses?limit=${page.limit}&offset=${page.offset}`, { signal }) });
}

export function useBusiness(id: string) {
  const { session } = useAdminSession();
  return useQuery({ queryKey: [...privateKey, 'business', id], queryFn: ({ signal }) => session.api.request<BusinessDetail>(`/admin/businesses/${encodeURIComponent(id)}`, { signal }) });
}

export function useAgents(business_id: string | undefined, page: PageQuery) {
  const { session } = useAdminSession();
  const query = new URLSearchParams({ limit: String(page.limit), offset: String(page.offset) });
  if (business_id) query.set('business_id', business_id);
  return useQuery({ queryKey: [...privateKey, 'agents', business_id, page], queryFn: ({ signal }) => session.api.request<Page<Agent>>(`/admin/agents?${query}`, { signal }) });
}

export function useCardSearch(filters: { barcode?: string; phone?: string; business_id?: string }, page: PageQuery, enabled: boolean) {
  const { session } = useAdminSession();
  return useQuery({
    queryKey: [...privateKey, 'card-search', filters, page], enabled,
    queryFn: ({ signal }) => session.api.request<Page<Card>>(`/admin/cards/search?limit=${page.limit}&offset=${page.offset}`, { method: 'POST', body: filters, signal }),
  });
}

export function useCard(id: string) {
  const { session } = useAdminSession();
  return useQuery({ queryKey: [...privateKey, 'card', id], queryFn: ({ signal }) => session.api.request<CardDetail>(`/admin/cards/${encodeURIComponent(id)}`, { signal }) });
}

export function useUserSearch(filters: { phone: string; business_id?: string }, page: PageQuery, enabled: boolean) {
  const { session } = useAdminSession();
  return useQuery({
    queryKey: [...privateKey, 'user-search', filters, page], enabled,
    queryFn: ({ signal }) => session.api.request<Page<AdminUser>>(`/admin/users/search?limit=${page.limit}&offset=${page.offset}`, { method: 'POST', body: filters, signal }),
  });
}

export function useUser(id: string, business_id: string | undefined, page: PageQuery) {
  const { session } = useAdminSession();
  const query = new URLSearchParams({ limit: String(page.limit), offset: String(page.offset) });
  if (business_id) query.set('business_id', business_id);
  return useQuery({ queryKey: [...privateKey, 'user', id, business_id, page], queryFn: ({ signal }) => session.api.request<AdminUserDetail>(`/admin/users/${encodeURIComponent(id)}?${query}`, { signal }) });
}

export function useAudit(page: PageQuery) {
  const { session } = useAdminSession();
  return useQuery({ queryKey: [...privateKey, 'audit', page], queryFn: ({ signal }) => session.api.request<Page<AuditItem>>(`/admin/audit?limit=${page.limit}&offset=${page.offset}`, { signal }) });
}

export function useAgent(id: string) {
  const { session } = useAdminSession();
  return useQuery({ queryKey: [...privateKey, 'agent', id], queryFn: ({ signal }) => session.api.request<Agent>(`/admin/agents/${encodeURIComponent(id)}`, { signal }) });
}
