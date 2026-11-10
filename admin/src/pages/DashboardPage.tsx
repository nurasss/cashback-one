import { useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useAdminSession } from '../auth/provider';
import { useBusinesses, useDashboard } from '../api/queries';
import { EmptyState, ErrorNotice, LoadingPage, PageHeading, StatusPill } from '../components/Feedback';
import { IconCards, IconCheckShield, IconTrendUp, IconUsers } from '../components/Icons';
import type { AgentHealth } from '../api/types';
import { formatDate, formatNumber, localDate, dayBoundary } from '../utils/format';
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
  return dayBoundary(day, end);
}

function getClientConnectionState(
  agents: {
    online: number;
    stale: number;
    never_connected: number;
    error: number;
    disabled: number;
  },
  t: ReturnType<typeof useAdminTranslation>,
) {
  const total =
    agents.online +
    agents.stale +
    agents.never_connected +
    agents.error +
    agents.disabled;

  if (total === 0) {
    return {
      statusText: t.dashboard.clientConnOffline,
      desc: t.dashboard.clientConnOfflineDesc,
      tone: 'neutral' as const,
      isWarning: false,
    };
  }
  if (agents.error > 0) {
    return {
      statusText: t.dashboard.clientConnError,
      desc: t.dashboard.clientConnErrorDesc,
      tone: 'negative' as const,
      isWarning: true,
    };
  }
  if (agents.stale > 0) {
    return {
      statusText: t.dashboard.clientConnStale,
      desc: t.dashboard.clientConnStaleDesc,
      tone: 'warning' as const,
      isWarning: true,
    };
  }
  if (agents.online > 0) {
    return {
      statusText: t.dashboard.clientConnActive,
      desc: t.dashboard.clientConnActiveDesc,
      tone: 'positive' as const,
      isWarning: false,
    };
  }
  if (agents.never_connected > 0) {
    return {
      statusText: t.dashboard.clientConnWaiting,
      desc: t.dashboard.clientConnWaitingDesc,
      tone: 'warning' as const,
      isWarning: true,
    };
  }
  return {
    statusText: t.dashboard.clientConnOffline,
    desc: t.dashboard.clientConnOfflineDesc,
    tone: 'neutral' as const,
    isWarning: false,
  };
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

  const isClient = view.admin.role === 'business_manager';

  return (
    <div className="page-stack">
      <PageHeading
        title={title}
        subtitle={t.dashboard.subtitle}
        actions={
          isClient ? (
            <div className="heading-actions">
              <Link to="/admin/operations" className="button button-secondary">
                {t.dashboard.findClientBtn}
              </Link>
              <Link to="/admin/notifications?create=1" className="button button-primary">
                {t.dashboard.createNoticeBtn}
              </Link>
            </div>
          ) : undefined
        }
      />
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
          {!isClient && (
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

      {isClient ? (
        <section className="metric-grid" aria-label={t.dashboard.metricsAria}>
          <Metric
            title={t.dashboard.cardsTitle}
            value={data.cards}
            caption={t.dashboard.cardsCaption}
            icon={<IconCards />}
            locale={locale}
          />
          <Metric
            title={t.dashboard.clientCustomersTitle}
            value={data.customers_with_business_cards}
            caption={t.dashboard.clientCustomersCaption}
            icon={<IconUsers />}
            locale={locale}
          />
          <Metric
            title={t.dashboard.clientTransactionsTitle}
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
      ) : (
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
      )}

      {isClient ? (
        <section className="surface-card client-connection-card">
          <div className="section-heading" style={{ marginBottom: '1rem' }}>
            <div>
              <h2>{t.dashboard.clientSyncTitle}</h2>
            </div>
            <Link className="text-link" to="/admin/agents">
              {t.dashboard.clientDetailsLink} <span aria-hidden="true">→</span>
            </Link>
          </div>
          {(() => {
            const state = getClientConnectionState(data.agents, t);
            return (
              <div
                className={`client-conn-content ${state.isWarning ? 'has-warning' : ''}`}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '1rem',
                  padding: '1rem',
                  borderRadius: '8px',
                  background: state.isWarning ? 'rgba(239, 68, 68, 0.06)' : 'var(--bg-secondary, #f8fafc)',
                  border: `1px solid ${state.isWarning ? 'rgba(239, 68, 68, 0.25)' : 'var(--border-color, #e2e8f0)'}`,
                }}
              >
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem', flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <StatusPill tone={state.tone}>{state.statusText}</StatusPill>
                  </div>
                  <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-muted, #64748b)' }}>
                    {state.desc}
                  </p>
                </div>
              </div>
            );
          })()}
        </section>
      ) : (
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
              {(Object.keys(t.dashboard.healthLabels) as AgentHealth[]).map(key => {
                const label = t.dashboard.healthLabels[key];
                return (
                  <div key={key} className="health-row">
                    <StatusPill tone={healthTone[key]}>{label}</StatusPill>
                    <strong>{data.agents[key]}</strong>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      )}

      <p className="data-note">
        {isClient ? t.dashboard.clientDataNote : t.dashboard.dataNote}
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
