import { getClientConfig } from '../config/client';
import type { ClientStatus, ClientStatuses } from '../../clients/keremet/statuses';
import type { AppContent, Card, Tier } from '../types/api';
import type { Key } from '../i18n';
import { amountText } from '../utils/format';

export interface StatusTier {
  id: string;
  level: number;
  priority: number;
  key?: string;
  name: string;
  name_ru: string;
  name_kk: string;
  description: string | null;
  description_ru: string | null;
  description_kk: string | null;
  image_url: string | null;
  localImage?: unknown;
  /** Historical, optional; never shown and never used for progress (lifetime turnover). */
  turnover_period_months?: number;
  min_turnover: string;
  max_turnover: string | null;
  percent: string;
  threshold?: number;
}

export interface StatusCatalog {
  version: number;
  businessId?: string;
  tiers: StatusTier[];
  isServer: boolean;
  maxPercent: string;
}

// Strict Decimal format: optional minus, digits, optional dot with digits.
export const DECIMAL_RE = /^-?\d+(\.\d+)?$/;

export function parseValidDecimal(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  if (!DECIMAL_RE.test(trimmed)) return null;
  return trimmed;
}

/** Exact Decimal subtraction (aStr - bStr) using BigInt cents to avoid float precision loss */
export function decimalSubtract(aStr: string, bStr: string): string {
  const a = parseValidDecimal(aStr);
  const b = parseValidDecimal(bStr);
  if (!a || !b) return '0';
  const [aInt = '0', aFrac = ''] = a.split('.');
  const [bInt = '0', bFrac = ''] = b.split('.');
  const maxFrac = Math.max(aFrac.length, bFrac.length);
  const aPadded = aInt + aFrac.padEnd(maxFrac, '0');
  const bPadded = bInt + bFrac.padEnd(maxFrac, '0');
  try {
    const diff = BigInt(aPadded) - BigInt(bPadded);
    if (diff <= 0n) return '0';
    const diffStr = diff.toString().padStart(maxFrac + 1, '0');
    if (maxFrac === 0) return diffStr;
    const whole = diffStr.slice(0, -maxFrac) || '0';
    const frac = diffStr.slice(-maxFrac).replace(/0+$/, '');
    return frac ? `${whole}.${frac}` : whole;
  } catch {
    const numDiff = Math.max(0, Number(a) - Number(b));
    return String(numDiff);
  }
}

// Named statuses with artwork exist only for clients that configure them (Keremet). Everyone else keeps the server's levels.
export function getClientStatuses(slug?: string): ClientStatuses | null {
  try {
    return getClientConfig(slug).statuses ?? null;
  } catch {
    return null;
  }
}

/**
 * Resolves unified status catalog from AppContent:
 *  - if loyalty_tiers is defined on backend: uses it (empty array [] means an explicit empty scale, NEVER fallback to Keremet);
 *  - if loyalty_tiers is undefined (legacy backend): falls back to client's legacy configured statuses if available.
 */
export function resolveCatalog(
  appContent?: AppContent | null,
  clientSlug?: string,
): StatusCatalog | null {
  // 1. Backend loyalty_tiers
  if (appContent && appContent.loyalty_tiers !== undefined) {
    const rawTiers = appContent.loyalty_tiers;
    if (rawTiers.length === 0) {
      return {
        version: appContent.loyalty_tiers_version ?? 1,
        businessId: appContent.business_id,
        tiers: [],
        isServer: true,
        maxPercent: '0',
      };
    }

    const sorted = [...rawTiers].sort((a, b) => a.level - b.level || a.priority - b.priority);
    const maxVal = sorted.length > 0
      ? Math.max(...sorted.map(t => Number(t.percent) || 0))
      : 0;

    const tiers: StatusTier[] = sorted.map(t => ({
      id: t.id,
      level: t.level,
      priority: t.priority,
      name: t.name_ru,
      name_ru: t.name_ru,
      name_kk: t.name_kk || t.name_ru,
      description: t.description_ru,
      description_ru: t.description_ru,
      description_kk: t.description_kk,
      image_url: t.image_url,
      turnover_period_months: t.turnover_period_months,
      min_turnover: t.min_turnover,
      max_turnover: t.max_turnover,
      percent: t.percent,
    }));

    return {
      version: appContent.loyalty_tiers_version ?? 1,
      businessId: appContent.business_id,
      tiers,
      isServer: true,
      maxPercent: String(maxVal),
    };
  }

  // 2. Fallback for older backend without loyalty_tiers field
  const legacy = getClientStatuses(clientSlug);
  if (legacy && legacy.levels.length > 0) {
    let clientBusinessId: string | undefined;
    try {
      clientBusinessId = getClientConfig(clientSlug).business_id ?? undefined;
    } catch {
      clientBusinessId = undefined;
    }
    const sorted = [...legacy.levels].sort((a, b) => a.level - b.level);
    const tiers: StatusTier[] = sorted.map((l, idx) => {
      const next = sorted[idx + 1];
      return {
        id: `legacy-${l.key}`,
        level: l.level,
        priority: l.level,
        key: l.key,
        name: l.name,
        name_ru: l.name,
        name_kk: l.name,
        description: null,
        description_ru: null,
        description_kk: null,
        image_url: null,
        localImage: l.image,
        min_turnover: String(l.threshold),
        max_turnover: next ? String(next.threshold) : null,
        percent: String(l.percent),
        threshold: l.threshold,
      };
    });

    return {
      version: 1,
      businessId: clientBusinessId,
      tiers,
      isServer: false,
      maxPercent: String(Math.max(...legacy.levels.map(l => l.percent))),
    };
  }

  return null;
}

/** The highest level whose (inclusive) threshold the turnover reaches. Thresholds are sorted and never overlap. */
export function statusForSpend(levels: readonly ClientStatus[], spend: number): ClientStatus {
  const sorted = [...levels].sort((a, b) => a.threshold - b.threshold);
  let current = sorted[0]!;
  for (const level of sorted) if (spend >= level.threshold) current = level;
  return current;
}

export type StatusUnavailableReason =
  | 'unconfirmed'
  | 'stale'
  | 'no_match'
  | 'no-tier'
  | 'no-spend'
  | 'mismatch'
  | 'version-mismatch';

export type CurrentStatus =
  | { known: false; reason: StatusUnavailableReason }
  | {
      known: true;
      status: StatusTier;
      percent: string;
      spend: number;
      spendDecimal?: string;
      next: StatusTier | null;
      remaining: number | null;
      remainingDecimal?: string | null;
      progress: number | null;
      isMax: boolean;
    };

const same = (a: number, b: string) => Number.isFinite(Number(b)) && Math.abs(a - Number(b)) < 1e-6;

function resolveLegacyStatus(tier: Tier | null | undefined, catalog: ClientStatuses): CurrentStatus {
  if (!catalog.turnoverConfirmed) return { known: false, reason: 'unconfirmed' };
  if (!tier) return { known: false, reason: 'no-tier' };
  if (tier.spend_total === null || tier.spend_total === undefined || tier.spend_total === '') return { known: false, reason: 'no-spend' };
  const spend = Number(tier.spend_total);
  if (!Number.isFinite(spend) || spend < 0) return { known: false, reason: 'no-spend' };
  const status = statusForSpend(catalog.levels, spend);
  const serverLevels = tier.levels ?? [];
  const levelsAgree = serverLevels.length === 0
    || (serverLevels.length === catalog.levels.length
      && catalog.levels.every(level => serverLevels.some(s => s.level === level.level && same(level.threshold, s.threshold) && same(level.percent, s.percent))));
  if (tier.level !== status.level || !levelsAgree) return { known: false, reason: 'mismatch' };
  const sorted = [...catalog.levels].sort((a, b) => a.threshold - b.threshold);
  const next = sorted[sorted.findIndex(level => level.level === status.level) + 1] ?? null;
  const progress = next ? Math.min(1, Math.max(0, spend / next.threshold)) : 1;

  const legacyTier: StatusTier = {
    id: `legacy-${status.key}`,
    level: status.level,
    priority: status.level,
    key: status.key,
    name: status.name,
    name_ru: status.name,
    name_kk: status.name,
    description: null,
    description_ru: null,
    description_kk: null,
    image_url: null,
    localImage: status.image,
    min_turnover: String(status.threshold),
    max_turnover: next ? String(next.threshold) : null,
    percent: String(status.percent),
    threshold: status.threshold,
  };

  const nextLegacyTier: StatusTier | null = next ? {
    id: `legacy-${next.key}`,
    level: next.level,
    priority: next.level,
    key: next.key,
    name: next.name,
    name_ru: next.name,
    name_kk: next.name,
    description: null,
    description_ru: null,
    description_kk: null,
    image_url: null,
    localImage: next.image,
    min_turnover: String(next.threshold),
    max_turnover: null,
    percent: String(next.percent),
    threshold: next.threshold,
  } : null;

  return {
    known: true,
    status: legacyTier,
    percent: String(status.percent),
    spend,
    next: nextLegacyTier,
    remaining: next ? Math.max(next.threshold - spend, 0) : null,
    progress,
    isMax: !next,
  };
}

/**
 * Resolves current status of card from confirmed server data:
 *  - Checks card.loyalty_status: known=true, tier_id exists in catalog, program_version matches;
 *  - Validates turnover_amount and percent as required non-negative decimals (never falls back to catalog tier percent);
 *  - Never derives level or percent from balance, single spend_total or legacy tier when unconfirmed;
 *  - Uses lifetime turnover for progress to next tier.
 */
export function resolveCurrentStatus(
  cardOrTier: Card | Tier | null | undefined,
  catalog?: StatusCatalog | ClientStatuses | null,
  ...rest: [(AppContent | null | undefined)?]
): CurrentStatus {
  if (!cardOrTier) return { known: false, reason: 'no-tier' };

  // If passed directly legacy ClientStatuses catalog:
  if (catalog && 'turnoverConfirmed' in catalog) {
    const tier = 'spend_total' in cardOrTier ? cardOrTier : (cardOrTier as Card).tier;
    return resolveLegacyStatus(tier, catalog);
  }

  // If cardOrTier is only Tier (legacy test caller) without Card wrapper:
  if (!('barcode' in cardOrTier)) {
    const legacyCat = getClientStatuses();
    return legacyCat ? resolveLegacyStatus(cardOrTier as Tier, legacyCat) : { known: false, reason: 'no-tier' };
  }

  const card = cardOrTier as Card;
  const cat = catalog as StatusCatalog | null | undefined;
  if (!cat || cat.tiers.length === 0) {
    return { known: false, reason: 'no-tier' };
  }

  // 1. New secure contract: card.loyalty_status
  const ls = card.loyalty_status;
  if (ls) {
    if (ls.known !== true) {
      const r = ls.reason;
      const reason: StatusUnavailableReason = r === 'stale' || r === 'no_match' ? r : 'unconfirmed';
      return { known: false, reason };
    }
    // Business match check: both must be confirmed, missing id is NOT a match!
    const appContent = rest[0];
    const targetBusinessId = appContent?.business_id ?? ('businessId' in cat ? cat.businessId : undefined);
    if (!targetBusinessId || !card.business?.id || card.business.id !== targetBusinessId) {
      return { known: false, reason: 'mismatch' };
    }
    // Version match check: both must be valid numbers and match
    if (typeof cat.version !== 'number' || typeof ls.program_version !== 'number' || ls.program_version !== cat.version) {
      return { known: false, reason: 'version-mismatch' };
    }
    // Find tier in catalog by tier_id (or level for legacy)
    if (!ls.tier_id) {
      return { known: false, reason: 'mismatch' };
    }
    const currentTier = cat.tiers.find(t => t.id === ls.tier_id)
      ?? (cat.isServer ? null : cat.tiers.find(t => t.level === ls.level));
    if (!currentTier) {
      return { known: false, reason: 'mismatch' };
    }

    // Turnover amount validation: missing/null/undefined is no-spend; empty/non-decimal/negative is unconfirmed.
    if (ls.turnover_amount === null || ls.turnover_amount === undefined) {
      return { known: false, reason: 'no-spend' };
    }
    const validatedTurnover = parseValidDecimal(ls.turnover_amount);
    if (validatedTurnover === null || validatedTurnover.startsWith('-')) {
      return { known: false, reason: 'unconfirmed' };
    }

    // Confirmed percent must come strictly from server loyalty_status.percent (never substituted from catalog tier).
    if (ls.percent === undefined || ls.percent === null) {
      return { known: false, reason: 'unconfirmed' };
    }
    const validatedPercent = parseValidDecimal(ls.percent);
    if (validatedPercent === null || validatedPercent.startsWith('-')) {
      return { known: false, reason: 'unconfirmed' };
    }
    const resolvedPercent = validatedPercent;

    const turnoverAmount = Number(validatedTurnover);
    const sorted = [...cat.tiers].sort((a, b) => a.level - b.level || a.priority - b.priority);
    const currentIndex = sorted.findIndex(t => t.id === currentTier.id);
    const nextTier = sorted[currentIndex + 1] ?? null;

    if (!nextTier) {
      return {
        known: true,
        status: currentTier,
        percent: resolvedPercent,
        spend: turnoverAmount,
        spendDecimal: validatedTurnover,
        next: null,
        remaining: null,
        remainingDecimal: null,
        progress: 1,
        isMax: true,
      };
    }

    // Lifetime turnover: progress to the next level never depends on historical periods.
    const nextThresholdDecimal = nextTier.min_turnover;
    const nextThreshold = Number(nextThresholdDecimal);
    const remainingDecimal = decimalSubtract(nextThresholdDecimal, validatedTurnover);
    const remaining = Number(remainingDecimal);
    const progress = Number.isFinite(nextThreshold) && nextThreshold > 0
      ? Math.min(1, Math.max(0, turnoverAmount / nextThreshold))
      : 0;
    return {
      known: true,
      status: currentTier,
      percent: resolvedPercent,
      spend: turnoverAmount,
      spendDecimal: validatedTurnover,
      next: nextTier,
      remaining,
      remainingDecimal,
      progress,
      isMax: false,
    };
  }

  // 2. Legacy fallback if card has no loyalty_status
  if (!cat.isServer) {
    const legacyCatalog = getClientStatuses();
    if (legacyCatalog) {
      return resolveLegacyStatus(card.tier, legacyCatalog);
    }
  }

  return { known: false, reason: 'unconfirmed' };
}

export type StatusDisplay =
  | { kind: 'confirmed'; current: Extract<CurrentStatus, { known: true }> }
  | { kind: 'minimum'; status: StatusTier; percent: string }
  | { kind: 'unavailable'; reason: StatusUnavailableReason };

const ELIGIBLE_UNCONFIRMED_REASONS = new Set(['unconfirmed', 'turnover_unknown']);

/** Selects the minimum tier by catalog order (level, then priority) and validates its percent (>= 0, incl. 0%). */
export function resolveMinimumCatalogTier(
  catalog: StatusCatalog | ClientStatuses | null | undefined,
): { status: StatusTier; percent: string } | null {
  if (!catalog) return null;

  if ('levels' in catalog) {
    if (catalog.levels.length === 0) return null;
    const sorted = [...catalog.levels].sort((a, b) => a.level - b.level);
    const min = sorted[0];
    if (!min) return null;
    const validatedPercent = parseValidDecimal(String(min.percent));
    if (validatedPercent === null || validatedPercent.startsWith('-')) return null;
    if (!min.name?.trim()) return null;
    return {
      status: {
        id: `legacy-${min.key}`,
        level: min.level,
        priority: min.level,
        key: min.key,
        name: min.name,
        name_ru: min.name,
        name_kk: min.name,
        description: null,
        description_ru: null,
        description_kk: null,
        image_url: null,
        localImage: min.image,
        min_turnover: String(min.threshold),
        max_turnover: null,
        percent: validatedPercent,
        threshold: min.threshold,
      },
      percent: validatedPercent,
    };
  }

  if (catalog.tiers.length === 0) return null;
  const sorted = [...catalog.tiers].sort((a, b) => a.level - b.level || a.priority - b.priority);
  const minTier = sorted[0];
  if (!minTier) return null;
  const validatedPercent = parseValidDecimal(minTier.percent);
  if (validatedPercent === null || validatedPercent.startsWith('-')) return null;
  const hasName = Boolean((minTier.name_ru || minTier.name_kk || minTier.name)?.trim());
  if (!hasName) return null;
  return { status: minTier, percent: validatedPercent };
}

/**
 * Display resolution for both Home and Status screens:
 *  1. Preserves priority of fully confirmed personal status (`known: true` with server percent).
 *  2. If the user has a card and personal data is missing/unconfirmed (without bypassing business, version,
 *     `stale`, `no_match`, tier mismatch, or corrupted/negative field guards), returns the catalog's minimum
 *     tier (`level`, then `priority`) and its validated percent without setting `known: true` or faking 0 turnover.
 */
export function resolveStatusDisplay(
  card: Card | null | undefined,
  catalog: StatusCatalog | ClientStatuses | null | undefined,
  appContent?: AppContent | null,
): StatusDisplay {
  const current = resolveCurrentStatus(card, catalog, appContent);
  if (current.known) {
    return { kind: 'confirmed', current };
  }
  if (!card || !catalog) {
    return { kind: 'unavailable', reason: current.reason };
  }
  if (
    current.reason === 'no-tier'
    || current.reason === 'stale'
    || current.reason === 'no_match'
    || current.reason === 'mismatch'
    || current.reason === 'version-mismatch'
  ) {
    return { kind: 'unavailable', reason: current.reason };
  }

  if ('tiers' in catalog) {
    const targetBusinessId = catalog.isServer
      ? (appContent?.business_id ?? catalog.businessId)
      : catalog.businessId;
    if (catalog.isServer) {
      if (!targetBusinessId || !card.business?.id || card.business.id !== targetBusinessId) {
        return { kind: 'unavailable', reason: 'mismatch' };
      }
    } else if (targetBusinessId && (!card.business?.id || card.business.id !== targetBusinessId)) {
      return { kind: 'unavailable', reason: 'mismatch' };
    }
  }

  const ls = card.loyalty_status;
  if (ls) {
    if (ls.known !== true) {
      const reason = typeof ls.reason === 'string' ? ls.reason.trim() : '';
      if (reason && !ELIGIBLE_UNCONFIRMED_REASONS.has(reason)) {
        return { kind: 'unavailable', reason: current.reason };
      }
      if (
        typeof ls.program_version === 'number'
        && 'version' in catalog
        && typeof catalog.version === 'number'
        && ls.program_version !== catalog.version
      ) {
        return { kind: 'unavailable', reason: 'version-mismatch' };
      }
    } else {
      if (ls.turnover_amount !== null && ls.turnover_amount !== undefined) {
        const vt = parseValidDecimal(ls.turnover_amount);
        if (vt === null || vt.startsWith('-')) {
          return { kind: 'unavailable', reason: 'unconfirmed' };
        }
      }
      if (ls.percent !== null && ls.percent !== undefined) {
        const vp = parseValidDecimal(ls.percent);
        if (vp === null || vp.startsWith('-')) {
          return { kind: 'unavailable', reason: 'unconfirmed' };
        }
      }
    }
  }

  const min = resolveMinimumCatalogTier(catalog);
  if (!min) {
    return { kind: 'unavailable', reason: current.reason };
  }
  return { kind: 'minimum', status: min.status, percent: min.percent };
}

/** Condition text for a tier */
export function getTierCondition(
  tier: StatusTier,
  t: (key: Key, params?: Record<string, string | number>) => string,
): string {
  const min = Number(tier.min_turnover);
  const max = tier.max_turnover !== null ? Number(tier.max_turnover) : null;
  if (min === 0 && max !== null) {
    return t('statusUpTo', { amount: amountText(String(max)) });
  }
  if (max !== null) {
    return t('statusRange', { from: amountText(String(min)), to: amountText(String(max)) });
  }
  return t('fromAmount', { amount: amountText(String(min)) });
}

/** Lead text. Loyalty statuses always use lifetime turnover (no months or rolling windows). */
export function getCatalogLead(
  catalog: StatusCatalog | ClientStatuses | null | undefined,
  t: (key: Key, params?: Record<string, string | number>) => string,
): string {
  if (!catalog) return t('howToLead');
  return t('statusLeadLifetime');
}

/** Legacy condition text helper for ClientStatuses backward compatibility */
export function statusCondition(
  levels: readonly ClientStatus[],
  level: ClientStatus,
): { key: 'statusUpTo' | 'statusRange' | 'fromAmount'; from: number; to: number | null } {
  const sorted = [...levels].sort((a, b) => a.threshold - b.threshold);
  const index = sorted.findIndex(item => item.level === level.level);
  const next = sorted[index + 1];
  if (index === 0 && next) return { key: 'statusUpTo', from: level.threshold, to: next.threshold };
  if (next) return { key: 'statusRange', from: level.threshold, to: next.threshold };
  return { key: 'fromAmount', from: level.threshold, to: null };
}

export function maxStatusPercent(
  catalog: StatusCatalog | ClientStatuses | null | undefined,
): number {
  if (!catalog) return 0;
  if ('tiers' in catalog) {
    if (catalog.tiers.length === 0) return 0;
    return Math.max(...catalog.tiers.map(t => Number(t.percent) || 0));
  }
  if ('levels' in catalog) {
    return Math.max(...catalog.levels.map(l => l.percent));
  }
  return 0;
}
