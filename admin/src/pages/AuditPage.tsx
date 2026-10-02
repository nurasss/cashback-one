import { useAdminSession } from '../auth/provider';
import { useAudit } from '../api/queries';
import type { AuditItem } from '../api/types';
import { DataTable } from '../components/DataTable';
import { EmptyState, ErrorNotice, LoadingPage, PageHeading, StatusPill } from '../components/Feedback';
import { formatDate } from '../utils/format';
import { usePage } from '../utils/usePage';

function StateView({ label, value }: { label: string; value: Record<string, unknown> | null }) {
  if (!value) return <span className="muted-copy">—</span>;
  return <details className="audit-state"><summary>{label}</summary><pre>{JSON.stringify(value, null, 2)}</pre></details>;
}

export function AuditPage() {
  const { view } = useAdminSession();
  const [page, setPage] = usePage();
  const query = useAudit(page);
  const isManager = view.status === 'authenticated' && view.admin.role === 'business_manager';
  return <div className="page-stack"><PageHeading eyebrow="БЕЗОПАСНОСТЬ" title="Журнал событий"
    subtitle={isManager ? `События только бизнеса «${view.admin.business?.name ?? ''}».` : 'Административные события всех бизнесов.'} />
    <p className="data-note"><StatusPill tone="warning">Только чтение</StatusPill> Старые события без business_id видны только суперадминистратору.</p>
    {query.isPending ? <LoadingPage label="Загружаем журнал…" /> : query.isError ? <ErrorNotice error={query.error} retry={() => { void query.refetch(); }} /> : query.data?.items.length === 0 && page.offset === 0 ?
      <EmptyState title="Событий пока нет" detail="Новые административные изменения появятся в этом журнале." /> : query.data ?
      <DataTable<AuditItem> page={{ ...page, has_more: query.data.has_more }} onPage={setPage} rows={query.data.items} rowKey={row => row.id} columns={[
        { key: 'created', title: 'ДАТА И ВРЕМЯ (UTC)', render: row => <time dateTime={row.created_at}>{formatDate(row.created_at)}</time> },
        { key: 'actor', title: 'АКТОР', render: row => <span className="cell-primary">{row.actor}</span> },
        { key: 'action', title: 'ДЕЙСТВИЕ', render: row => <StatusPill>{row.action}</StatusPill> },
        { key: 'entity', title: 'СУЩНОСТЬ', render: row => <span>{row.entity}</span> },
        { key: 'before', title: 'ДО', render: row => <StateView label="Показать" value={row.before_state} /> },
        { key: 'after', title: 'ПОСЛЕ', render: row => <StateView label="Показать" value={row.after_state} /> },
      ]} /> : null}
  </div>;
}
