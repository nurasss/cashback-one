export type HistoryPeriod =
  | 'all'
  | '7d'
  | '30d'
  | '90d'
  | { from: string; to: string }; // ISO YYYY-MM-DD

export function historyRange(
  period: HistoryPeriod,
  now = new Date()
): { from?: string; to?: string } {
  if (period === 'all') {
    return {};
  }

  if (typeof period === 'object') {
    const [fy = 0, fm = 1, fd = 1] = period.from.split('-').map(Number);
    const [ty = 0, tm = 1, td = 1] = period.to.split('-').map(Number);
    const fromDate = new Date(fy, fm - 1, fd, 0, 0, 0, 0);
    const toDate = new Date(ty, tm - 1, td + 1, 0, 0, 0, 0);
    return {
      from: fromDate.toISOString(),
      to: toDate.toISOString(),
    };
  }

  const daysBack = period === '7d' ? 6 : period === '30d' ? 29 : 89;
  const fromDate = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate() - daysBack,
    0,
    0,
    0,
    0
  );

  return {
    from: fromDate.toISOString(),
  };
}
