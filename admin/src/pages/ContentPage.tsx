import { useEffect, useState, type FormEvent } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { messageForError } from '../api/errors';
import { privateKey, useAppNotifications, useBusinesses, usePromotions } from '../api/queries';
import type { AppNotification, BroadcastPushResult, BusinessStore, Promotion, PromotionKind } from '../api/types';
import { useAdminSession } from '../auth/provider';
import { DataTable } from '../components/DataTable';
import { useTableExpansion } from '../components/CompactTable';
import { ErrorNotice, LoadingPage, PageHeading, StatusPill } from '../components/Feedback';
import { ImageUploadField } from '../components/ImageUploadField';
import { NumericInput } from '../components/NumericInput';
import { DialogFrame } from '../features/AdminMutations';
import { BusinessAppContent, BusinessSplashSection, BusinessStoresSection, BusinessTextsSection } from '../features/BusinessAppContent';
import { astanaLocalToUtcIso, formatAstanaDateTime, formatAstanaSchedule, formatDate, getAstanaNowLocal, isValidAstanaDateTimeLocal, utcIsoToAstanaLocal } from '../utils/format';
import { usePage } from '../utils/usePage';
import { useLocale } from '../i18n/LocaleContext';
import { useAdminTranslation } from '../i18n/admin';

type SuperadminTab = 'promotions' | 'notifications' | 'app';
type ClientTab = 'banners' | 'offers' | 'stores' | 'texts' | 'splash';
const GLOBAL = '';

function useIsSuperadmin() {
  const { view } = useAdminSession();
  return view.status === 'authenticated' && view.admin.role === 'superadmin';
}

function BusinessPicker({ id, value, onChange, allowAll }: { id: string; value: string; onChange: (value: string) => void; allowAll: string }) {
  const businesses = useBusinesses({ limit: 100, offset: 0 });
  return (
    <select id={id} value={value} onChange={event => onChange(event.target.value)}>
      <option value={GLOBAL}>{allowAll}</option>
      {businesses.data?.items.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
    </select>
  );
}

export function ContentPage() {
  const superadmin = useIsSuperadmin();
  const { view } = useAdminSession();
  const t = useAdminTranslation();
  const [adminTab, setAdminTab] = useState<SuperadminTab>('promotions');
  const [clientTab, setClientTab] = useState<ClientTab>('banners');
  const [businessFilter, setBusinessFilter] = useState(GLOBAL);
  const [editing, setEditing] = useState<Promotion | 'new' | 'new-banner' | 'new-offer' | null>(null);
  const [editingStore, setEditingStore] = useState<BusinessStore | 'new' | null>(null);
  const [noticeOpen, setNoticeOpen] = useState(false);
  const [noticeFeedback, setNoticeFeedback] = useState<string | null>(null);

  const handleNoticeCreated = (push?: BroadcastPushResult | null, scheduledAt?: string | null) => {
    if (scheduledAt) {
      setNoticeFeedback(t.content.noticeScheduleSuccess(formatAstanaSchedule(scheduledAt)));
      return;
    }
    if (!push) return;
    if (push.status === 'sent') {
      setNoticeFeedback(t.content.noticePushSent(push.delivered, push.devices));
    } else if (push.status === 'disabled') {
      setNoticeFeedback(t.content.noticePushDisabled);
    } else if (push.status === 'skipped') {
      if (push.devices === 0) {
        setNoticeFeedback(t.content.noticePushNoDevices);
      }
    } else if (push.status === 'failed') {
      setNoticeFeedback(t.content.noticePushFailed);
    }
  };

  const managerBusinessId =
    view.status === 'authenticated' && view.admin.role === 'business_manager'
      ? view.admin.business?.id
      : undefined;
  const activeAppBusinessId = superadmin ? businessFilter : managerBusinessId;

  const renderHeadingActions = () => {
    if (superadmin) {
      if (adminTab === 'promotions') {
        return (
          <button className="button button-primary" type="button" onClick={() => setEditing('new')}>
            {t.content.addPromoBtn}
          </button>
        );
      }
      if (adminTab === 'notifications') {
        return (
          <button className="button button-primary" type="button" onClick={() => setNoticeOpen(true)}>
            {t.content.sendNoticeBtn}
          </button>
        );
      }
      return null;
    }

    // business_manager
    if (clientTab === 'banners') {
      return (
        <button className="button button-primary" type="button" onClick={() => setEditing('new-banner')}>
          {t.content.addBannerBtn}
        </button>
      );
    }
    if (clientTab === 'offers') {
      return (
        <button className="button button-primary" type="button" onClick={() => setEditing('new-offer')}>
          {t.content.addOfferBtn}
        </button>
      );
    }
    if (clientTab === 'stores') {
      return (
        <button className="button button-primary" type="button" onClick={() => setEditingStore('new')}>
          {t.appContent.addStoreBtn}
        </button>
      );
    }
    return null;
  };

  return (
    <div className="page-stack">
      <PageHeading
        title={t.content.title}
        subtitle={t.content.subtitle}
        actions={renderHeadingActions()}
      />
      <section className="filter-panel">
        <div className="search-tabs" role="tablist">
          {superadmin ? (
            <>
              <button
                type="button"
                role="tab"
                aria-selected={adminTab === 'promotions'}
                className={adminTab === 'promotions' ? 'search-tab selected' : 'search-tab'}
                onClick={() => setAdminTab('promotions')}
              >
                {t.content.tabPromotions}
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={adminTab === 'notifications'}
                className={adminTab === 'notifications' ? 'search-tab selected' : 'search-tab'}
                onClick={() => setAdminTab('notifications')}
              >
                {t.content.tabNotifications}
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={adminTab === 'app'}
                className={adminTab === 'app' ? 'search-tab selected' : 'search-tab'}
                onClick={() => setAdminTab('app')}
              >
                {t.content.tabApp}
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                role="tab"
                aria-selected={clientTab === 'banners'}
                className={clientTab === 'banners' ? 'search-tab selected' : 'search-tab'}
                onClick={() => setClientTab('banners')}
              >
                {t.content.clientTabBanners}
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={clientTab === 'offers'}
                className={clientTab === 'offers' ? 'search-tab selected' : 'search-tab'}
                onClick={() => setClientTab('offers')}
              >
                {t.content.clientTabOffers}
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={clientTab === 'stores'}
                className={clientTab === 'stores' ? 'search-tab selected' : 'search-tab'}
                onClick={() => setClientTab('stores')}
              >
                {t.content.clientTabStores}
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={clientTab === 'texts'}
                className={clientTab === 'texts' ? 'search-tab selected' : 'search-tab'}
                onClick={() => setClientTab('texts')}
              >
                {t.content.clientTabTexts}
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={clientTab === 'splash'}
                className={clientTab === 'splash' ? 'search-tab selected' : 'search-tab'}
                onClick={() => setClientTab('splash')}
                data-testid="client-tab-splash"
              >
                {t.content.clientTabSplash}
              </button>
            </>
          )}
        </div>
        {superadmin && (
          <div className="filter-controls">
            <label className="form-control business-select" htmlFor="content-business">
              {t.content.businessFilterLabel}
              <BusinessPicker id="content-business" value={businessFilter} onChange={setBusinessFilter} allowAll={t.content.allRecords} />
            </label>
          </div>
        )}
      </section>

      {superadmin ? (
        adminTab === 'promotions' ? (
          <PromotionsTable businessId={businessFilter || undefined} onEdit={setEditing} />
        ) : adminTab === 'notifications' ? (
          <>
            {noticeFeedback && (
              <section
                className="notice"
                role="status"
                style={{
                  marginBottom: '1rem',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <p>{noticeFeedback}</p>
                <button
                  className="link-button"
                  type="button"
                  onClick={() => setNoticeFeedback(null)}
                  aria-label={t.mutations.close}
                >
                  ×
                </button>
              </section>
            )}
            <NotificationsTable businessId={businessFilter || undefined} />
          </>
        ) : activeAppBusinessId ? (
          <BusinessAppContent businessId={activeAppBusinessId} />
        ) : (
          <section className="surface-card">
            <p className="table-empty">{t.content.selectBusinessHint}</p>
          </section>
        )
      ) : (
        // Client view (business_manager)
        clientTab === 'banners' ? (
          <PromotionsTable businessId={managerBusinessId} kind="banner" onEdit={setEditing} />
        ) : clientTab === 'offers' ? (
          <PromotionsTable businessId={managerBusinessId} kind="offer" onEdit={setEditing} />
        ) : clientTab === 'stores' ? (
          activeAppBusinessId ? (
            <BusinessStoresSection
              businessId={activeAppBusinessId}
              hideHeadingAction
              editingStore={editingStore}
              onEditingStoreChange={setEditingStore}
            />
          ) : null
        ) : clientTab === 'texts' ? (
          activeAppBusinessId ? (
            <BusinessTextsSection businessId={activeAppBusinessId} />
          ) : null
        ) : (
          activeAppBusinessId ? (
            <BusinessSplashSection businessId={activeAppBusinessId} />
          ) : null
        )
      )}

      {editing && (
        <PromotionDialog
          promotion={typeof editing === 'object' ? editing : undefined}
          defaultKind={
            editing === 'new-banner'
              ? 'banner'
              : editing === 'new-offer'
                ? 'offer'
                : 'offer'
          }
          onClose={() => setEditing(null)}
        />
      )}
      {noticeOpen && (
        <NotificationDialog
          onClose={() => setNoticeOpen(false)}
          onCreated={handleNoticeCreated}
        />
      )}
    </div>
  );
}

export function PromotionsTable({
  businessId,
  kind,
  onEdit,
}: {
  businessId?: string;
  kind?: PromotionKind;
  onEdit: (promotion: Promotion) => void;
}) {
  const expansion = useTableExpansion();
  const t = useAdminTranslation();
  const pageSize = kind !== undefined ? 7 : 25;
  const [page, setPage] = usePage(pageSize);

  useEffect(() => {
    setPage(0);
  }, [businessId, kind, setPage]);

  const query = usePromotions(businessId, page, kind);
  const remove = useRemove('promotions');

  if (query.isPending) return <LoadingPage label={t.content.loadingPromos} />;
  if (query.isError) return <ErrorNotice error={query.error} retry={() => { void query.refetch(); }} />;

  const columns = [
    {
      key: 'title',
      title: t.content.colPromo,
      render: (item: Promotion) => (
        <span className="table-name">
          {item.title}
          <span>{item.badge ?? item.subtitle ?? ''}</span>
        </span>
      ),
    },
    ...(kind === undefined
      ? [
          {
            key: 'kind',
            title: t.content.colKind,
            render: (item: Promotion) =>
              item.kind === 'banner' ? t.content.kindBanner : t.content.kindOffer,
          },
        ]
      : []),
    {
      key: 'audience',
      title: t.content.colAudience,
      render: (item: Promotion) =>
        item.business_id ? t.content.audienceBiz : t.content.audienceAll,
    },
    {
      key: 'status',
      title: t.content.colPromoStatus,
      render: (item: Promotion) => (
        <StatusPill tone={item.is_active ? 'positive' : 'neutral'}>
          {item.is_active ? t.content.statusShown : t.content.statusHidden}
        </StatusPill>
      ),
    },
    {
      key: 'period',
      title: t.content.colPeriod,
      render: (item: Promotion) => (
        <span className="mono-value">
          {item.starts_at ? formatAstanaDateTime(item.starts_at) : '—'} —{' '}
          {item.ends_at ? formatAstanaDateTime(item.ends_at) : '∞'}
        </span>
      ),
    },
    {
      key: 'actions',
      title: '',
      align: 'right' as const,
      render: (item: Promotion) => (
        <span className="pagination-actions">
          <button className="link-button" type="button" onClick={() => onEdit(item)}>
            {t.content.editBtn}
          </button>
          <button
            className="link-button"
            type="button"
            disabled={remove.pending}
            onClick={() => {
              if (window.confirm(t.content.confirmDeletePromo(item.title)))
                void remove.run(item.id);
            }}
          >
            {t.content.deleteBtn}
          </button>
        </span>
      ),
    },
  ];

  const emptyMessage =
    kind === 'banner'
      ? t.content.emptyBanners
      : kind === 'offer'
        ? t.content.emptyOffers
        : undefined;

  return (
    <>
      {remove.error && <ErrorNotice error={remove.error} />}
      {query.data.items.length === 0 && emptyMessage ? (
        <section className="surface-card">
          <p className="table-empty">{emptyMessage}</p>
        </section>
      ) : (
        <DataTable<Promotion>
          expansion={expansion}
          page={{ ...page, has_more: query.data.has_more }}
          onPage={setPage}
          rows={query.data.items}
          rowKey={item => item.id}
          columns={columns}
          disableCompacting={kind !== undefined}
        />
      )}
    </>
  );
}

export function NotificationsTable({ businessId }: { businessId?: string }) {
  const expansion = useTableExpansion();
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const [page, setPage] = usePage();
  const query = useAppNotifications(businessId, page);
  const remove = useRemove('notifications');

  if (query.isPending) return <LoadingPage label={t.content.loadingNotices} />;
  if (query.isError) return <ErrorNotice error={query.error} retry={() => { void query.refetch(); }} />;

  return (
    <>
      {remove.error && <ErrorNotice error={remove.error} />}
      <DataTable<AppNotification>
        expansion={expansion}
        page={{ ...page, has_more: query.data.has_more }}
        onPage={setPage}
        rows={query.data.items}
        rowKey={item => item.id}
        columns={[
          {
            key: 'title',
            title: t.content.colNotice,
            render: item => (
              <span className="table-name">
                {item.title}
                <span>{item.body}</span>
              </span>
            ),
          },
          {
            key: 'audience',
            title: t.content.colAudience,
            render: item => (item.business_id ? t.content.audienceBiz : t.content.audienceAll),
          },
          {
            key: 'created',
            title: t.content.colSent,
            render: item => {
              const isFuture = Boolean(
                item.scheduled_at && new Date(item.scheduled_at).getTime() > Date.now()
              );
              if (isFuture && item.scheduled_at) {
                return (
                  <span className="table-name">
                    {t.content.noticeStatusScheduled(formatAstanaSchedule(item.scheduled_at))}
                  </span>
                );
              }
              const displayDate = item.scheduled_at || item.created_at;
              return (
                <span className="table-name">
                  {t.content.noticeStatusSent}
                  <time dateTime={displayDate}>{formatDate(displayDate, locale)}</time>
                </span>
              );
            },
          },
          {
            key: 'actions',
            title: '',
            align: 'right',
            render: item => (
              <button
                className="link-button"
                type="button"
                disabled={remove.pending}
                onClick={() => {
                  if (window.confirm(t.content.confirmDeleteNotice)) void remove.run(item.id);
                }}
              >
                {t.content.deleteBtn}
              </button>
            ),
          },
        ]}
      />
    </>
  );
}

function useRemove(resource: 'promotions' | 'notifications') {
  const { session } = useAdminSession();
  const queryClient = useQueryClient();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const run = async (id: string) => {
    setPending(true);
    setError(null);
    try {
      await session.api.request<void>(`/admin/${resource}/${encodeURIComponent(id)}`, { method: 'DELETE' });
      await queryClient.invalidateQueries({
        queryKey: [...privateKey, resource === 'promotions' ? 'promotions' : 'app-notifications'],
      });
    } catch (removeError) {
      setError(removeError);
    } finally {
      setPending(false);
    }
  };
  return { run, pending, error };
}

export function PromotionDialog({
  promotion,
  defaultKind = 'offer',
  onClose,
}: {
  promotion?: Promotion;
  defaultKind?: PromotionKind;
  onClose: () => void;
}) {
  const { session } = useAdminSession();
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const superadmin = useIsSuperadmin();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    business_id: promotion?.business_id ?? GLOBAL,
    kind: promotion?.kind ?? defaultKind,
    title: promotion?.title ?? '',
    subtitle: promotion?.subtitle ?? '',
    badge: promotion?.badge ?? '',
    body: promotion?.body ?? '',
    image_url: promotion?.image_url ?? '',
    starts_at: utcIsoToAstanaLocal(promotion?.starts_at ?? null),
    ends_at: utcIsoToAstanaLocal(promotion?.ends_at ?? null),
    sort_order: String(promotion?.sort_order ?? 0),
    is_active: promotion?.is_active ?? true,
  });
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState({ sort_order: '', starts_at: '', ends_at: '' });
  const [saving, setSaving] = useState(false);
  const [uploadingImage, setUploadingImage] = useState(false);
  const set = (key: keyof typeof form) => (event: { target: { value: string } }) => {
    setForm(current => ({ ...current, [key]: event.target.value }));
    if (key === 'sort_order' || key === 'starts_at' || key === 'ends_at') {
      setFieldErrors(current => ({ ...current, [key]: '' }));
    }
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    if (!form.title.trim()) {
      setError(t.content.promoErrTitle);
      return;
    }
    if (form.image_url.trim() && !form.image_url.trim().startsWith('https://')) {
      setError(t.content.promoErrImage);
      return;
    }
    const sort = Number(form.sort_order);
    const nextFieldErrors = { sort_order: '', starts_at: '', ends_at: '' };
    if (!form.sort_order.trim() || !Number.isInteger(sort) || Math.abs(sort) > 1000) {
      nextFieldErrors.sort_order = t.content.promoErrSort;
    }

    // Date validations in Astana time
    if (form.starts_at.trim() && !isValidAstanaDateTimeLocal(form.starts_at.trim())) {
      nextFieldErrors.starts_at = t.content.promoErrInvalidDate;
    }
    if (form.ends_at.trim() && !isValidAstanaDateTimeLocal(form.ends_at.trim())) {
      nextFieldErrors.ends_at = t.content.promoErrInvalidDate;
    }
    if (!promotion && form.starts_at.trim()) {
      const startUtc = astanaLocalToUtcIso(form.starts_at.trim());
      if (startUtc && new Date(startUtc).getTime() < Date.now() - 5 * 60 * 1000) {
        nextFieldErrors.starts_at = t.content.promoErrStartPast;
      }
    }
    if (form.starts_at.trim() && form.ends_at.trim()) {
      const startUtc = astanaLocalToUtcIso(form.starts_at.trim());
      const endUtc = astanaLocalToUtcIso(form.ends_at.trim());
      if (startUtc && endUtc && new Date(endUtc).getTime() <= new Date(startUtc).getTime()) {
        nextFieldErrors.ends_at = t.content.promoErrEndAfterStart;
      }
    }
    setFieldErrors(nextFieldErrors);
    if (Object.values(nextFieldErrors).some(Boolean)) return;

    const payload = {
      kind: form.kind,
      title: form.title.trim(),
      subtitle: form.subtitle.trim() || null,
      badge: form.badge.trim() || null,
      body: form.body.trim() || null,
      image_url: form.image_url.trim() || null,
      starts_at: form.starts_at.trim() ? astanaLocalToUtcIso(form.starts_at.trim()) : null,
      ends_at: form.ends_at.trim() ? astanaLocalToUtcIso(form.ends_at.trim()) : null,
      sort_order: sort,
      is_active: form.is_active,
    };
    setSaving(true);
    try {
      if (promotion) {
        await session.api.request<Promotion>(`/admin/promotions/${encodeURIComponent(promotion.id)}`, {
          method: 'PATCH',
          body: payload,
        });
      } else {
        await session.api.request<Promotion>('/admin/promotions', {
          method: 'POST',
          body: { ...payload, ...(superadmin && form.business_id ? { business_id: form.business_id } : {}) },
        });
      }
      await queryClient.invalidateQueries({ queryKey: [...privateKey, 'promotions'] });
      onClose();
    } catch (saveError) {
      setError(messageForError(saveError, locale));
    } finally {
      setSaving(false);
    }
  };

  const dialogTitle =
    form.kind === 'banner'
      ? promotion
        ? t.content.bannerDialogTitleEdit
        : t.content.bannerDialogTitleNew
      : promotion
        ? t.content.offerDialogTitleEdit
        : t.content.offerDialogTitleNew;

  return (
    <DialogFrame title={dialogTitle} onClose={onClose} className="mutation-dialog--wide">
      <form className="mutation-form" noValidate onSubmit={event => { void submit(event); }}>
        {superadmin && !promotion && (
          <>
            <label htmlFor="promo-business">{t.content.promoFieldAudience}</label>
            <BusinessPicker
              id="promo-business"
              value={form.business_id}
              onChange={value => setForm(current => ({ ...current, business_id: value }))}
              allowAll={t.content.promoAllClients}
            />
          </>
        )}
        {superadmin && (
          <>
            <label htmlFor="promo-kind">{t.content.promoFieldKind}</label>
            <select id="promo-kind" value={form.kind} onChange={set('kind')}>
              <option value="offer">{t.content.promoKindOfferOption}</option>
              <option value="banner">{t.content.promoKindBannerOption}</option>
            </select>
          </>
        )}
        <label htmlFor="promo-title">{t.content.promoFieldTitle}</label>
        <input id="promo-title" value={form.title} maxLength={120} onChange={set('title')} required autoFocus />
        <label htmlFor="promo-badge">{t.content.promoFieldBadge}</label>
        <input id="promo-badge" value={form.badge} maxLength={40} onChange={set('badge')} />
        <label htmlFor="promo-subtitle">{t.content.promoFieldSubtitle}</label>
        <input id="promo-subtitle" value={form.subtitle} maxLength={255} onChange={set('subtitle')} />
        <label htmlFor="promo-body">{t.content.promoFieldBody}</label>
        <textarea id="promo-body" rows={4} value={form.body} maxLength={4000} onChange={set('body')} />
        <label htmlFor="promo-image">{t.content.promoFieldImage}</label>
        <ImageUploadField
          id="promo-image"
          value={form.image_url}
          onChange={url => setForm(current => ({ ...current, image_url: url }))}
          purpose="promotion"
          onUploadingChange={setUploadingImage}
          disabled={saving}
        />

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <label htmlFor="promo-start" style={{ margin: 0 }}>{t.content.promoFieldStart}</label>
            <button
              type="button"
              className="link-button"
              style={{ fontSize: '0.8125rem' }}
              onClick={() => setForm(c => ({ ...c, starts_at: getAstanaNowLocal() }))}
            >
              {t.content.startNowBtn}
            </button>
          </div>
          <input
            id="promo-start"
            type="datetime-local"
            value={form.starts_at}
            min={promotion ? undefined : getAstanaNowLocal()}
            aria-invalid={Boolean(fieldErrors.starts_at)}
            onChange={set('starts_at')}
          />
          {fieldErrors.starts_at && <p className="form-error">{fieldErrors.starts_at}</p>}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', marginTop: '0.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <label htmlFor="promo-end" style={{ margin: 0 }}>{t.content.promoFieldEnd}</label>
            <button
              type="button"
              className="link-button"
              style={{ fontSize: '0.8125rem' }}
              onClick={() => setForm(c => ({ ...c, ends_at: '' }))}
            >
              {t.content.noEndDateBtn}
            </button>
          </div>
          <input
            id="promo-end"
            type="datetime-local"
            value={form.ends_at}
            min={form.starts_at || getAstanaNowLocal()}
            aria-invalid={Boolean(fieldErrors.ends_at)}
            onChange={set('ends_at')}
          />
          {fieldErrors.ends_at && <p className="form-error">{fieldErrors.ends_at}</p>}
        </div>

        <label htmlFor="promo-sort">{t.content.promoFieldSort}</label>
        <NumericInput id="promo-sort" min={-1000} max={1000} allowNegative value={form.sort_order} aria-invalid={Boolean(fieldErrors.sort_order)} onChange={set('sort_order')} />
        {fieldErrors.sort_order && <p className="form-error">{fieldErrors.sort_order}</p>}
        <label htmlFor="promo-active">
          <input
            id="promo-active"
            type="checkbox"
            checked={form.is_active}
            style={{ width: 'auto', minHeight: 0, marginRight: 8 }}
            onChange={event => setForm(current => ({ ...current, is_active: event.target.checked }))}
          />
          {t.content.promoFieldActive}
        </label>
        {error && <p className="form-error" role="alert">{error}</p>}
        <footer className="mutation-actions">
          <button className="button button-primary" type="submit" disabled={saving || uploadingImage}>
            {saving ? t.content.savingBtn : t.content.saveBtn}
          </button>
          <button className="button button-secondary" type="button" onClick={onClose} disabled={saving || uploadingImage}>
            {t.content.cancelBtn}
          </button>
        </footer>
      </form>
    </DialogFrame>
  );
}

export function NotificationDialog({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated?: (push?: BroadcastPushResult | null, scheduledAt?: string | null) => void;
}) {
  const { session } = useAdminSession();
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const superadmin = useIsSuperadmin();
  const queryClient = useQueryClient();
  const [businessId, setBusinessId] = useState(GLOBAL);
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [whenToSend, setWhenToSend] = useState<'now' | 'scheduled'>('now');
  const [scheduledLocal, setScheduledLocal] = useState('');
  const [error, setError] = useState('');
  const [scheduledError, setScheduledError] = useState('');
  const [saving, setSaving] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setScheduledError('');
    if (!title.trim() || !body.trim()) {
      setError(t.content.noticeErrFields);
      return;
    }

    let scheduledAtUtc: string | undefined = undefined;
    if (whenToSend === 'scheduled') {
      if (!scheduledLocal.trim()) {
        setScheduledError(t.content.noticeErrScheduledRequired);
        return;
      }
      if (!isValidAstanaDateTimeLocal(scheduledLocal.trim())) {
        setScheduledError(t.content.promoErrInvalidDate);
        return;
      }
      const utcIso = astanaLocalToUtcIso(scheduledLocal.trim());
      if (!utcIso) {
        setScheduledError(t.content.noticeErrScheduledRequired);
        return;
      }
      const targetTime = new Date(utcIso).getTime();
      const nowTime = Date.now();
      if (isNaN(targetTime) || targetTime <= nowTime) {
        setScheduledError(t.content.noticeErrPast);
        return;
      }
      if (targetTime > nowTime + 30 * 24 * 60 * 60 * 1000) {
        setScheduledError(t.content.noticeErrTooFar);
        return;
      }
      scheduledAtUtc = utcIso;
    }

    setSaving(true);
    setError('');
    try {
      const res = await session.api.request<AppNotification>('/admin/notifications', {
        method: 'POST',
        body: {
          title: title.trim(),
          body: body.trim(),
          send_push: true,
          ...(scheduledAtUtc ? { scheduled_at: scheduledAtUtc } : {}),
          ...(superadmin && businessId ? { business_id: businessId } : {}),
        },
      });
      await queryClient.invalidateQueries({ queryKey: [...privateKey, 'app-notifications'] });
      onClose();
      onCreated?.(res.push, res.scheduled_at);
    } catch (saveError) {
      setError(messageForError(saveError, locale));
    } finally {
      setSaving(false);
    }
  };

  return (
    <DialogFrame title={t.content.noticeDialogTitle} onClose={onClose}>
      <form className="mutation-form" noValidate onSubmit={event => { void submit(event); }}>
        {superadmin && (
          <>
            <label htmlFor="note-business">{t.content.noticeFieldTo}</label>
            <BusinessPicker id="note-business" value={businessId} onChange={setBusinessId} allowAll={t.content.noticeAllClients} />
          </>
        )}
        <label htmlFor="note-title">{t.content.noticeFieldTitle}</label>
        <input id="note-title" value={title} maxLength={120} onChange={event => setTitle(event.target.value)} required autoFocus />
        <label htmlFor="note-body">{t.content.noticeFieldBody}</label>
        <textarea id="note-body" rows={4} value={body} maxLength={2000} onChange={event => setBody(event.target.value)} required />

        <fieldset className="mutation-fieldset">
          <legend>{t.content.noticeWhenToSend}</legend>
          <div className="mutation-radio-group">
            <label className="mutation-radio-label">
              <input
                type="radio"
                name="whenToSend"
                value="now"
                checked={whenToSend === 'now'}
                onChange={() => { setWhenToSend('now'); setScheduledError(''); }}
              />
              {t.content.noticeSendNow}
            </label>
            <label className="mutation-radio-label">
              <input
                type="radio"
                name="whenToSend"
                value="scheduled"
                checked={whenToSend === 'scheduled'}
                onChange={() => { setWhenToSend('scheduled'); setScheduledError(''); }}
              />
              {t.content.noticeSendScheduled}
            </label>
          </div>
        </fieldset>

        {whenToSend === 'scheduled' && (
          <>
            <label htmlFor="note-scheduled">{t.content.noticeFieldScheduledTime}</label>
            <input
              id="note-scheduled"
              type="datetime-local"
              value={scheduledLocal}
              min={getAstanaNowLocal()}
              aria-invalid={Boolean(scheduledError)}
              onChange={event => { setScheduledLocal(event.target.value); setScheduledError(''); }}
            />
            {scheduledError && <p className="form-error">{scheduledError}</p>}
          </>
        )}

        <p className="muted-copy">{t.content.noticeHint}</p>
        {error && <p className="form-error" role="alert">{error}</p>}
        <footer className="mutation-actions">
          <button className="button button-primary" type="submit" disabled={saving}>
            {saving
              ? t.content.sendingBtn
              : whenToSend === 'scheduled'
                ? t.content.noticeScheduleBtn
                : t.content.sendBtn}
          </button>
          <button className="button button-secondary" type="button" onClick={onClose} disabled={saving}>
            {t.content.cancelBtn}
          </button>
        </footer>
      </form>
    </DialogFrame>
  );
}
