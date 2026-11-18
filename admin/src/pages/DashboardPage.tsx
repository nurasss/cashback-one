import { useState, useEffect, useRef, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useAdminSession } from '../auth/provider';
import { useActiveBusiness } from '../context/ActiveBusinessContext';
import { useAllBusinesses, useDashboard } from '../api/queries';
import { BusinessSelect } from '../components/BusinessSelect';
import { EmptyState, ErrorNotice, LoadingPage, PageHeading, StatusPill } from '../components/Feedback';
import { IconCards, IconCheckShield, IconTrendUp, IconUsers } from '../components/Icons';
import { ApiError, messageForError } from '../api/errors';
import type { AgentHealth } from '../api/types';
import { calendarDaysInclusive, clampDefaultPeriodDays, dayBoundary, formatDate, formatNumber, isoToAstanaDay, isValidDateOnly, localDate, shiftAstanaDay } from '../utils/format';
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

function defaultPeriodRange(regDay: string | null, todayDay: string) {
  return clampDefaultPeriodDays(shiftAstanaDay(todayDay, -29), todayDay, regDay, todayDay);
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
  const { setActiveBusiness } = useActiveBusiness();
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const initialRegDay =
    view.status === 'authenticated' && view.admin.role === 'business_manager'
      ? isoToAstanaDay(view.admin.business?.created_at)
      : null;
  const [defaultPeriod] = useState(() => {
    const todayDay = localDate(new Date());
    const clamped = defaultPeriodRange(initialRegDay, todayDay);
    return { from: clamped.from, to: clamped.to, today: todayDay };
  });
  const [currentDay, setCurrentDay] = useState(defaultPeriod.today);
  const [businessId, setBusinessId] = useState('');
  const [from, setFrom] = useState(defaultPeriod.from);
  const [to, setTo] = useState(defaultPeriod.to);
  const [filters, setFilters] = useState({
    from: periodBoundary(defaultPeriod.from, false),
    to: periodBoundary(defaultPeriod.to, true),
    business_id: undefined as string | undefined,
  });
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [dismissedServerPeriodError, setDismissedServerPeriodError] = useState(false);
  const hasCustomRangeRef = useRef(false);

  const isAuthenticated = view.status === 'authenticated';
  const adminRole = isAuthenticated ? view.admin.role : null;
  const isClient = adminRole === 'business_manager';
  const isUnlimited = isAuthenticated ? view.adminStatsUnlimitedPeriod === true : false;
  const maxPeriodDays = isAuthenticated ? view.adminMaxStatsPeriodDays : 90;

  const businesses = useAllBusinesses(isAuthenticated && adminRole === 'superadmin');
  const selectedBusiness =
    !isClient && businessId
      ? businesses.items.find(b => b.id === businessId) ?? null
      : null;
  const awaitingRegDate =
    isAuthenticated &&
    !isClient &&
    Boolean(businessId) &&
    !selectedBusiness &&
    (businesses.isPending || businesses.isLoadingMore);
  const effectiveRegDay = isAuthenticated
    ? isClient
      ? isoToAstanaDay(view.admin.business?.created_at)
      : selectedBusiness
        ? isoToAstanaDay(selectedBusiness.created_at)
        : null
    : null;

  useEffect(() => {
    const syncToday = () => {
      const next = localDate(new Date());
      setCurrentDay(prev => (prev === next ? prev : next));
    };
    const onVisibility = () => {
      if (document.visibilityState === 'visible') syncToday();
    };
    window.addEventListener('focus', syncToday);
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      window.removeEventListener('focus', syncToday);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, []);

  useEffect(() => {
    if (!isAuthenticated || !isClient || hasCustomRangeRef.current) return;
    const nowDay = localDate(new Date());
    const clamped = defaultPeriodRange(effectiveRegDay, nowDay);
    if (
      (effectiveRegDay !== null && (from < effectiveRegDay || to < effectiveRegDay)) ||
      from > nowDay ||
      to > nowDay
    ) {
      setFrom(clamped.from);
      setTo(clamped.to);
      setFilters({
        from: periodBoundary(clamped.from, false),
        to: periodBoundary(clamped.to, true),
        business_id: undefined,
      });
    }
  }, [isAuthenticated, isClient, effectiveRegDay, from, to]);

  useEffect(() => {
    if (!isAuthenticated || adminRole !== 'superadmin') return;
    setActiveBusiness(selectedBusiness ? {
      id: selectedBusiness.id,
      name: selectedBusiness.name,
      logo_url: selectedBusiness.logo_url,
      android_app_id: selectedBusiness.android_app_id,
    } : null);
  }, [selectedBusiness, isAuthenticated, adminRole, setActiveBusiness]);

  useEffect(() => {
    return () => {
      setActiveBusiness(null);
    };
  }, [setActiveBusiness]);

  const liveNowDay = localDate(new Date());
  const needsInitialClientClamp =
    isAuthenticated &&
    isClient &&
    !hasCustomRangeRef.current &&
    ((effectiveRegDay !== null && (from < effectiveRegDay || to < effectiveRegDay)) ||
      from > liveNowDay ||
      to > liveNowDay);

  const dashboard = useDashboard(
    filters,
    isAuthenticated && !awaitingRegDate && !needsInitialClientClamp,
    refreshVersion,
  );
  const title = isAuthenticated ? view.admin.business?.name ?? t.dashboard.allBusinesses : t.layout.nav.overview;

  useEffect(() => {
    const resetToDefault = () => {
      const nowDay = localDate(new Date());
      setCurrentDay(nowDay);
      setDismissedServerPeriodError(true);
      hasCustomRangeRef.current = false;
      const target = defaultPeriodRange(effectiveRegDay, nowDay);
      setFrom(target.from);
      setTo(target.to);
      setFilters({
        from: periodBoundary(target.from, false),
        to: periodBoundary(target.to, true),
        business_id: businessId || undefined,
      });
      setRefreshVersion(version => version + 1);
    };
    window.addEventListener('admin-dashboard-reset', resetToDefault);
    return () => window.removeEventListener('admin-dashboard-reset', resetToDefault);
  }, [effectiveRegDay, businessId]);

  if (view.status !== 'authenticated') return null;

  const liveToday = localDate(new Date());
  const effectiveToday = liveToday !== currentDay ? liveToday : currentDay;
  const data = dashboard.data;

  const validateRange = (checkFrom: string, checkTo: string, todayDay: string) => {
    const fromValid = isValidDateOnly(checkFrom);
    const toValid = isValidDateOnly(checkTo);
    if (!fromValid || !toValid) {
      return {
        valid: false,
        fromInvalid: !fromValid,
        toInvalid: !toValid,
        message: t.dashboard.periodDateInvalid,
      };
    }
    const fromOutOfBounds = checkFrom > todayDay;
    const toOutOfBounds = checkTo > todayDay;
    if (fromOutOfBounds || toOutOfBounds) {
      return {
        valid: false,
        fromInvalid: fromOutOfBounds,
        toInvalid: toOutOfBounds,
        message: t.dashboard.periodOutOfBounds,
      };
    }
    if (checkFrom > checkTo) {
      return {
        valid: false,
        fromInvalid: true,
        toInvalid: true,
        message: t.dashboard.periodInvalid,
      };
    }
    const requestedDays = calendarDaysInclusive(checkFrom, checkTo);
    if (!isUnlimited && requestedDays > maxPeriodDays) {
      return {
        valid: false,
        fromInvalid: true,
        toInvalid: true,
        message: t.dashboard.periodTooLarge(maxPeriodDays),
      };
    }
    return {
      valid: true,
      fromInvalid: false,
      toInvalid: false,
      message: '',
    };
  };

  const validation = validateRange(from, to, effectiveToday);
  const isServerPeriodError =
    !dismissedServerPeriodError &&
    dashboard.isError &&
    dashboard.error instanceof ApiError &&
    (dashboard.error.code === 'ADMIN_INVALID_PERIOD' || dashboard.error.code === 'ADMIN_PERIOD_TOO_LARGE');
  const serverPeriodMessage = isServerPeriodError ? messageForError(dashboard.error, locale) : '';
  const periodHint = validation.message || serverPeriodMessage;
  const fromInvalid = validation.fromInvalid || isServerPeriodError;
  const toInvalid = validation.toInvalid || isServerPeriodError;

  const syncDayNow = () => {
    const nowDay = localDate(new Date());
    setCurrentDay(prev => (prev === nowDay ? prev : nowDay));
    return nowDay;
  };

  const handleFromChange = (nextValue: string) => {
    hasCustomRangeRef.current = true;
    setDismissedServerPeriodError(true);
    syncDayNow();
    setFrom(nextValue);
  };

  const handleToChange = (nextValue: string) => {
    hasCustomRangeRef.current = true;
    setDismissedServerPeriodError(true);
    syncDayNow();
    setTo(nextValue);
  };

  const handleBusinessChange = (nextBusinessId: string) => {
    const nowDay = syncDayNow();
    setDismissedServerPeriodError(true);
    setBusinessId(nextBusinessId);
    if (!hasCustomRangeRef.current) {
      const nextBiz = nextBusinessId
        ? businesses.items.find(b => b.id === nextBusinessId) ?? null
        : null;
      const nextRegDay = nextBusinessId ? isoToAstanaDay(nextBiz?.created_at) : null;
      const clamped = defaultPeriodRange(nextRegDay, nowDay);
      setFrom(clamped.from);
      setTo(clamped.to);
    }
  };

  const apply = () => {
    const nowDay = syncDayNow();
    if (awaitingRegDate) return;
    const latestCheck = validateRange(from, to, nowDay);
    if (!latestCheck.valid) return;
    setDismissedServerPeriodError(false);
    setFilters({ from: periodBoundary(from, false), to: periodBoundary(to, true), business_id: businessId || undefined });
    setRefreshVersion(version => version + 1);
  };

  const fromPickerMin = '1000-01-01';
  const fromPickerMax = isValidDateOnly(to) && to <= effectiveToday ? to : effectiveToday;
  const toPickerMin = isValidDateOnly(from) && from <= effectiveToday ? from : fromPickerMin;

  const totalAgents = data?.agents ? Object.values(data.agents).reduce((sum, item) => sum + item, 0) : 0;

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
      <section className="filter-panel" aria-label={t.dashboard.filterAria}>
        <div className="filter-heading">
          <span className="panel-kicker">{t.dashboard.filterKicker}</span>
          <span className="panel-caption">{t.dashboard.tzCaption}</span>
        </div>
        <div className="filter-controls">
          <label className="form-control">
            <span>{t.dashboard.fromLabel}</span>
            <input
              type="date"
              min={fromPickerMin}
              max={fromPickerMax}
              value={from}
              aria-invalid={fromInvalid}
              aria-describedby={periodHint ? 'dashboard-period-error' : undefined}
              onFocus={syncDayNow}
              onChange={event => handleFromChange(event.target.value)}
            />
          </label>
          <label className="form-control">
            <span>{t.dashboard.toLabel}</span>
            <input
              type="date"
              min={toPickerMin}
              max={effectiveToday}
              value={to}
              aria-invalid={toInvalid}
              aria-describedby={periodHint ? 'dashboard-period-error' : undefined}
              onFocus={syncDayNow}
              onChange={event => handleToChange(event.target.value)}
            />
          </label>
          {!isClient && (
            <div className="form-control business-select">
              <label htmlFor="dashboard-business">{t.dashboard.businessLabel}</label>
              <BusinessSelect
                id="dashboard-business"
                ariaLabel={t.dashboard.businessLabel}
                value={businessId}
                onChange={handleBusinessChange}
                allowAllLabel={t.dashboard.allBusinesses}
                businesses={businesses}
              />
            </div>
          )}
          <button className="button button-primary" type="button" disabled={dashboard.isLoading} onClick={apply}>
            {t.dashboard.refreshBtn}
          </button>
        </div>
        {periodHint && (
          <div className="dashboard-period-hint-row">
            <p id="dashboard-period-error" className="form-error" role="alert">{periodHint}</p>
          </div>
        )}
      </section>

      {dashboard.isError && !isServerPeriodError && (
        <div className="dashboard-period-error">
          <ErrorNotice error={dashboard.error} retry={() => { void dashboard.refetch(); }} />
        </div>
      )}

      {dashboard.isPending && !data && <LoadingPage label={t.dashboard.loadingMetrics} />}
      {!dashboard.isPending && !dashboard.isError && !data && (
        <EmptyState title={t.feedback.noDataTitle} detail={t.dashboard.emptyDetail} />
      )}

      {data && <>
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
      </>}
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
