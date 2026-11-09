import { useState, useEffect, useRef, type FormEvent } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { messageForError } from '../api/errors';
import { privateKey, useBusinessAppTexts, useBusinessSplashConfig, useBusinessStores } from '../api/queries';
import type { BusinessSplashUpdateRequest, BusinessStore, BusinessStoreInput, SplashMediaUploadResponse } from '../api/types';
import { useAdminSession } from '../auth/provider';
import { CompactTableToggle, useCompactRows, useTableExpansion } from '../components/CompactTable';
import { StatusPill } from '../components/Feedback';
import { DialogFrame } from './AdminMutations';
import { useLocale } from '../i18n/LocaleContext';
import { adminErrorMessage, useAdminTranslation } from '../i18n/admin';

export function validateMapUrl(url: string): boolean {
  const trimmed = url.trim();
  if (!trimmed) return true;
  if (!trimmed.startsWith('https://')) return false;
  try {
    const parsed = new URL(trimmed);
    return parsed.protocol === 'https:' && Boolean(parsed.hostname);
  } catch {
    return false;
  }
}

interface StoreDialogProps {
  businessId: string;
  store?: BusinessStore;
  onClose: () => void;
  onSaved: () => void;
}

export function StoreDialog({ businessId, store, onClose, onSaved }: StoreDialogProps) {
  const { session } = useAdminSession();
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const queryClient = useQueryClient();

  const [titleRu, setTitleRu] = useState(store?.title_ru ?? '');
  const [titleKk, setTitleKk] = useState(store?.title_kk ?? '');
  const [addressRu, setAddressRu] = useState(store?.address_ru ?? '');
  const [addressKk, setAddressKk] = useState(store?.address_kk ?? '');
  const [mapUrl, setMapUrl] = useState(store?.map_url ?? '');
  const [sortOrder, setSortOrder] = useState<number>(store?.sort_order ?? 0);
  const [isActive, setIsActive] = useState<boolean>(store?.is_active ?? true);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');

    const cleanTitleRu = titleRu.trim();
    const cleanTitleKk = titleKk.trim();
    const cleanAddressRu = addressRu.trim();
    const cleanAddressKk = addressKk.trim();
    const cleanMapUrl = mapUrl.trim();

    if (!cleanTitleRu || !cleanTitleKk) {
      setError(t.appContent.errTitleRequired);
      return;
    }
    if (!cleanAddressRu || !cleanAddressKk) {
      setError(t.appContent.errAddressRequired);
      return;
    }
    if (cleanMapUrl && !validateMapUrl(cleanMapUrl)) {
      setError(t.appContent.errMapUrlInvalid);
      return;
    }

    setSaving(true);
    try {
      const payload: BusinessStoreInput = {
        title_ru: cleanTitleRu,
        title_kk: cleanTitleKk,
        address_ru: cleanAddressRu,
        address_kk: cleanAddressKk,
        map_url: cleanMapUrl || null,
        sort_order: Number.isFinite(sortOrder) ? sortOrder : 0,
        is_active: isActive,
      };

      if (store) {
        await session.api.request(
          `/admin/businesses/${encodeURIComponent(businessId)}/stores/${encodeURIComponent(store.id)}`,
          {
            method: 'PATCH',
            body: payload,
          }
        );
      } else {
        await session.api.request(
          `/admin/businesses/${encodeURIComponent(businessId)}/stores`,
          {
            method: 'POST',
            body: payload,
          }
        );
      }

      await queryClient.invalidateQueries({
        queryKey: [...privateKey, 'business-stores', businessId],
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
      title={store ? t.appContent.storeDialogEditTitle : t.appContent.storeDialogCreateTitle}
      onClose={onClose}
    >
      <form className="mutation-form" onSubmit={handleSubmit}>
        {error && <p className="form-error" role="alert">{error}</p>}

        <label className="form-control" htmlFor="store-title-ru">
          {t.appContent.fieldTitleRu}
          <input
            id="store-title-ru"
            type="text"
            required
            maxLength={160}
            placeholder={t.appContent.fieldTitleRuPlaceholder}
            value={titleRu}
            onChange={e => setTitleRu(e.target.value)}
          />
        </label>

        <label className="form-control" htmlFor="store-title-kk">
          {t.appContent.fieldTitleKk}
          <input
            id="store-title-kk"
            type="text"
            required
            maxLength={160}
            placeholder={t.appContent.fieldTitleKkPlaceholder}
            value={titleKk}
            onChange={e => setTitleKk(e.target.value)}
          />
        </label>

        <label className="form-control" htmlFor="store-address-ru">
          {t.appContent.fieldAddressRu}
          <input
            id="store-address-ru"
            type="text"
            required
            maxLength={255}
            placeholder={t.appContent.fieldAddressRuPlaceholder}
            value={addressRu}
            onChange={e => setAddressRu(e.target.value)}
          />
        </label>

        <label className="form-control" htmlFor="store-address-kk">
          {t.appContent.fieldAddressKk}
          <input
            id="store-address-kk"
            type="text"
            required
            maxLength={255}
            placeholder={t.appContent.fieldAddressKkPlaceholder}
            value={addressKk}
            onChange={e => setAddressKk(e.target.value)}
          />
        </label>

        <label className="form-control" htmlFor="store-map-url">
          {t.appContent.fieldMapUrl}
          <input
            id="store-map-url"
            type="url"
            maxLength={1024}
            placeholder="https://2gis.kz/astana/firm/…"
            value={mapUrl}
            onChange={e => setMapUrl(e.target.value)}
          />
          <span className="muted-copy">{t.appContent.fieldMapUrlHint}</span>
        </label>

        <label className="form-control" htmlFor="store-sort-order">
          {t.appContent.fieldSortOrder}
          <input
            id="store-sort-order"
            type="number"
            min={-1000}
            max={1000}
            value={sortOrder}
            onChange={e => setSortOrder(parseInt(e.target.value, 10) || 0)}
          />
        </label>

        <label className="checkbox-row" htmlFor="store-is-active">
          <input
            id="store-is-active"
            type="checkbox"
            checked={isActive}
            onChange={e => setIsActive(e.target.checked)}
          />
          <span>{t.appContent.fieldIsActive}</span>
        </label>

        <div className="dialog-actions">
          <button className="button button-secondary" type="button" onClick={onClose} disabled={saving}>
            {t.appContent.cancelBtn}
          </button>
          <button className="button button-primary" type="submit" disabled={saving}>
            {saving ? t.appContent.savingBtn : t.appContent.saveBtn}
          </button>
        </div>
      </form>
    </DialogFrame>
  );
}

interface BusinessStoresSectionProps {
  businessId: string;
  hideHeadingAction?: boolean;
  editingStore?: BusinessStore | 'new' | null;
  onEditingStoreChange?: (store: BusinessStore | 'new' | null) => void;
}

export function BusinessStoresSection({
  businessId,
  hideHeadingAction = false,
  editingStore: controlledEditingStore,
  onEditingStoreChange,
}: BusinessStoresSectionProps) {
  const { session } = useAdminSession();
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const queryClient = useQueryClient();

  const storesQuery = useBusinessStores(businessId);
  const expansion = useTableExpansion();
  const compact = useCompactRows(storesQuery.data ?? [], expansion);

  const [internalEditingStore, setInternalEditingStore] = useState<BusinessStore | 'new' | null>(null);
  const editingStore = controlledEditingStore !== undefined ? controlledEditingStore : internalEditingStore;
  const setEditingStore = onEditingStoreChange ?? setInternalEditingStore;
  const [storeActionError, setStoreActionError] = useState('');

  const handleDeleteStore = async (store: BusinessStore) => {
    const displayName = locale === 'kk' ? (store.title_kk || store.title_ru) : store.title_ru;
    if (!window.confirm(t.appContent.confirmDeleteStore(displayName))) {
      return;
    }
    setStoreActionError('');
    try {
      await session.api.request(
        `/admin/businesses/${encodeURIComponent(businessId)}/stores/${encodeURIComponent(store.id)}`,
        { method: 'DELETE' }
      );
      await queryClient.invalidateQueries({
        queryKey: [...privateKey, 'business-stores', businessId],
      });
    } catch (err) {
      setStoreActionError(messageForError(err, locale));
    }
  };

  return (
    <section className="surface-card">
      <div className="section-heading">
        <div>
          <h2>{t.appContent.storesTitle}</h2>
          <p className="muted-copy">{t.appContent.storesSubtitle}</p>
        </div>
        {!hideHeadingAction && (
          <button
            className="button button-primary"
            type="button"
            onClick={() => setEditingStore('new')}
          >
            {t.appContent.addStoreBtn}
          </button>
        )}
      </div>

      {storeActionError && <p className="form-error" role="alert">{storeActionError}</p>}

      {storesQuery.isPending ? (
        <p className="loading-copy">{t.appContent.loadingStores}</p>
      ) : storesQuery.isError ? (
        <p className="form-error">{messageForError(storesQuery.error, locale)}</p>
      ) : !storesQuery.data || storesQuery.data.length === 0 ? (
        <p className="table-empty">{t.appContent.emptyStores}</p>
      ) : (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t.appContent.colTitle}</th>
                  <th>{t.appContent.colAddress}</th>
                  <th>{t.appContent.colMap}</th>
                  <th>{t.appContent.colOrder}</th>
                  <th>{t.appContent.colStatus}</th>
                  <th aria-label="actions" />
                </tr>
              </thead>
              <tbody id={compact.bodyId}>
                {compact.visibleRows.map(store => (
                  <tr key={store.id}>
                    <td>
                      <strong>{locale === 'kk' ? (store.title_kk || store.title_ru) : store.title_ru}</strong>
                    </td>
                    <td>
                      <span>{locale === 'kk' ? (store.address_kk || store.address_ru) : store.address_ru}</span>
                    </td>
                    <td>
                      {store.map_url ? (
                        <a
                          href={store.map_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="table-link"
                        >
                          {t.appContent.openMap}
                        </a>
                      ) : (
                        <span className="muted-copy">{t.appContent.noMap}</span>
                      )}
                    </td>
                    <td>
                      <span className="mono-value">{store.sort_order}</span>
                    </td>
                    <td>
                      <StatusPill tone={store.is_active ? 'positive' : 'neutral'}>
                        {store.is_active ? t.content.statusShown : t.content.statusHidden}
                      </StatusPill>
                    </td>
                    <td className="align-right">
                      <span className="pagination-actions">
                        <button
                          className="link-button"
                          type="button"
                          onClick={() => setEditingStore(store)}
                        >
                          {t.content.editBtn}
                        </button>
                        <button
                          className="link-button"
                          type="button"
                          onClick={() => { void handleDeleteStore(store); }}
                        >
                          {t.content.deleteBtn}
                        </button>
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <CompactTableToggle {...compact} />
        </>
      )}

      {editingStore && (
        <StoreDialog
          businessId={businessId}
          store={editingStore === 'new' ? undefined : editingStore}
          onClose={() => setEditingStore(null)}
          onSaved={() => {
            void storesQuery.refetch();
          }}
        />
      )}
    </section>
  );
}

export function BusinessTextsSection({ businessId }: { businessId: string }) {
  const { session } = useAdminSession();
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const queryClient = useQueryClient();

  const textsQuery = useBusinessAppTexts(businessId);

  const [homeRu, setHomeRu] = useState('');
  const [homeKk, setHomeKk] = useState('');
  const [leadRu, setLeadRu] = useState('');
  const [leadKk, setLeadKk] = useState('');
  const [delayRu, setDelayRu] = useState('');
  const [delayKk, setDelayKk] = useState('');
  const [textsSaving, setTextsSaving] = useState(false);
  const [textsSaved, setTextsSaved] = useState(false);
  const [textsError, setTextsError] = useState('');

  useEffect(() => {
    if (textsQuery.data) {
      setHomeRu(textsQuery.data.home_text?.ru ?? '');
      setHomeKk(textsQuery.data.home_text?.kk ?? '');
      setLeadRu(textsQuery.data.home_store_note_lead?.ru ?? '');
      setLeadKk(textsQuery.data.home_store_note_lead?.kk ?? '');
      setDelayRu(textsQuery.data.balance_delay_note?.ru ?? '');
      setDelayKk(textsQuery.data.balance_delay_note?.kk ?? '');
    }
  }, [textsQuery.data]);

  const previewText = locale === 'kk' ? (homeKk || homeRu) : (homeRu || homeKk);

  const handleSaveTexts = async (e: FormEvent) => {
    e.preventDefault();
    setTextsError('');
    setTextsSaved(false);
    setTextsSaving(true);

    try {
      await session.api.request(
        `/admin/businesses/${encodeURIComponent(businessId)}/app-texts`,
        {
          method: 'PUT',
          body: {
            home_text: {
              ru: homeRu.trim() || null,
              kk: homeKk.trim() || null,
            },
            home_store_note_lead: {
              ru: leadRu.trim() || null,
              kk: leadKk.trim() || null,
            },
            balance_delay_note: {
              ru: delayRu.trim() || null,
              kk: delayKk.trim() || null,
            },
          },
        }
      );
      await queryClient.invalidateQueries({
        queryKey: [...privateKey, 'business-app-texts', businessId],
      });
      setTextsSaved(true);
      setTimeout(() => setTextsSaved(false), 4000);
    } catch (err) {
      setTextsError(messageForError(err, locale));
    } finally {
      setTextsSaving(false);
    }
  };

  return (
    <section className="surface-card">
      <div className="section-heading">
        <div>
          <h2>{t.appContent.textsTitle}</h2>
          <p className="muted-copy">{t.appContent.textsSubtitle}</p>
        </div>
      </div>

      {textsQuery.isPending ? (
        <p className="loading-copy">{t.appContent.loadingTexts}</p>
      ) : (
        <form className="mutation-form app-texts-form" onSubmit={handleSaveTexts}>
          {textsError && <p className="form-error" role="alert">{textsError}</p>}
          {textsSaved && <p className="notice" role="status" style={{ padding: '0.75rem 1rem', marginBottom: '1rem', color: '#15803d', background: '#f0fdf4', borderRadius: '6px' }}>{t.appContent.textsSaved}</p>}

          <fieldset className="app-texts-fieldset">
            <legend>{t.appContent.homeTextTitle}</legend>
            <p className="muted-copy" style={{ margin: '0 0 0.75rem', fontSize: '0.875rem' }}>{t.appContent.homeTextHint}</p>

            <label className="form-control" htmlFor="text-home-ru" style={{ marginBottom: '0.75rem' }}>
              {t.appContent.fieldRu}
              <textarea
                id="text-home-ru"
                className="app-text-textarea"
                rows={3}
                maxLength={2000}
                placeholder={t.appContent.homeTextPlaceholderRu}
                value={homeRu}
                onChange={e => setHomeRu(e.target.value)}
              />
            </label>

            <label className="form-control" htmlFor="text-home-kk" style={{ marginBottom: '0.75rem' }}>
              {t.appContent.fieldKk}
              <textarea
                id="text-home-kk"
                className="app-text-textarea"
                rows={3}
                maxLength={2000}
                placeholder={t.appContent.homeTextPlaceholderKk}
                value={homeKk}
                onChange={e => setHomeKk(e.target.value)}
              />
            </label>

            {previewText.trim() && (
              <div
                className="home-text-preview-box"
                style={{
                  marginTop: '0.5rem',
                  padding: '0.75rem 1rem',
                  borderRadius: '6px',
                  background: 'var(--bg-card, #f8fafc)',
                  border: '1px dashed var(--border-color, #cbd5e1)',
                }}
              >
                <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted, #64748b)', marginBottom: '0.25rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  {t.appContent.homeTextPreviewLabel}
                </div>
                <div style={{ whiteSpace: 'pre-wrap', fontSize: '0.9375rem', lineHeight: 1.5 }}>
                  {previewText}
                </div>
              </div>
            )}
          </fieldset>

          <fieldset className="app-texts-fieldset">
            <legend>{t.appContent.delayNoteTitle}</legend>
            <p className="muted-copy" style={{ margin: '0 0 0.75rem', fontSize: '0.875rem' }}>{t.appContent.delayNoteHint}</p>

            <label className="form-control" htmlFor="text-delay-ru" style={{ marginBottom: '0.75rem' }}>
              {t.appContent.fieldRu}
              <textarea
                id="text-delay-ru"
                className="app-text-textarea"
                rows={2}
                maxLength={500}
                placeholder={t.appContent.delayNotePlaceholderRu}
                value={delayRu}
                onChange={e => setDelayRu(e.target.value)}
              />
            </label>

            <label className="form-control" htmlFor="text-delay-kk">
              {t.appContent.fieldKk}
              <textarea
                id="text-delay-kk"
                className="app-text-textarea"
                rows={2}
                maxLength={500}
                placeholder={t.appContent.delayNotePlaceholderKk}
                value={delayKk}
                onChange={e => setDelayKk(e.target.value)}
              />
            </label>
          </fieldset>

          <button className="button button-primary app-texts-submit" type="submit" disabled={textsSaving}>
            {textsSaving ? t.appContent.savingBtn : t.appContent.saveTextsBtn}
          </button>
        </form>
      )}
    </section>
  );
}

export function BusinessSplashSection({ businessId }: { businessId: string }) {
  const { session } = useAdminSession();
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const queryClient = useQueryClient();
  const splashQuery = useBusinessSplashConfig(businessId);

  const [enabled, setEnabled] = useState(false);
  const [mediaType, setMediaType] = useState<'image' | 'video' | null>(null);
  const [mediaUrl, setMediaUrl] = useState<string | null>(null);
  const [width, setWidth] = useState<number | null>(null);
  const [height, setHeight] = useState<number | null>(null);
  const [durationSeconds, setDurationSeconds] = useState<number | null>(null);
  const [fileSize, setFileSize] = useState<number | null>(null);

  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (splashQuery.data) {
      setEnabled(splashQuery.data.enabled);
      setMediaType(splashQuery.data.media_type);
      setMediaUrl(splashQuery.data.media_url);
      setWidth(splashQuery.data.width);
      setHeight(splashQuery.data.height);
      setDurationSeconds(splashQuery.data.duration_seconds);
      setFileSize(splashQuery.data.file_size);
    }
  }, [splashQuery.data]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;

    setError(null);
    setFeedback(null);
    setUploading(true);

    try {
      const formData = new FormData();
      formData.append('file', file, file.name);
      formData.append('business_id', businessId);

      const res = await session.api.request<SplashMediaUploadResponse>('/admin/media/splash', {
        method: 'POST',
        body: formData,
        timeoutMs: 60_000,
      });

      setMediaType(res.media_type);
      setMediaUrl(res.url);
      setWidth(res.width);
      setHeight(res.height);
      setDurationSeconds(res.duration_seconds);
      setFileSize(res.bytes);
      setError(null);
    } catch (err) {
      setError(adminErrorMessage(err, locale));
    } finally {
      setUploading(false);
    }
  };

  const handleRemoveMedia = () => {
    setMediaUrl(null);
    setMediaType(null);
    setWidth(null);
    setHeight(null);
    setDurationSeconds(null);
    setFileSize(null);
    setEnabled(false);
    setError(null);
    setFeedback(null);
  };

  const handleSave = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setFeedback(null);

    if (enabled && !mediaUrl) {
      setError(t.appContent.splashNoMediaWarning);
      return;
    }

    setSaving(true);
    try {
      const body: BusinessSplashUpdateRequest = {
        enabled,
        media_type: mediaUrl ? mediaType : null,
        media_url: mediaUrl || null,
        width: mediaUrl ? width : null,
        height: mediaUrl ? height : null,
        duration_seconds: mediaUrl ? durationSeconds : null,
        file_size: mediaUrl ? fileSize : null,
      };

      await session.api.request(
        `/admin/businesses/${encodeURIComponent(businessId)}/splash`,
        {
          method: 'PUT',
          body,
        }
      );

      await queryClient.invalidateQueries({
        queryKey: [...privateKey, 'business-splash', businessId],
      });
      setFeedback(t.appContent.splashSavedSuccess);
    } catch (err) {
      setError(adminErrorMessage(err, locale));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="surface-card app-splash-section" data-testid="app-splash-section">
      <div className="section-header">
        <div>
          <h2>{t.appContent.splashTitle}</h2>
          <p className="muted-copy">{t.appContent.splashSubtitle}</p>
        </div>
      </div>

      <div className="app-splash-limits-callout">
        <p className="muted-copy">{t.appContent.splashLimitsHint}</p>
      </div>

      {splashQuery.isLoading ? (
        <p className="loading-copy">{t.appContent.splashLoading}</p>
      ) : splashQuery.isError ? (
        <p className="error-copy">{adminErrorMessage(splashQuery.error, locale)}</p>
      ) : (
        <form onSubmit={handleSave} className="app-splash-form">
          {error && <p className="error-copy" data-testid="splash-error">{error}</p>}
          {feedback && <p className="success-copy" data-testid="splash-feedback">{feedback}</p>}

          <div className="app-splash-toggle-row">
            <label className="toggle-label" htmlFor="splash-enabled-toggle">
              <input
                id="splash-enabled-toggle"
                type="checkbox"
                checked={enabled}
                onChange={e => setEnabled(e.target.checked)}
                disabled={uploading || saving}
              />
              <span className="toggle-text">{t.appContent.splashEnableToggle}</span>
            </label>
          </div>

          <div className="app-splash-media-area">
            <input
              ref={fileInputRef}
              type="file"
              accept=".png,.jpg,.jpeg,.webp,.mp4,image/png,image/jpeg,image/webp,video/mp4"
              style={{ display: 'none' }}
              onChange={handleFileUpload}
              data-testid="splash-file-input"
            />

            {mediaUrl ? (
              <div className="app-splash-preview-container" data-testid="splash-preview">
                <div className="app-splash-media-frame">
                  {mediaType === 'video' ? (
                    <video
                      src={mediaUrl}
                      controls={false}
                      autoPlay
                      loop
                      muted
                      playsInline
                      className="app-splash-preview-media"
                    />
                  ) : (
                    <img
                      src={mediaUrl}
                      alt=""
                      className="app-splash-preview-media"
                    />
                  )}
                </div>

                <div className="app-splash-preview-details">
                  <div className="app-splash-meta-badge">
                    <span className="meta-type">
                      {mediaType === 'video'
                        ? t.appContent.splashTypeVideo
                        : t.appContent.splashTypeImage}
                    </span>
                    {width && height && (
                      <span className="meta-dimensions">{width} × {height}</span>
                    )}
                    {durationSeconds != null && (
                      <span className="meta-duration">
                        {t.appContent.splashDurationSeconds(durationSeconds)}
                      </span>
                    )}
                    {fileSize != null && (
                      <span className="meta-size">
                        {(fileSize / (1024 * 1024)).toFixed(2)} МБ
                      </span>
                    )}
                  </div>
                  {mediaType === 'video' && (
                    <p className="app-splash-audio-note">
                      {t.appContent.splashAudioForbiddenNotice}
                    </p>
                  )}

                  <div className="app-splash-media-actions">
                    <button
                      type="button"
                      className="button button-secondary app-splash-change-btn"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={uploading || saving}
                    >
                      {uploading ? t.appContent.splashUploading : t.appContent.splashChangeBtn}
                    </button>
                    <button
                      type="button"
                      className="button button-danger app-splash-remove-btn"
                      onClick={handleRemoveMedia}
                      disabled={uploading || saving}
                    >
                      {t.appContent.splashRemoveBtn}
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="app-splash-empty-dropzone">
                <button
                  type="button"
                  className="button button-secondary app-splash-upload-btn"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading || saving}
                  data-testid="splash-upload-btn"
                >
                  {uploading ? t.appContent.splashUploading : t.appContent.splashUploadBtn}
                </button>
              </div>
            )}
          </div>

          <div className="app-splash-form-actions">
            <button
              className="button button-primary app-splash-save-btn"
              type="submit"
              disabled={uploading || saving}
            >
              {saving ? t.appContent.splashSaving : t.appContent.splashSaveBtn}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}

export function BusinessAppContent({ businessId }: { businessId: string }) {
  return (
    <div className="page-stack">
      <BusinessStoresSection businessId={businessId} />
      <BusinessTextsSection businessId={businessId} />
      <BusinessSplashSection businessId={businessId} />
    </div>
  );
}
