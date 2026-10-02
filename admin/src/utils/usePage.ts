import { useCallback, useState } from 'react';
import type { PageQuery } from '../api/types';

export function usePage(initialLimit = 25): [PageQuery, (offset: number) => void] {
  const [page, setPage] = useState<PageQuery>({ limit: initialLimit, offset: 0 });
  const move = useCallback((offset: number) => setPage(current => ({ ...current, offset: Math.max(0, Math.min(100_000, offset)) })), []);
  return [page, move];
}
