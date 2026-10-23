import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useAdminSession } from '../auth/provider';
import { DataTable } from '../components/DataTable';
import { useTableExpansion } from '../components/CompactTable';
import { EmptyState, ErrorNotice, LoadingPage, PageHeading, StatusPill } from '../components/Feedback';
import { messageForError } from '../api/errors';
import { useBusiness, useBusinesses } from '../api/queries';
import type { Business, ManagerAccessDisclosure } from '../api/types';
import { formatDate, formatNumber } from '../utils/format';
import { usePage } from '../utils/usePage';
import type { ReactNode } from 'react';
import { BusinessEditorDialog, ManagerAccessDialog } from '../features/AdminMutations';
import { useLocale } from '../i18n/LocaleContext';
import { useAdminTranslation } from '../i18n/admin';

export function BusinessesPage() {
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const [createOpen, setCreateOpen] = useState(false);
  const [managerAccess, setManagerAccess] = useState<ManagerAccessDisclosure | null>(null);
  const [page, setPage] = usePage();
  const expansion = useTableExpansion();
  const query = useBusinesses(page);

  return (
    <div className="page-stack">
      <PageHeading
        title={t.businesses.title}
        subtitle={t.businesses.subtitle}
        actions={
          <button className="button button-primary" type="button" onClick={() => setCreateOpen(true)}>
            {t.businesses.createBtn}
          </button>
        }
      />
      {query.isPending ? (
        <LoadingPage label={t.businesses.loading} />
      ) : query.isError ? (
        <ErrorNotice error={query.error} retry={() => { void query.refetch(); }} />
      ) : query.data?.items.length === 0 && page.offset === 0 ? (
        <EmptyState title={t.businesses.emptyTitle} detail={t.businesses.emptyDetail} />
      ) : query.data ? (
        <DataTable<Business>
          expansion={expansion}
          page={{ ...page, has_more: query.data.has_more }}
          onPage={setPage}
          rows={query.data.items}
          rowKey={item => item.id}
          columns={[
            {
              key: 'name',
              title: t.businesses.colName,
              render: item => (
                <Link className="table-name" to={`/admin/businesses/${encodeURIComponent(item.id)}`}>
                  {item.name}
                  <span>{item.id}</span>
                </Link>
              ),
            },
            {
              key: 'status',
              title: t.businesses.colStatus,
              render: item => (
                <StatusPill tone={item.status === 'active' ? 'positive' : 'neutral'}>
                  {item.status === 'active'
                    ? t.businesses.statusActive
                    : item.status === 'inactive'
                    ? t.businesses.statusInactive
                    : item.status}
                </StatusPill>
              ),
            },
            {
              key: 'prefixes',
              title: t.businesses.colPrefixes,
              render: item => (
                <span className="mono-value">
                  {item.barcode_prefixes?.length ? item.barcode_prefixes.join(', ') : '—'}
                </span>
              ),
            },
            {
              key: 'updated',
              title: t.businesses.colUpdated,
              render: item => <time dateTime={item.updated_at}>{formatDate(item.updated_at, locale)}</time>,
            },
          ]}
        />
      ) : null}
      {createOpen && (
        <BusinessEditorDialog
          onClose={() => setCreateOpen(false)}
          onSaved={access => {
            setCreateOpen(false);
            if (access) setManagerAccess(access);
          }}
        />
      )}
      {managerAccess && <ManagerAccessDialog disclosure={managerAccess} onClose={() => setManagerAccess(null)} />}
    </div>
  );
}

export function BusinessDetailPage() {
  const { session, view } = useAdminSession();
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const [editOpen, setEditOpen] = useState(false);
  const [managerAccess, setManagerAccess] = useState<ManagerAccessDisclosure | null>(null);
  const [actionError, setActionError] = useState('');
  const [resetting, setResetting] = useState(false);
  const { businessId } = useParams<{ businessId: string }>();
  const query = useBusiness(businessId ?? '');

  const handleManagerAccess = async (bId: string) => {
    if (!window.confirm(t.businesses.confirmResetManager)) {
      return;
    }
    setActionError('');
    setResetting(true);
    try {
      const disclosure = await session.api.request<ManagerAccessDisclosure>(
        `/admin/businesses/${encodeURIComponent(bId)}/manager-access`,
        { method: 'POST' }
      );
      setManagerAccess(disclosure);
    } catch (err) {
      setActionError(messageForError(err, locale));
    } finally {
      setResetting(false);
    }
  };

  if (query.isPending) return <LoadingPage label={t.businesses.loading} />;
  if (query.isError || !query.data) {
    return (
      <div className="page-stack">
        <ErrorNotice error={query.error} retry={() => { void query.refetch(); }} />
      </div>
    );
  }
  const business = query.data;

  return (
    <div className="page-stack">
      <PageHeading
        title={business.name}
        subtitle={t.businesses.detailSubtitle}
        actions={
          <>
            {view.status === 'authenticated' && view.admin.role === 'superadmin' && (
              <>
                <button
                  className="button button-secondary"
                  type="button"
                  disabled={resetting}
                  onClick={() => { void handleManagerAccess(business.id); }}
                >
                  {resetting ? t.businesses.resettingBtn : t.businesses.grantAccessBtn}
                </button>
                <button className="button button-primary" type="button" onClick={() => setEditOpen(true)}>
                  {t.businesses.editBtn}
                </button>
              </>
            )}
            <Link className="button button-secondary" to="/admin/businesses">
              {t.businesses.backToList}
            </Link>
          </>
        }
      />
      {actionError && <p className="form-error" role="alert">{actionError}</p>}
      <section className="metric-grid three-up">
        <DetailMetric
          title={t.businesses.metricCards}
          value={business.cards_count}
          detail={t.businesses.metricCardsDetail}
          locale={locale}
        />
        <DetailMetric
          title={t.businesses.metricUnblocked}
          value={business.unblocked_cards_count}
          detail="is_blocked = false"
          locale={locale}
        />
        <DetailMetric
          title={t.businesses.metricCustomers}
          value={business.customers_with_cards_count}
          detail={t.businesses.metricCustomersDetail}
          locale={locale}
        />
      </section>
      <section className="detail-grid">
        <article className="surface-card">
          <span className="panel-kicker">{t.businesses.panelSettings}</span>
          <dl className="detail-list">
            <DetailLine label={t.businesses.lineStatus}>
              <StatusPill tone={business.status === 'active' ? 'positive' : 'neutral'}>
                {business.status === 'active'
                  ? t.businesses.statusActive
                  : business.status === 'inactive'
                  ? t.businesses.statusInactive
                  : business.status}
              </StatusPill>
            </DetailLine>
            <DetailLine label={t.businesses.lineAgents}>{business.agents_count}</DetailLine>
            <DetailLine label={t.businesses.lineCreated}>
              <time dateTime={business.created_at}>{formatDate(business.created_at, locale)}</time>
            </DetailLine>
            <DetailLine label={t.businesses.lineUpdated}>
              <time dateTime={business.updated_at}>{formatDate(business.updated_at, locale)}</time>
            </DetailLine>
            <DetailLine label={t.businesses.lineLogo}>
              <BusinessLogo url={business.logo_url} t={t} />
            </DetailLine>
            <DetailLine label={t.businesses.linePrefixes}>
              <span className="mono-value">
                {business.barcode_prefixes?.length
                  ? business.barcode_prefixes.join(', ')
                  : t.businesses.prefixesNone}
              </span>
            </DetailLine>
          </dl>
        </article>
        <article className="surface-card">
          <span className="panel-kicker">{t.businesses.panelColors}</span>
          {business.colors && Object.keys(business.colors).length > 0 ? (
            <dl className="detail-list">
              {Object.entries(business.colors).map(([key, value]) => (
                <DetailLine key={key} label={key}>
                  <code className="safe-value">{String(value)}</code>
                </DetailLine>
              ))}
            </dl>
          ) : (
            <p className="table-empty">{t.businesses.colorsEmpty}</p>
          )}
        </article>
      </section>
      {editOpen && (
        <BusinessEditorDialog
          business={business}
          onClose={() => setEditOpen(false)}
          onSaved={() => {
            setEditOpen(false);
            void query.refetch();
          }}
        />
      )}
      {managerAccess && <ManagerAccessDialog disclosure={managerAccess} onClose={() => setManagerAccess(null)} />}
    </div>
  );
}

function DetailMetric({
  title,
  value,
  detail,
  locale,
}: {
  title: string;
  value: number;
  detail: string;
  locale: 'ru' | 'kk';
}) {
  return (
    <article className="metric-card compact-metric">
      <span className="metric-title">{title}</span>
      <strong className="metric-value">{formatNumber(value, locale)}</strong>
      <span className="metric-footnote">{detail}</span>
    </article>
  );
}

function DetailLine({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="detail-line">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function BusinessLogo({ url, t }: { url: string | null; t: ReturnType<typeof useAdminTranslation> }) {
  if (!url) return <span className="muted-copy">{t.businesses.logoNone}</span>;
  let safeSource: string;
  try {
    const parsed = new URL(url, window.location.origin);
    if (parsed.protocol !== 'https:' && parsed.origin !== window.location.origin) {
      return <span className="muted-copy">{t.businesses.logoHttpsOnly}</span>;
    }
    safeSource = parsed.href;
  } catch {
    return <span className="muted-copy">{t.businesses.logoInvalid}</span>;
  }
  return <img className="business-logo" src={safeSource} alt={t.businesses.logoAlt} loading="lazy" referrerPolicy="no-referrer" />;
}
