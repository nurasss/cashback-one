import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAdminSession } from '../auth/provider';
import { useBusinesses, useDashboard } from '../api/queries';
import { EmptyState, ErrorNotice, LoadingPage, PageHeading, StatusPill } from '../components/Feedback';
import type { AgentHealth } from '../api/types';
import { formatDate } from '../utils/format';

const healthLabels: Record<AgentHealth, string> = {
  online: 'Недавно на связи', stale: 'Устаревшее состояние', never_connected: 'Ещё не подключался', error: 'Есть ошибка', disabled: 'Отключён',
};
const healthTone: Record<AgentHealth, 'neutral' | 'positive' | 'warning' | 'negative'> = {
  online: 'positive', stale: 'warning', never_connected: 'neutral', error: 'negative', disabled: 'neutral',
};
function localDate(value: Date): string {
  const date = new Date(value.getTime() - value.getTimezoneOffset() * 60_000);
  return date.toISOString().slice(0, 10);
}
function periodBoundary(day: string, end: boolean): string {
  const next = new Date(`${day}T00:00:00`);
  if (end) next.setDate(next.getDate() + 1);
  if (end) next.setMilliseconds(next.getMilliseconds() - 1);
  return next.toISOString();
}

export function DashboardPage() {
  const { view } = useAdminSession();
  const [businessId, setBusinessId] = useState('');
  const today = localDate(new Date());
  const defaultFrom = localDate(new Date(Date.now() - 29 * 86400_000));
  const [from, setFrom] = useState(defaultFrom);
  const [to, setTo] = useState(today);
  const [filters, setFilters] = useState({ from: periodBoundary(defaultFrom, false), to: periodBoundary(today, true), business_id: undefined as string | undefined });
  const businesses = useBusinesses(
    { limit: 100, offset: 0 },
    view.status === 'authenticated' && view.admin.role === 'superadmin',
  );
  const dashboard = useDashboard(filters, view.status === 'authenticated');
  const title = view.status === 'authenticated' ? view.admin.business?.name ?? 'Все бизнесы' : 'Обзор';
  if (view.status !== 'authenticated') return null;

  if (dashboard.isPending) return <LoadingPage label="Загружаем показатели…" />;
  if (dashboard.isError && !dashboard.data) return <div className="page-stack"><ErrorNotice error={dashboard.error} retry={() => { void dashboard.refetch(); }} /></div>;
  const data = dashboard.data;
  if (!data) return <EmptyState title="Нет данных" detail="Для выбранного периода пока нет показателей." />;
  const apply = () => {
    if (from > to) return;
    setFilters({ from: periodBoundary(from, false), to: periodBoundary(to, true), business_id: businessId || undefined });
  };
  const totalAgents = Object.values(data.agents).reduce((sum, item) => sum + item, 0);

  return <div className="page-stack">
    <PageHeading eyebrow="ОПЕРАТИВНЫЙ ОБЗОР" title={title} subtitle="Сводка по картам, клиентам и синхронизации." />
    {dashboard.isError && <ErrorNotice error={dashboard.error} retry={() => { void dashboard.refetch(); }} />}
    <section className="filter-panel" aria-label="Период статистики">
      <div className="filter-heading"><span className="panel-kicker">ПЕРИОД СТАТИСТИКИ</span><span className="panel-caption">Часовой пояс базы: UTC</span></div>
      <div className="filter-controls">
        <label className="form-control"><span>С</span><input type="date" value={from} max={to} onChange={event => setFrom(event.target.value)} /></label>
        <label className="form-control"><span>По</span><input type="date" value={to} min={from} max={today} onChange={event => setTo(event.target.value)} /></label>
        {view.admin.role === 'superadmin' && <label className="form-control business-select"><span>Бизнес</span>
          <select value={businessId} onChange={event => setBusinessId(event.target.value)} aria-label="Фильтр по бизнесу">
            <option value="">Все бизнесы</option>{businesses.data?.items.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </label>}
        <button className="button button-primary" type="button" disabled={from > to} onClick={apply}>Обновить</button>
      </div>
    </section>
    <section className="metric-grid" aria-label="Показатели бизнеса">
      <Metric title="Клиенты с картами бизнеса" value={data.customers_with_business_cards} caption="Уникальные активные профили" icon="◉" />
      <Metric title="Карты" value={data.cards} caption="В выбранном бизнесе" icon="▤" />
      <Metric title="Незаблокированные карты" value={data.unblocked_cards} caption="Карты со статусом is_blocked = false" icon="◈" />
      <Metric title="Операции" value={data.transactions} caption={`За ${data.period_days} дн. · ${formatDate(data.period_from)} — ${formatDate(data.period_to)}`} icon="↗" />
    </section>
    <section className="surface-card">
      <div className="section-heading"><div><span className="panel-kicker">СИНХРОНИЗАЦИЯ</span><h2>Состояние агентов</h2></div>
        <Link className="text-link" to="/agents">К списку агентов <span aria-hidden="true">→</span></Link></div>
      {totalAgents === 0 ? <div className="compact-empty">Агенты для выбранного бизнеса пока не подключены.</div> :
        <div className="health-grid">{(Object.keys(healthLabels) as AgentHealth[]).map(key => <div key={key} className="health-row"><StatusPill tone={healthTone[key]}>{healthLabels[key]}</StatusPill><strong>{data.agents[key]}</strong></div>)}</div>}
    </section>
    <p className="data-note">Баланс и операции — read-only зеркало данных из Cloud Backend. «Незаблокированные» основано только на поле is_blocked; отдельное определение активной карты не выводится.</p>
  </div>;
}

function Metric({ title, value, caption, icon }: { title: string; value: number; caption: string; icon: string }) {
  return <article className="metric-card"><div className="metric-top"><span className="metric-icon" aria-hidden="true">{icon}</span><span className="metric-caption">ЛОЯЛЬНОСТЬ</span></div>
    <span className="metric-title">{title}</span><strong className="metric-value">{new Intl.NumberFormat('ru-RU').format(value)}</strong><span className="metric-footnote">{caption}</span></article>;
}
