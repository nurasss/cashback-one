import { useState, type FormEvent } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { messageForError } from '../api/errors';
import { privateKey, useBusinesses, useLoyaltyTiers } from '../api/queries';
import type { LoyaltyTier, LoyaltyTierInput } from '../api/types';
import { useAdminSession } from '../auth/provider';
import { ErrorNotice, LoadingPage, PageHeading, StatusPill } from '../components/Feedback';
import { ImageUploadField } from '../components/ImageUploadField';
import { DialogFrame } from '../features/AdminMutations';
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

  const [level, setLevel] = useState<number>(tier?.level ?? 1);
  const [priority, setPriority] = useState<number>(tier?.priority ?? 1);
  const [titleRu, setTitleRu] = useState(tier?.name_ru ?? '');
  const [titleKk, setTitleKk] = useState(tier?.name_kk ?? '');
  const [descriptionRu, setDescriptionRu] = useState(tier?.description_ru ?? '');
  const [descriptionKk, setDescriptionKk] = useState(tier?.description_kk ?? '');
  const [turnoverPeriodMonths, setTurnoverPeriodMonths] = useState<number>(tier?.turnover_period_months ?? 6);
  const [thresholdMin, setThresholdMin] = useState<string>(tier?.min_turnover != null ? String(tier.min_turnover) : '0');
  const [thresholdMax, setThresholdMax] = useState<string>(tier?.max_turnover != null ? String(tier.max_turnover) : '');
  const [percent, setPercent] = useState<string>(tier?.percent != null ? String(tier.percent) : '2');
  const [imageUrl, setImageUrl] = useState<string>(tier?.image_url ?? '');
  const [isActive, setIsActive] = useState<boolean>(tier?.is_active ?? true);

  const [error, setError] = useState('');
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
    if (!Number.isInteger(level) || level <= 0) {
      setError(t.statuses.errLevelRequired);
      return;
    }
    if (!Number.isInteger(turnoverPeriodMonths) || turnoverPeriodMonths < 1 || turnoverPeriodMonths > 36) {
      setError(t.statuses.errTurnoverPeriod);
      return;
    }

    const minNum = Number(thresholdMin);
    const maxNum = thresholdMax.trim() !== '' ? Number(thresholdMax) : null;
    if (isNaN(minNum) || minNum < 0 || (maxNum !== null && (isNaN(maxNum) || maxNum <= minNum))) {
      setError(t.statuses.errThresholds);
      return;
    }

    const pctNum = Number(percent);
    if (isNaN(pctNum) || pctNum < 0 || pctNum > 100) {
      setError(t.statuses.errPercent);
      return;
    }

    const payload: LoyaltyTierInput = {
      level,
      priority: Number.isInteger(priority) ? priority : level,
      name_ru: cleanTitleRu,
      name_kk: cleanTitleKk,
      description_ru: cleanDescRu || null,
      description_kk: cleanDescKk || null,
      turnover_period_months: turnoverPeriodMonths,
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
      <form className="mutation-form" onSubmit={handleSubmit}>
        {error && <p className="form-error" role="alert">{error}</p>}

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
          <label className="form-control" htmlFor="tier-level">
            {t.statuses.fieldLevel}
            <input
              id="tier-level"
              type="number"
              min={1}
              max={100}
              required
              value={level}
              onChange={e => setLevel(parseInt(e.target.value, 10) || 1)}
            />
          </label>
          <label className="form-control" htmlFor="tier-priority">
            {t.statuses.fieldPriority}
            <input
              id="tier-priority"
              type="number"
              min={1}
              max={1000}
              required
              value={priority}
              onChange={e => setPriority(parseInt(e.target.value, 10) || 1)}
            />
          </label>
        </div>

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
          <input
            id="tier-period"
            type="number"
            min={1}
            max={36}
            required
            value={turnoverPeriodMonths}
            onChange={e => setTurnoverPeriodMonths(parseInt(e.target.value, 10) || 1)}
          />
          <span className="muted-copy">{t.statuses.fieldTurnoverPeriodHint}</span>
        </label>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
          <label className="form-control" htmlFor="tier-min">
            {t.statuses.fieldThresholdMin}
            <input
              id="tier-min"
              type="number"
              min={0}
              step="any"
              required
              value={thresholdMin}
              onChange={e => setThresholdMin(e.target.value)}
            />
          </label>
          <label className="form-control" htmlFor="tier-max">
            {t.statuses.fieldThresholdMax}
            <input
              id="tier-max"
              type="number"
              min={0}
              step="any"
              placeholder="Бессрочно / без предела"
              value={thresholdMax}
              onChange={e => setThresholdMax(e.target.value)}
            />
          </label>
        </div>

        <label className="form-control" htmlFor="tier-percent">
          {t.statuses.fieldPercent}
          <input
            id="tier-percent"
            type="number"
            min={0}
            max={100}
            step="any"
            required
            value={percent}
            onChange={e => setPercent(e.target.value)}
          />
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

  const tiersQuery = useLoyaltyTiers(activeBusinessId);
  const [editingTier, setEditingTier] = useState<LoyaltyTier | 'new' | null>(null);
  const [actionError, setActionError] = useState('');

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
                  <th>{t.statuses.colPriority}</th>
                  <th>{t.statuses.colTitle}</th>
                  <th>{t.statuses.colTurnoverPeriod}</th>
                  <th>{t.statuses.colThreshold}</th>
                  <th>{t.statuses.colPercent}</th>
                  <th>{t.statuses.colStatus}</th>
                  <th aria-label="actions" />
                </tr>
              </thead>
              <tbody>
                {tiersQuery.data.map(tier => (
                  <tr key={tier.id}>
                    <td>
                      <span className="mono-value">#{tier.level}</span>
                    </td>
                    <td>
                      <span className="mono-value">{tier.priority}</span>
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
