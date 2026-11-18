import { useState } from 'react';
import { useAdminSession } from '../auth/provider';
import { useAudit } from '../api/queries';
import type { AuditItem } from '../api/types';
import { DataTable } from '../components/DataTable';
import { useTableExpansion } from '../components/CompactTable';
import { EmptyState, ErrorNotice, LoadingPage, PageHeading, StatusPill } from '../components/Feedback';
import { formatDate } from '../utils/format';
import { usePage } from '../utils/usePage';
import { useLocale } from '../i18n/LocaleContext';
import { useAdminTranslation } from '../i18n/admin';

const MANAGER_AUDIT_FIELDS = [
  'title_ru',
  'title_kk',
  'title',
  'subtitle',
  'subtitle_ru',
  'subtitle_kk',
  'badge',
  'body',
  'name_ru',
  'name_kk',
  'name',
  'kind',
  'is_active',
  'status',
  'targeted_user',
  'starts_at',
  'ends_at',
  'scheduled_at',
  'push_sent_at',
  'push_devices',
  'push_delivered',
  'sort_order',
  'level',
  'threshold',
  'min_turnover',
  'max_turnover',
  'percent',
  'is_default',
  'address_ru',
  'address_kk',
  'address',
  'phone',
  'working_hours',
  'barcode',
  'balance',
  'is_blocked',
  'block_reason',
  'user_phone',
  'enabled',
  'duration_sec',
  'media_type',
  'image_url',
  'logo_url',
  'about_ru',
  'about_kk',
  'status_earn_hint_ru',
  'status_earn_hint_kk',
  'support_phone',
  'support_whatsapp',
  'primary',
  'accent',
] as const;

const STORE_SAFE_MANAGER_FIELDS = [
  'title_ru',
  'title_kk',
  'title',
  'address_ru',
  'address_kk',
  'address',
  'sort_order',
  'is_active',
] as const;

const TIER_SAFE_MANAGER_FIELDS = [
  'level',
  'name_ru',
  'name_kk',
  'name',
  'min_turnover',
  'max_turnover',
  'threshold',
  'percent',
  'is_active',
  'is_default',
] as const;

const NOTIFICATION_SAFE_MANAGER_FIELDS = [
  'title',
  'body',
  'kind',
  'targeted_user',
  'scheduled_at',
  'push_sent_at',
  'push_devices',
  'push_delivered',
] as const;

const APP_TEXT_BLOCKS = ['home_text', 'home_store_note_lead', 'balance_delay_note'] as const;
type AppTextBlock = (typeof APP_TEXT_BLOCKS)[number];
const APP_TEXT_BLOCK_SET = new Set<string>(APP_TEXT_BLOCKS);
const APP_TEXT_LOCALES = ['ru', 'kk'] as const;
type AppTextLocale = (typeof APP_TEXT_LOCALES)[number];
const APP_TEXT_LOCALE_SET = new Set<string>(APP_TEXT_LOCALES);

interface AppTextsMetaState {
  blocks: Partial<Record<AppTextBlock, Partial<Record<AppTextLocale, boolean>>>>;
  configuredFields: AppTextBlock[];
  changedFields: AppTextBlock[];
  changedLocales: Array<{ block: AppTextBlock; lang: AppTextLocale }>;
  texts: Partial<Record<AppTextBlock, Partial<Record<AppTextLocale, string | null>>>>;
  hasTexts: boolean;
  isExplicitNoOp: boolean;
}

function parseAppTextsBlockList(raw: unknown): AppTextBlock[] {
  if (!Array.isArray(raw)) return [];
  const seen = new Set<AppTextBlock>();
  const out: AppTextBlock[] = [];
  for (const item of raw) {
    if (typeof item === 'string' && APP_TEXT_BLOCK_SET.has(item)) {
      const typed = item as AppTextBlock;
      if (!seen.has(typed)) {
        seen.add(typed);
        out.push(typed);
      }
    }
  }
  return out;
}

function parseAppTextsLocalePairs(raw: unknown): Array<{ block: AppTextBlock; lang: AppTextLocale }> {
  if (!Array.isArray(raw)) return [];
  const seen = new Set<string>();
  const out: Array<{ block: AppTextBlock; lang: AppTextLocale }> = [];
  for (const item of raw) {
    if (typeof item !== 'string') continue;
    const dot = item.indexOf('.');
    if (dot <= 0) continue;
    const block = item.slice(0, dot);
    const lang = item.slice(dot + 1);
    if (!APP_TEXT_BLOCK_SET.has(block) || !APP_TEXT_LOCALE_SET.has(lang)) continue;
    const key = `${block}.${lang}`;
    if (!seen.has(key)) {
      seen.add(key);
      out.push({ block: block as AppTextBlock, lang: lang as AppTextLocale });
    }
  }
  return out;
}

function parseAppTextsMetaState(value: Record<string, unknown> | null): AppTextsMetaState | null {
  if (!value || typeof value !== 'object') return null;
  const blocks: Partial<Record<AppTextBlock, Partial<Record<AppTextLocale, boolean>>>> = {};
  let hasAnyValidBlock = false;
  for (const block of APP_TEXT_BLOCKS) {
    const rawBlock = value[block];
    if (!rawBlock || typeof rawBlock !== 'object' || Array.isArray(rawBlock)) continue;
    const blockObj = rawBlock as Record<string, unknown>;
    const flags: Partial<Record<AppTextLocale, boolean>> = {};
    let hasBool = false;
    for (const lang of APP_TEXT_LOCALES) {
      if (typeof blockObj[lang] === 'boolean') {
        flags[lang] = blockObj[lang] as boolean;
        hasBool = true;
      }
    }
    if (hasBool) {
      blocks[block] = flags;
      hasAnyValidBlock = true;
    }
  }

  const texts: Partial<Record<AppTextBlock, Partial<Record<AppTextLocale, string | null>>>> = {};
  let hasTexts = false;
  if (value.texts && typeof value.texts === 'object' && !Array.isArray(value.texts)) {
    const rawTexts = value.texts as Record<string, unknown>;
    for (const block of APP_TEXT_BLOCKS) {
      const rawBlockTexts = rawTexts[block];
      if (!rawBlockTexts || typeof rawBlockTexts !== 'object' || Array.isArray(rawBlockTexts)) continue;
      const blockTextsObj = rawBlockTexts as Record<string, unknown>;
      const perLang: Partial<Record<AppTextLocale, string | null>> = {};
      let hasPair = false;
      for (const lang of APP_TEXT_LOCALES) {
        if (!Object.prototype.hasOwnProperty.call(blockTextsObj, lang)) continue;
        const entry = blockTextsObj[lang];
        if (entry === null || typeof entry === 'string') {
          perLang[lang] = entry;
          hasPair = true;
        }
      }
      if (hasPair) {
        texts[block] = perLang;
        hasTexts = true;
      }
    }
  }

  const hasConfiguredFieldsKey = Array.isArray(value.configured_fields);
  const hasChangedFieldsKey = Array.isArray(value.changed_fields);
  const hasChangedLocalesKey = Array.isArray(value.changed_locales);
  const configuredFields = parseAppTextsBlockList(value.configured_fields);
  const changedFields = parseAppTextsBlockList(value.changed_fields);
  const changedLocales = parseAppTextsLocalePairs(value.changed_locales);

  const isExplicitNoOp =
    hasChangedFieldsKey &&
    hasChangedLocalesKey &&
    (value.changed_fields as unknown[]).length === 0 &&
    (value.changed_locales as unknown[]).length === 0 &&
    !hasTexts &&
    (hasAnyValidBlock || hasConfiguredFieldsKey);

  if (
    !hasAnyValidBlock &&
    !hasTexts &&
    configuredFields.length === 0 &&
    changedFields.length === 0 &&
    changedLocales.length === 0 &&
    !isExplicitNoOp
  ) {
    return null;
  }

  return {
    blocks,
    configuredFields,
    changedFields,
    changedLocales,
    texts,
    hasTexts,
    isExplicitNoOp,
  };
}

const SUPERADMIN_EXTRA_FIELDS = ['android_app_id', 'barcode_prefixes', 'colors'] as const;

const SENSITIVE_KEY_RE = /(secret|token|password|hash|api_key|key_hash|private)/i;
const CONTENT_TEXT_FIELDS = new Set([
  'title',
  'title_ru',
  'title_kk',
  'subtitle',
  'subtitle_ru',
  'subtitle_kk',
  'badge',
  'body',
  'ru',
  'kk',
]);

function isRedactedOrSecret(key: string, val: unknown): boolean {
  if (SENSITIVE_KEY_RE.test(key)) return true;
  if (!CONTENT_TEXT_FIELDS.has(key) && typeof val === 'string') {
    const trimmed = val.trim();
    if (trimmed === '[REDACTED]' || trimmed === '***') return true;
  }
  return false;
}

function sanitizeRawValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(item => sanitizeRawValue(item));
  }
  if (value && typeof value === 'object') {
    return sanitizeForRawDetails(value as Record<string, unknown>);
  }
  return value;
}

function sanitizeForRawDetails(value: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(value)) {
    if (isRedactedOrSecret(k, v)) continue;
    out[k] = sanitizeRawValue(v);
  }
  return out;
}

function formatTurnoverMoney(val: unknown, locale: 'ru' | 'kk'): string {
  const num = Number(val);
  if (!Number.isFinite(num)) return String(val);
  return `${num.toLocaleString(locale === 'kk' ? 'kk-KZ' : 'ru-RU', { maximumFractionDigits: 2 })} ₸`;
}

function formatPercentDisplay(val: unknown): string {
  const num = Number(val);
  if (Number.isFinite(num)) {
    return `${Number(num.toFixed(2))}`;
  }
  return String(val);
}

function formatAuditValue(
  key: string,
  val: unknown,
  locale: 'ru' | 'kk',
  t: ReturnType<typeof useAdminTranslation>
): string {
  if (key === 'max_turnover' && val === null) return t.audit.valUnbounded;
  if (key === 'starts_at' && val === null) return t.audit.valNotSet;
  if (key === 'ends_at' && val === null) return t.content.noEndDateBtn;
  if (key === 'scheduled_at' && val === null) return t.audit.valSendNow;
  if (key === 'push_sent_at' && val === null) return t.audit.valPushNotSent;
  if (val === null || val === undefined || val === '') return t.audit.valEmpty;
  if (key === 'kind') {
    if (val === 'banner') return t.audit.kindBanner;
    if (val === 'offer') return t.audit.kindOffer;
    if (val === 'info') return t.audit.kindInfo;
  }
  if (key === 'targeted_user') return val ? t.audit.targetedYes : t.audit.targetedNo;
  if (key === 'is_active') return val ? t.audit.valActive : t.audit.valInactive;
  if (key === 'is_blocked') return val ? t.audit.valBlocked : t.audit.valUnblocked;
  if (key === 'enabled') return val ? t.audit.valEnabled : t.audit.valDisabled;
  if (key === 'status') {
    if (val === 'active') return t.mutations.statusActive;
    if (val === 'inactive') return t.mutations.statusInactive;
  }
  if (typeof val === 'boolean') return val ? t.audit.valYes : t.audit.valNo;
  if ((key === 'min_turnover' || key === 'max_turnover' || key === 'threshold') && (typeof val === 'number' || typeof val === 'string')) {
    return formatTurnoverMoney(val, locale);
  }
  if (key === 'percent' && (typeof val === 'number' || typeof val === 'string')) {
    return `${formatPercentDisplay(val)}%`;
  }
  if ((key === 'starts_at' || key === 'ends_at' || key === 'scheduled_at' || key === 'push_sent_at') && typeof val === 'string') {
    return formatDate(val, locale) || val;
  }
  if (Array.isArray(val)) {
    if (val.length === 0) return '[]';
    return val.map(item => String(item)).join(', ');
  }
  if (typeof val === 'object') {
    const obj = val as Record<string, unknown>;
    if (typeof obj.configured === 'boolean' && Object.keys(obj).length === 1) {
      if (locale === 'kk') return obj.configured ? 'Орнатылған' : 'Орнатылмаған';
      return obj.configured ? 'Заданы' : 'Не заданы';
    }
    const entries = Object.entries(obj)
      .filter(([k, v]) => !isRedactedOrSecret(k, v) && v !== undefined && v !== null);
    if (entries.length === 0) return t.audit.valEmpty;
    return entries.map(([k, v]) => `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`).join(', ');
  }
  const str = String(val);
  if (CONTENT_TEXT_FIELDS.has(key)) return str;
  return str.length > 80 ? `${str.slice(0, 77)}…` : str;
}

const AUDIT_PRIMARY_LIMIT = 8;

function getDiffKeys(
  before: Record<string, unknown> | null,
  after: Record<string, unknown> | null,
  allowedFields: readonly string[]
): string[] {
  const beforeKeys = new Set(before ? Object.keys(before) : []);
  const afterKeys = new Set(after ? Object.keys(after) : []);
  const presentAllowed = allowedFields.filter(key => {
    const inBefore = beforeKeys.has(key) && !isRedactedOrSecret(key, before?.[key]);
    const inAfter = afterKeys.has(key) && !isRedactedOrSecret(key, after?.[key]);
    return inBefore || inAfter;
  });

  if (before && after) {
    const changed = presentAllowed.filter(key => {
      const hasBefore = beforeKeys.has(key);
      const hasAfter = afterKeys.has(key);
      if (hasBefore !== hasAfter) return true;
      const a = before[key] === undefined ? '__undefined__' : JSON.stringify(before[key]);
      const b = after[key] === undefined ? '__undefined__' : JSON.stringify(after[key]);
      return a !== b;
    });
    if (changed.length > 0) return changed;
  }
  return presentAllowed;
}

interface ScaleAuditTierRow {
  tier_id?: string;
  level: number;
  min_turnover: string | number;
  max_turnover?: string | number | null;
  percent: string | number;
  is_active: boolean;
}

function parseScaleAuditTiers(raw: unknown): ScaleAuditTierRow[] {
  if (!Array.isArray(raw)) return [];
  const items: ScaleAuditTierRow[] = [];
  for (const entry of raw) {
    if (!entry || typeof entry !== 'object') continue;
    const obj = entry as Record<string, unknown>;
    if (typeof obj.level !== 'number') continue;
    if (obj.min_turnover === undefined || obj.min_turnover === null) continue;
    if (obj.percent === undefined || obj.percent === null) continue;
    let maxTurnover: string | number | null | undefined;
    if ('max_turnover' in obj) {
      if (obj.max_turnover === null) {
        maxTurnover = null;
      } else if (typeof obj.max_turnover === 'number' || typeof obj.max_turnover === 'string') {
        maxTurnover = obj.max_turnover;
      }
    }
    items.push({
      ...(typeof obj.tier_id === 'string' ? { tier_id: obj.tier_id } : {}),
      level: obj.level,
      min_turnover: typeof obj.min_turnover === 'number' || typeof obj.min_turnover === 'string' ? obj.min_turnover : '0',
      ...(maxTurnover !== undefined ? { max_turnover: maxTurnover } : {}),
      percent: typeof obj.percent === 'number' || typeof obj.percent === 'string' ? obj.percent : '0',
      is_active: obj.is_active !== false,
    });
  }
  return items.sort((a, b) => a.level - b.level);
}

function scaleTierSignature(tier: ScaleAuditTierRow): string {
  return JSON.stringify([
    tier.level,
    String(tier.min_turnover),
    tier.max_turnover === undefined ? '__absent__' : tier.max_turnover === null ? null : String(tier.max_turnover),
    String(tier.percent),
    tier.is_active,
  ]);
}

interface AlignedScaleEntry {
  key: string;
  level: number;
  tier: ScaleAuditTierRow | null;
}

function indexScaleTiers(tiers: readonly ScaleAuditTierRow[]): Map<string, ScaleAuditTierRow> {
  const map = new Map<string, ScaleAuditTierRow>();
  const levelCounts = new Map<number, number>();
  for (const tier of tiers) {
    const occ = levelCounts.get(tier.level) ?? 0;
    levelCounts.set(tier.level, occ + 1);
    const key = tier.tier_id || (occ === 0 ? `lvl:${tier.level}` : `lvl:${tier.level}#${occ}`);
    map.set(key, tier);
  }
  return map;
}

function buildAlignedScaleEntries(
  currentTiers: readonly ScaleAuditTierRow[],
  otherTiers: readonly ScaleAuditTierRow[]
): AlignedScaleEntry[] {
  const currentMap = indexScaleTiers(currentTiers);
  if (otherTiers.length === 0) {
    return Array.from(currentMap.entries())
      .map(([key, tier]) => ({ key, level: tier.level, tier }))
      .sort((a, b) => a.level - b.level || a.key.localeCompare(b.key));
  }

  const otherMap = indexScaleTiers(otherTiers);
  const allKeys = new Set<string>([...currentMap.keys(), ...otherMap.keys()]);
  const sortedAll = Array.from(allKeys)
    .map(key => {
      const cur = currentMap.get(key) ?? null;
      const oth = otherMap.get(key) ?? null;
      const level = cur?.level ?? oth?.level ?? 0;
      return { key, level, cur, oth };
    })
    .sort((a, b) => a.level - b.level || a.key.localeCompare(b.key));

  const totalScaleSize = Math.max(currentTiers.length, otherTiers.length);
  const changed = sortedAll.filter(item => {
    if (!item.cur || !item.oth) return true;
    return scaleTierSignature(item.cur) !== scaleTierSignature(item.oth);
  });

  const selected = changed.length > 0 && totalScaleSize > 4 ? changed : sortedAll;
  return selected.map(item => ({
    key: item.key,
    level: item.level,
    tier: item.cur,
  }));
}

function AuditDiffOverflowControl({
  totalCount,
  visibleCount,
  expanded,
  onToggleExpand,
}: {
  totalCount: number;
  visibleCount: number;
  expanded: boolean;
  onToggleExpand: () => void;
}) {
  const t = useAdminTranslation();
  if (totalCount <= AUDIT_PRIMARY_LIMIT) return null;
  const hiddenCount = Math.max(0, totalCount - visibleCount);
  return (
    <div className="audit-diff-more">
      {!expanded && hiddenCount > 0 && (
        <span className="audit-diff-hidden-count">
          {t.audit.hiddenDetailsCount(hiddenCount, totalCount)}
        </span>
      )}
      <button
        type="button"
        className="link-button audit-diff-toggle"
        aria-expanded={expanded}
        onClick={onToggleExpand}
      >
        {expanded ? t.audit.collapseDetails : t.audit.showAllDetails(totalCount)}
      </button>
    </div>
  );
}

function StateView({
  side,
  action,
  entity,
  value,
  otherValue,
  isSuperadmin,
  locale,
  expanded,
  onToggleExpand,
}: {
  side: 'before' | 'after';
  action: string;
  entity: string;
  value: Record<string, unknown> | null;
  otherValue: Record<string, unknown> | null;
  isSuperadmin: boolean;
  locale: 'ru' | 'kk';
  expanded: boolean;
  onToggleExpand: () => void;
}) {
  const t = useAdminTranslation();
  const isCreation = /_(created|registered|uploaded)$/.test(action);
  const isDeletion = /_deleted$/.test(action);

  if (!value) {
    if (side === 'before' && isCreation && otherValue) {
      return <span className="muted-copy">—</span>;
    }
    if (side === 'after' && isDeletion && otherValue) {
      return <span className="muted-copy">—</span>;
    }
    return <span className="audit-empty-state">{t.audit.noDetails}</span>;
  }

  if (action === 'loyalty_scale_updated' || entity === 'business_loyalty_scale' || Array.isArray(value.tiers)) {
    const tiers = parseScaleAuditTiers(value.tiers);
    const otherTiers = parseScaleAuditTiers(otherValue?.tiers);
    const hasVersion = typeof value.version === 'number';
    if (tiers.length > 0 || hasVersion) {
      const entries = tiers.length > 0 ? buildAlignedScaleEntries(tiers, otherTiers) : [];
      const displayed = expanded || entries.length <= AUDIT_PRIMARY_LIMIT
        ? entries
        : entries.slice(0, AUDIT_PRIMARY_LIMIT);
      return (
        <div>
          <ul className="audit-diff-list">
            {hasVersion && (
              <li className="audit-diff-row" key="version">
                <span className="audit-diff-label">{t.audit.fieldLabels.version ?? 'version'}:</span>
                <span className="audit-diff-value">{t.audit.scaleVersionLabel(value.version as number)}</span>
              </li>
            )}
            {displayed.map(entry => (
              <li className="audit-diff-row" key={entry.key}>
                <span className="audit-diff-label">#{entry.level}:</span>
                <span className="audit-diff-value">
                  {entry.tier
                    ? t.audit.scaleTierSummary(
                        formatTurnoverMoney(entry.tier.min_turnover, locale),
                        entry.tier.max_turnover === undefined
                          ? undefined
                          : entry.tier.max_turnover === null
                            ? null
                            : formatTurnoverMoney(entry.tier.max_turnover, locale),
                        formatPercentDisplay(entry.tier.percent),
                        entry.tier.is_active
                      )
                    : '—'}
                </span>
              </li>
            ))}
          </ul>
          <AuditDiffOverflowControl
            totalCount={entries.length}
            visibleCount={displayed.length}
            expanded={expanded}
            onToggleExpand={onToggleExpand}
          />
          {isSuperadmin && (
            <details className="audit-state" style={{ marginTop: 4 }}>
              <summary>{t.audit.rawDetails}</summary>
              <pre>{JSON.stringify(sanitizeForRawDetails(value), null, 2)}</pre>
            </details>
          )}
        </div>
      );
    }
  }

  if (
    action === 'app_texts_updated' ||
    action === 'business_app_texts_updated' ||
    entity === 'business_app_texts' ||
    entity === 'app_texts'
  ) {
    const meta = parseAppTextsMetaState(value);
    if (meta) {
      const otherMeta = parseAppTextsMetaState(otherValue);
      const hasAnyTexts = meta.hasTexts || Boolean(otherMeta?.hasTexts);
      const rows: Array<{
        key: string;
        label: string;
        valueText: string;
        stacked?: boolean;
        muted?: boolean;
      }> = [];

      const resolveAppTextStatusWord = (block: AppTextBlock, lang: AppTextLocale): string => {
        const beforeFlag = otherMeta?.blocks[block]?.[lang];
        const afterFlag = meta.blocks[block]?.[lang];
        if (beforeFlag === false && afterFlag === true) return t.audit.appTextsStateAdded;
        if (beforeFlag === true && afterFlag === true) return t.audit.appTextsStateUpdated;
        if (beforeFlag === true && afterFlag === false) return t.audit.appTextsStateCleared;
        if (otherMeta && meta.hasTexts) {
          const otherBlock = otherMeta.texts[block];
          const curBlock = meta.texts[block];
          const hasOther = Boolean(otherBlock && Object.prototype.hasOwnProperty.call(otherBlock, lang));
          const hasCur = Boolean(curBlock && Object.prototype.hasOwnProperty.call(curBlock, lang));
          if (hasOther && hasCur) {
            const ov = otherBlock?.[lang];
            const cv = curBlock?.[lang];
            if ((ov === null || ov === '') && typeof cv === 'string' && cv !== '') {
              return t.audit.appTextsStateAdded;
            }
            if (typeof ov === 'string' && ov !== '' && (cv === null || cv === '')) {
              return t.audit.appTextsStateCleared;
            }
            if (typeof ov === 'string' && typeof cv === 'string') {
              return t.audit.appTextsStateUpdated;
            }
          }
        }
        return t.audit.appTextsStateChanged;
      };

      if (hasAnyTexts) {
        const textPairs: Array<{ block: AppTextBlock; lang: AppTextLocale }> = [];
        const seenPairKeys = new Set<string>();
        const pushPair = (block: AppTextBlock, lang: AppTextLocale) => {
          const pairKey = `${block}.${lang}`;
          if (!seenPairKeys.has(pairKey)) {
            seenPairKeys.add(pairKey);
            textPairs.push({ block, lang });
          }
        };

        const primaryChanged = side === 'after' ? meta.changedLocales : (otherMeta?.changedLocales ?? []);
        for (const pair of primaryChanged) {
          pushPair(pair.block, pair.lang);
        }
        for (const block of APP_TEXT_BLOCKS) {
          for (const lang of APP_TEXT_LOCALES) {
            const inSelf = Boolean(meta.texts[block] && Object.prototype.hasOwnProperty.call(meta.texts[block], lang));
            const inOther = Boolean(
              otherMeta?.texts[block] && Object.prototype.hasOwnProperty.call(otherMeta.texts[block], lang),
            );
            if (inSelf || inOther) {
              pushPair(block, lang);
            }
          }
        }

        const coveredBlocks = new Set<AppTextBlock>(textPairs.map(pair => pair.block));
        if (side === 'after') {
          for (const block of meta.changedFields) {
            if (coveredBlocks.has(block)) continue;
            const blockLabel = t.audit.appTextBlocks[block] ?? block;
            rows.push({
              key: `chg-${block}`,
              label: t.audit.appTextsChangedLabel,
              valueText: `${blockLabel} (${t.audit.appTextsStateChanged})`,
            });
          }
        }

        for (const pair of textPairs) {
          const blockLabel = t.audit.appTextBlocks[pair.block] ?? pair.block;
          const localeLabel = t.audit.appTextLocales[pair.lang] ?? pair.lang.toUpperCase();
          const blockTexts = meta.texts[pair.block];
          const hasKey = Boolean(blockTexts && Object.prototype.hasOwnProperty.call(blockTexts, pair.lang));
          const rawVal = hasKey ? blockTexts?.[pair.lang] : undefined;

          let valueText: string;
          let muted = false;
          if (!hasKey || rawVal === undefined) {
            valueText = t.audit.valSnapshotMissing;
            muted = true;
          } else if (rawVal === null || rawVal === '') {
            valueText = t.audit.valEmpty;
            muted = true;
          } else {
            valueText = rawVal;
          }

          const label =
            side === 'after'
              ? `${blockLabel} — ${localeLabel} (${resolveAppTextStatusWord(pair.block, pair.lang)})`
              : `${blockLabel} — ${localeLabel}`;

          rows.push({
            key: `txt-${pair.block}-${pair.lang}`,
            label,
            valueText,
            stacked: true,
            muted,
          });
        }
      } else if (side === 'after') {
        const coveredBlocks = new Set<AppTextBlock>();
        for (const pair of meta.changedLocales) {
          coveredBlocks.add(pair.block);
          const blockLabel = t.audit.appTextBlocks[pair.block] ?? pair.block;
          const localeLabel = t.audit.appTextLocales[pair.lang] ?? pair.lang.toUpperCase();
          rows.push({
            key: `chg-${pair.block}-${pair.lang}`,
            label: t.audit.appTextsChangedLabel,
            valueText: `${blockLabel} — ${localeLabel} (${resolveAppTextStatusWord(pair.block, pair.lang)})`,
          });
        }
        for (const block of meta.changedFields) {
          if (coveredBlocks.has(block)) continue;
          const blockLabel = t.audit.appTextBlocks[block] ?? block;
          rows.push({
            key: `chg-${block}`,
            label: t.audit.appTextsChangedLabel,
            valueText: `${blockLabel} (${t.audit.appTextsStateChanged})`,
          });
        }
        if (meta.isExplicitNoOp && rows.length === 0) {
          rows.push({
            key: 'chg-noop',
            label: t.audit.appTextsChangedLabel,
            valueText: t.audit.appTextsNoChanges,
          });
        }
      }

      if (Object.keys(meta.blocks).length > 0 || Array.isArray(value.configured_fields)) {
        const activeBlockSummaries: string[] = [];
        for (const block of APP_TEXT_BLOCKS) {
          const flags = meta.blocks[block];
          const activeLangs = APP_TEXT_LOCALES.filter(lang => flags?.[lang] === true);
          if (activeLangs.length > 0 || meta.configuredFields.includes(block)) {
            const blockLabel = t.audit.appTextBlocks[block] ?? block;
            const langSuffix = activeLangs.length > 0
              ? ` (${activeLangs.map(lang => t.audit.appTextLocales[lang] ?? lang.toUpperCase()).join(', ')})`
              : '';
            activeBlockSummaries.push(`${blockLabel}${langSuffix}`);
          }
        }

        rows.push({
          key: 'configured-summary',
          label: t.audit.appTextsConfiguredLabel,
          valueText: activeBlockSummaries.length > 0
            ? activeBlockSummaries.join('; ')
            : t.audit.appTextsNoneConfigured,
        });
      }

      const displayed = expanded || rows.length <= AUDIT_PRIMARY_LIMIT
        ? rows
        : rows.slice(0, AUDIT_PRIMARY_LIMIT);

      return (
        <div>
          <ul className="audit-diff-list">
            {displayed.map(item => (
              <li
                className={item.stacked ? 'audit-diff-row audit-diff-row--stacked' : 'audit-diff-row'}
                key={item.key}
              >
                <span className="audit-diff-label">{item.label}:</span>
                <span className={item.muted ? 'audit-diff-value audit-empty-state' : 'audit-diff-value'}>
                  {item.valueText}
                </span>
              </li>
            ))}
          </ul>
          <AuditDiffOverflowControl
            totalCount={rows.length}
            visibleCount={displayed.length}
            expanded={expanded}
            onToggleExpand={onToggleExpand}
          />
          {isSuperadmin && (
            <details className="audit-state" style={{ marginTop: 4 }}>
              <summary>{t.audit.rawDetails}</summary>
              <pre>{JSON.stringify(sanitizeForRawDetails(value), null, 2)}</pre>
            </details>
          )}
        </div>
      );
    }
  }

  const baseFields: readonly string[] =
    entity === 'business_store' && !isSuperadmin
      ? STORE_SAFE_MANAGER_FIELDS
      : entity === 'business_loyalty_tier' && !isSuperadmin
        ? TIER_SAFE_MANAGER_FIELDS
        : entity === 'notification' && !isSuperadmin
          ? NOTIFICATION_SAFE_MANAGER_FIELDS
          : MANAGER_AUDIT_FIELDS;

  const isTargetedNotification =
    entity === 'notification' && Boolean(value.targeted_user ?? otherValue?.targeted_user);

  const allowedFields: readonly string[] = (
    isSuperadmin ? [...baseFields, ...SUPERADMIN_EXTRA_FIELDS] : baseFields
  ).filter(field => !(isTargetedNotification && (field === 'title' || field === 'body')));

  const keys = getDiffKeys(
    side === 'before' ? value : otherValue,
    side === 'after' ? value : otherValue,
    allowedFields
  );

  const visibleEntries = keys
    .filter(key => key in value)
    .map(key => {
      const formatted = formatAuditValue(key, value[key], locale, t);
      const isTextBody = key === 'body' || key === 'subtitle';
      const isStacked = isTextBody || formatted.includes('\n') || formatted.length > 80;
      const isEmptyContent = CONTENT_TEXT_FIELDS.has(key) && (value[key] === null || value[key] === '');
      return {
        key,
        label:
          entity === 'notification' && key === 'kind'
            ? t.audit.notificationKindLabel
            : entity === 'promotion' && key === 'body'
              ? t.audit.promotionBodyLabel
              : (t.audit.fieldLabels[key] ?? key),
        formatted,
        isStacked,
        isEmptyContent,
      };
    });

  if (visibleEntries.length === 0) {
    if (!isSuperadmin) {
      return <span className="audit-empty-state">{t.audit.noDetails}</span>;
    }
    const sanitized = sanitizeForRawDetails(value);
    if (Object.keys(sanitized).length === 0) {
      return <span className="audit-empty-state">{t.audit.noDetails}</span>;
    }
    return (
      <details className="audit-state">
        <summary>{t.audit.rawDetails}</summary>
        <pre>{JSON.stringify(sanitized, null, 2)}</pre>
      </details>
    );
  }

  const displayedEntries = expanded || visibleEntries.length <= AUDIT_PRIMARY_LIMIT
    ? visibleEntries
    : visibleEntries.slice(0, AUDIT_PRIMARY_LIMIT);

  return (
    <div>
      <ul className="audit-diff-list">
        {displayedEntries.map(entry => (
          <li
            className={entry.isStacked ? 'audit-diff-row audit-diff-row--stacked' : 'audit-diff-row'}
            key={entry.key}
          >
            <span className="audit-diff-label">{entry.label}:</span>
            <span className={entry.isEmptyContent ? 'audit-diff-value audit-empty-state' : 'audit-diff-value'}>
              {entry.formatted}
            </span>
          </li>
        ))}
      </ul>
      <AuditDiffOverflowControl
        totalCount={visibleEntries.length}
        visibleCount={displayedEntries.length}
        expanded={expanded}
        onToggleExpand={onToggleExpand}
      />
      {isSuperadmin && (
        <details className="audit-state" style={{ marginTop: 4 }}>
          <summary>{t.audit.rawDetails}</summary>
          <pre>{JSON.stringify(sanitizeForRawDetails(value), null, 2)}</pre>
        </details>
      )}
    </div>
  );
}

function describeAuditAction(action: string, locale: 'ru' | 'kk', isSuperadmin = false, row?: AuditItem): string {
  const kind = (row?.after_state?.kind ?? row?.before_state?.kind) as string | undefined;
  if (action === 'promotion_created') {
    if (kind === 'banner') return locale === 'kk' ? 'Баннер жасалды' : 'Создан баннер';
    if (kind === 'offer') return locale === 'kk' ? 'Акция жасалды' : 'Создана акция';
  }
  if (action === 'promotion_updated') {
    if (kind === 'banner') return locale === 'kk' ? 'Баннер өзгертілді' : 'Изменён баннер';
    if (kind === 'offer') return locale === 'kk' ? 'Акция өзгертілді' : 'Изменена акция';
  }
  if (action === 'promotion_deleted') {
    if (kind === 'banner') return locale === 'kk' ? 'Баннер жойылды' : 'Удалён баннер';
    if (kind === 'offer') return locale === 'kk' ? 'Акция жойылды' : 'Удалена акция';
  }

  const dict: Record<string, { ru: string; kk: string }> = {
    promotion_created: { ru: 'Создана акция / баннер', kk: 'Акция / баннер жасалды' },
    promotion_updated: { ru: 'Изменена акция / баннер', kk: 'Акция / баннер өзгертілді' },
    promotion_deleted: { ru: 'Удалена акция / баннер', kk: 'Акция / баннер жойылды' },
    store_created: { ru: 'Добавлен магазин', kk: 'Дүкен қосылды' },
    store_updated: { ru: 'Изменён магазин', kk: 'Дүкен өзгертілді' },
    store_deleted: { ru: 'Удалён магазин', kk: 'Дүкен жойылды' },
    loyalty_tier_created: { ru: 'Создан статус лояльности', kk: 'Адалдық дәрежесі жасалды' },
    loyalty_tier_updated: { ru: 'Изменён статус лояльности', kk: 'Адалдық дәрежесі өзгертілді' },
    loyalty_tier_deleted: { ru: 'Удалён статус лояльности', kk: 'Адалдық дәрежесі жойылды' },
    loyalty_scale_updated: { ru: 'Обновлена шкала статусов лояльности', kk: 'Адалдық дәрежелері шкаласы жаңартылды' },
    business_created: { ru: 'Создан бизнес', kk: 'Бизнес жасалды' },
    business_updated: { ru: 'Обновлены настройки бизнеса', kk: 'Бизнес баптаулары жаңартылды' },
    business_manager_created: { ru: 'Создан управляющий', kk: 'Басқарушы жасалды' },
    business_manager_password_reset: { ru: 'Сброшен пароль управляющего', kk: 'Басқарушы құпия сөзі қалпына келтірілді' },
    app_texts_updated: { ru: 'Обновлены тексты приложения', kk: 'Қолданба мәтіндері жаңартылды' },
    business_app_texts_updated: { ru: 'Обновлены тексты приложения', kk: 'Қолданба мәтіндері жаңартылды' },
    business_splash_updated: { ru: 'Обновлены настройки заставки', kk: 'Заставка баптаулары жаңартылды' },
    business_splash_uploaded: { ru: 'Загружена заставка', kk: 'Заставка жүктелді' },
    splash_media_uploaded: { ru: 'Загружена заставка', kk: 'Заставка жүктелді' },
    splash_media_deleted: { ru: 'Удалена заставка', kk: 'Заставка жойылды' },
    image_uploaded: { ru: 'Загружена картинка', kk: 'Сурет жүктелді' },
    media_uploaded: { ru: 'Загружен медиафайл', kk: 'Медиа файл жүктелді' },
    agent_created: { ru: 'Создан агент', kk: 'Агент жасалды' },
    agent_registered: { ru: 'Зарегистрирован агент', kk: 'Агент тіркелді' },
    agent_rekeyed: { ru: 'Перевыпущен ключ агента', kk: 'Агент кілті қайта шығарылды' },
    agent_key_rotated: { ru: 'Сменён ключ агента', kk: 'Агент кілті ауыстырылды' },
    agent_revoked: { ru: 'Отозван агент', kk: 'Агент кері қайтарылды' },
    agent_full_resync_requested: { ru: 'Запрошена полная синхронизация', kk: 'Толық синхрондау сұралды' },
    pos_key_created: { ru: 'Создан кассовый ключ', kk: 'Касса кілті жасалды' },
    pos_key_revoked: { ru: 'Отозван кассовый ключ', kk: 'Касса кілті кері қайтарылды' },
    card_unbound: { ru: 'Отвязана карта', kk: 'Карта ажыратылды' },
    notification_created: { ru: 'Создана рассылка', kk: 'Хабарлама жасалды' },
    notification_deleted: { ru: 'Удалена рассылка', kk: 'Хабарлама жойылды' },
  };

  const item = dict[action];
  if (item) return item[locale];
  if (!isSuperadmin) {
    return locale === 'kk' ? 'Жүйедегі басқа әрекет' : 'Другое действие в системе';
  }
  const humanized = action.replace(/_/g, ' ');
  return locale === 'kk' ? `Жүйелік әрекет (${humanized})` : `Системное действие (${humanized})`;
}

function describeAuditEntity(
  entity: string,
  locale: 'ru' | 'kk',
  t: ReturnType<typeof useAdminTranslation>,
  row?: AuditItem
): string {
  if (entity === 'promotion') {
    const kind = (row?.after_state?.kind ?? row?.before_state?.kind) as string | undefined;
    if (kind === 'banner') return locale === 'kk' ? 'Баннер' : 'Баннер';
    if (kind === 'offer') return locale === 'kk' ? 'Акция' : 'Акция';
  }
  if (entity === 'business_app_texts' || entity === 'app_texts') return t.audit.entityTexts;
  if (entity === 'business_splash' || entity === 'splash_media' || entity === 'business_splash_asset') {
    return t.audit.entitySplash;
  }

  const dict: Record<string, { ru: string; kk: string }> = {
    promotion: { ru: 'Акция / баннер', kk: 'Акция / баннер' },
    business_store: { ru: 'Магазин', kk: 'Дүкен' },
    business_loyalty_tier: { ru: 'Статус лояльности', kk: 'Адалдық дәрежесі' },
    business_loyalty_scale: { ru: 'Шкала статусов', kk: 'Дәрежелер шкаласы' },
    business: { ru: 'Бизнес', kk: 'Бизнес' },
    admin_user: { ru: 'Пользователь', kk: 'Пайдаланушы' },
    agent_command: { ru: 'Команда агента', kk: 'Агент командасы' },
    pos_key: { ru: 'Кассовый ключ', kk: 'Касса кілті' },
    card: { ru: 'Карта', kk: 'Карта' },
    agent: { ru: 'Агент', kk: 'Агент' },
    image: { ru: 'Изображение', kk: 'Сурет' },
    notification: { ru: 'Рассылка', kk: 'Хабарлама' },
  };
  const item = dict[entity];
  if (item) return item[locale];
  return entity.replace(/_/g, ' ');
}

function getAuditTargetName(item: AuditItem, locale: 'ru' | 'kk'): string | null {
  const state = item.after_state ?? item.before_state;
  if (!state || typeof state !== 'object') return null;
  const s = state as Record<string, unknown>;
  if (item.entity === 'notification' && Boolean(s.targeted_user)) {
    return null;
  }
  const candidates =
    locale === 'kk'
      ? [s.title_kk, s.name_kk, s.title_ru, s.name_ru, s.title, s.name, s.barcode, s.user_phone, s.phone]
      : [s.title_ru, s.name_ru, s.title_kk, s.name_kk, s.title, s.name, s.barcode, s.user_phone, s.phone];
  for (const val of candidates) {
    if (typeof val === 'string' && val.trim()) {
      return val.trim();
    }
  }
  if (item.entity === 'business_loyalty_scale' && typeof s.version === 'number') {
    return `v${s.version}`;
  }
  if (typeof s.level === 'number' || typeof s.level === 'string') {
    return `#${String(s.level)}`;
  }
  return null;
}

export function AuditPage() {
  const { view } = useAdminSession();
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const [page, setPage] = usePage();
  const expansion = useTableExpansion();
  const [expandedRowIds, setExpandedRowIds] = useState<Record<string, boolean>>({});
  const toggleRowDetails = (id: string) => {
    setExpandedRowIds(current => ({ ...current, [id]: !current[id] }));
  };
  const query = useAudit(page);
  const isManager = view.status === 'authenticated' && view.admin.role === 'business_manager';
  const isSuperadmin = view.status === 'authenticated' && view.admin.role === 'superadmin';

  return (
    <div className="page-stack">
      <PageHeading
        title={t.audit.title}
        subtitle={
          isManager
            ? t.audit.subtitleScope(view.admin.business?.name ?? '')
            : t.audit.subtitleAll
        }
      />
      <p className="data-note">
        <StatusPill tone="warning">{t.audit.readOnlyBadge}</StatusPill> {t.audit.note}
      </p>
      {query.isPending ? (
        <LoadingPage label={t.audit.loading} />
      ) : query.isError ? (
        <ErrorNotice error={query.error} retry={() => { void query.refetch(); }} />
      ) : query.data?.items.length === 0 && page.offset === 0 ? (
        <EmptyState title={t.audit.emptyTitle} detail={t.audit.emptyDetail} />
      ) : query.data ? (
        <DataTable<AuditItem>
          expansion={expansion}
          page={{ ...page, has_more: query.data.has_more }}
          onPage={setPage}
          rows={query.data.items}
          rowKey={row => row.id}
          columns={[
            {
              key: 'created',
              title: t.audit.colDateTime,
              render: row => <time dateTime={row.created_at}>{formatDate(row.created_at, locale)}</time>,
            },
            { key: 'actor', title: t.audit.colActor, render: row => <span className="cell-primary">{row.actor}</span> },
            {
              key: 'action',
              title: t.audit.colAction,
              render: row => {
                const target = getAuditTargetName(row, locale);
                return (
                  <div>
                    <strong>{describeAuditAction(row.action, locale, isSuperadmin, row)}</strong>
                    {target && (
                      <div className="muted-copy" style={{ fontSize: '0.8125rem' }}>
                        «{target}»
                      </div>
                    )}
                  </div>
                );
              },
            },
            {
              key: 'entity',
              title: t.audit.colEntity,
              render: row => <span>{describeAuditEntity(row.entity, locale, t, row)}</span>,
            },
            {
              key: 'before',
              title: t.audit.colBefore,
              render: row => (
                <StateView
                  side="before"
                  action={row.action}
                  entity={row.entity}
                  value={row.before_state}
                  otherValue={row.after_state}
                  isSuperadmin={isSuperadmin}
                  locale={locale}
                  expanded={Boolean(expandedRowIds[row.id])}
                  onToggleExpand={() => toggleRowDetails(row.id)}
                />
              ),
            },
            {
              key: 'after',
              title: t.audit.colAfter,
              render: row => (
                <StateView
                  side="after"
                  action={row.action}
                  entity={row.entity}
                  value={row.after_state}
                  otherValue={row.before_state}
                  isSuperadmin={isSuperadmin}
                  locale={locale}
                  expanded={Boolean(expandedRowIds[row.id])}
                  onToggleExpand={() => toggleRowDetails(row.id)}
                />
              ),
            },
          ]}
        />
      ) : null}
    </div>
  );
}
