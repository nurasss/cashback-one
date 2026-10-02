import { NavLink, useNavigate } from 'react-router-dom';
import type { PropsWithChildren } from 'react';
import { useAdminSession } from '../auth/provider';
import { Navigation } from '../features/Navigation';

export function AdminLayout({ children }: PropsWithChildren) {
  const { session, view } = useAdminSession();
  const navigate = useNavigate();
  if (view.status !== 'authenticated') return null;
  const { admin } = view;
  const signOut = async () => { await session.logout(); navigate('/login', { replace: true }); };
  return <div className="app-frame">
    <aside className="sidebar">
      <NavLink className="brand-lockup" to="/" aria-label="POSCENTER Loyalty — на главную">
        <span className="brand-mark">P</span><span><strong>POSCENTER</strong><small>LOYALTY · ADMIN</small></span>
      </NavLink>
      <Navigation role={admin.role} />
      <div className="sidebar-note"><span className="security-dot"/> Режим просмотра<br/><small>Административные изменения отключены</small></div>
    </aside>
    <div className="main-column">
      <header className="topbar">
        <div className="topbar-context"><span>Платформа лояльности</span><span aria-hidden="true">/</span><strong>{admin.business?.name ?? 'Все бизнесы'}</strong></div>
        <div className="account-menu"><div className="account-avatar" aria-hidden="true">{admin.login.slice(0, 1).toUpperCase()}</div>
          <div className="account-copy"><strong>{admin.login}</strong><span>{admin.role === 'superadmin' ? 'Суперадминистратор' : 'Менеджер бизнеса'}</span></div>
          <button className="button button-secondary signout-button" type="button" onClick={() => { void signOut(); }}>Выйти</button>
        </div>
      </header>
      <main className="main-content">{children}</main>
    </div>
  </div>;
}
