import { useState, useEffect, useMemo, useRef, useCallback, type FormEvent } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { ApiError, messageForError, type SafeErrorField } from '../api/errors';
import { getLoyaltyScale, privateKey, saveLoyaltyScale, useAllBusinesses, useLoyaltyTiers } from '../api/queries';
import type { LoyaltyScaleSaveRequest, LoyaltyScaleTierPatch, LoyaltyTier, LoyaltyTierInput } from '../api/types';
import { useAdminSession } from '../auth/provider';
import { useActiveBusiness } from '../context/ActiveBusinessContext';
import { BusinessSelect } from '../components/BusinessSelect';
import { ErrorNotice, LoadingPage, PageHeading, Pagination, StatusPill } from '../components/Feedback';
import { ImageUploadField } from '../components/ImageUploadField';
import { NumericInput } from '../components/NumericInput';
import { DialogFrame } from '../features/AdminMutations';
import { CompactTableToggle, useCompactRows, useTableExpansion } from '../components/CompactTable';
import { useClientPagination } from '../utils/usePage';
import { useLocale } from '../i18n/LocaleContext';
import { useAdminTranslation } from '../i18n/admin';

function normalizeDecimalInput(raw: string): string {
  return raw.trim().replace(/[\s\u00A0\u202F]+/g, '').replace(',', '.');
}

function hasAtMostTwoDecimals(normalized: string): boolean {
  return /^\d+(?:\.\d{1,2})?$/.test(normalized);
}

function toMinorUnits(normalized: string): bigint | null {
  if (!/^\d{1,12}(?:\.\d{1,2})?$/.test(normalized)) return null;
  const [intPart, fracPart = ''] = normalized.split('.');
  const paddedFrac = (fracPart + '00').slice(0, 2);
  return BigInt(intPart!) * 100n + BigInt(paddedFrac);
}

interface ScaleDraftRow {
  id: string;
  level: number;
  name_ru: string;
  name_kk: string;
  description_ru: string;
  description_kk: string;
  image_url: string;
  min_turnover: string;
  max_turnover: string;
  unbounded: boolean;
  percent: string;
  is_active: boolean;
}

type ScaleRowFieldError = Partial<
  Record<'min_turnover' | 'max_turnover' | 'percent' | 'name_ru' | 'name_kk' | 'image_url', string>
>;

interface ScaleHighlightInfo {
  fields: Set<SafeErrorField>;
  otherLevels: number[];
  message?: string;
}

function sortTiersStable(tiers: readonly LoyaltyTier[]): LoyaltyTier[] {
  return [...tiers].sort((a, b) => a.level - b.level || a.priority - b.priority || a.id.localeCompare(b.id));
}

function toScaleDraftRows(tiers: readonly LoyaltyTier[]): ScaleDraftRow[] {
  return tiers.map(tier => ({
    id: tier.id,
    level: tier.level,
    name_ru: tier.name_ru ?? '',
    name_kk: tier.name_kk ?? '',
    description_ru: tier.description_ru ?? '',
    description_kk: tier.description_kk ?? '',
    image_url: tier.image_url ?? '',
    min_turnover: String(tier.min_turnover ?? '0'),
    max_turnover: tier.max_turnover != null ? String(tier.max_turnover) : '',
    unbounded: tier.max_turnover === null || tier.max_turnover === undefined,
    percent: String(tier.percent ?? '0'),
    is_active: Boolean(tier.is_active),
  }));
}

function formatPreviewNumber(normalized: string, locale: 'ru' | 'kk'): string {
  if (!normalized) return '—';
  const num = Number(normalized);
  if (!Number.isFinite(num)) return normalized;
  return num.toLocaleString(locale === 'kk' ? 'kk-KZ' : 'ru-RU');
}

function ScaleEditorSection({
  businessId,
  locale,
  onClose,
  onSaved,
  onUnsupported,
}: {
  businessId: string;
  locale: 'ru' | 'kk';
  onClose: () => void;
  onSaved: () => void;
  onUnsupported: () => void;
}) {
  const { session } = useAdminSession();
  const t = useAdminTranslation();
  const queryClient = useQueryClient();
  const formRef = useRef<HTMLFormElement>(null);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploadingIds, setUploadingIds] = useState<string[]>([]);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [version, setVersion] = useState<number>(1);
  const [baselineTiers, setBaselineTiers] = useState<LoyaltyTier[]>([]);
  const [draftRows, setDraftRows] = useState<ScaleDraftRow[]>([]);
  const [rowErrors, setRowErrors] = useState<Record<string, ScaleRowFieldError>>({});
  const [conflictHighlights, setConflictHighlights] = useState<Record<string, ScaleHighlightInfo>>({});
  const [submitError, setSubmitError] = useState('');
  const [saveNotice, setSaveNotice] = useState('');
  const [versionConflict, setVersionConflict] = useState<{ currentVersion?: number } | null>(null);
  const [needsServerReload, setNeedsServerReload] = useState(false);

  const loadScale = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    setSubmitError('');
    setSaveNotice('');
    setVersionConflict(null);
    setNeedsServerReload(false);
    setRowErrors({});
    setConflictHighlights({});
    try {
      const res = await getLoyaltyScale(session.api, businessId);
      const sorted = sortTiersStable(Array.isArray(res.tiers) ? res.tiers : []);
      setVersion(res.version);
      setBaselineTiers(sorted);
      setDraftRows(toScaleDraftRows(sorted));
    } catch (err) {
      if (err instanceof ApiError && (err.status === 404 || err.status === 405)) {
        onUnsupported();
        return;
      }
      setLoadError(err);
    } finally {
      setLoading(false);
    }
  }, [businessId, onUnsupported, session.api]);

  useEffect(() => {
    void loadScale();
  }, [loadScale]);

  const clearRowFeedback = (tierId: string, field?: SafeErrorField) => {
    setSaveNotice('');
    if (field) {
      setRowErrors(current => {
        const prev = current[tierId];
        if (!prev || !(field in prev)) return current;
        const nextRow = { ...prev };
        delete nextRow[field as keyof ScaleRowFieldError];
        return { ...current, [tierId]: nextRow };
      });
      setConflictHighlights(current => {
        const prev = current[tierId];
        if (!prev) return current;
        const nextFields = new Set(prev.fields);
        nextFields.delete(field);
        if (nextFields.size === 0) {
          const copy = { ...current };
          delete copy[tierId];
          return copy;
        }
        return { ...current, [tierId]: { ...prev, fields: nextFields } };
      });
    } else {
      setConflictHighlights(current => {
        if (!(tierId in current)) return current;
        const copy = { ...current };
        delete copy[tierId];
        return copy;
      });
    }
  };

  const updateRow = (tierId: string, patch: Partial<ScaleDraftRow>, clearedFields?: SafeErrorField[]) => {
    setDraftRows(current => current.map(row => (row.id === tierId ? { ...row, ...patch } : row)));
    if (clearedFields && clearedFields.length > 0) {
      for (const f of clearedFields) clearRowFeedback(tierId, f);
    } else {
      clearRowFeedback(tierId);
    }
  };

  const previewInfo = useMemo(() => {
    const activeItems = draftRows
      .filter(r => r.is_active)
      .map(r => {
        const minNorm = normalizeDecimalInput(r.min_turnover);
        const maxNorm = r.unbounded ? '' : normalizeDecimalInput(r.max_turnover);
        const pctNorm = normalizeDecimalInput(r.percent);
        return {
          row: r,
          minNorm,
          maxNorm,
          pctNorm,
          minMinor: toMinorUnits(minNorm),
          maxMinor: r.unbounded ? null : toMinorUnits(maxNorm),
        };
      })
      .sort((a, b) => {
        if (a.minMinor !== null && b.minMinor !== null && a.minMinor !== b.minMinor) {
          return a.minMinor < b.minMinor ? -1 : 1;
        }
        return a.row.level - b.row.level;
      });

    const inactiveItems = draftRows
      .filter(r => !r.is_active)
      .map(r => ({
        row: r,
        minNorm: normalizeDecimalInput(r.min_turnover),
        maxNorm: r.unbounded ? '' : normalizeDecimalInput(r.max_turnover),
        pctNorm: normalizeDecimalInput(r.percent),
      }));

    const warnings: string[] = [];
    for (let i = 0; i < activeItems.length - 1; i++) {
      const curr = activeItems[i]!;
      const next = activeItems[i + 1]!;
      if (curr.minMinor === null || next.minMinor === null) continue;
      if (curr.maxMinor === null) {
        warnings.push(t.statuses.scalePreviewOverlapWarn(curr.row.level, next.row.level));
      } else if (curr.maxMinor > next.minMinor) {
        warnings.push(t.statuses.scalePreviewOverlapWarn(curr.row.level, next.row.level));
      } else if (curr.maxMinor < next.minMinor) {
        warnings.push(
          t.statuses.scalePreviewGapNote(
            curr.row.level,
            next.row.level,
            formatPreviewNumber(curr.maxNorm, locale),
            formatPreviewNumber(next.minNorm, locale)
          )
        );
      }
    }

    return {
      ordered: [
        ...activeItems.map(item => ({
          row: item.row,
          minText: formatPreviewNumber(item.minNorm, locale),
          maxText: item.row.unbounded ? null : formatPreviewNumber(item.maxNorm, locale),
          pctText: item.pctNorm || '—',
        })),
        ...inactiveItems.map(item => ({
          row: item.row,
          minText: formatPreviewNumber(item.minNorm, locale),
          maxText: item.row.unbounded ? null : formatPreviewNumber(item.maxNorm, locale),
          pctText: item.pctNorm || '—',
        })),
      ],
      warnings,
    };
  }, [draftRows, locale, t.statuses]);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setSubmitError('');
    setSaveNotice('');
    setVersionConflict(null);
    setNeedsServerReload(false);
    setConflictHighlights({});

    const nextRowErrors: Record<string, ScaleRowFieldError> = {};
    let hasClientError = false;
    const baselineById = new Map(baselineTiers.map(tier => [tier.id, tier]));
    const patchItems: LoyaltyScaleTierPatch[] = [];

    for (const row of draftRows) {
      const base = baselineById.get(row.id);
      const err: ScaleRowFieldError = {};

      const minNorm = normalizeDecimalInput(row.min_turnover);
      const minMinor = minNorm ? toMinorUnits(minNorm) : null;
      if (!minNorm) {
        err.min_turnover = t.statuses.errThresholds;
      } else if (minMinor === null) {
        err.min_turnover = hasAtMostTwoDecimals(minNorm)
          ? t.statuses.errThresholds
          : t.statuses.errTurnoverPrecision;
      }

      let maxNorm: string | null = null;
      if (!row.unbounded) {
        const candidateMax = normalizeDecimalInput(row.max_turnover);
        if (!candidateMax) {
          err.max_turnover = t.statuses.scaleErrMaxRequiredOrUnbounded;
        } else {
          const maxMinor = toMinorUnits(candidateMax);
          if (maxMinor === null) {
            err.max_turnover = hasAtMostTwoDecimals(candidateMax)
              ? t.statuses.errThresholds
              : t.statuses.errTurnoverPrecision;
          } else if (minMinor !== null && maxMinor <= minMinor) {
            err.max_turnover = t.statuses.errThresholds;
          } else {
            maxNorm = candidateMax;
          }
        }
      }

      const pctNorm = normalizeDecimalInput(row.percent);
      const pctMinor = pctNorm ? toMinorUnits(pctNorm) : null;
      if (!pctNorm || pctMinor === null) {
        err.percent = pctNorm && !hasAtMostTwoDecimals(pctNorm) ? t.statuses.errPercentPrecision : t.statuses.errPercent;
      } else if (pctMinor < 0n || pctMinor > 10000n) {
        err.percent = t.statuses.errPercent;
      }

      const nextNameRu = row.name_ru.trim();
      const nextNameKk = row.name_kk.trim();
      if (base && nextNameRu !== (base.name_ru ?? '')) {
        if (!nextNameRu || nextNameRu.length > 120) err.name_ru = t.statuses.errTitleRequired;
      }
      if (base && nextNameKk !== (base.name_kk ?? '')) {
        if (!nextNameKk || nextNameKk.length > 120) err.name_kk = t.statuses.errTitleRequired;
      }

      const nextImg = row.image_url.trim();
      const baseImg = (base?.image_url ?? '').trim();
      if (nextImg !== baseImg && nextImg && (!nextImg.startsWith('https://') || nextImg.length > 1024)) {
        err.image_url = t.statuses.scaleErrImageHttps;
      }

      if (Object.keys(err).length > 0) {
        hasClientError = true;
        nextRowErrors[row.id] = err;
      } else {
        const item: LoyaltyScaleTierPatch = {
          id: row.id,
          min_turnover: minNorm,
          max_turnover: maxNorm,
          percent: pctNorm,
        };
        if (base) {
          if (nextNameRu !== (base.name_ru ?? '')) item.name_ru = nextNameRu;
          if (nextNameKk !== (base.name_kk ?? '')) item.name_kk = nextNameKk;
          const nextDescRu = row.description_ru.trim() || null;
          const baseDescRu = (base.description_ru ?? '').trim() || null;
          if (nextDescRu !== baseDescRu) item.description_ru = nextDescRu;
          const nextDescKk = row.description_kk.trim() || null;
          const baseDescKk = (base.description_kk ?? '').trim() || null;
          if (nextDescKk !== baseDescKk) item.description_kk = nextDescKk;
          const normalizedImg = nextImg || null;
          if (normalizedImg !== (baseImg || null)) item.image_url = normalizedImg;
          if (row.is_active !== base.is_active) item.is_active = row.is_active;
        }
        patchItems.push(item);
      }
    }

    setRowErrors(nextRowErrors);
    if (hasClientError) {
      setSubmitError(t.errors.VALIDATION_ERROR);
      requestAnimationFrame(() => {
        const firstInvalid = formRef.current?.querySelector<HTMLElement>('[aria-invalid="true"]');
        firstInvalid?.focus();
      });
      return;
    }

    const requestBody: LoyaltyScaleSaveRequest = {
      expected_version: version,
      tiers: patchItems,
    };

    setSaving(true);
    try {
      const saved = await saveLoyaltyScale(session.api, businessId, requestBody);
      const sorted = sortTiersStable(Array.isArray(saved.tiers) ? saved.tiers : []);
      setVersion(saved.version);
      setBaselineTiers(sorted);
      setDraftRows(toScaleDraftRows(sorted));
      setRowErrors({});
      setConflictHighlights({});
      setSaveNotice(
        saved.changed
          ? t.statuses.scaleSavedVersion(saved.version)
          : t.statuses.scaleSavedUnchanged(saved.version)
      );
      await queryClient.invalidateQueries({
        queryKey: [...privateKey, 'loyalty-tiers', businessId],
      });
      onSaved();
    } catch (err) {
      if (err instanceof ApiError && (err.status === 404 || err.status === 405) && err.code !== 'ADMIN_RESOURCE_NOT_FOUND') {
        onUnsupported();
        return;
      }
      const msg = messageForError(err, locale);
      setSubmitError(msg);
      if (err instanceof ApiError && err.detail) {
        const reason = err.detail.reason;
        if (reason === 'LOYALTY_SCALE_VERSION_CONFLICT') {
          setVersionConflict({ currentVersion: err.detail.currentVersion });
        } else if (reason === 'LOYALTY_SCALE_RANGE_OVERLAP') {
          const highlights: Record<string, ScaleHighlightInfo> = {};
          const levelById = new Map(draftRows.map(r => [r.id, r.level]));
          const addHighlight = (id: string, otherLevel: number | undefined, fields: readonly SafeErrorField[]) => {
            const existing = highlights[id] ?? { fields: new Set<SafeErrorField>(), otherLevels: [] };
            const targetFields = fields.length > 0 ? fields : (['min_turnover', 'max_turnover'] as SafeErrorField[]);
            for (const f of targetFields) existing.fields.add(f);
            if (typeof otherLevel === 'number' && !existing.otherLevels.includes(otherLevel)) {
              existing.otherLevels.push(otherLevel);
            }
            highlights[id] = existing;
          };
          for (const conflict of err.detail.scaleConflicts ?? []) {
            const levelA = conflict.levels?.[0] ?? levelById.get(conflict.tier_id);
            const levelB = conflict.levels?.[1] ?? levelById.get(conflict.other_tier_id);
            addHighlight(conflict.tier_id, levelB, conflict.fields);
            addHighlight(conflict.other_tier_id, levelA, conflict.fields);
          }
          setConflictHighlights(highlights);
        } else if (reason === 'LOYALTY_SCALE_INVALID_RANGE' && err.detail.tierId) {
          const fields = err.detail.fields?.length
            ? err.detail.fields
            : (['min_turnover', 'max_turnover'] as SafeErrorField[]);
          setConflictHighlights({
            [err.detail.tierId]: {
              fields: new Set(fields),
              otherLevels: [],
              message: msg,
            },
          });
        } else if (
          reason === 'LOYALTY_SCALE_INCOMPLETE'
          || reason === 'LOYALTY_SCALE_UNKNOWN_TIER'
          || reason === 'LOYALTY_SCALE_DUPLICATE_TIER'
        ) {
          setNeedsServerReload(true);
          if (err.detail.tierIds?.length) {
            const highlights: Record<string, ScaleHighlightInfo> = {};
            for (const id of err.detail.tierIds) {
              highlights[id] = { fields: new Set(['min_turnover', 'max_turnover']), otherLevels: [] };
            }
            setConflictHighlights(highlights);
          }
        }
      }
      requestAnimationFrame(() => {
        const alertEl = formRef.current?.querySelector<HTMLElement>('[role="alert"]');
        if (typeof alertEl?.scrollIntoView === 'function') {
          alertEl.scrollIntoView({ block: 'center' });
        }
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="surface-card scale-editor-card" aria-labelledby="scale-editor-heading">
      <div className="scale-editor-header">
        <div>
          <div className="scale-editor-title-row">
            <h2 id="scale-editor-heading">{t.statuses.scaleEditorTitle}</h2>
            {!loading && !loadError && (
              <StatusPill tone="neutral">{t.statuses.scaleVersionBadge(version)}</StatusPill>
            )}
          </div>
          <p className="muted-copy" style={{ marginTop: 4 }}>{t.statuses.scaleEditorSubtitle}</p>
        </div>
        <button className="button button-secondary" type="button" onClick={onClose} disabled={saving}>
          {t.statuses.closeScaleBtn}
        </button>
      </div>

      {loading ? (
        <LoadingPage label={t.statuses.scaleLoading} />
      ) : loadError ? (
        <ErrorNotice error={loadError} retry={() => { void loadScale(); }} />
      ) : draftRows.length === 0 ? (
        <p className="table-empty">{t.statuses.scaleEmptyForEditor}</p>
      ) : (
        <form ref={formRef} className="mutation-form" onSubmit={handleSubmit} noValidate>
          {saveNotice && (
            <div className="notice-banner notice-banner--success" role="status">
              {saveNotice}
            </div>
          )}

          {submitError && (
            <div className="form-error" role="alert">
              <p style={{ margin: 0 }}>{submitError}</p>
              {(versionConflict !== null || needsServerReload) && (
                <div style={{ marginTop: 8 }}>
                  <button
                    type="button"
                    className="button button-secondary"
                    onClick={() => { void loadScale(); }}
                    disabled={saving}
                  >
                    {t.statuses.scaleLoadActualBtn}
                  </button>
                </div>
              )}
            </div>
          )}

          <div className="scale-editor-list">
            {draftRows.map(row => {
              const title = locale === 'kk' ? (row.name_kk || row.name_ru) : row.name_ru;
              const errors = rowErrors[row.id] ?? {};
              const highlight = conflictHighlights[row.id];
              const isHighlighted = Boolean(highlight);
              const minInvalid = Boolean(errors.min_turnover) || Boolean(highlight?.fields.has('min_turnover'));
              const maxInvalid = Boolean(errors.max_turnover) || Boolean(highlight?.fields.has('max_turnover'));
              const pctInvalid = Boolean(errors.percent) || Boolean(highlight?.fields.has('percent'));
              const minErrorId = `scale-min-err-${row.id}`;
              const maxErrorId = `scale-max-err-${row.id}`;
              const pctErrorId = `scale-pct-err-${row.id}`;

              return (
                <article
                  key={row.id}
                  data-scale-tier-id={row.id}
                  className={`scale-tier-card${isHighlighted ? ' scale-tier-card--conflict' : ''}`}
                >
                  <div className="scale-tier-card-head">
                    <div>
                      <strong className="mono-value">#{row.level}</strong>{' '}
                      <strong>{title}</strong>
                    </div>
                    <label className="checkbox-row" htmlFor={`scale-active-${row.id}`}>
                      <input
                        id={`scale-active-${row.id}`}
                        type="checkbox"
                        checked={row.is_active}
                        disabled={saving}
                        onChange={e => updateRow(row.id, { is_active: e.target.checked }, ['is_active'])}
                      />
                      <span>{t.statuses.fieldIsActive}</span>
                    </label>
                  </div>

                  {highlight && (highlight.otherLevels.length > 0 || highlight.message) && (
                    <p className="field-error" style={{ margin: 0 }}>
                      {highlight.otherLevels.length > 0
                        ? t.statuses.scaleRowConflictHint(highlight.otherLevels)
                        : highlight.message}
                    </p>
                  )}

                  <div className="scale-tier-grid">
                    <label className="form-control" htmlFor={`scale-min-${row.id}`}>
                      {t.statuses.fieldThresholdMin}
                      <NumericInput
                        id={`scale-min-${row.id}`}
                        decimal
                        min={0}
                        value={row.min_turnover}
                        disabled={saving}
                        aria-invalid={minInvalid ? 'true' : 'false'}
                        aria-describedby={errors.min_turnover ? minErrorId : undefined}
                        onChange={e => updateRow(row.id, { min_turnover: e.target.value }, ['min_turnover'])}
                      />
                      {errors.min_turnover && (
                        <span id={minErrorId} className="field-error">{errors.min_turnover}</span>
                      )}
                    </label>

                    <div className="scale-tier-max-wrap">
                      <label className="form-control" htmlFor={`scale-max-${row.id}`}>
                        {t.statuses.fieldThresholdMax}
                        <NumericInput
                          id={`scale-max-${row.id}`}
                          decimal
                          min={0}
                          disabled={saving || row.unbounded}
                          placeholder={t.statuses.scaleUnboundedLabel}
                          value={row.unbounded ? '' : row.max_turnover}
                          aria-invalid={maxInvalid ? 'true' : 'false'}
                          aria-describedby={errors.max_turnover ? maxErrorId : undefined}
                          onChange={e => updateRow(row.id, { max_turnover: e.target.value }, ['max_turnover'])}
                        />
                        {errors.max_turnover && (
                          <span id={maxErrorId} className="field-error">{errors.max_turnover}</span>
                        )}
                      </label>
                      <label className="checkbox-row" htmlFor={`scale-unbounded-${row.id}`}>
                        <input
                          id={`scale-unbounded-${row.id}`}
                          type="checkbox"
                          checked={row.unbounded}
                          disabled={saving}
                          onChange={e =>
                            updateRow(
                              row.id,
                              { unbounded: e.target.checked, max_turnover: e.target.checked ? '' : row.max_turnover },
                              ['max_turnover']
                            )
                          }
                        />
                        <span>{t.statuses.scaleUnboundedLabel}</span>
                      </label>
                    </div>

                    <label className="form-control" htmlFor={`scale-percent-${row.id}`}>
                      {t.statuses.fieldPercent}
                      <NumericInput
                        id={`scale-percent-${row.id}`}
                        decimal
                        min={0}
                        max={100}
                        disabled={saving}
                        value={row.percent}
                        aria-invalid={pctInvalid ? 'true' : 'false'}
                        aria-describedby={errors.percent ? pctErrorId : undefined}
                        onChange={e => updateRow(row.id, { percent: e.target.value }, ['percent'])}
                      />
                      {errors.percent && (
                        <span id={pctErrorId} className="field-error">{errors.percent}</span>
                      )}
                    </label>
                  </div>

                  <details className="business-raw-details">
                    <summary>{t.statuses.scaleOptionalToggle}</summary>
                    <div style={{ display: 'grid', gap: 10, marginTop: 8 }}>
                      <div className="mutation-form-row--two-col">
                        <label className="form-control" htmlFor={`scale-name-kk-${row.id}`}>
                          {t.statuses.fieldTitleKk}
                          <input
                            id={`scale-name-kk-${row.id}`}
                            type="text"
                            maxLength={120}
                            disabled={saving}
                            value={row.name_kk}
                            aria-invalid={errors.name_kk ? 'true' : 'false'}
                            onChange={e => updateRow(row.id, { name_kk: e.target.value }, ['name_kk'])}
                          />
                          {errors.name_kk && <span className="field-error">{errors.name_kk}</span>}
                        </label>
                        <label className="form-control" htmlFor={`scale-name-ru-${row.id}`}>
                          {t.statuses.fieldTitleRu}
                          <input
                            id={`scale-name-ru-${row.id}`}
                            type="text"
                            maxLength={120}
                            disabled={saving}
                            value={row.name_ru}
                            aria-invalid={errors.name_ru ? 'true' : 'false'}
                            onChange={e => updateRow(row.id, { name_ru: e.target.value }, ['name_ru'])}
                          />
                          {errors.name_ru && <span className="field-error">{errors.name_ru}</span>}
                        </label>
                      </div>
                      <div className="mutation-form-row--two-col">
                        <label className="form-control" htmlFor={`scale-desc-kk-${row.id}`}>
                          {t.statuses.fieldDescKk}
                          <textarea
                            id={`scale-desc-kk-${row.id}`}
                            rows={2}
                            maxLength={2000}
                            disabled={saving}
                            value={row.description_kk}
                            onChange={e => updateRow(row.id, { description_kk: e.target.value }, ['description_kk'])}
                          />
                        </label>
                        <label className="form-control" htmlFor={`scale-desc-ru-${row.id}`}>
                          {t.statuses.fieldDescRu}
                          <textarea
                            id={`scale-desc-ru-${row.id}`}
                            rows={2}
                            maxLength={2000}
                            disabled={saving}
                            value={row.description_ru}
                            onChange={e => updateRow(row.id, { description_ru: e.target.value }, ['description_ru'])}
                          />
                        </label>
                      </div>
                      <div className="tier-attachment-row">
                        <label htmlFor={`scale-image-${row.id}`}>{t.statuses.fieldAttachment}</label>
                        <ImageUploadField
                          id={`scale-image-${row.id}`}
                          value={row.image_url}
                          onChange={url => updateRow(row.id, { image_url: url }, ['image_url'])}
                          purpose="promotion"
                          hint={t.statuses.imageHint}
                          onUploadingChange={uploading =>
                            setUploadingIds(curr =>
                              uploading
                                ? (curr.includes(row.id) ? curr : [...curr, row.id])
                                : curr.filter(item => item !== row.id)
                            )
                          }
                          disabled={saving}
                        />
                        {errors.image_url && <span className="field-error">{errors.image_url}</span>}
                      </div>
                    </div>
                  </details>
                </article>
              );
            })}
          </div>

          <div className="scale-summary-box">
            <h3>{t.statuses.scaleSummaryTitle}</h3>
            <ul className="scale-summary-list">
              {previewInfo.ordered.map(({ row, minText, maxText, pctText }) => {
                const label = locale === 'kk' ? (row.name_kk || row.name_ru) : row.name_ru;
                return (
                  <li key={row.id}>
                    {t.statuses.scaleSummaryRow(row.level, label, minText, maxText, pctText, row.is_active)}
                  </li>
                );
              })}
            </ul>
            {previewInfo.warnings.map((warn, idx) => (
              <p key={idx} className="notice-banner notice-banner--warning" style={{ margin: '4px 0 0' }}>
                {warn}
              </p>
            ))}
          </div>

          <div className="scale-editor-actions">
            <button className="button button-primary" type="submit" disabled={saving || uploadingIds.length > 0}>
              {saving ? t.statuses.savingScaleBtn : t.statuses.saveScaleBtn}
            </button>
            <button
              className="button button-secondary"
              type="button"
              onClick={() => { void loadScale(); }}
              disabled={saving || uploadingIds.length > 0}
            >
              {t.statuses.scaleLoadActualBtn}
            </button>
            <button className="button button-secondary" type="button" onClick={onClose} disabled={saving || uploadingIds.length > 0}>
              {t.statuses.cancelBtn}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}

interface TierDialogProps {
  businessId: string;
  tier?: LoyaltyTier;
  onClose: () => void;
  onSaved: () => void;
}

type TierFieldKey =
  | 'level'
  | 'percent'
  | 'thresholdMin'
  | 'thresholdMax'
  | 'titleKk'
  | 'titleRu'
  | 'descriptionKk'
  | 'descriptionRu'
  | 'imageUrl'
  | 'isActive';

const TIER_FIELD_ORDER: readonly TierFieldKey[] = [
  'level',
  'percent',
  'thresholdMin',
  'thresholdMax',
  'titleKk',
  'titleRu',
  'descriptionKk',
  'descriptionRu',
  'imageUrl',
  'isActive',
];

const TIER_FIELD_ERROR_ID: Record<TierFieldKey, string> = {
  level: 'tier-level-error',
  percent: 'tier-percent-error',
  thresholdMin: 'tier-min-error',
  thresholdMax: 'tier-max-error',
  titleKk: 'tier-title-kk-error',
  titleRu: 'tier-title-ru-error',
  descriptionKk: 'tier-desc-kk-error',
  descriptionRu: 'tier-desc-ru-error',
  imageUrl: 'tier-image-error',
  isActive: 'tier-is-active-error',
};

const SAFE_ERROR_TO_TIER_FIELD: Partial<Record<SafeErrorField, TierFieldKey>> = {
  level: 'level',
  percent: 'percent',
  min_turnover: 'thresholdMin',
  max_turnover: 'thresholdMax',
  name_kk: 'titleKk',
  name_ru: 'titleRu',
  description_kk: 'descriptionKk',
  description_ru: 'descriptionRu',
  image_url: 'imageUrl',
  is_active: 'isActive',
};

interface TierErrorGroup {
  id: string;
  fields: TierFieldKey[];
  anchor: TierFieldKey;
  message: string;
  isJointRange?: boolean;
}

export function TierDialog({ businessId, tier, onClose, onSaved }: TierDialogProps) {
  const { session } = useAdminSession();
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const queryClient = useQueryClient();

  const [level, setLevel] = useState<string>(tier?.level != null ? String(tier.level) : '1');
  const [titleRu, setTitleRu] = useState(tier?.name_ru ?? '');
  const [titleKk, setTitleKk] = useState(tier?.name_kk ?? '');
  const [descriptionRu, setDescriptionRu] = useState(tier?.description_ru ?? '');
  const [descriptionKk, setDescriptionKk] = useState(tier?.description_kk ?? '');
  const [thresholdMin, setThresholdMin] = useState<string>(tier?.min_turnover != null ? String(tier.min_turnover) : '0');
  const [thresholdMax, setThresholdMax] = useState<string>(tier?.max_turnover != null ? String(tier.max_turnover) : '');
  const [percent, setPercent] = useState<string>(tier?.percent != null ? String(tier.percent) : '2');
  const [imageUrl, setImageUrl] = useState<string>(tier?.image_url ?? '');
  const [isActive, setIsActive] = useState<boolean>(tier?.is_active ?? true);

  const [generalError, setGeneralError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<TierFieldKey, string>>>({});
  const [clientErrorGroups, setClientErrorGroups] = useState<TierErrorGroup[]>([]);
  const [serverErrorGroups, setServerErrorGroups] = useState<TierErrorGroup[]>([]);
  const [saving, setSaving] = useState(false);
  const [uploadingImage, setUploadingImage] = useState(false);

  const editCounterRef = useRef(0);
  const lastEditedSeqRef = useRef<Partial<Record<TierFieldKey, number>>>({});

  const pickAnchorField = (fields: readonly TierFieldKey[]): TierFieldKey => {
    let bestField: TierFieldKey | null = null;
    let bestSeq = 0;
    for (const field of fields) {
      const seq = lastEditedSeqRef.current[field] ?? 0;
      if (seq > bestSeq) {
        bestSeq = seq;
        bestField = field;
      }
    }
    if (bestField) return bestField;
    for (const ordered of TIER_FIELD_ORDER) {
      if (fields.includes(ordered)) return ordered;
    }
    return fields[0]!;
  };

  const updateErrorGroupsForEdit = (
    groups: readonly TierErrorGroup[],
    editedField: TierFieldKey,
  ): TierErrorGroup[] => {
    const next: TierErrorGroup[] = [];
    for (const group of groups) {
      if (!group.fields.includes(editedField)) {
        next.push(group);
        continue;
      }
      if (group.isJointRange) {
        continue;
      }
      const remaining = group.fields.filter(f => f !== editedField);
      if (remaining.length === 0) {
        continue;
      }
      next.push({
        ...group,
        fields: remaining,
        anchor: group.anchor === editedField ? pickAnchorField(remaining) : group.anchor,
      });
    }
    return next;
  };

  const handleFieldEdited = (field: TierFieldKey) => {
    editCounterRef.current += 1;
    lastEditedSeqRef.current[field] = editCounterRef.current;

    setFieldErrors(current => {
      if (!current[field]) return current;
      const next = { ...current };
      delete next[field];
      return next;
    });
    setClientErrorGroups(current =>
      current.length === 0 ? current : updateErrorGroupsForEdit(current, field),
    );
    setServerErrorGroups(current =>
      current.length === 0 ? current : updateErrorGroupsForEdit(current, field),
    );
  };

  const allErrorGroups = [...clientErrorGroups, ...serverErrorGroups];

  const isFieldInvalid = (field: TierFieldKey): boolean =>
    Boolean(fieldErrors[field]) || allErrorGroups.some(group => group.fields.includes(field));

  const describeField = (field: TierFieldKey): string | undefined => {
    const ids: string[] = [];
    if (fieldErrors[field]) {
      ids.push(TIER_FIELD_ERROR_ID[field]);
    }
    for (const group of allErrorGroups) {
      if (group.fields.includes(field)) {
        const anchorId = TIER_FIELD_ERROR_ID[group.anchor];
        if (!ids.includes(anchorId)) ids.push(anchorId);
      }
    }
    return ids.length > 0 ? ids.join(' ') : undefined;
  };

  const renderFieldError = (field: TierFieldKey) => {
    const msg = fieldErrors[field] ?? allErrorGroups.find(group => group.anchor === field)?.message ?? '';
    if (!msg) return null;
    return (
      <span id={TIER_FIELD_ERROR_ID[field]} className="form-error" role="alert">
        {msg}
      </span>
    );
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setGeneralError('');
    setServerErrorGroups([]);

    const cleanTitleRu = titleRu.trim();
    const cleanTitleKk = titleKk.trim();
    const cleanDescRu = descriptionRu.trim();
    const cleanDescKk = descriptionKk.trim();
    const cleanImageUrl = imageUrl.trim();

    const minNorm = normalizeDecimalInput(thresholdMin);
    const maxNorm = thresholdMax.trim() !== '' ? normalizeDecimalInput(thresholdMax) : '';
    const pctNorm = normalizeDecimalInput(percent);

    const parsedLevel = Number(level.trim());
    const minNum = minNorm !== '' ? Number(minNorm) : Number.NaN;
    const maxNum = maxNorm !== '' ? Number(maxNorm) : null;
    const pctNum = pctNorm !== '' ? Number(pctNorm) : Number.NaN;

    const minPrecisionError =
      minNorm !== '' && (!hasAtMostTwoDecimals(minNorm) || !Number.isFinite(minNum) || minNum > 999_999_999.99);
    const maxPrecisionError =
      maxNorm !== '' && (!hasAtMostTwoDecimals(maxNorm) || maxNum === null || !Number.isFinite(maxNum) || maxNum > 999_999_999.99);
    const pctPrecisionError =
      pctNorm !== '' && (!hasAtMostTwoDecimals(pctNorm) || !Number.isFinite(pctNum) || pctNum < 0 || pctNum > 100);

    const nextFieldErrors: Partial<Record<TierFieldKey, string>> = {};
    const nextClientGroups: TierErrorGroup[] = [];

    if (!Number.isInteger(parsedLevel) || parsedLevel < 1 || parsedLevel > 100) {
      nextFieldErrors.level = t.statuses.errLevelRequired;
    }

    const minMissingOrNegative = !minNorm || !Number.isFinite(minNum) || minNum < 0;
    if (minMissingOrNegative) {
      nextFieldErrors.thresholdMin = t.statuses.errThresholds;
    } else if (minPrecisionError) {
      nextFieldErrors.thresholdMin = t.statuses.errTurnoverPrecision;
    }

    if (maxNum !== null && maxPrecisionError) {
      nextFieldErrors.thresholdMax = t.statuses.errTurnoverPrecision;
    } else if (
      !minMissingOrNegative &&
      !minPrecisionError &&
      maxNum !== null &&
      (!Number.isFinite(maxNum) || maxNum <= minNum)
    ) {
      const rangeFields: TierFieldKey[] = ['thresholdMin', 'thresholdMax'];
      nextClientGroups.push({
        id: 'client-turnover-order',
        fields: rangeFields,
        anchor: pickAnchorField(rangeFields),
        message: t.statuses.errThresholds,
        isJointRange: true,
      });
    }

    if (!pctNorm || !Number.isFinite(pctNum) || pctNum < 0 || pctNum > 100) {
      nextFieldErrors.percent = t.statuses.errPercent;
    } else if (pctPrecisionError) {
      nextFieldErrors.percent = t.statuses.errPercentPrecision;
    }

    const missingTitleFields: TierFieldKey[] = [];
    if (!cleanTitleKk) missingTitleFields.push('titleKk');
    if (!cleanTitleRu) missingTitleFields.push('titleRu');
    if (missingTitleFields.length > 0) {
      nextClientGroups.push({
        id: 'client-title-required',
        fields: missingTitleFields,
        anchor: pickAnchorField(missingTitleFields),
        message: t.statuses.errTitleRequired,
      });
    }

    setFieldErrors(nextFieldErrors);
    setClientErrorGroups(nextClientGroups);
    if (Object.keys(nextFieldErrors).length > 0 || nextClientGroups.length > 0) return;

    const payload: LoyaltyTierInput = {
      level: parsedLevel,
      name_ru: cleanTitleRu,
      name_kk: cleanTitleKk,
      description_ru: cleanDescRu || null,
      description_kk: cleanDescKk || null,
      min_turnover: minNum,
      max_turnover: maxNum,
      percent: pctNum,
      image_url: cleanImageUrl || null,
      is_active: isActive,
    };

    setSaving(true);
    try {
      if (tier) {
        await session.api.request(
          `/admin/businesses/${encodeURIComponent(businessId)}/loyalty-tiers/${encodeURIComponent(tier.id)}`,
          { method: 'PATCH', body: payload }
        );
      } else {
        await session.api.request(
          `/admin/businesses/${encodeURIComponent(businessId)}/loyalty-tiers`,
          { method: 'POST', body: payload }
        );
      }

      await queryClient.invalidateQueries({
        queryKey: [...privateKey, 'loyalty-tiers', businessId],
      });
      onSaved();
      onClose();
    } catch (err) {
      const msg = messageForError(err, locale);
      if (err instanceof ApiError && err.detail) {
        if (err.detail.conflictKind === 'turnover_overlap') {
          const rangeFields: TierFieldKey[] = ['thresholdMin', 'thresholdMax'];
          setServerErrorGroups([{
            id: 'server-turnover-overlap',
            fields: rangeFields,
            anchor: pickAnchorField(rangeFields),
            message: msg,
            isJointRange: true,
          }]);
          return;
        }
        if (err.detail.conflictKind === 'level_exists') {
          setServerErrorGroups([{
            id: 'server-level-exists',
            fields: ['level'],
            anchor: 'level',
            message: msg,
          }]);
          return;
        }
        if (err.detail.validationHint === 'turnover_order') {
          const rangeFields: TierFieldKey[] = ['thresholdMin', 'thresholdMax'];
          setServerErrorGroups([{
            id: 'server-turnover-order',
            fields: rangeFields,
            anchor: pickAnchorField(rangeFields),
            message: msg,
            isJointRange: true,
          }]);
          return;
        }
        if (err.detail.fields?.length) {
          const mappedFields: TierFieldKey[] = [];
          for (const safeField of err.detail.fields) {
            const mapped = SAFE_ERROR_TO_TIER_FIELD[safeField];
            if (mapped && !mappedFields.includes(mapped)) {
              mappedFields.push(mapped);
            }
          }
          if (mappedFields.length > 0) {
            const isJointRange =
              mappedFields.length === 2
              && mappedFields.includes('thresholdMin')
              && mappedFields.includes('thresholdMax');
            setServerErrorGroups([{
              id: 'server-fields',
              fields: mappedFields,
              anchor: pickAnchorField(mappedFields),
              message: msg,
              isJointRange,
            }]);
            return;
          }
        }
      }
      setGeneralError(msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <DialogFrame
      title={tier ? t.statuses.dialogEditTitle : t.statuses.dialogCreateTitle}
      onClose={onClose}
      className="mutation-dialog--wide tier-dialog"
    >
      <form className="mutation-form" onSubmit={handleSubmit} noValidate>
        {generalError && <p id="tier-form-error" className="form-error" role="alert">{generalError}</p>}

        {/* Row 1: Номер уровня | Процент начисления бонусов */}
        <div className="mutation-form-row--two-col">
          <label className="form-control" htmlFor="tier-level">
            {t.statuses.fieldLevel}
            <NumericInput
              id="tier-level"
              min={1}
              max={100}
              value={level}
              aria-invalid={isFieldInvalid('level')}
              aria-describedby={describeField('level')}
              onChange={e => {
                setLevel(e.target.value);
                handleFieldEdited('level');
              }}
            />
            {renderFieldError('level')}
          </label>

          <label className="form-control" htmlFor="tier-percent">
            {t.statuses.fieldPercent}
            <NumericInput
              id="tier-percent"
              min={0}
              max={100}
              step="any"
              decimal
              value={percent}
              aria-invalid={isFieldInvalid('percent')}
              aria-describedby={describeField('percent')}
              onChange={e => {
                setPercent(e.target.value);
                handleFieldEdited('percent');
              }}
            />
            {renderFieldError('percent')}
          </label>
        </div>

        {/* Row 2: Минимальный оборот | Максимальный оборот */}
        <div className="mutation-form-row--two-col">
          <label className="form-control" htmlFor="tier-min">
            {t.statuses.fieldThresholdMin}
            <NumericInput
              id="tier-min"
              min={0}
              step="any"
              decimal
              value={thresholdMin}
              aria-invalid={isFieldInvalid('thresholdMin')}
              aria-describedby={describeField('thresholdMin')}
              onChange={e => {
                setThresholdMin(e.target.value);
                handleFieldEdited('thresholdMin');
              }}
            />
            {renderFieldError('thresholdMin')}
          </label>

          <label className="form-control" htmlFor="tier-max">
            {t.statuses.fieldThresholdMax}
            <NumericInput
              id="tier-max"
              min={0}
              step="any"
              decimal
              placeholder={t.statuses.placeholderThresholdMax}
              value={thresholdMax}
              aria-invalid={isFieldInvalid('thresholdMax')}
              aria-describedby={describeField('thresholdMax')}
              onChange={e => {
                setThresholdMax(e.target.value);
                handleFieldEdited('thresholdMax');
              }}
            />
            {renderFieldError('thresholdMax')}
          </label>
        </div>

        {/* Row 3: Название KK | Название RU */}
        <div className="mutation-form-row--two-col">
          <label className="form-control" htmlFor="tier-title-kk">
            {t.statuses.fieldTitleKk}
            <input
              id="tier-title-kk"
              type="text"
              required
              maxLength={120}
              placeholder="мысалы, Базалық"
              value={titleKk}
              aria-invalid={isFieldInvalid('titleKk')}
              aria-describedby={describeField('titleKk')}
              onChange={e => {
                setTitleKk(e.target.value);
                handleFieldEdited('titleKk');
              }}
            />
            {renderFieldError('titleKk')}
          </label>

          <label className="form-control" htmlFor="tier-title-ru">
            {t.statuses.fieldTitleRu}
            <input
              id="tier-title-ru"
              type="text"
              required
              maxLength={120}
              placeholder="например, Базовый"
              value={titleRu}
              aria-invalid={isFieldInvalid('titleRu')}
              aria-describedby={describeField('titleRu')}
              onChange={e => {
                setTitleRu(e.target.value);
                handleFieldEdited('titleRu');
              }}
            />
            {renderFieldError('titleRu')}
          </label>
        </div>

        {/* Row 4: Описание KK | Описание RU */}
        <div className="mutation-form-row--two-col">
          <label className="form-control" htmlFor="tier-desc-kk">
            {t.statuses.fieldDescKk}
            <textarea
              id="tier-desc-kk"
              rows={2}
              maxLength={500}
              placeholder="Бонустарды есептеу шарттары"
              value={descriptionKk}
              aria-invalid={isFieldInvalid('descriptionKk')}
              aria-describedby={describeField('descriptionKk')}
              onChange={e => {
                setDescriptionKk(e.target.value);
                handleFieldEdited('descriptionKk');
              }}
            />
            {renderFieldError('descriptionKk')}
          </label>

          <label className="form-control" htmlFor="tier-desc-ru">
            {t.statuses.fieldDescRu}
            <textarea
              id="tier-desc-ru"
              rows={2}
              maxLength={500}
              placeholder="Условия начисления бонусов"
              value={descriptionRu}
              aria-invalid={isFieldInvalid('descriptionRu')}
              aria-describedby={describeField('descriptionRu')}
              onChange={e => {
                setDescriptionRu(e.target.value);
                handleFieldEdited('descriptionRu');
              }}
            />
            {renderFieldError('descriptionRu')}
          </label>
        </div>

        {/* Row 5: Вложение */}
        <div className="tier-attachment-row">
          <label htmlFor="tier-image">{t.statuses.fieldAttachment}</label>
          <ImageUploadField
            id="tier-image"
            value={imageUrl}
            onChange={url => {
              setImageUrl(url);
              handleFieldEdited('imageUrl');
            }}
            purpose="promotion"
            hint={t.statuses.imageHint}
            onUploadingChange={setUploadingImage}
            disabled={saving}
          />
          {renderFieldError('imageUrl')}
        </div>

        {/* Row 6: Показывать статус в приложении */}
        <div className="form-control">
          <label className="checkbox-row" htmlFor="tier-is-active">
            <input
              id="tier-is-active"
              type="checkbox"
              checked={isActive}
              aria-invalid={isFieldInvalid('isActive')}
              aria-describedby={describeField('isActive')}
              onChange={e => {
                setIsActive(e.target.checked);
                handleFieldEdited('isActive');
              }}
            />
            <span>{t.statuses.fieldIsActive}</span>
          </label>
          {renderFieldError('isActive')}
        </div>

        {/* Actions: Left-aligned buttons */}
        <div className="dialog-actions dialog-actions--left">
          <button className="button button-primary" type="submit" disabled={saving || uploadingImage}>
            {saving ? t.statuses.savingBtn : t.statuses.saveBtn}
          </button>
          <button className="button button-secondary" type="button" onClick={onClose} disabled={saving || uploadingImage}>
            {t.statuses.cancelBtn}
          </button>
        </div>
      </form>
    </DialogFrame>
  );
}

export function StatusesPage() {
  const { view, session } = useAdminSession();
  const { setActiveBusiness } = useActiveBusiness();
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const queryClient = useQueryClient();
  const isSuperadmin = view.status === 'authenticated' && view.admin.role === 'superadmin';
  const businessesQuery = useAllBusinesses(isSuperadmin);

  const managerBusinessId =
    view.status === 'authenticated' && view.admin.business
      ? view.admin.business.id
      : '';

  const [selectedBusinessId, setSelectedBusinessId] = useState<string>('');
  const activeBusinessId = isSuperadmin
    ? selectedBusinessId || (businessesQuery.items[0]?.id ?? '')
    : managerBusinessId;

  useEffect(() => {
    if (!isSuperadmin) return;
    const selected = activeBusinessId ? businessesQuery.items.find(b => b.id === activeBusinessId) : null;
    setActiveBusiness(selected ? {
      id: selected.id,
      name: selected.name,
      logo_url: selected.logo_url,
      android_app_id: selected.android_app_id,
    } : null);
  }, [activeBusinessId, businessesQuery.items, isSuperadmin, setActiveBusiness]);

  useEffect(() => {
    return () => {
      setActiveBusiness(null);
    };
  }, [setActiveBusiness]);

  const tiersQuery = useLoyaltyTiers(activeBusinessId);
  const [editingTier, setEditingTier] = useState<LoyaltyTier | 'new' | null>(null);
  const [scaleOpenForBusinessId, setScaleOpenForBusinessId] = useState<string | null>(null);
  const [scaleUnsupportedForBusinessId, setScaleUnsupportedForBusinessId] = useState<string | null>(null);
  const [actionError, setActionError] = useState('');
  const expansion = useTableExpansion();
  const sortedTiers = useMemo(
    () =>
      Array.isArray(tiersQuery.data)
        ? [...tiersQuery.data].sort((a, b) => a.level - b.level || a.priority - b.priority)
        : [],
    [tiersQuery.data]
  );
  const pagination = useClientPagination(sortedTiers, activeBusinessId, 25);
  const compact = useCompactRows(pagination.pagedItems, expansion);
  const isScaleOpen = Boolean(activeBusinessId && scaleOpenForBusinessId === activeBusinessId);
  const isScaleUnsupported = Boolean(activeBusinessId && scaleUnsupportedForBusinessId === activeBusinessId);

  const handleDelete = async (tier: LoyaltyTier) => {
    const tierName = locale === 'kk' ? (tier.name_kk || tier.name_ru) : tier.name_ru;
    if (!window.confirm(t.statuses.confirmDelete(tierName))) return;
    setActionError('');
    try {
      await session.api.request(
        `/admin/businesses/${encodeURIComponent(activeBusinessId)}/loyalty-tiers/${encodeURIComponent(tier.id)}`,
        { method: 'DELETE' }
      );
      setScaleOpenForBusinessId(null);
      await queryClient.invalidateQueries({
        queryKey: [...privateKey, 'loyalty-tiers', activeBusinessId],
      });
    } catch (err) {
      setActionError(messageForError(err, locale));
    }
  };

  return (
    <div className="page-stack">
      <div className="section-heading" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', flexWrap: 'wrap' }}>
        <div>
          <PageHeading title={t.statuses.title} subtitle={t.statuses.subtitle} />
        </div>
        {activeBusinessId && (
          <div className="statuses-heading-actions">
            {sortedTiers.length > 0 && !isScaleUnsupported && !isScaleOpen && (
              <button
                className="button button-secondary"
                type="button"
                onClick={() => setScaleOpenForBusinessId(activeBusinessId)}
              >
                {t.statuses.editScaleBtn}
              </button>
            )}
            <button
              className="button button-primary"
              type="button"
              onClick={() => setEditingTier('new')}
            >
              {t.statuses.addTierBtn}
            </button>
          </div>
        )}
      </div>

      {isScaleUnsupported && (
        <div className="notice-banner notice-banner--warning" role="status">
          {t.statuses.scaleUnsupportedFallback}
        </div>
      )}

      {isSuperadmin && (
        <section className="search-filter-section" style={{ marginBottom: '1rem' }}>
          <div className="filter-controls">
            <div className="form-control business-select">
              <label htmlFor="statuses-business">{t.statuses.businessLabel}</label>
              <BusinessSelect
                id="statuses-business"
                value={activeBusinessId}
                onChange={setSelectedBusinessId}
                businesses={businessesQuery}
              />
            </div>
          </div>
        </section>
      )}

      {actionError && <p className="form-error" role="alert">{actionError}</p>}

      {isScaleOpen && activeBusinessId && (
        <ScaleEditorSection
          businessId={activeBusinessId}
          locale={locale}
          onClose={() => setScaleOpenForBusinessId(null)}
          onSaved={() => {
            void tiersQuery.refetch();
          }}
          onUnsupported={() => {
            setScaleOpenForBusinessId(null);
            setScaleUnsupportedForBusinessId(activeBusinessId);
          }}
        />
      )}

      {!activeBusinessId ? (
        <section className="surface-card">
          <p className="table-empty">{t.content.selectBusinessHint}</p>
        </section>
      ) : tiersQuery.isPending ? (
        <LoadingPage label={t.statuses.loading} />
      ) : tiersQuery.isError ? (
        <ErrorNotice error={tiersQuery.error} retry={() => { void tiersQuery.refetch(); }} />
      ) : !tiersQuery.data || tiersQuery.data.length === 0 ? (
        <section className="surface-card">
          <p className="table-empty">{t.statuses.empty}</p>
        </section>
      ) : (
        <div className="table-card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t.statuses.colLevel}</th>
                  <th>{t.statuses.colTitle}</th>
                  <th>{t.statuses.colThreshold}</th>
                  <th>{t.statuses.colPercent}</th>
                  <th>{t.statuses.colStatus}</th>
                  <th aria-label="actions" />
                </tr>
              </thead>
              <tbody id={compact.bodyId}>
                {compact.visibleRows.map(tier => (
                  <tr key={tier.id}>
                    <td>
                      <span className="mono-value">#{tier.level}</span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                        {tier.image_url ? (
                          <img
                            src={tier.image_url}
                            alt=""
                            style={{ width: 36, height: 24, objectFit: 'cover', borderRadius: 4 }}
                          />
                        ) : null}
                        <div>
                          <strong>{locale === 'kk' ? (tier.name_kk || tier.name_ru) : tier.name_ru}</strong>
                          {(tier.description_ru || tier.description_kk) && (
                            <div className="muted-copy" style={{ fontSize: '0.8125rem' }}>
                              {locale === 'kk' ? (tier.description_kk || tier.description_ru) : tier.description_ru}
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td>
                      <span>{t.statuses.turnoverRange(Number(tier.min_turnover), tier.max_turnover != null ? Number(tier.max_turnover) : null)}</span>
                    </td>
                    <td>
                      <strong className="mono-value">{tier.percent}%</strong>
                    </td>
                    <td>
                      <StatusPill tone={tier.is_active ? 'positive' : 'neutral'}>
                        {tier.is_active ? t.content.statusShown : t.content.statusHidden}
                      </StatusPill>
                    </td>
                    <td className="align-right">
                      <span className="pagination-actions">
                        <button
                          className="link-button"
                          type="button"
                          onClick={() => setEditingTier(tier)}
                        >
                          {t.content.editBtn}
                        </button>
                        <button
                          className="link-button"
                          type="button"
                          onClick={() => void handleDelete(tier)}
                        >
                          {t.statuses.deleteBtn}
                        </button>
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <CompactTableToggle {...compact} />
          <Pagination page={pagination.page} onChange={pagination.setPage} />
        </div>
      )}

      {editingTier && (
        <TierDialog
          businessId={activeBusinessId}
          tier={typeof editingTier === 'object' ? editingTier : undefined}
          onClose={() => setEditingTier(null)}
          onSaved={() => {
            setScaleOpenForBusinessId(null);
            void tiersQuery.refetch();
          }}
        />
      )}
    </div>
  );
}
