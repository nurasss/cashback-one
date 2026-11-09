import { getClientConfig } from '../config/client';
import type { ClientStatus, ClientStatuses } from '../../clients/keremet/statuses';
import type { Tier } from '../types/api';

// Named statuses with artwork exist only for clients that configure them (Keremet). Everyone else keeps the server's levels.
export function getClientStatuses(slug?: string): ClientStatuses | null {
  try { return getClientConfig(slug).statuses ?? null; } catch { return null; }
}

/** The highest level whose (inclusive) threshold the turnover reaches. Thresholds are sorted and never overlap. */
export function statusForSpend(levels: readonly ClientStatus[], spend: number): ClientStatus {
  const sorted = [...levels].sort((a, b) => a.threshold - b.threshold);
  let current = sorted[0]!;
  for (const level of sorted) if (spend >= level.threshold) current = level;
  return current;
}

export type StatusUnavailableReason =
  | 'unconfirmed' // the turnover period behind spend_total is not confirmed yet
  | 'no-tier' // the server returned no tier for the card
  | 'no-spend' // the server does not know the turnover (spend_total is null) — never treated as 0 / level 1
  | 'mismatch'; // the server's own levels disagree with the confirmed catalog

export type CurrentStatus =
  | { known: false; reason: StatusUnavailableReason }
  | { known: true; status: ClientStatus; spend: number; next: ClientStatus | null; remaining: number | null; progress: number; isMax: boolean };

const same = (a: number, b: string) => Number.isFinite(Number(b)) && Math.abs(a - Number(b)) < 1e-6;

/**
 * Current status from CONFIRMED server data only: `tier.spend_total` is the turnover; it is never derived from the balance or from
 * bonus transactions. Unknown or unverifiable data gives `known: false`, not a made-up level.
 */
export function resolveCurrentStatus(tier: Tier | null | undefined, catalog: ClientStatuses): CurrentStatus {
  if (!catalog.turnoverConfirmed) return { known: false, reason: 'unconfirmed' };
  if (!tier) return { known: false, reason: 'no-tier' };
  if (tier.spend_total === null || tier.spend_total === undefined || tier.spend_total === '') return { known: false, reason: 'no-spend' };
  const spend = Number(tier.spend_total);
  if (!Number.isFinite(spend)) return { known: false, reason: 'no-spend' };
  const status = statusForSpend(catalog.levels, spend);
  // The server computed its own level from its own thresholds: they must agree with the catalog, or the data is not trusted.
  const serverLevels = tier.levels ?? [];
  const levelsAgree = serverLevels.length === 0
    || (serverLevels.length === catalog.levels.length
      && catalog.levels.every(level => serverLevels.some(s => s.level === level.level && same(level.threshold, s.threshold) && same(level.percent, s.percent))));
  if (tier.level !== status.level || !levelsAgree) return { known: false, reason: 'mismatch' };
  const sorted = [...catalog.levels].sort((a, b) => a.threshold - b.threshold);
  const next = sorted[sorted.findIndex(level => level.level === status.level) + 1] ?? null;
  const progress = next ? Math.min(1, Math.max(0, spend / next.threshold)) : 1;
  return { known: true, status, spend, next, remaining: next ? Math.max(next.threshold - spend, 0) : null, progress, isMax: !next };
}

/** Condition text key + amounts for one level: "up to X", "from X to Y" or "from X" (the upper bound is exclusive: the next level starts there). */
export function statusCondition(levels: readonly ClientStatus[], level: ClientStatus): { key: 'statusUpTo' | 'statusRange' | 'fromAmount'; from: number; to: number | null } {
  const sorted = [...levels].sort((a, b) => a.threshold - b.threshold);
  const index = sorted.findIndex(item => item.level === level.level);
  const next = sorted[index + 1];
  if (index === 0 && next) return { key: 'statusUpTo', from: level.threshold, to: next.threshold };
  if (next) return { key: 'statusRange', from: level.threshold, to: next.threshold };
  return { key: 'fromAmount', from: level.threshold, to: null };
}

export function maxStatusPercent(catalog: ClientStatuses): number {
  return Math.max(...catalog.levels.map(level => level.percent));
}
