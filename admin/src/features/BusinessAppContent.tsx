import { useState, useEffect, type FormEvent } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { messageForError } from '../api/errors';
import { privateKey, useBusinessAppTexts, useBusinessStores } from '../api/queries';
import type { BusinessStore, BusinessStoreInput } from '../api/types';
import { useAdminSession } from '../auth/provider';
import { CompactTableToggle, useCompactRows, useTableExpansion } from '../components/CompactTable';
import { StatusPill } from '../components/Feedback';
import { DialogFrame } from './AdminMutations';
import { useLocale } from '../i18n/LocaleContext';
import { useAdminTranslation } from '../i18n/admin';

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

export function BusinessAppContent({ businessId }: { businessId: string }) {
  const { session } = useAdminSession();
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const queryClient = useQueryClient();

  const storesQuery = useBusinessStores(businessId);
  const textsQuery = useBusinessAppTexts(businessId);
  const expansion = useTableExpansion();
  const compact = useCompactRows(storesQuery.data ?? [], expansion);

  const [editingStore, setEditingStore] = useState<BusinessStore | 'new' | null>(null);
  const [storeActionError, setStoreActionError] = useState('');

  // Texts form state
  const [leadRu, setLeadRu] = useState('');
  const [leadKk, setLeadKk] = useState('');
  const [delayRu, setDelayRu] = useState('');
  const [delayKk, setDelayKk] = useState('');
  const [textsSaving, setTextsSaving] = useState(false);
  const [textsSaved, setTextsSaved] = useState(false);
  const [textsError, setTextsError] = useState('');

  // Sync loaded texts
  useEffect(() => {
    if (textsQuery.data) {
      setLeadRu(textsQuery.data.home_store_note_lead?.ru ?? '');
      setLeadKk(textsQuery.data.home_store_note_lead?.kk ?? '');
      setDelayRu(textsQuery.data.balance_delay_note?.ru ?? '');
      setDelayKk(textsQuery.data.balance_delay_note?.kk ?? '');
    }
  }, [textsQuery.data]);

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
    <div className="page-stack">
      {/* 1. Physical Stores Section */}
      <section className="surface-card">
        <div className="section-heading">
          <div>
            <h2>{t.appContent.storesTitle}</h2>
            <p className="muted-copy">{t.appContent.storesSubtitle}</p>
          </div>
          <button
            className="button button-primary"
            type="button"
            onClick={() => setEditingStore('new')}
          >
            {t.appContent.addStoreBtn}
          </button>
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
      </section>

      {/* 2. App Texts Section */}
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

            {/* Field: home_store_note_lead */}
            <fieldset className="app-texts-fieldset">
              <legend>{t.appContent.leadNoteTitle}</legend>
              <p className="muted-copy" style={{ margin: '0 0 0.75rem', fontSize: '0.875rem' }}>{t.appContent.leadNoteHint}</p>

              <label className="form-control" htmlFor="text-lead-ru" style={{ marginBottom: '0.75rem' }}>
                {t.appContent.fieldRu}
                <textarea
                  id="text-lead-ru"
                  className="app-text-textarea"
                  rows={2}
                  maxLength={500}
                  placeholder={t.appContent.leadNotePlaceholderRu}
                  value={leadRu}
                  onChange={e => setLeadRu(e.target.value)}
                />
              </label>

              <label className="form-control" htmlFor="text-lead-kk">
                {t.appContent.fieldKk}
                <textarea
                  id="text-lead-kk"
                  className="app-text-textarea"
                  rows={2}
                  maxLength={500}
                  placeholder={t.appContent.leadNotePlaceholderKk}
                  value={leadKk}
                  onChange={e => setLeadKk(e.target.value)}
                />
              </label>
            </fieldset>

            {/* Field: balance_delay_note */}
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

      {/* Store Dialog */}
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
    </div>
  );
}
