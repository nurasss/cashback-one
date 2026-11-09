import { Link } from 'react-router-dom';
import { PageHeading } from '../components/Feedback';
import { IconAgents, IconAudit } from '../components/Icons';
import { useAdminTranslation } from '../i18n/admin';

export function SettingsPage() {
  const t = useAdminTranslation();

  return (
    <div className="page-stack">
      <PageHeading title={t.settings.title} subtitle={t.settings.subtitle} />

      <div className="settings-grid">
        <section className="surface-card settings-card">
          <div className="settings-card-content">
            <div className="settings-card-header">
              <span className="settings-card-icon" aria-hidden="true">
                <IconAgents />
              </span>
              <div>
                <h2>{t.settings.agentsTitle}</h2>
                <p className="muted-copy">{t.settings.agentsDesc}</p>
              </div>
            </div>
          </div>
          <div className="settings-card-actions">
            <Link to="/admin/agents" className="button button-secondary">
              {t.settings.agentsLink} <span aria-hidden="true">→</span>
            </Link>
          </div>
        </section>

        <section className="surface-card settings-card">
          <div className="settings-card-content">
            <div className="settings-card-header">
              <span className="settings-card-icon" aria-hidden="true">
                <IconAudit />
              </span>
              <div>
                <h2>{t.settings.auditTitle}</h2>
                <p className="muted-copy">{t.settings.auditDesc}</p>
              </div>
            </div>
          </div>
          <div className="settings-card-actions">
            <Link to="/admin/audit" className="button button-secondary">
              {t.settings.auditLink} <span aria-hidden="true">→</span>
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
}
