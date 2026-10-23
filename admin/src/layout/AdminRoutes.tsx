import { Link, Navigate, Route, Routes } from 'react-router-dom';
import '@fontsource/roboto/cyrillic-ext-400.css';
import '@fontsource/roboto/cyrillic-400.css';
import '@fontsource/roboto/latin-400.css';
import '@fontsource/roboto/cyrillic-ext-500.css';
import '@fontsource/roboto/cyrillic-500.css';
import '@fontsource/roboto/latin-500.css';
import '@fontsource/roboto/cyrillic-ext-600.css';
import '@fontsource/roboto/cyrillic-600.css';
import '@fontsource/roboto/latin-600.css';
import '@fontsource/roboto/cyrillic-ext-700.css';
import '@fontsource/roboto/cyrillic-700.css';
import '@fontsource/roboto/latin-700.css';
import { AdminProvider, useAdminSession } from '../auth/provider';
import { RequireAdmin, RequireSuperadmin } from '../auth/RequireAdmin';
import { LoginPage } from '../pages/LoginPage';
import { DashboardPage } from '../pages/DashboardPage';
import { BusinessesPage, BusinessDetailPage } from '../pages/BusinessesPage';
import { AgentsPage, AgentDetailPage } from '../pages/AgentsPage';
import { OperationsPage, CardDetailPage, UserDetailPage } from '../pages/OperationsPage';
import { AuditPage } from '../pages/AuditPage';
import { ContentPage } from '../pages/ContentPage';
import { ErrorNotice, LoadingPage } from '../components/Feedback';
import { AdminErrorBoundary } from './AdminErrorBoundary';
import { LanguageSwitcher } from '../i18n/LocaleContext';
import { useAdminTranslation } from '../i18n/admin';

export { AdminErrorBoundary };

export function AdminNotFoundPage() {
  const t = useAdminTranslation();
  return (
    <div className="center-screen">
      <div className="failure-panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div className="brand-mark-wrap">
            <img src="/brand-mark.png" alt="" className="brand-mark-img" width="36" height="36" />
          </div>
          <LanguageSwitcher className="admin-not-found-lang-switcher" />
        </div>
        <h1>{t.routes.adminNotFoundTitle}</h1>
        <p className="error-copy">{t.routes.adminNotFoundCopy}</p>
        <Link to="/admin" className="button button-primary">
          {t.routes.backToOverview}
        </Link>
      </div>
    </div>
  );
}

function ProtectedLayout() {
  return <RequireAdmin />;
}

function AdminRouterState() {
  const { session, view } = useAdminSession();
  const t = useAdminTranslation();

  if (view.status === 'loading') return <LoadingPage label={t.routes.loadingSession} />;

  if (view.status === 'error') {
    return (
      <main className="center-screen">
        <div className="failure-panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <div className="brand-mark-wrap">
              <img src="/brand-mark.png" alt="" className="brand-mark-img" width="36" height="36" />
            </div>
            <LanguageSwitcher className="admin-error-lang-switcher" />
          </div>
          <h1>{t.routes.noConnectionTitle}</h1>
          <ErrorNotice error={view.error} retry={() => { void session.bootstrap(); }} />
          <button className="button button-secondary" type="button" onClick={() => session.continueToLogin()}>
            {t.routes.goToLogin}
          </button>
        </div>
      </main>
    );
  }

  if (view.status === 'logout_error') {
    return (
      <main className="center-screen">
        <div className="failure-panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <div className="brand-mark-wrap">
              <img src="/brand-mark.png" alt="" className="brand-mark-img" width="36" height="36" />
            </div>
            <LanguageSwitcher className="admin-error-lang-switcher" />
          </div>
          <h1>{t.login.logoutUnconfirmed}</h1>
          <p className="error-copy">{t.login.logoutErrorCopy}</p>
          <button className="button button-primary" type="button" onClick={() => { void session.logout(); }}>
            {t.login.retryLogout}
          </button>
        </div>
      </main>
    );
  }

  if (view.status === 'signing_out') return <LoadingPage label={t.routes.signingOut} />;

  if (view.status === 'authenticating') {
    return (
      <Routes>
        <Route path="login" element={<LoginPage />} />
        <Route path="*" element={<LoadingPage label={t.routes.loadingSession} />} />
      </Routes>
    );
  }

  return (
    <Routes>
      <Route
        path="login"
        element={view.status === 'authenticated' ? <Navigate to="/admin" replace /> : <LoginPage />}
      />
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
        <Route path="*" element={<AdminNotFoundPage />} />
      </Route>
    </Routes>
  );
}

export default function AdminRoutes() {
  return (
    <div className="admin-surface">
      <AdminProvider>
        <AdminRouterState />
      </AdminProvider>
    </div>
  );
}
