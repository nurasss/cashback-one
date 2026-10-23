import { useAdminSession } from '../auth/provider';
import { useAudit } from '../api/queries';
import type { AuditItem } from '../api/types';
import { DataTable } from '../components/DataTable';
import { useTableExpansion } from '../components/CompactTable';
import { EmptyState, ErrorNotice, LoadingPage, PageHeading, StatusPill } from '../components/Feedback';
import { formatDate } from '../utils/format';
import { usePage } from '../utils/usePage';
import { useLocale } from '../i18n/LocaleContext';
import { useAdminTranslation } from '../i18n/admin';

function StateView({ label, value }: { label: string; value: Record<string, unknown> | null }) {
  if (!value) return <span className="muted-copy">—</span>;
  return (
    <details className="audit-state">
      <summary>{label}</summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}

export function AuditPage() {
  const { view } = useAdminSession();
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const [page, setPage] = usePage();
  const expansion = useTableExpansion();
  const query = useAudit(page);
  const isManager = view.status === 'authenticated' && view.admin.role === 'business_manager';

  return (
    <div className="page-stack">
      <PageHeading
        title={t.audit.title}
        subtitle={
          isManager
            ? t.audit.subtitleScope(view.admin.business?.name ?? '')
            : t.audit.subtitleAll
        }
      />
      <p className="data-note">
        <StatusPill tone="warning">{t.audit.readOnlyBadge}</StatusPill> {t.audit.note}
      </p>
      {query.isPending ? (
        <LoadingPage label={t.audit.loading} />
      ) : query.isError ? (
        <ErrorNotice error={query.error} retry={() => { void query.refetch(); }} />
      ) : query.data?.items.length === 0 && page.offset === 0 ? (
        <EmptyState title={t.audit.emptyTitle} detail={t.audit.emptyDetail} />
      ) : query.data ? (
        <DataTable<AuditItem>
          expansion={expansion}
          page={{ ...page, has_more: query.data.has_more }}
          onPage={setPage}
          rows={query.data.items}
          rowKey={row => row.id}
          columns={[
            {
              key: 'created',
              title: t.audit.colDateTime,
              render: row => <time dateTime={row.created_at}>{formatDate(row.created_at, locale)}</time>,
            },
            { key: 'actor', title: t.audit.colActor, render: row => <span className="cell-primary">{row.actor}</span> },
            { key: 'action', title: t.audit.colAction, render: row => <StatusPill>{row.action}</StatusPill> },
            { key: 'entity', title: t.audit.colEntity, render: row => <span>{row.entity}</span> },
            { key: 'before', title: t.audit.colBefore, render: row => <StateView label={t.audit.stateShow} value={row.before_state} /> },
            { key: 'after', title: t.audit.colAfter, render: row => <StateView label={t.audit.stateShow} value={row.after_state} /> },
          ]}
        />
      ) : null}
    </div>
  );
}
