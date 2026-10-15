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

type Tab = 'promotions' | 'notifications';
const GLOBAL = '';

function useIsSuperadmin() {
  const { view } = useAdminSession();
  return view.status === 'authenticated' && view.admin.role === 'superadmin';
}

function BusinessPicker({ id, value, onChange, allowAll }: { id: string; value: string; onChange: (value: string) => void; allowAll: string }) {
  const businesses = useBusinesses({ limit: 100, offset: 0 });
  return <select id={id} value={value} onChange={event => onChange(event.target.value)}>
    <option value={GLOBAL}>{allowAll}</option>
    {businesses.data?.items.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
  </select>;
}

export function ContentPage() {
  const superadmin = useIsSuperadmin();
  const [tab, setTab] = useState<Tab>('promotions');
  const [businessFilter, setBusinessFilter] = useState(GLOBAL);
  const [editing, setEditing] = useState<Promotion | 'new' | null>(null);
  const [noticeOpen, setNoticeOpen] = useState(false);
  return <div className="page-stack">
    <PageHeading eyebrow="МОБИЛЬНОЕ ПРИЛОЖЕНИЕ" title="Приложение" subtitle="Баннеры, акции и уведомления, которые видят покупатели."
      actions={tab === 'promotions'
        ? <button className="button button-primary" type="button" onClick={() => setEditing('new')}>Добавить акцию</button>
        : <button className="button button-primary" type="button" onClick={() => setNoticeOpen(true)}>Отправить уведомление</button>} />
    <section className="filter-panel">
      <div className="search-tabs" role="tablist">
        <button type="button" role="tab" aria-selected={tab === 'promotions'} className={tab === 'promotions' ? 'search-tab selected' : 'search-tab'} onClick={() => setTab('promotions')}>Акции и баннеры</button>
        <button type="button" role="tab" aria-selected={tab === 'notifications'} className={tab === 'notifications' ? 'search-tab selected' : 'search-tab'} onClick={() => setTab('notifications')}>Уведомления</button>
      </div>
      {superadmin && <div className="filter-controls"><label className="form-control business-select" htmlFor="content-business">Бизнес
        <BusinessPicker id="content-business" value={businessFilter} onChange={setBusinessFilter} allowAll="Все записи" /></label></div>}
    </section>
    {tab === 'promotions'
      ? <PromotionsTable businessId={businessFilter || undefined} onEdit={setEditing} />
      : <NotificationsTable businessId={businessFilter || undefined} />}
    {editing && <PromotionDialog promotion={editing === 'new' ? undefined : editing} onClose={() => setEditing(null)} />}
    {noticeOpen && <NotificationDialog onClose={() => setNoticeOpen(false)} />}
  </div>;
}

function PromotionsTable({ businessId, onEdit }: { businessId?: string; onEdit: (promotion: Promotion) => void }) {
  const [page, setPage] = usePage();
  const query = usePromotions(businessId, page);
  const remove = useRemove('promotions');
  if (query.isPending) return <LoadingPage label="Загружаем акции…" />;
  if (query.isError) return <ErrorNotice error={query.error} retry={() => { void query.refetch(); }} />;
  return <>{remove.error && <ErrorNotice error={remove.error} />}<DataTable<Promotion> page={{ ...page, has_more: query.data.has_more }} onPage={setPage} rows={query.data.items} rowKey={item => item.id} columns={[
    { key: 'title', title: 'АКЦИЯ', render: item => <span className="table-name">{item.title}<span>{item.badge ?? item.subtitle ?? ''}</span></span> },
    { key: 'kind', title: 'МЕСТО', render: item => item.kind === 'banner' ? 'Баннер на главной' : 'Раздел «Акции»' },
    { key: 'audience', title: 'ДЛЯ КОГО', render: item => item.business_id ? 'Клиенты бизнеса' : 'Все клиенты' },
    { key: 'status', title: 'СТАТУС', render: item => <StatusPill tone={item.is_active ? 'positive' : 'neutral'}>{item.is_active ? 'Показывается' : 'Скрыта'}</StatusPill> },
    { key: 'period', title: 'ПЕРИОД', render: item => <span className="mono-value">{item.starts_at ? formatDate(item.starts_at) : '—'} — {item.ends_at ? formatDate(item.ends_at) : '∞'}</span> },
    { key: 'actions', title: '', align: 'right', render: item => <span className="pagination-actions">
      <button className="link-button" type="button" onClick={() => onEdit(item)}>Изменить</button>
      <button className="link-button" type="button" disabled={remove.pending} onClick={() => { if (window.confirm(`Удалить «${item.title}»?`)) void remove.run(item.id); }}>Удалить</button>
    </span> },
  ]} /></>;
}

function NotificationsTable({ businessId }: { businessId?: string }) {
  const [page, setPage] = usePage();
  const query = useAppNotifications(businessId, page);
  const remove = useRemove('notifications');
  if (query.isPending) return <LoadingPage label="Загружаем уведомления…" />;
  if (query.isError) return <ErrorNotice error={query.error} retry={() => { void query.refetch(); }} />;
  return <>{remove.error && <ErrorNotice error={remove.error} />}<DataTable<AppNotification> page={{ ...page, has_more: query.data.has_more }} onPage={setPage} rows={query.data.items} rowKey={item => item.id} columns={[
    { key: 'title', title: 'УВЕДОМЛЕНИЕ', render: item => <span className="table-name">{item.title}<span>{item.body}</span></span> },
    { key: 'audience', title: 'ДЛЯ КОГО', render: item => item.business_id ? 'Клиенты бизнеса' : 'Все клиенты' },
    { key: 'created', title: 'ОТПРАВЛЕНО', render: item => <time dateTime={item.created_at}>{formatDate(item.created_at)}</time> },
    { key: 'actions', title: '', align: 'right', render: item => <button className="link-button" type="button" disabled={remove.pending} onClick={() => { if (window.confirm('Удалить уведомление у всех клиентов?')) void remove.run(item.id); }}>Удалить</button> },
  ]} /></>;
}

function useRemove(resource: 'promotions' | 'notifications') {
  const { session } = useAdminSession();
  const queryClient = useQueryClient();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const run = async (id: string) => {
    setPending(true); setError(null);
    try {
      await session.api.request<void>(`/admin/${resource}/${encodeURIComponent(id)}`, { method: 'DELETE' });
      await queryClient.invalidateQueries({ queryKey: [...privateKey, resource === 'promotions' ? 'promotions' : 'app-notifications'] });
    } catch (removeError) { setError(removeError); } finally { setPending(false); }
  };
  return { run, pending, error };
}

const toLocalInput = (value: string | null) => value ? new Date(new Date(value).getTime() - new Date(value).getTimezoneOffset() * 60_000).toISOString().slice(0, 16) : '';
const fromLocalInput = (value: string) => value ? new Date(value).toISOString() : null;

function PromotionDialog({ promotion, onClose }: { promotion?: Promotion; onClose: () => void }) {
  const { session } = useAdminSession();
  const superadmin = useIsSuperadmin();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    business_id: promotion?.business_id ?? GLOBAL, kind: promotion?.kind ?? 'offer' as PromotionKind,
    title: promotion?.title ?? '', subtitle: promotion?.subtitle ?? '', badge: promotion?.badge ?? '', body: promotion?.body ?? '',
    image_url: promotion?.image_url ?? '', starts_at: toLocalInput(promotion?.starts_at ?? null), ends_at: toLocalInput(promotion?.ends_at ?? null),
    sort_order: String(promotion?.sort_order ?? 0), is_active: promotion?.is_active ?? true,
  });
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const set = (key: keyof typeof form) => (event: { target: { value: string } }) => setForm(current => ({ ...current, [key]: event.target.value }));

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    if (!form.title.trim()) { setError('Введите заголовок.'); return; }
    if (form.image_url.trim() && !form.image_url.trim().startsWith('https://')) { setError('Картинка должна быть HTTPS-ссылкой.'); return; }
    const sort = Number(form.sort_order);
    if (!Number.isInteger(sort) || Math.abs(sort) > 1000) { setError('Порядок — целое число от -1000 до 1000.'); return; }
    const payload = {
      kind: form.kind, title: form.title.trim(), subtitle: form.subtitle.trim() || null, badge: form.badge.trim() || null,
      body: form.body.trim() || null, image_url: form.image_url.trim() || null, starts_at: fromLocalInput(form.starts_at),
      ends_at: fromLocalInput(form.ends_at), sort_order: sort, is_active: form.is_active,
    };
    setSaving(true);
    try {
      if (promotion) await session.api.request<Promotion>(`/admin/promotions/${encodeURIComponent(promotion.id)}`, { method: 'PATCH', body: payload });
      else await session.api.request<Promotion>('/admin/promotions', { method: 'POST', body: { ...payload, ...(superadmin && form.business_id ? { business_id: form.business_id } : {}) } });
      await queryClient.invalidateQueries({ queryKey: [...privateKey, 'promotions'] });
      onClose();
    } catch (saveError) { setError(messageForError(saveError)); } finally { setSaving(false); }
  };

  return <DialogFrame title={promotion ? 'Изменить акцию' : 'Новая акция'} onClose={onClose}>
    <form className="mutation-form" onSubmit={event => { void submit(event); }}>
      {superadmin && !promotion && <><label htmlFor="promo-business">Для кого</label>
        <BusinessPicker id="promo-business" value={form.business_id} onChange={value => setForm(current => ({ ...current, business_id: value }))} allowAll="Все клиенты" /></>}
      <label htmlFor="promo-kind">Где показывать</label>
      <select id="promo-kind" value={form.kind} onChange={set('kind')}>
        <option value="offer">Раздел «Акции» и «Горячие предложения»</option><option value="banner">Баннер-карусель на главной</option>
      </select>
      <label htmlFor="promo-title">Заголовок</label>
      <input id="promo-title" value={form.title} maxLength={120} onChange={set('title')} required autoFocus />
      <label htmlFor="promo-badge">Плашка (например, «Акция недели»)</label>
      <input id="promo-badge" value={form.badge} maxLength={40} onChange={set('badge')} />
      <label htmlFor="promo-subtitle">Подзаголовок</label>
      <input id="promo-subtitle" value={form.subtitle} maxLength={255} onChange={set('subtitle')} />
      <label htmlFor="promo-body">Описание</label>
      <textarea id="promo-body" rows={4} value={form.body} maxLength={4000} onChange={set('body')} />
      <label htmlFor="promo-image">Картинка (HTTPS URL)</label>
      <input id="promo-image" type="url" value={form.image_url} maxLength={1024} onChange={set('image_url')} />
      <label htmlFor="promo-start">Начало показа</label>
      <input id="promo-start" type="datetime-local" value={form.starts_at} onChange={set('starts_at')} />
      <label htmlFor="promo-end">Конец показа</label>
      <input id="promo-end" type="datetime-local" value={form.ends_at} onChange={set('ends_at')} />
      <label htmlFor="promo-sort">Порядок (меньше — выше)</label>
      <input id="promo-sort" type="number" value={form.sort_order} onChange={set('sort_order')} />
      <label htmlFor="promo-active"><input id="promo-active" type="checkbox" checked={form.is_active} style={{ width: 'auto', minHeight: 0, marginRight: 8 }}
        onChange={event => setForm(current => ({ ...current, is_active: event.target.checked }))} />Показывать в приложении</label>
      {error && <p className="form-error" role="alert">{error}</p>}
      <footer className="mutation-actions">
        <button className="button button-secondary" type="button" onClick={onClose} disabled={saving}>Отмена</button>
        <button className="button button-primary" type="submit" disabled={saving}>{saving ? 'Сохраняем…' : 'Сохранить'}</button>
      </footer>
    </form>
  </DialogFrame>;
}

function NotificationDialog({ onClose }: { onClose: () => void }) {
  const { session } = useAdminSession();
  const superadmin = useIsSuperadmin();
  const queryClient = useQueryClient();
  const [businessId, setBusinessId] = useState(GLOBAL);
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!title.trim() || !body.trim()) { setError('Заполните заголовок и текст.'); return; }
    setSaving(true); setError('');
    try {
      await session.api.request<AppNotification>('/admin/notifications', { method: 'POST', body: {
        title: title.trim(), body: body.trim(), ...(superadmin && businessId ? { business_id: businessId } : {}),
      } });
      await queryClient.invalidateQueries({ queryKey: [...privateKey, 'app-notifications'] });
      onClose();
    } catch (saveError) { setError(messageForError(saveError)); } finally { setSaving(false); }
  };
  return <DialogFrame title="Отправить уведомление" onClose={onClose}>
    <form className="mutation-form" onSubmit={event => { void submit(event); }}>
      {superadmin && <><label htmlFor="note-business">Кому</label>
        <BusinessPicker id="note-business" value={businessId} onChange={setBusinessId} allowAll="Всем клиентам" /></>}
      <label htmlFor="note-title">Заголовок</label>
      <input id="note-title" value={title} maxLength={120} onChange={event => setTitle(event.target.value)} required autoFocus />
      <label htmlFor="note-body">Текст</label>
      <textarea id="note-body" rows={4} value={body} maxLength={2000} onChange={event => setBody(event.target.value)} required />
      <p className="muted-copy">Уведомление появится в разделе «Уведомления» у клиентов и подсветит значок колокольчика.</p>
      {error && <p className="form-error" role="alert">{error}</p>}
      <footer className="mutation-actions">
        <button className="button button-secondary" type="button" onClick={onClose} disabled={saving}>Отмена</button>
        <button className="button button-primary" type="submit" disabled={saving}>{saving ? 'Отправляем…' : 'Отправить'}</button>
      </footer>
    </form>
  </DialogFrame>;
}
