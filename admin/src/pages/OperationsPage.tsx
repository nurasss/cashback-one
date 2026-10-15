import { useState, type FormEvent, type ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { messageForError } from '../api/errors';
import { useAdminSession } from '../auth/provider';
import { privateKey, useBusinesses, useCard, useCardSearch, useUser, useUserSearch } from '../api/queries';
import type { AdminUser, Card, CardUnbindResult, PageQuery } from '../api/types';
import { DataTable } from '../components/DataTable';
import { EmptyState, ErrorNotice, LoadingPage, PageHeading, StatusPill } from '../components/Feedback';
import { formatBalance, formatDate } from '../utils/format';
import { usePage } from '../utils/usePage';

export function OperationsPage() {
  const { view } = useAdminSession();
  const [mode, setMode] = useState<'barcode' | 'phone'>('barcode');
  const [raw, setRaw] = useState('');
  const [businessId, setBusinessId] = useState('');
  const [criteria, setCriteria] = useState<{ barcode?: string; phone?: string; business_id?: string } | null>(null);
  const [cardPage, setCardPage] = usePage();
  const [userPage, setUserPage] = usePage();
  const businesses = useBusinesses({ limit: 100, offset: 0 }, view.status === 'authenticated' && view.admin.role === 'superadmin');
  const cardSearch = useCardSearch(criteria ?? {}, cardPage, criteria !== null && mode === 'barcode');
  const userSearch = useUserSearch({ phone: criteria?.phone ?? '', ...(criteria?.business_id ? { business_id: criteria.business_id } : {}) }, userPage, criteria !== null && mode === 'phone');

  const search = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const term = raw.trim();
    if (!term) return;
    if (mode === 'barcode' && !/^[0-9]{13}$/.test(term)) return;
    if (mode === 'phone' && term.replace(/\D/g, '').length < 7) return;
    const next = {
      ...(mode === 'barcode' ? { barcode: term } : { phone: term }),
      ...(businessId ? { business_id: businessId } : {}),
    };
    setCriteria(next);
    setCardPage(0);
    setUserPage(0);
  };

  const errors = mode === 'barcode' ? cardSearch.error : userSearch.error;
  const pending = mode === 'barcode' ? cardSearch.isFetching : userSearch.isFetching;
  const didSearch = criteria !== null;
  return <div className="page-stack"><PageHeading eyebrow="ПОИСК ПО ДАННЫМ" title="Карты и клиенты" subtitle={view.status === 'authenticated' && view.admin.business ? `Область поиска: «${view.admin.business.name}».` : 'Поиск использует только данные Cloud Backend.'} />
    <section className="search-panel surface-card">
      <div className="search-tabs" role="tablist" aria-label="Тип поиска">
        <button className={mode === 'barcode' ? 'search-tab selected' : 'search-tab'} type="button" role="tab" aria-selected={mode === 'barcode'} onClick={() => { setMode('barcode'); setRaw(''); setCriteria(null); }}>По номеру карты</button>
        <button className={mode === 'phone' ? 'search-tab selected' : 'search-tab'} type="button" role="tab" aria-selected={mode === 'phone'} onClick={() => { setMode('phone'); setRaw(''); setCriteria(null); }}>По телефону</button>
      </div>
      <form className="search-form" onSubmit={search}>
        <label className="form-control search-input"><span>{mode === 'barcode' ? '13-значный номер штрихкода' : 'Телефон клиента'}</span>
          <input aria-label={mode === 'barcode' ? 'Штрихкод карты' : 'Телефон клиента'} autoComplete="off" spellCheck={false}
            inputMode={mode === 'barcode' ? 'numeric' : 'tel'} maxLength={mode === 'barcode' ? 64 : 32} value={raw} onChange={event => setRaw(event.target.value)}
            placeholder={mode === 'barcode' ? 'Например, 0123456789012' : 'Например, +7 701 123 45 67'} />
        </label>
        {view.status === 'authenticated' && view.admin.role === 'superadmin' && <label className="form-control"><span>Бизнес</span>
          <select aria-label="Бизнес поиска" value={businessId} onChange={event => setBusinessId(event.target.value)}><option value="">Все бизнесы</option>{businesses.data?.items.map(business => <option key={business.id} value={business.id}>{business.name}</option>)}</select>
        </label>}
        <button className="button button-primary" type="submit" disabled={pending || !raw.trim()}>{pending ? 'Ищем…' : 'Найти'}</button>
      </form>
      <p className="search-hint">Barcode ищется точным совпадением строки, начальные нули сохраняются. Телефон нормализует сервер.</p>
    </section>
    {errors && didSearch && <ErrorNotice error={errors} retry={() => { if (mode === 'barcode') void cardSearch.refetch(); else void userSearch.refetch(); }} />}
    {!didSearch ? <EmptyState title="Начните поиск" detail={mode === 'barcode' ? 'Введите полный 13-значный номер карты.' : 'Введите телефон, чтобы найти профиль и видимые вам карты.'} /> :
      mode === 'barcode' ? <CardResults page={cardPage} setPage={setCardPage} rows={cardSearch.data?.items ?? []} hasMore={cardSearch.data?.has_more ?? false} /> :
        <UserResults page={userPage} setPage={setUserPage} rows={userSearch.data?.items ?? []} hasMore={userSearch.data?.has_more ?? false} />}
  </div>;
}

function CardResults({ page, setPage, rows, hasMore }: { page: PageQuery; setPage: (offset: number) => void; rows: Card[]; hasMore: boolean }) {
  return <DataTable<Card> page={{ ...page, has_more: hasMore }} onPage={setPage} rows={rows} rowKey={row => row.id} columns={[
    { key: 'barcode', title: 'КАРТА', render: row => <Link className="table-name mono-value" to={`/cards/${encodeURIComponent(row.id)}`}>{row.barcode}<span>{row.business_name}</span></Link> },
    { key: 'balance', title: 'БАЛАНС', render: row => <span className="numeric-value">{formatBalance(row.balance)}</span>, align: 'right' },
    { key: 'status', title: 'СТАТУС', render: row => <StatusPill tone={row.is_blocked ? 'negative' : 'positive'}>{row.is_blocked ? 'Заблокирована' : 'Не заблокирована'}</StatusPill> },
    { key: 'owner', title: 'КЛИЕНТ', render: row => row.bind_method && row.phone_masked ? <span>{row.phone_masked}</span> : <span className="muted-copy">Не привязана</span> },
    { key: 'updated', title: 'ОБНОВЛЕНА', render: row => <time dateTime={row.updated_at}>{formatDate(row.updated_at)}</time> },
  ]} />;
}

function UserResults({ page, setPage, rows, hasMore }: { page: PageQuery; setPage: (offset: number) => void; rows: AdminUser[]; hasMore: boolean }) {
  return <DataTable<AdminUser> page={{ ...page, has_more: hasMore }} onPage={setPage} rows={rows} rowKey={row => row.id} columns={[
    { key: 'phone', title: 'КЛИЕНТ', render: row => <Link className="table-name" to={`/users/${encodeURIComponent(row.id)}`}>{row.phone_masked ?? 'Телефон не указан'}<span>Язык: {row.language}</span></Link> },
    { key: 'cards', title: 'КАРТ В БИЗНЕСЕ', render: row => <span className="numeric-value">{row.business_cards_count}</span>, align: 'right' },
    { key: 'created', title: 'ЗАРЕГИСТРИРОВАН', render: row => <time dateTime={row.created_at}>{formatDate(row.created_at)}</time> },
  ]} />;
}

export function CardDetailPage() {
  const { view, session } = useAdminSession();
  const queryClient = useQueryClient();
  const { cardId = '' } = useParams<{ cardId: string }>();
  const query = useCard(cardId);
  const [unbindBusy, setUnbindBusy] = useState(false);
  const [unbindError, setUnbindError] = useState('');
  const [unbindResult, setUnbindResult] = useState<CardUnbindResult['status'] | null>(null);
  if (query.isPending) return <LoadingPage label="Загружаем карту…" />;
  if (query.isError || !query.data) return <div className="page-stack"><ErrorNotice error={query.error} retry={() => { void query.refetch(); }} /></div>;
  const card = query.data;
  const canUnbind = view.status === 'authenticated' && (view.admin.role === 'superadmin' || view.admin.role === 'business_manager');
  const submitUnbind = async () => {
    const maskedCustomer = card.phone_masked ?? 'клиент не указан';
    const warning = `Отвязать карту?\n\nБизнес: ${card.business_name}\nКлиент: ${maskedCustomer}\nШтрихкод: ${card.barcode}\n\nБудет удалена только связь с клиентом. Карта и баланс сохранятся.`;
    if (!window.confirm(warning)) return;
    setUnbindBusy(true); setUnbindError(''); setUnbindResult(null);
    try {
      const result = await session.api.request<CardUnbindResult>(`/admin/cards/${encodeURIComponent(card.id)}/unbind`, { method: 'POST', body: {} });
      setUnbindResult(result.status);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: [...privateKey, 'card', card.id] }),
        queryClient.invalidateQueries({ queryKey: [...privateKey, 'user'] }),
        queryClient.invalidateQueries({ queryKey: [...privateKey, 'card-search'] }),
        queryClient.invalidateQueries({ queryKey: [...privateKey, 'user-search'] }),
        queryClient.invalidateQueries({ queryKey: [...privateKey, 'business', card.business_id] }),
        queryClient.invalidateQueries({ queryKey: [...privateKey, 'dashboard'] }),
      ]);
    } catch (error) {
      setUnbindError(messageForError(error));
    } finally { setUnbindBusy(false); }
  };
  return <div className="page-stack"><PageHeading eyebrow="КАРТЫ / ПРОФИЛЬ" title={card.business_name} subtitle="Карта и привязка отображаются только для доступных вам бизнесов." actions={<>
      {canUnbind && <button className="button button-danger" type="button" disabled={unbindBusy || !card.bind_method} onClick={() => { void submitUnbind(); }}>{unbindBusy ? 'Отвязываем…' : 'Отвязать карту'}</button>}
      <Link className="button button-secondary" to="/operations">К результатам поиска</Link>
    </>} />
    {unbindError && <p className="form-error" role="alert">{unbindError}</p>}
    {unbindResult && <p className="success-copy" role="status">{unbindResult === 'unbound' ? 'Привязка удалена. Карта и баланс сохранены.' : 'Карта уже была отвязана.'}</p>}
    <section className="surface-card"><dl className="detail-list">
      <Detail label="Номер карты"><span className="mono-value">{card.barcode}</span></Detail><Detail label="Баланс"><strong className="numeric-value">{formatBalance(card.balance)}</strong></Detail>
      <Detail label="Статус"><StatusPill tone={card.is_blocked ? 'negative' : 'positive'}>{card.is_blocked ? 'Заблокирована' : 'Не заблокирована'}</StatusPill></Detail>
      <Detail label="Телефон карты">{card.phone_masked ?? 'Не указан'}</Detail><Detail label="Клиент">{card.full_name ?? 'Не указан'}</Detail>
      <Detail label="Язык профиля">{card.owner_language ?? 'Нет активного профиля'}</Detail><Detail label="Тип привязки">{card.bind_method ?? 'Не привязана'}</Detail>
      <Detail label="Дата привязки">{card.bound_at ? formatDate(card.bound_at) : '—'}</Detail><Detail label="Скрыта клиентом">{card.hidden_at ? formatDate(card.hidden_at) : 'Нет'}</Detail>
      <Detail label="Источник данных">POSCENTER Cloud mirror</Detail><Detail label="Обновлена"><time dateTime={card.updated_at}>{formatDate(card.updated_at)}</time></Detail>
    </dl></section>
  </div>;
}

export function UserDetailPage() {
  const { userId = '' } = useParams<{ userId: string }>();
  const { view } = useAdminSession();
  const [page, setPage] = usePage();
  const businessId = view.status === 'authenticated' && view.admin.role === 'superadmin' ? undefined : view.status === 'authenticated' ? view.admin.business?.id : undefined;
  const query = useUser(userId, businessId, page);
  if (query.isPending) return <LoadingPage label="Загружаем клиента…" />;
  if (query.isError || !query.data) return <div className="page-stack"><ErrorNotice error={query.error} retry={() => { void query.refetch(); }} /></div>;
  const user = query.data;
  return <div className="page-stack"><PageHeading eyebrow="КЛИЕНТЫ / ПРОФИЛЬ" title={user.phone ?? 'Клиент'} subtitle="Отображаются только карты, входящие в разрешённую область данных." actions={<Link className="button button-secondary" to="/operations">К поиску</Link>} />
    <section className="surface-card"><dl className="detail-list"><Detail label="Телефон">{user.phone ?? 'Не указан'}</Detail><Detail label="Язык">{user.language}</Detail><Detail label="Создан"><time dateTime={user.created_at}>{formatDate(user.created_at)}</time></Detail></dl></section>
    <section className="surface-card"><div className="section-heading"><h2>Карты в области доступа</h2></div>
      {user.cards.items.length === 0 ? <p className="table-empty">Карт не найдено.</p> : <div className="table-wrap"><table><thead><tr><th>КАРТА</th><th>БИЗНЕС</th><th>БАЛАНС</th><th>ПРИВЯЗКА</th><th>СТАТУС</th></tr></thead>
        <tbody>{user.cards.items.map(card => <tr key={card.id}><td><Link className="text-link mono-value" to={`/cards/${encodeURIComponent(card.id)}`}>{card.barcode}</Link></td><td>{card.business_name}</td><td>{formatBalance(card.balance)}</td><td>{card.bind_method ?? '—'}</td><td>{card.is_blocked ? 'Заблокирована' : 'Не заблокирована'}</td></tr>)}</tbody></table></div>}
      {user.cards.items.length > 0 && <div className="pagination"><span>Карты постранично</span><div className="pagination-actions"><button className="button button-secondary" disabled={page.offset === 0} onClick={() => setPage(Math.max(0, page.offset - page.limit))}>Назад</button><button className="button button-secondary" disabled={!user.cards.has_more} onClick={() => setPage(page.offset + page.limit)}>Дальше</button></div></div>}
    </section>
  </div>;
}

function Detail({ label, children }: { label: string; children: ReactNode }) { return <div className="detail-line"><dt>{label}</dt><dd>{children}</dd></div>; }
