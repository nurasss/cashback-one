import { useCallback, useEffect, useMemo, useState } from 'react';
import type { PageQuery } from '../api/types';

export function usePage(initialLimit = 25): [PageQuery, (offset: number) => void] {
  const [page, setPage] = useState<PageQuery>({ limit: initialLimit, offset: 0 });
  const move = useCallback((offset: number) => setPage(current => ({ ...current, offset: Math.max(0, Math.min(100_000, offset)) })), []);
  return [page, move];
}

export function useClientPagination<T>(items: readonly T[], resetKey?: string, initialLimit = 25) {
  const [page, setPage] = usePage(initialLimit);

  useEffect(() => {
    setPage(0);
  }, [resetKey, setPage]);

  const total = items.length;
  const maxOffset = total === 0 ? 0 : Math.floor((total - 1) / page.limit) * page.limit;

  useEffect(() => {
    if (page.offset > maxOffset) {
      setPage(maxOffset);
    }
  }, [page.offset, maxOffset, setPage]);

  const effectiveOffset = Math.min(page.offset, maxOffset);
  const pagedItems = useMemo(
    () => items.slice(effectiveOffset, effectiveOffset + page.limit),
    [items, effectiveOffset, page.limit]
  );

  return {
    page: {
      limit: page.limit,
      offset: effectiveOffset,
      has_more: effectiveOffset + page.limit < total,
      total,
    },
    setPage,
    pagedItems,
  };
}
