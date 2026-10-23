import { useState, type FormEvent } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { messageForError } from '../api/errors';
import { privateKey, useAppNotifications, useBusinesses, usePromotions } from '../api/queries';
import type { AppNotification, Promotion, PromotionKind } from '../api/types';
import { useAdminSession } from '../auth/provider';
import { DataTable } from '../components/DataTable';
import { ErrorNotice, LoadingPage, PageHeading, StatusPill } from '../components/Feedback';
import { DialogFrame } from '../features/AdminMutations';
import { formatDate } from '../utils/format';
import { usePage } from '../utils/usePage';
import { useLocale } from '../i18n/LocaleContext';
import { useAdminTranslation } from '../i18n/admin';

type Tab = 'promotions' | 'notifications';
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
  const t = useAdminTranslation();
  const [tab, setTab] = useState<Tab>('promotions');
  const [businessFilter, setBusinessFilter] = useState(GLOBAL);
  const [editing, setEditing] = useState<Promotion | 'new' | null>(null);
  const [noticeOpen, setNoticeOpen] = useState(false);

  return (
    <div className="page-stack">
      <PageHeading
        eyebrow={t.content.eyebrow}
        title={t.content.title}
        subtitle={t.content.subtitle}
        actions={
          tab === 'promotions' ? (
            <button className="button button-primary" type="button" onClick={() => setEditing('new')}>
              {t.content.addPromoBtn}
            </button>
          ) : (
            <button className="button button-primary" type="button" onClick={() => setNoticeOpen(true)}>
              {t.content.sendNoticeBtn}
            </button>
          )
        }
      />
      <section className="filter-panel">
        <div className="search-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'promotions'}
            className={tab === 'promotions' ? 'search-tab selected' : 'search-tab'}
            onClick={() => setTab('promotions')}
          >
            {t.content.tabPromotions}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'notifications'}
            className={tab === 'notifications' ? 'search-tab selected' : 'search-tab'}
            onClick={() => setTab('notifications')}
          >
            {t.content.tabNotifications}
          </button>
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
      {tab === 'promotions' ? (
        <PromotionsTable businessId={businessFilter || undefined} onEdit={setEditing} />
      ) : (
        <NotificationsTable businessId={businessFilter || undefined} />
      )}
      {editing && <PromotionDialog promotion={editing === 'new' ? undefined : editing} onClose={() => setEditing(null)} />}
      {noticeOpen && <NotificationDialog onClose={() => setNoticeOpen(false)} />}
    </div>
  );
}

function PromotionsTable({ businessId, onEdit }: { businessId?: string; onEdit: (promotion: Promotion) => void }) {
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const [page, setPage] = usePage();
  const query = usePromotions(businessId, page);
  const remove = useRemove('promotions');

  if (query.isPending) return <LoadingPage label={t.content.loadingPromos} />;
  if (query.isError) return <ErrorNotice error={query.error} retry={() => { void query.refetch(); }} />;

  return (
    <>
      {remove.error && <ErrorNotice error={remove.error} />}
      <DataTable<Promotion>
        page={{ ...page, has_more: query.data.has_more }}
        onPage={setPage}
        rows={query.data.items}
        rowKey={item => item.id}
        columns={[
          {
            key: 'title',
            title: t.content.colPromo,
            render: item => (
              <span className="table-name">
                {item.title}
                <span>{item.badge ?? item.subtitle ?? ''}</span>
              </span>
            ),
          },
          {
            key: 'kind',
            title: t.content.colKind,
            render: item => (item.kind === 'banner' ? t.content.kindBanner : t.content.kindOffer),
          },
          {
            key: 'audience',
            title: t.content.colAudience,
            render: item => (item.business_id ? t.content.audienceBiz : t.content.audienceAll),
          },
          {
            key: 'status',
            title: t.content.colPromoStatus,
            render: item => (
              <StatusPill tone={item.is_active ? 'positive' : 'neutral'}>
                {item.is_active ? t.content.statusShown : t.content.statusHidden}
              </StatusPill>
            ),
          },
          {
            key: 'period',
            title: t.content.colPeriod,
            render: item => (
              <span className="mono-value">
                {item.starts_at ? formatDate(item.starts_at, locale) : '—'} — {item.ends_at ? formatDate(item.ends_at, locale) : '∞'}
              </span>
            ),
          },
          {
            key: 'actions',
            title: '',
            align: 'right',
            render: item => (
              <span className="pagination-actions">
                <button className="link-button" type="button" onClick={() => onEdit(item)}>
                  {t.content.editBtn}
                </button>
                <button
                  className="link-button"
                  type="button"
                  disabled={remove.pending}
                  onClick={() => {
                    if (window.confirm(t.content.confirmDeletePromo(item.title))) void remove.run(item.id);
                  }}
                >
                  {t.content.deleteBtn}
                </button>
              </span>
            ),
          },
        ]}
      />
    </>
  );
}

function NotificationsTable({ businessId }: { businessId?: string }) {
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
            render: item => <time dateTime={item.created_at}>{formatDate(item.created_at, locale)}</time>,
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

const toLocalInput = (value: string | null) =>
  value ? new Date(new Date(value).getTime() - new Date(value).getTimezoneOffset() * 60_000).toISOString().slice(0, 16) : '';
const fromLocalInput = (value: string) => (value ? new Date(value).toISOString() : null);

function PromotionDialog({ promotion, onClose }: { promotion?: Promotion; onClose: () => void }) {
  const { session } = useAdminSession();
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const superadmin = useIsSuperadmin();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    business_id: promotion?.business_id ?? GLOBAL,
    kind: promotion?.kind ?? ('offer' as PromotionKind),
    title: promotion?.title ?? '',
    subtitle: promotion?.subtitle ?? '',
    badge: promotion?.badge ?? '',
    body: promotion?.body ?? '',
    image_url: promotion?.image_url ?? '',
    starts_at: toLocalInput(promotion?.starts_at ?? null),
    ends_at: toLocalInput(promotion?.ends_at ?? null),
    sort_order: String(promotion?.sort_order ?? 0),
    is_active: promotion?.is_active ?? true,
  });
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const set = (key: keyof typeof form) => (event: { target: { value: string } }) =>
    setForm(current => ({ ...current, [key]: event.target.value }));

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
    if (!Number.isInteger(sort) || Math.abs(sort) > 1000) {
      setError(t.content.promoErrSort);
      return;
    }
    const payload = {
      kind: form.kind,
      title: form.title.trim(),
      subtitle: form.subtitle.trim() || null,
      badge: form.badge.trim() || null,
      body: form.body.trim() || null,
      image_url: form.image_url.trim() || null,
      starts_at: fromLocalInput(form.starts_at),
      ends_at: fromLocalInput(form.ends_at),
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

  return (
    <DialogFrame title={promotion ? t.content.promoDialogTitleEdit : t.content.promoDialogTitleNew} onClose={onClose}>
      <form className="mutation-form" onSubmit={event => { void submit(event); }}>
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
        <label htmlFor="promo-kind">{t.content.promoFieldKind}</label>
        <select id="promo-kind" value={form.kind} onChange={set('kind')}>
          <option value="offer">{t.content.promoKindOfferOption}</option>
          <option value="banner">{t.content.promoKindBannerOption}</option>
        </select>
        <label htmlFor="promo-title">{t.content.promoFieldTitle}</label>
        <input id="promo-title" value={form.title} maxLength={120} onChange={set('title')} required autoFocus />
        <label htmlFor="promo-badge">{t.content.promoFieldBadge}</label>
        <input id="promo-badge" value={form.badge} maxLength={40} onChange={set('badge')} />
        <label htmlFor="promo-subtitle">{t.content.promoFieldSubtitle}</label>
        <input id="promo-subtitle" value={form.subtitle} maxLength={255} onChange={set('subtitle')} />
        <label htmlFor="promo-body">{t.content.promoFieldBody}</label>
        <textarea id="promo-body" rows={4} value={form.body} maxLength={4000} onChange={set('body')} />
        <label htmlFor="promo-image">{t.content.promoFieldImage}</label>
        <input id="promo-image" type="url" value={form.image_url} maxLength={1024} onChange={set('image_url')} />
        <label htmlFor="promo-start">{t.content.promoFieldStart}</label>
        <input id="promo-start" type="datetime-local" value={form.starts_at} onChange={set('starts_at')} />
        <label htmlFor="promo-end">{t.content.promoFieldEnd}</label>
        <input id="promo-end" type="datetime-local" value={form.ends_at} onChange={set('ends_at')} />
        <label htmlFor="promo-sort">{t.content.promoFieldSort}</label>
        <input id="promo-sort" type="number" value={form.sort_order} onChange={set('sort_order')} />
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
          <button className="button button-secondary" type="button" onClick={onClose} disabled={saving}>
            {t.content.cancelBtn}
          </button>
          <button className="button button-primary" type="submit" disabled={saving}>
            {saving ? t.content.savingBtn : t.content.saveBtn}
          </button>
        </footer>
      </form>
    </DialogFrame>
  );
}

function NotificationDialog({ onClose }: { onClose: () => void }) {
  const { session } = useAdminSession();
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const superadmin = useIsSuperadmin();
  const queryClient = useQueryClient();
  const [businessId, setBusinessId] = useState(GLOBAL);
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!title.trim() || !body.trim()) {
      setError(t.content.noticeErrFields);
      return;
    }
    setSaving(true);
    setError('');
    try {
      await session.api.request<AppNotification>('/admin/notifications', {
        method: 'POST',
        body: {
          title: title.trim(),
          body: body.trim(),
          ...(superadmin && businessId ? { business_id: businessId } : {}),
        },
      });
      await queryClient.invalidateQueries({ queryKey: [...privateKey, 'app-notifications'] });
      onClose();
    } catch (saveError) {
      setError(messageForError(saveError, locale));
    } finally {
      setSaving(false);
    }
  };

  return (
    <DialogFrame title={t.content.noticeDialogTitle} onClose={onClose}>
      <form className="mutation-form" onSubmit={event => { void submit(event); }}>
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
        <p className="muted-copy">{t.content.noticeHint}</p>
        {error && <p className="form-error" role="alert">{error}</p>}
        <footer className="mutation-actions">
          <button className="button button-secondary" type="button" onClick={onClose} disabled={saving}>
            {t.content.cancelBtn}
          </button>
          <button className="button button-primary" type="submit" disabled={saving}>
            {saving ? t.content.sendingBtn : t.content.sendBtn}
          </button>
        </footer>
      </form>
    </DialogFrame>
  );
}
