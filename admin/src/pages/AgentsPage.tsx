import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { messageForError } from '../api/errors';
import { privateKey, useAgent, useAgents } from '../api/queries';
import type { Agent, AgentCommand, AgentHealth, AgentKeyDisclosure } from '../api/types';
import { useAdminSession } from '../auth/provider';
import { DataTable } from '../components/DataTable';
import { EmptyState, ErrorNotice, LoadingPage, PageHeading, StatusPill } from '../components/Feedback';
import { AgentCreateDialog, AgentKeyDialog } from '../features/AdminMutations';
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
  const [createOpen, setCreateOpen] = useState(false);
  const [disclosure, setDisclosure] = useState<AgentKeyDisclosure | null>(null);
  const query = useAgents(undefined, page);
  const scopeDescription = view.status === 'authenticated' && view.admin.business ? `Агенты бизнеса «${view.admin.business.name}».` : 'Состояние синхронизации по бизнесам.';
  return <div className="page-stack"><PageHeading eyebrow="СИНХРОНИЗАЦИЯ" title="Агенты" subtitle={scopeDescription} actions={view.status === 'authenticated' && view.admin.role === 'superadmin' ?
    <button className="button button-primary" type="button" onClick={() => setCreateOpen(true)}>Создать агента</button> : undefined} />
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
    {createOpen && <AgentCreateDialog onClose={() => setCreateOpen(false)} onCreated={value => { setCreateOpen(false); setDisclosure(value); }} />}
    {disclosure && <AgentKeyDialog disclosure={disclosure} onClose={() => setDisclosure(null)} />}
  </div>;
}

export function AgentDetailPage() {
  const { view, session } = useAdminSession();
  const queryClient = useQueryClient();
  const { agentId = '' } = useParams<{ agentId: string }>();
  const query = useAgent(agentId);
  const [disclosure, setDisclosure] = useState<AgentKeyDisclosure | null>(null);
  const [command, setCommand] = useState<AgentCommand | null>(null);
  const [actionError, setActionError] = useState('');
  const [busy, setBusy] = useState(false);
  if (query.isPending) return <LoadingPage label="Загружаем сведения об агенте…" />;
  if (query.isError || !query.data) return <div className="page-stack"><ErrorNotice error={query.error} retry={() => { void query.refetch(); }} /></div>;
  const item = query.data;
  const canManage = view.status === 'authenticated' && view.admin.role === 'superadmin';
  const refreshAgent = async () => {
    await queryClient.invalidateQueries({ queryKey: [...privateKey, 'agent', item.id] });
    await queryClient.invalidateQueries({ queryKey: [...privateKey, 'agents'] });
  };
  const rotate = async () => {
    if (!window.confirm(`Заменить ключ агента «${item.business_name}»? Старый ключ сразу перестанет работать. Новый ключ будет показан один раз.`)) return;
    setBusy(true); setActionError('');
    try {
      const response = await session.api.request<AgentKeyDisclosure>(`/admin/agents/${encodeURIComponent(item.id)}/rotate-key`, { method: 'POST' });
      setDisclosure({ agent: response.agent, api_key: response.api_key });
      await refreshAgent();
    } catch (error) { setActionError(messageForError(error)); }
    finally { setBusy(false); }
  };
  const revoke = async () => {
    if (!window.confirm(`Отозвать доступ агента «${item.business_name}»? Его текущий API key перестанет работать.`)) return;
    setBusy(true); setActionError('');
    try {
      await session.api.request(`/admin/agents/${encodeURIComponent(item.id)}/revoke`, { method: 'POST' });
      await refreshAgent();
    } catch (error) { setActionError(messageForError(error)); }
    finally { setBusy(false); }
  };
  const requestResync = async () => {
    if (!window.confirm(`Запросить полную синхронизацию для «${item.business_name}»? Запрос останется pending до поддержки выполнения со стороны Agent.`)) return;
    setBusy(true); setActionError('');
    try {
      const result = await session.api.request<AgentCommand>(`/admin/agents/${encodeURIComponent(item.id)}/full-resync`, { method: 'POST' });
      setCommand(result);
    } catch (error) { setActionError(messageForError(error)); }
    finally { setBusy(false); }
  };
  return <div className="page-stack"><PageHeading eyebrow="АГЕНТЫ / СОСТОЯНИЕ" title={item.business_name} subtitle="Сведения из состояния облачной синхронизации." actions={<>
      {canManage && item.status === 'active' && <button className="button button-secondary" type="button" disabled={busy} onClick={() => { void rotate(); }}>Ротировать ключ</button>}
      {canManage && item.status !== 'revoked' && <button className="button button-secondary" type="button" disabled={busy} onClick={() => { void revoke(); }}>Отозвать</button>}
      {canManage && <button className="button button-primary" type="button" disabled={busy || item.status !== 'active'} onClick={() => { void requestResync(); }}>Запросить полную синхронизацию</button>}
      <Link className="button button-secondary" to="/agents">К списку агентов</Link>
    </>} />
    {actionError && <p className="form-error" role="alert">{actionError}</p>}
    {command && <section className="notice" role="status"><div><strong>Запрос синхронизации создан · {command.status}</strong>
      <p>ID: <code>{command.command_id}</code>. Выполнение отложено до поддержки Agent; данные не объявляются синхронизированными.</p></div></section>}
    <section className="surface-card"><div className="section-heading"><h2>Состояние соединения</h2><AgentHealthBadge health={item.health} /></div>
      <dl className="detail-list"><DetailLine label="Статус">{item.status}</DetailLine><DetailLine label="Версия">{item.version ?? 'Нет данных'}</DetailLine>
        <DetailLine label="Последний сигнал">{item.last_seen_at ? formatDate(item.last_seen_at) : 'Агент ещё не подключался'}</DetailLine>
        <DetailLine label="Последняя синхронизация">{item.last_sync_at ? formatDate(item.last_sync_at) : 'Нет данных'}</DetailLine>
        <DetailLine label="Последняя ошибка">{item.last_error ?? 'Ошибок не сообщалось'}</DetailLine>
      </dl>
    </section>
    {disclosure && <AgentKeyDialog disclosure={disclosure} title="Ключ агента ротирован" onClose={() => setDisclosure(null)} />}
  </div>;
}
function DetailLine({ label, children }: { label: string; children: ReactNode }) {
  return <div className="detail-line"><dt>{label}</dt><dd>{children}</dd></div>;
}
