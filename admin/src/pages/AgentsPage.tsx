import { Link, useParams } from 'react-router-dom';
import type { ReactNode } from 'react';
import { useAdminSession } from '../auth/provider';
import { useAgent, useAgents } from '../api/queries';
import type { Agent, AgentHealth } from '../api/types';
import { DataTable } from '../components/DataTable';
import { EmptyState, ErrorNotice, LoadingPage, PageHeading, StatusPill } from '../components/Feedback';
import { usePage } from '../utils/usePage';
import { formatDate } from '../utils/format';

const healthText: Record<AgentHealth, string> = {
  online: 'Недавно на связи', stale: 'Устаревшее состояние', never_connected: 'Ещё не подключался', error: 'Есть ошибка', disabled: 'Отключён',
};
const healthTone: Record<AgentHealth, 'neutral' | 'positive' | 'warning' | 'negative'> = {
  online: 'positive', stale: 'warning', never_connected: 'neutral', error: 'negative', disabled: 'neutral',
};
function AgentHealthBadge({ health }: { health: AgentHealth }) {
  return <StatusPill tone={healthTone[health]}>{healthText[health]}</StatusPill>;
}

export function AgentsPage() {
  const { view } = useAdminSession();
  const [page, setPage] = usePage();
  const query = useAgents(undefined, page);
  const scopeDescription = view.status === 'authenticated' && view.admin.business ? `Агенты бизнеса «${view.admin.business.name}».` : 'Состояние синхронизации по бизнесам.';
  return <div className="page-stack"><PageHeading eyebrow="СИНХРОНИЗАЦИЯ" title="Агенты" subtitle={`${scopeDescription} Данные доступны только для чтения.`} />
    {query.isPending ? <LoadingPage label="Загружаем агентов…" /> : query.isError ? <ErrorNotice error={query.error} retry={() => { void query.refetch(); }} /> : query.data?.items.length === 0 && page.offset === 0 ?
      <EmptyState title="Агентов пока нет" detail="Статус появится после подключения агента бизнеса." /> : query.data ?
      <DataTable<Agent> page={{ ...page, has_more: query.data.has_more }} onPage={setPage} rows={query.data.items} rowKey={item => item.id} columns={[
        { key: 'agent', title: 'АГЕНТ', render: item => <Link className="table-name" to={`/agents/${encodeURIComponent(item.id)}`}>{item.business_name}<span>{item.id}</span></Link> },
        { key: 'health', title: 'СВЯЗЬ', render: item => <AgentHealthBadge health={item.health} /> },
        { key: 'status', title: 'СТАТУС', render: item => <span>{item.status}</span> },
        { key: 'version', title: 'ВЕРСИЯ', render: item => <span className="mono-value">{item.version ?? '—'}</span> },
        { key: 'lastseen', title: 'ПОСЛЕДНИЙ СИГНАЛ', render: item => item.last_seen_at ? <time dateTime={item.last_seen_at}>{formatDate(item.last_seen_at)}</time> : <span className="muted-copy">Нет данных</span> },
        { key: 'lastsync', title: 'ПОСЛЕДНЯЯ СИНХРОНИЗАЦИЯ', render: item => item.last_sync_at ? <time dateTime={item.last_sync_at}>{formatDate(item.last_sync_at)}</time> : <span className="muted-copy">—</span> },
        { key: 'error', title: 'ПОСЛЕДНЯЯ ОШИБКА', render: item => item.last_error ? <span className="error-preview">{item.last_error}</span> : <span className="muted-copy">—</span> },
      ]} /> : null}
  </div>;
}

export function AgentDetailPage() {
  const { agentId = '' } = useParams<{ agentId: string }>();
  const query = useAgent(agentId);
  if (query.isPending) return <LoadingPage label="Загружаем сведения об агенте…" />;
  if (query.isError || !query.data) return <div className="page-stack"><ErrorNotice error={query.error} retry={() => { void query.refetch(); }} /></div>;
  const item = query.data;
  return <div className="page-stack"><PageHeading eyebrow="АГЕНТЫ / СОСТОЯНИЕ" title={item.business_name} subtitle="Сведения read-only из состояния облачной синхронизации." actions={<Link className="button button-secondary" to="/agents">К списку агентов</Link>} />
    <section className="surface-card"><div className="section-heading"><h2>Состояние соединения</h2><AgentHealthBadge health={item.health} /></div>
      <dl className="detail-list"><DetailLine label="Статус">{item.status}</DetailLine><DetailLine label="Версия">{item.version ?? 'Нет данных'}</DetailLine>
        <DetailLine label="Последний сигнал">{item.last_seen_at ? formatDate(item.last_seen_at) : 'Агент ещё не подключался'}</DetailLine>
        <DetailLine label="Последняя синхронизация">{item.last_sync_at ? formatDate(item.last_sync_at) : 'Нет данных'}</DetailLine>
        <DetailLine label="Последняя ошибка">{item.last_error ?? 'Ошибок не сообщалось'}</DetailLine>
      </dl>
    </section>
  </div>;
}
function DetailLine({ label, children }: { label: string; children: ReactNode }) {
  return <div className="detail-line"><dt>{label}</dt><dd>{children}</dd></div>;
}
