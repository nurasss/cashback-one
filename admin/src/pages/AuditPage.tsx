import { useAudit } from '../api/queries';
import type { AuditItem } from '../api/types';
import { DataTable } from '../components/DataTable';
import { EmptyState, ErrorNotice, LoadingPage, PageHeading, StatusPill } from '../components/Feedback';
import { formatDate } from '../utils/format';
import { usePage } from '../utils/usePage';

export function AuditPage() {
  const [page, setPage] = usePage();
  const query = useAudit(page);
  return <div className="page-stack"><PageHeading eyebrow="БЕЗОПАСНОСТЬ" title="Журнал событий" subtitle="Общий AuditLog доступен только суперадминистратору: в текущей записи нет business_id." />
    <p className="data-note"><StatusPill tone="warning">Только чтение</StatusPill> Поля до/после не показываются: текущая JSON-схема не размечает секреты и область бизнеса.</p>
    {query.isPending ? <LoadingPage label="Загружаем журнал…" /> : query.isError ? <ErrorNotice error={query.error} retry={() => { void query.refetch(); }} /> : query.data?.items.length === 0 && page.offset === 0 ?
      <EmptyState title="Событий пока нет" detail="События появятся после использования существующих audit-писателей." /> : query.data ?
      <DataTable<AuditItem> page={{ ...page, has_more: query.data.has_more }} onPage={setPage} rows={query.data.items} rowKey={row => row.id} columns={[
        { key: 'created', title: 'ДАТА И ВРЕМЯ (UTC)', render: row => <time dateTime={row.created_at}>{formatDate(row.created_at)}</time> },
        { key: 'actor', title: 'АКТОР', render: row => <span className="cell-primary">{row.actor}</span> },
        { key: 'action', title: 'ДЕЙСТВИЕ', render: row => <StatusPill>{row.action}</StatusPill> },
        { key: 'entity', title: 'ТИП ДАННЫХ', render: row => <span>{row.entity}</span> },
      ]} /> : null}
  </div>;
}
