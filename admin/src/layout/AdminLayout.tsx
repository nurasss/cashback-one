import { NavLink, useNavigate } from 'react-router-dom';
import type { PropsWithChildren } from 'react';
import { useAdminSession } from '../auth/provider';
import { Navigation } from '../features/Navigation';
import { IconBuilding, IconLogout } from '../components/Icons';

export function AdminLayout({ children }: PropsWithChildren) {
  const { session, view } = useAdminSession();
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
          <NavLink className="brand-lockup" to="/admin" aria-label="POSCENTER Loyalty — на главную">
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
              <span className="security-title">Режим просмотра</span>
            </div>
            <small>Административные изменения отключены</small>
          </div>
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div className="topbar-context">
            <span className="context-platform">Платформа лояльности</span>
            <span className="context-divider" aria-hidden="true">/</span>
            <span className="context-business">
              <IconBuilding className="context-icon" aria-hidden="true" />
              <strong>{admin.business?.name ?? 'Все бизнесы'}</strong>
            </span>
          </div>

          <div className="account-menu">
            <div className="account-avatar" aria-hidden="true">
              {admin.login.slice(0, 1).toUpperCase()}
            </div>
            <div className="account-copy">
              <strong>{admin.login}</strong>
              <span className="account-role-pill">
                {admin.role === 'superadmin' ? 'Суперадминистратор' : 'Менеджер бизнеса'}
              </span>
            </div>
            <button
              className="button button-secondary signout-button"
              type="button"
              onClick={() => { void signOut(); }}
              title="Завершить сеанс"
            >
              <IconLogout className="button-icon" aria-hidden="true" />
              <span>Выйти</span>
            </button>
          </div>
        </header>

        <main className="main-content">{children}</main>
      </div>
    </div>
  );
}
