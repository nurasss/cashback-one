import { useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useAdminSession } from '../auth/provider';
import { useBusinesses, useDashboard } from '../api/queries';
import { EmptyState, ErrorNotice, LoadingPage, PageHeading, StatusPill } from '../components/Feedback';
import { IconCards, IconCheckShield, IconTrendUp, IconUsers } from '../components/Icons';
import type { AgentHealth } from '../api/types';
import { formatDate, formatNumber, localDate } from '../utils/format';
import { useLocale } from '../i18n/LocaleContext';
import { useAdminTranslation } from '../i18n/admin';

const healthTone: Record<AgentHealth, 'neutral' | 'positive' | 'warning' | 'negative'> = {
  online: 'positive',
  stale: 'warning',
  never_connected: 'neutral',
  error: 'negative',
  disabled: 'neutral',
};

function periodBoundary(day: string, end: boolean): string {
  const next = new Date(`${day}T00:00:00`);
  if (end) next.setDate(next.getDate() + 1);
  if (end) next.setMilliseconds(next.getMilliseconds() - 1);
  return next.toISOString();
}

export function DashboardPage() {
  const { view } = useAdminSession();
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const [businessId, setBusinessId] = useState('');
  const today = localDate(new Date());
  const defaultFrom = localDate(new Date(Date.now() - 29 * 86400_000));
  const [from, setFrom] = useState(defaultFrom);
  const [to, setTo] = useState(today);
  const [filters, setFilters] = useState({
    from: periodBoundary(defaultFrom, false),
    to: periodBoundary(today, true),
    business_id: undefined as string | undefined,
  });

  const businesses = useBusinesses(
    { limit: 100, offset: 0 },
    view.status === 'authenticated' && view.admin.role === 'superadmin',
  );
  const dashboard = useDashboard(filters, view.status === 'authenticated');
  const title = view.status === 'authenticated' ? view.admin.business?.name ?? t.dashboard.allBusinesses : t.layout.nav.overview;

  if (view.status !== 'authenticated') return null;

  if (dashboard.isPending) return <LoadingPage label={t.dashboard.loadingMetrics} />;
  if (dashboard.isError && !dashboard.data) {
    return (
      <div className="page-stack">
        <ErrorNotice error={dashboard.error} retry={() => { void dashboard.refetch(); }} />
      </div>
    );
  }

  const data = dashboard.data;
  if (!data) return <EmptyState title={t.feedback.noDataTitle} detail={t.dashboard.emptyDetail} />;

  const apply = () => {
    if (from > to) return;
    setFilters({ from: periodBoundary(from, false), to: periodBoundary(to, true), business_id: businessId || undefined });
  };

  const totalAgents = Object.values(data.agents).reduce((sum, item) => sum + item, 0);

  return (
    <div className="page-stack">
      <PageHeading title={title} subtitle={t.dashboard.subtitle} />
      {dashboard.isError && <ErrorNotice error={dashboard.error} retry={() => { void dashboard.refetch(); }} />}

      <section className="filter-panel" aria-label={t.dashboard.filterAria}>
        <div className="filter-heading">
          <span className="panel-kicker">{t.dashboard.filterKicker}</span>
          <span className="panel-caption">{t.dashboard.tzCaption}</span>
        </div>
        <div className="filter-controls">
          <label className="form-control">
            <span>{t.dashboard.fromLabel}</span>
            <input type="date" value={from} max={to} onChange={event => setFrom(event.target.value)} />
          </label>
          <label className="form-control">
            <span>{t.dashboard.toLabel}</span>
            <input type="date" value={to} min={from} max={today} onChange={event => setTo(event.target.value)} />
          </label>
          {view.admin.role === 'superadmin' && (
            <label className="form-control business-select">
              <span>{t.dashboard.businessLabel}</span>
              <select value={businessId} onChange={event => setBusinessId(event.target.value)} aria-label={t.dashboard.businessLabel}>
                <option value="">{t.dashboard.allBusinesses}</option>
                {businesses.data?.items.map(item => (
                  <option key={item.id} value={item.id}>{item.name}</option>
                ))}
              </select>
            </label>
          )}
          <button className="button button-primary" type="button" disabled={from > to} onClick={apply}>
            {t.dashboard.refreshBtn}
          </button>
        </div>
      </section>

      <section className="metric-grid" aria-label={t.dashboard.metricsAria}>
        <Metric
          title={t.dashboard.customersTitle}
          value={data.customers_with_business_cards}
          caption={t.dashboard.customersCaption}
          icon={<IconUsers />}
          locale={locale}
        />
        <Metric
          title={t.dashboard.cardsTitle}
          value={data.cards}
          caption={t.dashboard.cardsCaption}
          icon={<IconCards />}
          locale={locale}
        />
        <Metric
          title={t.dashboard.unblockedTitle}
          value={data.unblocked_cards}
          caption={t.dashboard.unblockedCaption}
          icon={<IconCheckShield />}
          locale={locale}
        />
        <Metric
          title={t.dashboard.transactionsTitle}
          value={data.transactions}
          caption={t.dashboard.transactionsCaption(
            data.period_days,
            formatDate(data.period_from, locale),
            formatDate(data.period_to, locale),
          )}
          icon={<IconTrendUp />}
          locale={locale}
        />
      </section>

      <section className="surface-card">
        <div className="section-heading">
          <div>
            <span className="panel-kicker">{t.dashboard.syncKicker}</span>
            <h2>{t.dashboard.agentsHealthTitle}</h2>
          </div>
          <Link className="text-link" to="/admin/agents">
            {t.dashboard.toAgentsLink} <span aria-hidden="true">→</span>
          </Link>
        </div>
        {totalAgents === 0 ? (
          <div className="compact-empty">{t.dashboard.noAgentsConnected}</div>
        ) : (
          <div className="health-grid">
            {(Object.keys(t.dashboard.healthLabels) as AgentHealth[]).map(key => (
              <div key={key} className="health-row">
                <StatusPill tone={healthTone[key]}>{t.dashboard.healthLabels[key]}</StatusPill>
                <strong>{data.agents[key]}</strong>
              </div>
            ))}
          </div>
        )}
      </section>

      <p className="data-note">
        {t.dashboard.dataNote}
      </p>
    </div>
  );
}

function Metric({
  title,
  value,
  caption,
  icon,
  locale,
}: {
  title: string;
  value: number;
  caption: string;
  icon: ReactNode;
  locale: 'ru' | 'kk';
}) {
  return (
    <article className="metric-card">
      <div className="metric-top">
        <span className="metric-icon" aria-hidden="true">{icon}</span>
      </div>
      <span className="metric-title">{title}</span>
      <strong className="metric-value">{formatNumber(value, locale)}</strong>
      <span className="metric-footnote">{caption}</span>
    </article>
  );
}
