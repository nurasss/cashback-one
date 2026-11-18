import { useCallback, useEffect, useMemo } from 'react';
import { keepPreviousData, useInfiniteQuery, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query';
import { useAdminSession } from '../auth/provider';
import type { AdminApiClient } from './client';
import { ApiError } from './errors';
import type {
  Agent, AdminTransaction, AdminUser, AdminUserDetail, AppNotification, AppTexts, AuditItem, Business, BusinessDetail, BusinessSplashConfig, BusinessStore, Card, CardDetail, Dashboard, LoyaltyScaleResponse, LoyaltyScaleSaveRequest, LoyaltyScaleSaveResponse, LoyaltyTier, Page, PageQuery, PosKey, Promotion, PromotionKind,
} from './types';

export const privateKey = ['admin'] as const;

export function useDashboard(filters: { business_id?: string; from?: string; to?: string }, enabled = true, refreshVersion = 0) {
  const { session } = useAdminSession();
  const params = new URLSearchParams();
  if (filters.business_id) params.set('business_id', filters.business_id);
  if (filters.from) params.set('from', filters.from);
  if (filters.to) params.set('to', filters.to);
  const query = params.size ? `?${params}` : '';
  return useQuery({
    queryKey: [...privateKey, 'dashboard', filters, refreshVersion],
    enabled,
    placeholderData: keepPreviousData,
    queryFn: ({ signal }) => session.api.request<Dashboard>(`/admin/dashboard${query}`, { signal }),
  });
}

export const ALL_BUSINESSES_PAGE_LIMIT = 100;
const ALL_BUSINESSES_QUERY_KEY = [...privateKey, 'businesses', 'all'] as const;

interface InFlightNextPageEntry {
  cursorKey: string;
  promise: Promise<unknown>;
}

// Per-QueryClient in-flight guard prevents competing fetchNextPage calls when multiple
// selectors (e.g. ContentPage + BusinessPicker + open dialog) observe the same query.
const inFlightNextPageByClient = new WeakMap<QueryClient, InFlightNextPageEntry>();

export interface AllBusinessesResult {
  items: Business[];
  isPending: boolean;
  isLoadingMore: boolean;
  hasMore: boolean;
  isError: boolean;
  error: unknown;
  loadedCount: number;
  retry: () => Promise<unknown>;
}

export function useBusinesses(page: PageQuery = { limit: 25, offset: 0 }, enabled = true) {
  const { session } = useAdminSession();
  return useQuery({ queryKey: [...privateKey, 'businesses', page], enabled, queryFn: ({ signal }) => session.api.request<Page<Business>>(`/admin/businesses?limit=${page.limit}&offset=${page.offset}`, { signal }) });
}

export function useAllBusinesses(enabled = true): AllBusinessesResult {
  const { session } = useAdminSession();
  const queryClient = useQueryClient();
  const query = useInfiniteQuery({
    queryKey: ALL_BUSINESSES_QUERY_KEY,
    enabled,
    initialPageParam: 0,
    queryFn: ({ pageParam, signal }) =>
      session.api.request<Page<Business>>(
        `/admin/businesses?limit=${ALL_BUSINESSES_PAGE_LIMIT}&offset=${pageParam}`,
        { signal }
      ),
    getNextPageParam: (lastPage, allPages, lastPageParam) => {
      if (!lastPage.has_more || lastPage.items.length === 0) return undefined;
      const baseOffset = typeof lastPage.offset === 'number' && lastPage.offset >= lastPageParam
        ? lastPage.offset
        : lastPageParam;
      const nextOffset = baseOffset + lastPage.items.length;
      if (nextOffset <= lastPageParam) return undefined;

      if (allPages.length > 1) {
        const prevIds = new Set<string>();
        for (let i = 0; i < allPages.length - 1; i++) {
          for (const item of allPages[i]!.items) {
            prevIds.add(item.id);
          }
        }
        if (!lastPage.items.some(item => !prevIds.has(item.id))) {
          return undefined;
        }
      }
      return nextOffset;
    },
  });

  const { items, paginationStalled } = useMemo(() => {
    const pages = query.data?.pages ?? [];
    const seen = new Set<string>();
    const deduped: Business[] = [];
    let stalled = false;

    for (let i = 0; i < pages.length; i++) {
      const p = pages[i]!;
      let addedInPage = 0;
      for (const item of p.items) {
        if (!seen.has(item.id)) {
          seen.add(item.id);
          deduped.push(item);
          addedInPage += 1;
        }
      }
      if (p.has_more && (p.items.length === 0 || (i > 0 && addedInPage === 0))) {
        stalled = true;
      }
    }

    return { items: deduped, paginationStalled: stalled };
  }, [query.data?.pages]);

  const pages = query.data?.pages;
  const pageParams = query.data?.pageParams;
  const pagesCount = pages?.length ?? 0;
  const lastPage = pagesCount > 0 ? pages![pagesCount - 1] : undefined;
  const pageProgressKey = pagesCount > 0
    ? `${pagesCount}:${(pageParams ?? []).map(param => String(param)).join(',')}:${lastPage?.items.length ?? 0}:${String(Boolean(lastPage?.has_more))}`
    : '';

  const hasFetchError = query.isError || query.isFetchNextPageError;
  const hasMore = Boolean(query.hasNextPage) || paginationStalled;
  const isLoadingMore =
    enabled &&
    !query.isPending &&
    !hasFetchError &&
    !paginationStalled &&
    (query.isFetchingNextPage || Boolean(query.hasNextPage));

  const {
    isPending,
    isFetching,
    isFetchingNextPage,
    hasNextPage,
    dataUpdatedAt,
    fetchNextPage,
    refetch,
  } = query;

  useEffect(() => {
    if (!enabled) return;
    if (!hasNextPage || hasFetchError || isPending || isFetching || isFetchingNextPage || paginationStalled) {
      return;
    }
    const cachedQuery = queryClient.getQueryCache().find({ queryKey: ALL_BUSINESSES_QUERY_KEY });
    if (cachedQuery && cachedQuery.state.fetchStatus !== 'idle') {
      return;
    }
    if (inFlightNextPageByClient.get(queryClient)?.cursorKey === pageProgressKey) {
      return;
    }
    const promise = fetchNextPage({ cancelRefetch: false }).finally(() => {
      if (inFlightNextPageByClient.get(queryClient)?.promise === promise) {
        inFlightNextPageByClient.delete(queryClient);
      }
    });
    inFlightNextPageByClient.set(queryClient, { cursorKey: pageProgressKey, promise });
  }, [
    enabled,
    hasNextPage,
    hasFetchError,
    isPending,
    isFetching,
    isFetchingNextPage,
    paginationStalled,
    pageProgressKey,
    dataUpdatedAt,
    queryClient,
    fetchNextPage,
  ]);

  const error = query.error ?? (paginationStalled ? new ApiError('INVALID_RESPONSE', 502) : null);
  const isError = hasFetchError || paginationStalled;

  const retry = useCallback(async () => {
    if (query.data && hasNextPage && !paginationStalled) {
      return fetchNextPage({ cancelRefetch: false });
    }
    return refetch();
  }, [query.data, hasNextPage, paginationStalled, fetchNextPage, refetch]);

  return {
    items,
    isPending: enabled && isPending,
    isLoadingMore,
    hasMore,
    isError,
    error,
    loadedCount: items.length,
    retry,
  };
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

export function useCards(business_id: string | undefined, page: PageQuery, enabled = true) {
  const { session } = useAdminSession();
  const query = new URLSearchParams({ limit: String(page.limit), offset: String(page.offset) });
  if (business_id) query.set('business_id', business_id);
  return useQuery({
    queryKey: [...privateKey, 'cards', business_id, page],
    enabled,
    queryFn: ({ signal }) => session.api.request<Page<Card>>(`/admin/cards?${query}`, { signal }),
  });
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

export function useCardTransactions(cardId: string, page: PageQuery, enabled = true) {
  const { session } = useAdminSession();
  const query = new URLSearchParams({ limit: String(page.limit), offset: String(page.offset) });
  return useQuery({
    queryKey: [...privateKey, 'card-transactions', cardId, page],
    enabled: Boolean(cardId) && enabled,
    queryFn: ({ signal }) =>
      session.api.request<Page<AdminTransaction>>(
        `/admin/cards/${encodeURIComponent(cardId)}/transactions?${query}`,
        { signal },
      ),
  });
}

export function useUsers(business_id: string | undefined, page: PageQuery, enabled = true) {
  const { session } = useAdminSession();
  const query = new URLSearchParams({ limit: String(page.limit), offset: String(page.offset) });
  if (business_id) query.set('business_id', business_id);
  return useQuery({
    queryKey: [...privateKey, 'users', business_id, page],
    enabled,
    queryFn: ({ signal }) => session.api.request<Page<AdminUser>>(`/admin/users?${query}`, { signal }),
  });
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

export function useUserTransactions(
  userId: string,
  business_id: string | undefined,
  page: PageQuery,
  enabled = true,
) {
  const { session } = useAdminSession();
  const query = new URLSearchParams({ limit: String(page.limit), offset: String(page.offset) });
  if (business_id) query.set('business_id', business_id);
  return useQuery({
    queryKey: [...privateKey, 'user-transactions', userId, business_id, page],
    enabled: Boolean(userId) && enabled,
    queryFn: ({ signal }) =>
      session.api.request<Page<AdminTransaction>>(
        `/admin/users/${encodeURIComponent(userId)}/transactions?${query}`,
        { signal },
      ),
  });
}

export function useAudit(page: PageQuery) {
  const { session } = useAdminSession();
  return useQuery({ queryKey: [...privateKey, 'audit', page], queryFn: ({ signal }) => session.api.request<Page<AuditItem>>(`/admin/audit?limit=${page.limit}&offset=${page.offset}`, { signal }) });
}

export function useAgent(id: string) {
  const { session } = useAdminSession();
  return useQuery({ queryKey: [...privateKey, 'agent', id], queryFn: ({ signal }) => session.api.request<Agent>(`/admin/agents/${encodeURIComponent(id)}`, { signal }) });
}

export function usePromotions(business_id: string | undefined, page: PageQuery, kind?: PromotionKind) {
  const { session } = useAdminSession();
  const query = new URLSearchParams({ limit: String(page.limit), offset: String(page.offset) });
  if (business_id) query.set('business_id', business_id);
  if (kind) query.set('kind', kind);
  return useQuery({ queryKey: [...privateKey, 'promotions', business_id, page, kind], queryFn: ({ signal }) => session.api.request<Page<Promotion>>(`/admin/promotions?${query}`, { signal }) });
}

export function useAppNotifications(business_id: string | undefined, page: PageQuery) {
  const { session } = useAdminSession();
  const query = new URLSearchParams({ limit: String(page.limit), offset: String(page.offset) });
  if (business_id) query.set('business_id', business_id);
  return useQuery({ queryKey: [...privateKey, 'app-notifications', business_id, page], queryFn: ({ signal }) => session.api.request<Page<AppNotification>>(`/admin/notifications?${query}`, { signal }) });
}

export function useBusinessStores(businessId: string | undefined, enabled = true) {
  const { session } = useAdminSession();
  return useQuery({
    queryKey: [...privateKey, 'business-stores', businessId],
    enabled: Boolean(businessId) && enabled,
    queryFn: ({ signal }) =>
      session.api.request<BusinessStore[]>(
        `/admin/businesses/${encodeURIComponent(businessId!)}/stores`,
        { signal }
      ),
  });
}
export function useBusinessAppTexts(businessId: string | undefined, enabled = true) {
  const { session } = useAdminSession();
  return useQuery({
    queryKey: [...privateKey, 'business-app-texts', businessId],
    enabled: Boolean(businessId) && enabled,
    queryFn: ({ signal }) =>
      session.api.request<AppTexts>(
        `/admin/businesses/${encodeURIComponent(businessId!)}/app-texts`,
        { signal }
      ),
  });
}

export function usePosKeys(businessId: string | undefined, enabled = true) {
  const { session } = useAdminSession();
  return useQuery({
    queryKey: [...privateKey, 'pos-keys', businessId],
    enabled: Boolean(businessId) && enabled,
    queryFn: ({ signal }) =>
      session.api.request<PosKey[]>(
        `/admin/businesses/${encodeURIComponent(businessId!)}/pos-keys`,
        { signal }
      ),
  });
}

export function useBusinessSplashConfig(businessId: string | undefined, enabled = true) {
  const { session } = useAdminSession();
  return useQuery({
    queryKey: [...privateKey, 'business-splash', businessId],
    enabled: Boolean(businessId) && enabled,
    queryFn: ({ signal }) =>
      session.api.request<BusinessSplashConfig>(
        `/admin/businesses/${encodeURIComponent(businessId!)}/splash`,
        { signal }
      ),
  });
}

export function useLoyaltyTiers(businessId: string | undefined, enabled = true) {
  const { session } = useAdminSession();
  return useQuery({
    queryKey: [...privateKey, 'loyalty-tiers', businessId],
    enabled: Boolean(businessId) && enabled,
    queryFn: ({ signal }) =>
      session.api.request<LoyaltyTier[]>(
        `/admin/businesses/${encodeURIComponent(businessId!)}/loyalty-tiers`,
        { signal }
      ),
  });
}

export function getLoyaltyScale(api: AdminApiClient, businessId: string, signal?: AbortSignal) {
  return api.request<LoyaltyScaleResponse>(
    `/admin/businesses/${encodeURIComponent(businessId)}/loyalty-tiers/scale`,
    { signal }
  );
}

export function saveLoyaltyScale(
  api: AdminApiClient,
  businessId: string,
  payload: LoyaltyScaleSaveRequest,
  signal?: AbortSignal
) {
  return api.request<LoyaltyScaleSaveResponse>(
    `/admin/businesses/${encodeURIComponent(businessId)}/loyalty-tiers/scale`,
    { method: 'PUT', body: payload, signal }
  );
}
