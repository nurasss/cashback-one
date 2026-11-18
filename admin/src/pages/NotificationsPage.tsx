import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { BroadcastPushResult } from '../api/types';
import { useAdminSession } from '../auth/provider';
import { useAllBusinesses } from '../api/queries';
import { BusinessSelect } from '../components/BusinessSelect';
import { PageHeading } from '../components/Feedback';
import { NotificationsTable, NotificationDialog } from './ContentPage';
import { useAdminTranslation } from '../i18n/admin';

const GLOBAL = '';

export function NotificationsPage() {
  const { view } = useAdminSession();
  const t = useAdminTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const isSuperadmin = view.status === 'authenticated' && view.admin.role === 'superadmin';
  const managerBusinessId =
    view.status === 'authenticated' && view.admin.role === 'business_manager'
      ? view.admin.business?.id
      : undefined;

  const [businessFilter, setBusinessFilter] = useState(GLOBAL);
  const [noticeOpen, setNoticeOpen] = useState(searchParams.get('create') === '1');
  const [noticeFeedback, setNoticeFeedback] = useState<string | null>(null);

  const businesses = useAllBusinesses(isSuperadmin);

  useEffect(() => {
    setNoticeOpen(searchParams.get('create') === '1');
  }, [searchParams]);

  const handleOpen = () => {
    setNoticeOpen(true);
    const next = new URLSearchParams(searchParams);
    next.set('create', '1');
    setSearchParams(next);
  };

  const handleClose = () => {
    setNoticeOpen(false);
    if (searchParams.get('create')) {
      const next = new URLSearchParams(searchParams);
      next.delete('create');
      setSearchParams(next, { replace: true });
    }
  };

  const handleNoticeCreated = (push?: BroadcastPushResult | null) => {
    if (!push) return;
    if (push.status === 'sent') {
      setNoticeFeedback(t.content.noticePushSent(push.delivered, push.devices));
    } else if (push.status === 'disabled') {
      setNoticeFeedback(t.content.noticePushDisabled);
    } else if (push.status === 'skipped') {
      if (push.devices === 0) {
        setNoticeFeedback(t.content.noticePushNoDevices);
      }
    } else if (push.status === 'failed') {
      setNoticeFeedback(t.content.noticePushFailed);
    }
  };

  const effectiveBusinessId = isSuperadmin ? (businessFilter || undefined) : managerBusinessId;

  return (
    <div className="page-stack">
      <PageHeading
        title={t.notifications.title}
        subtitle={t.notifications.subtitle}
        actions={
          <button className="button button-primary" type="button" onClick={handleOpen}>
            {t.notifications.createBtn}
          </button>
        }
      />

      {isSuperadmin && (
        <section className="filter-panel">
          <div className="filter-controls">
            <div className="form-control business-select">
              <label htmlFor="notice-business-filter">{t.content.businessFilterLabel}</label>
              <BusinessSelect
                id="notice-business-filter"
                value={businessFilter}
                onChange={setBusinessFilter}
                allowAllLabel={t.content.allRecords}
                businesses={businesses}
              />
            </div>
          </div>
        </section>
      )}

      {noticeFeedback && (
        <section
          className="notice"
          role="status"
          style={{
            marginBottom: '1rem',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <p>{noticeFeedback}</p>
          <button
            className="link-button"
            type="button"
            onClick={() => setNoticeFeedback(null)}
            aria-label={t.mutations.close}
          >
            ×
          </button>
        </section>
      )}

      <NotificationsTable businessId={effectiveBusinessId} />

      {noticeOpen && (
        <NotificationDialog
          onClose={handleClose}
          onCreated={handleNoticeCreated}
        />
      )}
    </div>
  );
}
