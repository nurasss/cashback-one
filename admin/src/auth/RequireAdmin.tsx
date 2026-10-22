import { Navigate, Outlet } from 'react-router-dom';
import { useAdminSession } from './provider';
import { ApiError } from '../api/errors';
import type { ReactNode } from 'react';
import { AccessDenied, ErrorNotice, LoadingPage } from '../components/Feedback';
import { AdminLayout } from '../layout/AdminLayout';

export function RequireAdmin() {
  const { session, view } = useAdminSession();
  if (view.status === 'loading' || view.status === 'authenticating') return <LoadingPage />;
  if (view.status === 'anonymous') return <Navigate to="/admin/login" replace />;
  if (view.status === 'error') return <BootstrapFailure retry={() => { void session.bootstrap(); }} />;
  if (view.status === 'logout_error') return <LogoutFailure retry={() => { void session.logout(); }} />;
  if (view.status === 'signing_out') return <LoadingPage label="Выполняем выход…" />;
  return <AdminLayout><Outlet /></AdminLayout>;
}

function BootstrapFailure({ retry }: { retry: () => void }) {
  return <main className="center-screen"><div className="failure-panel">
    <div className="brand-mark-wrap"><img src="/brand-mark.png" alt="" className="brand-mark-img" width="36" height="36" /></div>
    <h1>Нет соединения с Admin</h1>
    <ErrorNotice error={new ApiError('NETWORK_UNAVAILABLE')} retry={retry} />
    <p className="muted-copy">Можно перейти ко входу и повторить позже.</p>
    <NavigateLink />
  </div></main>;
}
function NavigateLink() { return <a className="button button-secondary" href="/admin/login">Перейти ко входу</a>; }

function LogoutFailure({ retry }: { retry: () => void }) {
  return <main className="center-screen"><div className="failure-panel">
    <div className="brand-mark-wrap"><img src="/brand-mark.png" alt="" className="brand-mark-img" width="36" height="36" /></div>
    <h1>Выход не подтверждён</h1>
    <p className="error-copy">Браузер заблокировал доступ на этом устройстве. Сервер ещё не подтвердил отзыв сессии; повторите запрос.</p>
    <button className="button button-primary" type="button" onClick={retry}>Повторить выход</button>
  </div></main>;
}

export function RequireSuperadmin({ children }: { children: ReactNode }) {
  const { view } = useAdminSession();
  if (view.status !== 'authenticated') return null;
  return view.admin.role === 'superadmin' ? <>{children}</> : <AccessDenied />;
}
