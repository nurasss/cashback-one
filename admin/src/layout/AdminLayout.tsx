import { NavLink, useNavigate } from 'react-router-dom';
import type { PropsWithChildren } from 'react';
import { useAdminSession } from '../auth/provider';
import { Navigation } from '../features/Navigation';
import { IconBuilding, IconLogout } from '../components/Icons';
import { LanguageSwitcher } from '../i18n/LocaleContext';
import { useAdminTranslation } from '../i18n/admin';

export function AdminLayout({ children }: PropsWithChildren) {
  const { session, view } = useAdminSession();
  const t = useAdminTranslation();
  const navigate = useNavigate();
  if (view.status !== 'authenticated') return null;
  const { admin } = view;
  const signOut = async () => {
    await session.logout();
    navigate('/admin/login', { replace: true });
  };

  return (
    <div className="app-frame">
      <aside className="sidebar">
        <div className="sidebar-brand-container">
          <NavLink className="brand-lockup" to="/admin" aria-label={t.layout.brandAria}>
            <div className="brand-mark-wrap">
              <img src="/brand-mark.png" alt="" className="brand-mark-img" width="36" height="36" />
            </div>
            <div className="brand-text">
              <strong>POSCENTER.KZ</strong>
              <small>LOYALTY · ADMIN</small>
            </div>
          </NavLink>
        </div>

        <Navigation role={admin.role} />

        <div className="sidebar-footer">
          <div className="sidebar-note">
            <div className="sidebar-note-header">
              <span className="security-dot" aria-hidden="true" />
              <span className="security-title">{t.layout.viewMode}</span>
            </div>
            <small>{t.layout.viewModeNote}</small>
          </div>
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div className="topbar-context">
            <span className="context-platform">{t.layout.platform}</span>
            <span className="context-divider" aria-hidden="true">/</span>
            <span className="context-business">
              <IconBuilding className="context-icon" aria-hidden="true" />
              <strong>{admin.business?.name ?? t.layout.allBusinesses}</strong>
            </span>
          </div>

          <div className="account-menu">
            <LanguageSwitcher className="topbar-lang-switcher" />
            <div className="account-avatar" aria-hidden="true">
              {admin.login.slice(0, 1).toUpperCase()}
            </div>
            <div className="account-copy">
              <strong>{admin.login}</strong>
              <span className="account-role-pill">
                {admin.role === 'superadmin' ? t.layout.roles.superadmin : t.layout.roles.business_manager}
              </span>
            </div>
            <button
              className="button button-secondary signout-button"
              type="button"
              onClick={() => { void signOut(); }}
              title={t.layout.signoutTitle}
            >
              <IconLogout className="button-icon" aria-hidden="true" />
              <span>{t.layout.signout}</span>
            </button>
          </div>
        </header>

        <main className="main-content">{children}</main>
      </div>
    </div>
  );
}
