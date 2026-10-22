import { lazy, Suspense } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useInRouterContext, useLocation } from 'react-router-dom';
import { LandingPage, PublicNotFoundPage } from '../pages/LandingPage';
import { PrivacyPolicyPage, TermsPage } from '../pages/LegalPages';
import { LoadingPage } from '../components/Feedback';
import { AdminErrorBoundary } from './AdminErrorBoundary';

const AdminRoutesLazy = lazy(() => import('./AdminRoutes'));

function LegacyRedirect() {
  const location = useLocation();
  const cleanPath = location.pathname.replace(/\/+$/, '');
  const destination = `/admin${cleanPath}${location.search}${location.hash}`;
  return <Navigate to={destination} replace />;
}

export function AppRoutes() {
  return (
    <Routes>
      {/* Главная публичная страница */}
      <Route path="/" element={<LandingPage />} />
      <Route path="/privacy" element={<PrivacyPolicyPage />} />
      <Route path="/terms" element={<TermsPage />} />

      {/* Административная изолированная ветка с внешним перехватом ошибок загрузки */}
      <Route
        path="/admin/*"
        element={
          <AdminErrorBoundary>
            <Suspense
              fallback={
                <div className="admin-surface">
                  <LoadingPage label="Загружаем безопасную сессию…" />
                </div>
              }
            >
              <AdminRoutesLazy />
            </Suspense>
          </AdminErrorBoundary>
        }
      />

      {/* Legacy redirects с сохранением ID, query и hash */}
      <Route path="/login" element={<LegacyRedirect />} />
      <Route path="/login/*" element={<LegacyRedirect />} />
      <Route path="/businesses" element={<LegacyRedirect />} />
      <Route path="/businesses/*" element={<LegacyRedirect />} />
      <Route path="/agents" element={<LegacyRedirect />} />
      <Route path="/agents/*" element={<LegacyRedirect />} />
      <Route path="/operations" element={<LegacyRedirect />} />
      <Route path="/operations/*" element={<LegacyRedirect />} />
      <Route path="/cards/*" element={<LegacyRedirect />} />
      <Route path="/users/*" element={<LegacyRedirect />} />
      <Route path="/audit" element={<LegacyRedirect />} />
      <Route path="/audit/*" element={<LegacyRedirect />} />
      <Route path="/content" element={<LegacyRedirect />} />
      <Route path="/content/*" element={<LegacyRedirect />} />

      {/* Неизвестные публичные адреса */}
      <Route path="*" element={<PublicNotFoundPage />} />
    </Routes>
  );
}

export function AppRouter() {
  const inRouter = useInRouterContext();
  if (inRouter) {
    return <AppRoutes />;
  }
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
