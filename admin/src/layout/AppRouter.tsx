import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { useAdminSession } from '../auth/provider';
import { RequireAdmin, RequireSuperadmin } from '../auth/RequireAdmin';
import { LoginPage } from '../pages/LoginPage';
import { DashboardPage } from '../pages/DashboardPage';
import { BusinessesPage, BusinessDetailPage } from '../pages/BusinessesPage';
import { AgentsPage, AgentDetailPage } from '../pages/AgentsPage';
import { OperationsPage, CardDetailPage, UserDetailPage } from '../pages/OperationsPage';
import { AuditPage } from '../pages/AuditPage';
import { ContentPage } from '../pages/ContentPage';
import { ErrorNotice, LoadingPage } from '../components/Feedback';

function ProtectedLayout() {
  return <RequireAdmin />;
}

function RouterState() {
  const { session, view } = useAdminSession();
  if (view.status === 'loading') return <LoadingPage />;
  if (view.status === 'error') return <main className="center-screen"><div className="failure-panel">
    <div className="brand-mark-wrap"><img src="/brand-mark.png" alt="" className="brand-mark-img" width="36" height="36" /></div>
    <h1>Нет соединения с Admin</h1>
    <ErrorNotice error={view.error} retry={() => { void session.bootstrap(); }} />
    <button className="button button-secondary" type="button" onClick={() => session.continueToLogin()}>Перейти ко входу</button>
  </div></main>;
  if (view.status === 'logout_error') return <main className="center-screen"><div className="failure-panel">
    <div className="brand-mark-wrap"><img src="/brand-mark.png" alt="" className="brand-mark-img" width="36" height="36" /></div>
    <h1>Выход не подтверждён</h1>
    <p className="error-copy">Браузер заблокировал доступ на этом устройстве. Сервер ещё не подтвердил отзыв сессии.</p>
    <button className="button button-primary" type="button" onClick={() => { void session.logout(); }}>Повторить выход</button>
  </div></main>;
  if (view.status === 'signing_out') return <LoadingPage label="Выполняем выход…" />;
  if (view.status === 'authenticating') return <Routes><Route path="/login" element={<LoginPage />} /><Route path="/admin/login" element={<LoginPage />} /><Route path="*" element={<LoadingPage />} /></Routes>;
  return <Routes>
    <Route path="/login" element={view.status === 'authenticated' ? <Navigate to="/" replace /> : <LoginPage />} />
    <Route path="/admin/login" element={view.status === 'authenticated' ? <Navigate to="/" replace /> : <LoginPage />} />
    <Route element={<ProtectedLayout />}>
      <Route index element={<DashboardPage />} />
      <Route path="businesses" element={<RequireSuperadmin><BusinessesPage /></RequireSuperadmin>} />
      <Route path="businesses/:businessId" element={<RequireSuperadmin><BusinessDetailPage /></RequireSuperadmin>} />
      <Route path="agents" element={<AgentsPage />} />
      <Route path="agents/:agentId" element={<AgentDetailPage />} />
      <Route path="operations" element={<OperationsPage />} />
      <Route path="cards/:cardId" element={<CardDetailPage />} />
      <Route path="users/:userId" element={<UserDetailPage />} />
      <Route path="audit" element={<AuditPage />} />
      <Route path="content" element={<ContentPage />} />
      <Route path="admin" element={<DashboardPage />} />
      <Route path="admin/businesses" element={<RequireSuperadmin><BusinessesPage /></RequireSuperadmin>} />
      <Route path="admin/businesses/:businessId" element={<RequireSuperadmin><BusinessDetailPage /></RequireSuperadmin>} />
      <Route path="admin/agents" element={<AgentsPage />} />
      <Route path="admin/agents/:agentId" element={<AgentDetailPage />} />
      <Route path="admin/operations" element={<OperationsPage />} />
      <Route path="admin/cards/:cardId" element={<CardDetailPage />} />
      <Route path="admin/users/:userId" element={<UserDetailPage />} />
      <Route path="admin/audit" element={<AuditPage />} />
      <Route path="admin/content" element={<ContentPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Route>
  </Routes>;
}

export function AppRouter() {
  return <BrowserRouter><RouterState /></BrowserRouter>;
}
