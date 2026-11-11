import { useState, useEffect, type FormEvent } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { messageForError } from '../api/errors';
import { privateKey, useBusinesses, useLoyaltyTiers } from '../api/queries';
import type { LoyaltyTier, LoyaltyTierInput } from '../api/types';
import { useAdminSession } from '../auth/provider';
import { useActiveBusiness } from '../context/ActiveBusinessContext';
import { ErrorNotice, LoadingPage, PageHeading, StatusPill } from '../components/Feedback';
import { ImageUploadField } from '../components/ImageUploadField';
import { NumericInput } from '../components/NumericInput';
import { DialogFrame } from '../features/AdminMutations';
import { CompactTableToggle, useCompactRows, useTableExpansion } from '../components/CompactTable';
import { useLocale } from '../i18n/LocaleContext';
import { useAdminTranslation } from '../i18n/admin';

interface TierDialogProps {
  businessId: string;
  tier?: LoyaltyTier;
  onClose: () => void;
  onSaved: () => void;
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
  const [turnoverPeriodMonths, setTurnoverPeriodMonths] = useState<string>(
    tier?.turnover_period_months != null ? String(tier.turnover_period_months) : '6'
  );
  const [thresholdMin, setThresholdMin] = useState<string>(tier?.min_turnover != null ? String(tier.min_turnover) : '0');
  const [thresholdMax, setThresholdMax] = useState<string>(tier?.max_turnover != null ? String(tier.max_turnover) : '');
  const [percent, setPercent] = useState<string>(tier?.percent != null ? String(tier.percent) : '2');
  const [imageUrl, setImageUrl] = useState<string>(tier?.image_url ?? '');
  const [isActive, setIsActive] = useState<boolean>(tier?.is_active ?? true);

  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState({ level: '', period: '', thresholdMin: '', thresholdMax: '', percent: '' });
  const [saving, setSaving] = useState(false);
  const [uploadingImage, setUploadingImage] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');

    const cleanTitleRu = titleRu.trim();
    const cleanTitleKk = titleKk.trim();
    const cleanDescRu = descriptionRu.trim();
    const cleanDescKk = descriptionKk.trim();
    const cleanImageUrl = imageUrl.trim();

    if (!cleanTitleRu || !cleanTitleKk) {
      setError(t.statuses.errTitleRequired);
      return;
    }

    const parsedLevel = Number(level.trim());
    const parsedMonths = Number(turnoverPeriodMonths.trim());
    const minNum = Number(thresholdMin.trim());
    const maxNum = thresholdMax.trim() !== '' ? Number(thresholdMax.trim()) : null;
    const pctNum = Number(percent.trim());
    const nextFieldErrors = {
      level: !Number.isInteger(parsedLevel) || parsedLevel < 1 || parsedLevel > 100 ? t.statuses.errLevelRequired : '',
      period: !Number.isInteger(parsedMonths) || parsedMonths < 1 || parsedMonths > 36 ? t.statuses.errTurnoverPeriod : '',
      thresholdMin: !thresholdMin.trim() || !Number.isFinite(minNum) || minNum < 0 ? t.statuses.errThresholds : '',
      thresholdMax: maxNum !== null && (!Number.isFinite(maxNum) || !Number.isFinite(minNum) || maxNum <= minNum) ? t.statuses.errThresholds : '',
      percent: !Number.isFinite(pctNum) || pctNum < 0 || pctNum > 100 ? t.statuses.errPercent : '',
    };
    setFieldErrors(nextFieldErrors);
    if (Object.values(nextFieldErrors).some(Boolean)) return;

    const payload: LoyaltyTierInput = {
      level: parsedLevel,
      name_ru: cleanTitleRu,
      name_kk: cleanTitleKk,
      description_ru: cleanDescRu || null,
      description_kk: cleanDescKk || null,
      turnover_period_months: parsedMonths,
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
      setError(messageForError(err, locale));
    } finally {
      setSaving(false);
    }
  };

  return (
    <DialogFrame
      title={tier ? t.statuses.dialogEditTitle : t.statuses.dialogCreateTitle}
      onClose={onClose}
      className="mutation-dialog--wide"
    >
      <form className="mutation-form" onSubmit={handleSubmit} noValidate>
        {error && <p className="form-error" role="alert">{error}</p>}

        <label className="form-control" htmlFor="tier-level">
          {t.statuses.fieldLevel}
          <NumericInput
            id="tier-level"
            min={1}
            max={100}
            value={level}
            aria-invalid={Boolean(fieldErrors.level)}
            onChange={e => {
              setLevel(e.target.value);
              setFieldErrors(current => ({ ...current, level: '' }));
            }}
          />
          {fieldErrors.level && <span className="form-error">{fieldErrors.level}</span>}
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
            onChange={e => setTitleRu(e.target.value)}
          />
        </label>

        <label className="form-control" htmlFor="tier-title-kk">
          {t.statuses.fieldTitleKk}
          <input
            id="tier-title-kk"
            type="text"
            required
            maxLength={120}
            placeholder="мысалы, Базалық"
            value={titleKk}
            onChange={e => setTitleKk(e.target.value)}
          />
        </label>

        <label className="form-control" htmlFor="tier-desc-ru">
          {t.statuses.fieldDescRu}
          <textarea
            id="tier-desc-ru"
            rows={2}
            maxLength={500}
            placeholder="Условия начисления бонусов"
            value={descriptionRu}
            onChange={e => setDescriptionRu(e.target.value)}
          />
        </label>

        <label className="form-control" htmlFor="tier-desc-kk">
          {t.statuses.fieldDescKk}
          <textarea
            id="tier-desc-kk"
            rows={2}
            maxLength={500}
            placeholder="Бонустарды есептеу шарттары"
            value={descriptionKk}
            onChange={e => setDescriptionKk(e.target.value)}
          />
        </label>

        <label className="form-control" htmlFor="tier-period">
          {t.statuses.fieldTurnoverPeriodMonths}
          <NumericInput
            id="tier-period"
            min={1}
            max={36}
            value={turnoverPeriodMonths}
            aria-invalid={Boolean(fieldErrors.period)}
            onChange={e => {
              setTurnoverPeriodMonths(e.target.value);
              setFieldErrors(current => ({ ...current, period: '' }));
            }}
          />
          <span className="muted-copy">{t.statuses.fieldTurnoverPeriodHint}</span>
          {fieldErrors.period && <span className="form-error">{fieldErrors.period}</span>}
        </label>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
          <label className="form-control" htmlFor="tier-min">
            {t.statuses.fieldThresholdMin}
            <NumericInput
              id="tier-min"
              min={0}
              step="any"
              decimal
              value={thresholdMin}
              aria-invalid={Boolean(fieldErrors.thresholdMin)}
              onChange={e => {
                setThresholdMin(e.target.value);
                setFieldErrors(current => ({ ...current, thresholdMin: '' }));
              }}
            />
            {fieldErrors.thresholdMin && <span className="form-error">{fieldErrors.thresholdMin}</span>}
          </label>
          <label className="form-control" htmlFor="tier-max">
            {t.statuses.fieldThresholdMax}
            <NumericInput
              id="tier-max"
              min={0}
              step="any"
              decimal
              placeholder="Бессрочно / без предела"
              value={thresholdMax}
              aria-invalid={Boolean(fieldErrors.thresholdMax)}
              onChange={e => {
                setThresholdMax(e.target.value);
                setFieldErrors(current => ({ ...current, thresholdMax: '' }));
              }}
            />
            {fieldErrors.thresholdMax && <span className="form-error">{fieldErrors.thresholdMax}</span>}
          </label>
        </div>

        <label className="form-control" htmlFor="tier-percent">
          {t.statuses.fieldPercent}
          <NumericInput
            id="tier-percent"
            min={0}
            max={100}
            step="any"
            decimal
            value={percent}
            aria-invalid={Boolean(fieldErrors.percent)}
            onChange={e => {
              setPercent(e.target.value);
              setFieldErrors(current => ({ ...current, percent: '' }));
            }}
          />
          {fieldErrors.percent && <span className="form-error">{fieldErrors.percent}</span>}
        </label>

        <label htmlFor="tier-image">{t.statuses.fieldImageUrl}</label>
        <ImageUploadField
          id="tier-image"
          value={imageUrl}
          onChange={setImageUrl}
          purpose="promotion"
          onUploadingChange={setUploadingImage}
          disabled={saving}
        />

        <label className="checkbox-row" htmlFor="tier-is-active">
          <input
            id="tier-is-active"
            type="checkbox"
            checked={isActive}
            onChange={e => setIsActive(e.target.checked)}
          />
          <span>{t.statuses.fieldIsActive}</span>
        </label>

        <div className="dialog-actions">
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
  const businessesQuery = useBusinesses({ limit: 100, offset: 0 });

  const managerBusinessId =
    view.status === 'authenticated' && view.admin.business
      ? view.admin.business.id
      : '';

  const [selectedBusinessId, setSelectedBusinessId] = useState<string>('');
  const activeBusinessId = isSuperadmin
    ? selectedBusinessId || (businessesQuery.data?.items[0]?.id ?? '')
    : managerBusinessId;

  useEffect(() => {
    if (!isSuperadmin) return;
    const selected = activeBusinessId ? businessesQuery.data?.items.find(b => b.id === activeBusinessId) : null;
    setActiveBusiness(selected ? {
      id: selected.id,
      name: selected.name,
      logo_url: selected.logo_url,
      android_app_id: selected.android_app_id,
    } : null);
  }, [activeBusinessId, businessesQuery.data?.items, isSuperadmin, setActiveBusiness]);

  useEffect(() => {
    return () => {
      setActiveBusiness(null);
    };
  }, [setActiveBusiness]);

  const tiersQuery = useLoyaltyTiers(activeBusinessId);
  const [editingTier, setEditingTier] = useState<LoyaltyTier | 'new' | null>(null);
  const [actionError, setActionError] = useState('');
  const expansion = useTableExpansion();
  const sortedTiers = Array.isArray(tiersQuery.data)
    ? [...tiersQuery.data].sort((a, b) => a.level - b.level || a.priority - b.priority)
    : [];
  const compact = useCompactRows(sortedTiers, expansion);

  const handleDelete = async (tier: LoyaltyTier) => {
    const tierName = locale === 'kk' ? (tier.name_kk || tier.name_ru) : tier.name_ru;
    if (!window.confirm(t.statuses.confirmDelete(tierName))) return;
    setActionError('');
    try {
      await session.api.request(
        `/admin/businesses/${encodeURIComponent(activeBusinessId)}/loyalty-tiers/${encodeURIComponent(tier.id)}`,
        { method: 'DELETE' }
      );
      await queryClient.invalidateQueries({
        queryKey: [...privateKey, 'loyalty-tiers', activeBusinessId],
      });
    } catch (err) {
      setActionError(messageForError(err, locale));
    }
  };

  return (
    <div className="page-stack">
      <div className="section-heading" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <PageHeading title={t.statuses.title} subtitle={t.statuses.subtitle} />
        </div>
        {activeBusinessId && (
          <button
            className="button button-primary"
            type="button"
            onClick={() => setEditingTier('new')}
          >
            {t.statuses.addTierBtn}
          </button>
        )}
      </div>

      {isSuperadmin && (
        <section className="search-filter-section" style={{ marginBottom: '1rem' }}>
          <div className="filter-controls">
            <label className="form-control business-select" htmlFor="statuses-business">
              {t.statuses.businessLabel}
              <select
                id="statuses-business"
                value={activeBusinessId}
                onChange={e => setSelectedBusinessId(e.target.value)}
              >
                {businessesQuery.data?.items.map(b => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </section>
      )}

      {actionError && <p className="form-error" role="alert">{actionError}</p>}

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
                  <th>{t.statuses.colTurnoverPeriod}</th>
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
                      <span>{t.statuses.periodMonths(tier.turnover_period_months)}</span>
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
        </div>
      )}

      {editingTier && (
        <TierDialog
          businessId={activeBusinessId}
          tier={typeof editingTier === 'object' ? editingTier : undefined}
          onClose={() => setEditingTier(null)}
          onSaved={() => {
            void tiersQuery.refetch();
          }}
        />
      )}
    </div>
  );
}
