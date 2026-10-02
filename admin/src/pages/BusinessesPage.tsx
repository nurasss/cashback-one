import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useAdminSession } from '../auth/provider';
import { DataTable } from '../components/DataTable';
import { EmptyState, ErrorNotice, LoadingPage, PageHeading, StatusPill } from '../components/Feedback';
import { useBusiness, useBusinesses } from '../api/queries';
import type { Business } from '../api/types';
import { formatDate } from '../utils/format';
import { usePage } from '../utils/usePage';
import type { ReactNode } from 'react';
import { BusinessEditorDialog } from '../features/AdminMutations';

export function BusinessesPage() {
  const [createOpen, setCreateOpen] = useState(false);
  const [page, setPage] = usePage();
  const query = useBusinesses(page);
  return <div className="page-stack"><PageHeading eyebrow="ОРГАНИЗАЦИИ" title="Бизнесы" subtitle="Настройки бренда и статус каждого бизнеса."
      actions={<button className="button button-primary" type="button" onClick={() => setCreateOpen(true)}>Создать бизнес</button>} />
    {query.isPending ? <LoadingPage label="Загружаем бизнесы…" /> : query.isError ? <ErrorNotice error={query.error} retry={() => { void query.refetch(); }} /> : query.data?.items.length === 0 && page.offset === 0 ?
      <EmptyState title="Бизнесов пока нет" detail="После добавления бизнеса его настройки появятся здесь." /> : query.data ?
      <DataTable<Business> page={{ ...page, has_more: query.data.has_more }} onPage={setPage} rows={query.data.items} rowKey={item => item.id} columns={[
        { key: 'name', title: 'БИЗНЕС', render: item => <Link className="table-name" to={`/businesses/${encodeURIComponent(item.id)}`}>{item.name}<span>{item.id}</span></Link> },
        { key: 'status', title: 'СТАТУС', render: item => <StatusPill tone={item.status === 'active' ? 'positive' : 'neutral'}>{item.status === 'active' ? 'Активен' : item.status}</StatusPill> },
        { key: 'prefixes', title: 'ПРЕФИКСЫ ШТРИХКОДОВ', render: item => <span className="mono-value">{item.barcode_prefixes?.length ? item.barcode_prefixes.join(', ') : '—'}</span> },
        { key: 'updated', title: 'ИЗМЕНЁН', render: item => <time dateTime={item.updated_at}>{formatDate(item.updated_at)}</time> },
      ]} /> : null}
    {createOpen && <BusinessEditorDialog onClose={() => setCreateOpen(false)} onSaved={() => setCreateOpen(false)} />}
  </div>;
}

export function BusinessDetailPage() {
  const { view } = useAdminSession();
  const [editOpen, setEditOpen] = useState(false);
  const { businessId } = useParams<{ businessId: string }>();
  const query = useBusiness(businessId ?? '');
  if (query.isPending) return <LoadingPage label="Загружаем бизнес…" />;
  if (query.isError || !query.data) return <div className="page-stack"><ErrorNotice error={query.error} retry={() => { void query.refetch(); }} /></div>;
  const business = query.data;
  return <div className="page-stack"><PageHeading eyebrow="ОРГАНИЗАЦИИ / КАРТОЧКА" title={business.name} subtitle="Настройки доступны суперадминистратору." actions={<>
      {view.status === 'authenticated' && view.admin.role === 'superadmin' && <button className="button button-primary" type="button" onClick={() => setEditOpen(true)}>Изменить бизнес</button>}
      <Link className="button button-secondary" to="/businesses">К списку бизнесов</Link>
    </>} />
    <section className="metric-grid three-up">
      <DetailMetric title="Карты" value={business.cards_count} detail="Все зеркальные карты" />
      <DetailMetric title="Незаблокированные" value={business.unblocked_cards_count} detail="is_blocked = false" />
      <DetailMetric title="Клиенты с картами" value={business.customers_with_cards_count} detail="Уникальные активные профили" />
    </section>
    <section className="detail-grid">
      <article className="surface-card"><span className="panel-kicker">НАСТРОЙКИ БИЗНЕСА</span><dl className="detail-list">
        <DetailLine label="Статус"><StatusPill tone={business.status === 'active' ? 'positive' : 'neutral'}>{business.status}</StatusPill></DetailLine>
        <DetailLine label="Агенты">{business.agents_count}</DetailLine><DetailLine label="Создан"><time dateTime={business.created_at}>{formatDate(business.created_at)}</time></DetailLine>
        <DetailLine label="Обновлён"><time dateTime={business.updated_at}>{formatDate(business.updated_at)}</time></DetailLine><DetailLine label="Логотип"><BusinessLogo url={business.logo_url} /></DetailLine>
        <DetailLine label="Префиксы"><span className="mono-value">{business.barcode_prefixes?.length ? business.barcode_prefixes.join(', ') : 'Не заданы'}</span></DetailLine>
      </dl></article>
      <article className="surface-card"><span className="panel-kicker">ЦВЕТОВАЯ СХЕМА</span>{business.colors && Object.keys(business.colors).length > 0 ?
        <dl className="detail-list">{Object.entries(business.colors).map(([key, value]) => <DetailLine key={key} label={key}><code className="safe-value">{String(value)}</code></DetailLine>)}</dl> :
        <p className="table-empty">Цвета не настроены.</p>}</article>
    </section>
    {editOpen && <BusinessEditorDialog business={business} onClose={() => setEditOpen(false)} onSaved={() => { setEditOpen(false); void query.refetch(); }} />}
  </div>;
}

function DetailMetric({ title, value, detail }: { title: string; value: number; detail: string }) {
  return <article className="metric-card compact-metric"><span className="metric-title">{title}</span><strong className="metric-value">{value.toLocaleString('ru-RU')}</strong><span className="metric-footnote">{detail}</span></article>;
}
function DetailLine({ label, children }: { label: string; children: ReactNode }) {
  return <div className="detail-line"><dt>{label}</dt><dd>{children}</dd></div>;
}

function BusinessLogo({ url }: { url: string | null }) {
  if (!url) return <span className="muted-copy">Не задан</span>;
  let safeSource: string;
  try {
    const parsed = new URL(url, window.location.origin);
    if (parsed.protocol !== 'https:' && parsed.origin !== window.location.origin) {
      return <span className="muted-copy">Логотип доступен только по HTTPS</span>;
    }
    safeSource = parsed.href;
  } catch {
    return <span className="muted-copy">Некорректный адрес логотипа</span>;
  }
  return <img className="business-logo" src={safeSource} alt="Логотип бизнеса" loading="lazy" referrerPolicy="no-referrer" />;
}
