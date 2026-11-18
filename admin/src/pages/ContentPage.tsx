import { useEffect, useState, type FormEvent } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { ApiError, messageForError } from '../api/errors';
import { privateKey, useAllBusinesses, useAppNotifications, usePromotions } from '../api/queries';
import type { AppNotification, BroadcastPushResult, BusinessStore, Promotion, PromotionKind } from '../api/types';
import { useAdminSession } from '../auth/provider';
import { useActiveBusiness } from '../context/ActiveBusinessContext';
import { BusinessSelect } from '../components/BusinessSelect';
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
  const superadmin = useIsSuperadmin();
  const businesses = useAllBusinesses(superadmin);
  return (
    <BusinessSelect
      id={id}
      value={value}
      onChange={onChange}
      allowAllLabel={allowAll}
      businesses={businesses}
    />
  );
}

export function ContentPage() {
  const superadmin = useIsSuperadmin();
  const { view } = useAdminSession();
  const { setActiveBusiness } = useActiveBusiness();
  const businessesQuery = useAllBusinesses(superadmin);
  const t = useAdminTranslation();
  const [adminTab, setAdminTab] = useState<SuperadminTab>('promotions');
  const [clientTab, setClientTab] = useState<ClientTab>('banners');
  const [businessFilter, setBusinessFilter] = useState(GLOBAL);
  const [editing, setEditing] = useState<Promotion | 'new' | 'new-banner' | 'new-offer' | null>(null);
  const [editingStore, setEditingStore] = useState<BusinessStore | 'new' | null>(null);
  const [noticeOpen, setNoticeOpen] = useState(false);
  const [noticeFeedback, setNoticeFeedback] = useState<string | null>(null);

  useEffect(() => {
    if (!superadmin) return;
    const selected = businessFilter ? businessesQuery.items.find(b => b.id === businessFilter) : null;
    setActiveBusiness(selected ? {
      id: selected.id,
      name: selected.name,
      logo_url: selected.logo_url,
      android_app_id: selected.android_app_id,
    } : null);
  }, [superadmin, businessFilter, businessesQuery.items, setActiveBusiness]);

  useEffect(() => () => setActiveBusiness(null), [setActiveBusiness]);

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
            <div className="form-control business-select">
              <label htmlFor="content-business">{t.content.businessFilterLabel}</label>
              <BusinessPicker id="content-business" value={businessFilter} onChange={setBusinessFilter} allowAll={t.content.allRecords} />
            </div>
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
  const [page, setPage] = usePage(25);

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
      {query.data.items.length === 0 && page.offset === 0 && emptyMessage ? (
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
  useEffect(() => {
    setPage(0);
  }, [businessId, setPage]);
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
  const [startNow, setStartNow] = useState<boolean>(() => (promotion ? promotion.starts_at === null : true));
  const [startNowDisplay, setStartNowDisplay] = useState<string>(() => getAstanaNowLocal());
  const [noEndDate, setNoEndDate] = useState<boolean>(() => (promotion ? promotion.ends_at === null : true));
  const [startsDirty, setStartsDirty] = useState(false);
  const [endsDirty, setEndsDirty] = useState(false);
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState({
    title: '',
    image_url: '',
    sort_order: '',
    starts_at: '',
    ends_at: '',
  });
  const [saving, setSaving] = useState(false);
  const [uploadingImage, setUploadingImage] = useState(false);

  useEffect(() => {
    if (!startNow) return;
    const refreshDisplay = () => {
      setStartNowDisplay(getAstanaNowLocal());
    };
    const onVisibility = () => {
      if (document.visibilityState === 'visible') refreshDisplay();
    };
    window.addEventListener('focus', refreshDisplay);
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      window.removeEventListener('focus', refreshDisplay);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [startNow]);

  const set = (key: keyof typeof form) => (event: { target: { value: string } }) => {
    setForm(current => ({ ...current, [key]: event.target.value }));
    if (key === 'starts_at') setStartsDirty(true);
    if (key === 'ends_at') setEndsDirty(true);
    if (key === 'title' || key === 'image_url' || key === 'sort_order' || key === 'starts_at' || key === 'ends_at') {
      setFieldErrors(current => ({ ...current, [key]: '' }));
    }
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    const nextFieldErrors = {
      title: '',
      image_url: '',
      sort_order: '',
      starts_at: '',
      ends_at: '',
    };

    if (!form.title.trim()) {
      nextFieldErrors.title = t.content.promoErrTitle;
    }
    if (form.image_url.trim() && !form.image_url.trim().startsWith('https://')) {
      nextFieldErrors.image_url = t.content.promoErrImage;
    }
    const sort = Number(form.sort_order);
    if (!form.sort_order.trim() || !Number.isInteger(sort) || Math.abs(sort) > 1000) {
      nextFieldErrors.sort_order = t.content.promoErrSort;
    }

    const startRaw = startNow ? '' : form.starts_at.trim();
    const endRaw = noEndDate ? '' : form.ends_at.trim();

    if (!startNow) {
      if (!startRaw) {
        nextFieldErrors.starts_at = t.content.promoErrStartRequired;
      } else if (!isValidAstanaDateTimeLocal(startRaw)) {
        nextFieldErrors.starts_at = t.content.promoErrInvalidDate;
      }
    }

    if (!noEndDate) {
      if (!endRaw) {
        nextFieldErrors.ends_at = t.content.promoErrEndRequired;
      } else if (!isValidAstanaDateTimeLocal(endRaw)) {
        nextFieldErrors.ends_at = t.content.promoErrInvalidDate;
      }
    }

    const resolvedStartIso = startNow
      ? null
      : promotion && !startsDirty && promotion.starts_at
        ? promotion.starts_at
        : startRaw
          ? astanaLocalToUtcIso(startRaw)
          : null;

    const resolvedEndIso = noEndDate
      ? null
      : promotion && !endsDirty && promotion.ends_at
        ? promotion.ends_at
        : endRaw
          ? astanaLocalToUtcIso(endRaw)
          : null;

    if (!startNow && resolvedStartIso && (!promotion || startsDirty)) {
      if (new Date(resolvedStartIso).getTime() < Date.now() - 15_000) {
        nextFieldErrors.starts_at = t.content.promoErrStartPast;
      }
    }

    if (resolvedStartIso && resolvedEndIso) {
      if (new Date(resolvedEndIso).getTime() <= new Date(resolvedStartIso).getTime()) {
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
      starts_at: resolvedStartIso,
      ends_at: resolvedEndIso,
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
      const msg = messageForError(saveError, locale);
      if (saveError instanceof ApiError && saveError.code === 'VALIDATION_ERROR') {
        const fields = saveError.detail?.fields ?? [];
        const hint = saveError.detail?.validationHint;
        const mapped = {
          title: fields.includes('title') ? t.content.promoErrTitle : '',
          image_url: fields.includes('image_url') ? t.content.promoErrImage : '',
          sort_order: fields.includes('sort_order') ? t.content.promoErrSort : '',
          starts_at:
            hint === 'starts_at_past'
              ? t.content.promoErrStartPast
              : fields.includes('starts_at')
                ? msg
                : '',
          ends_at:
            hint === 'ends_at_order'
              ? t.content.promoErrEndAfterStart
              : fields.includes('ends_at')
                ? msg
                : '',
        };
        setFieldErrors(mapped);
        setError(msg);
      } else {
        setError(msg);
      }
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
    <DialogFrame title={dialogTitle} onClose={onClose} className="mutation-dialog--wide promo-dialog">
      <form className="mutation-form" noValidate onSubmit={event => { void submit(event); }}>
        {superadmin && !promotion && (
          <div className="mutation-form-row--two-col">
            <div className="form-control">
              <label htmlFor="promo-business">{t.content.promoFieldAudience}</label>
              <BusinessPicker
                id="promo-business"
                value={form.business_id}
                onChange={value => setForm(current => ({ ...current, business_id: value }))}
                allowAll={t.content.promoAllClients}
              />
            </div>
            <div className="form-control">
              <label htmlFor="promo-kind">{t.content.promoFieldKind}</label>
              <select id="promo-kind" value={form.kind} onChange={set('kind')}>
                <option value="offer">{t.content.promoKindOfferOption}</option>
                <option value="banner">{t.content.promoKindBannerOption}</option>
              </select>
            </div>
          </div>
        )}
        {superadmin && promotion && (
          <div className="form-control">
            <label htmlFor="promo-kind">{t.content.promoFieldKind}</label>
            <select id="promo-kind" value={form.kind} onChange={set('kind')}>
              <option value="offer">{t.content.promoKindOfferOption}</option>
              <option value="banner">{t.content.promoKindBannerOption}</option>
            </select>
          </div>
        )}

        {/* Full-width Title */}
        <div className="form-control">
          <label htmlFor="promo-title">{t.content.promoFieldTitle}</label>
          <input
            id="promo-title"
            value={form.title}
            maxLength={120}
            aria-invalid={Boolean(fieldErrors.title)}
            onChange={set('title')}
            required
            autoFocus
          />
          {fieldErrors.title && <p className="form-error">{fieldErrors.title}</p>}
        </div>

        {/* Full-width Subtitle */}
        <div className="form-control">
          <label htmlFor="promo-subtitle">{t.content.promoFieldSubtitle}</label>
          <input id="promo-subtitle" value={form.subtitle} maxLength={255} onChange={set('subtitle')} />
        </div>

        {/* Full-width Description */}
        <div className="form-control">
          <label htmlFor="promo-body">{t.content.promoFieldBody}</label>
          <textarea id="promo-body" rows={3} value={form.body} maxLength={4000} onChange={set('body')} />
        </div>

        {/* 2 columns: Плашка | Сортировка */}
        <div className="mutation-form-row--two-col">
          <div className="form-control">
            <label htmlFor="promo-badge">{t.content.promoFieldBadge}</label>
            <input id="promo-badge" value={form.badge} maxLength={40} onChange={set('badge')} />
          </div>

          <div className="form-control">
            <label htmlFor="promo-sort" title={t.content.promoFieldSort}>
              {t.content.promoFieldSortLabel}
            </label>
            <NumericInput
              id="promo-sort"
              min={-1000}
              max={1000}
              allowNegative
              value={form.sort_order}
              aria-invalid={Boolean(fieldErrors.sort_order)}
              onChange={set('sort_order')}
            />
            {fieldErrors.sort_order && <p className="form-error">{fieldErrors.sort_order}</p>}
          </div>
        </div>

        {/* 2 columns: Начало показа | Конец показа */}
        <div className="mutation-form-row--two-col">
          <div className="form-control promo-date-col">
            <label htmlFor="promo-start">{t.content.promoFieldStart}</label>
            <input
              id="promo-start"
              type="datetime-local"
              value={startNow ? startNowDisplay : form.starts_at}
              min={!startNow && (!promotion || startsDirty) ? getAstanaNowLocal() : undefined}
              disabled={startNow}
              aria-invalid={Boolean(fieldErrors.starts_at)}
              onChange={set('starts_at')}
            />
            <label className="checkbox-row promo-mode-checkbox" htmlFor="promo-start-now">
              <input
                id="promo-start-now"
                type="checkbox"
                checked={startNow}
                onChange={event => {
                  const checked = event.target.checked;
                  setStartNow(checked);
                  if (checked) {
                    setStartNowDisplay(getAstanaNowLocal());
                  }
                  setFieldErrors(current => ({ ...current, starts_at: '' }));
                }}
              />
              <span>{t.content.startNowBtn}</span>
            </label>
            {fieldErrors.starts_at && <p className="form-error">{fieldErrors.starts_at}</p>}
          </div>

          <div className="form-control promo-date-col">
            <label htmlFor="promo-end">{t.content.promoFieldEnd}</label>
            <input
              id="promo-end"
              type="datetime-local"
              value={noEndDate ? '' : form.ends_at}
              min={(!startNow && form.starts_at) || getAstanaNowLocal()}
              disabled={noEndDate}
              aria-invalid={Boolean(fieldErrors.ends_at)}
              onChange={set('ends_at')}
            />
            <label className="checkbox-row promo-mode-checkbox" htmlFor="promo-end-now">
              <input
                id="promo-end-now"
                type="checkbox"
                checked={noEndDate}
                onChange={event => {
                  const checked = event.target.checked;
                  setNoEndDate(checked);
                  setFieldErrors(current => ({ ...current, ends_at: '' }));
                }}
              />
              <span>{t.content.noEndDateBtn}</span>
            </label>
            {fieldErrors.ends_at && <p className="form-error">{fieldErrors.ends_at}</p>}
          </div>
        </div>

        {/* Attachment */}
        <div className="form-control promo-attachment-row">
          <label htmlFor="promo-image">{t.content.promoFieldImage}</label>
          <ImageUploadField
            id="promo-image"
            value={form.image_url}
            onChange={url => {
              setForm(current => ({ ...current, image_url: url }));
              setFieldErrors(current => ({ ...current, image_url: '' }));
            }}
            purpose="promotion"
            hint={form.kind === 'banner' ? t.content.promoImageHintBanner : t.content.promoImageHintOffer}
            onUploadingChange={setUploadingImage}
            disabled={saving}
          />
          {fieldErrors.image_url && <p className="form-error">{fieldErrors.image_url}</p>}
        </div>

        {/* Checkbox: Показывать в приложении */}
        <label className="checkbox-row" htmlFor="promo-active">
          <input
            id="promo-active"
            type="checkbox"
            checked={form.is_active}
            onChange={event => setForm(current => ({ ...current, is_active: event.target.checked }))}
          />
          <span>{t.content.promoFieldActive}</span>
        </label>

        {error && <p className="form-error" role="alert">{error}</p>}

        {/* Actions: Left-aligned buttons */}
        <footer className="dialog-actions dialog-actions--left">
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
