import { lazy, Suspense } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useInRouterContext, useLocation } from 'react-router-dom';
import { LandingPage, PublicNotFoundPage } from '../pages/LandingPage';
import { LoadingPage } from '../components/Feedback';
import { AdminErrorBoundary } from './AdminErrorBoundary';
import { LocaleProvider, useLocale } from '../i18n/LocaleContext';

const AdminRoutesLazy = lazy(() => import('./AdminRoutes'));

function LegacyRedirect() {
  const location = useLocation();
  const cleanPath = location.pathname.replace(/\/+$/, '');
  const destination = `/admin${cleanPath}${location.search}${location.hash}`;
  return <Navigate to={destination} replace />;
}

function AdminLazyFallback() {
  const { locale } = useLocale();
  return (
    <div className="admin-surface">
      <LoadingPage
        label={locale === 'kk' ? 'Қауіпсіз сессияны жүктеудеміз…' : 'Загружаем безопасную сессию…'}
      />
    </div>
  );
}

export function AppRoutes() {
  return (
    <Routes>
      {/* Главная публичная страница */}
      <Route path="/" element={<LandingPage />} />
      {/* LegalPages.tsx remains a draft until the operator and texts are approved. */}

      {/* Административная изолированная ветка с внешним перехватом ошибок загрузки */}
      <Route
        path="/admin/*"
        element={
          <AdminErrorBoundary>
            <Suspense fallback={<AdminLazyFallback />}>
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
    return (
      <LocaleProvider>
        <AppRoutes />
      </LocaleProvider>
    );
  }
  return (
    <BrowserRouter>
      <LocaleProvider>
        <AppRoutes />
      </LocaleProvider>
    </BrowserRouter>
  );
}
