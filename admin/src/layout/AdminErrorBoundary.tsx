import { Component, type ReactNode } from 'react';
import { LanguageSwitcher } from '../i18n/LocaleContext';
import { usePublicTranslation } from '../i18n/public';

interface ErrorBoundaryProps {
  children: ReactNode;
  onReload?: () => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: unknown;
}

export class AdminErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  override state: ErrorBoundaryState = {
    hasError: false,
    error: null,
  };

  static getDerivedStateFromError(error: unknown): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  handleReload = () => {
    if (this.props.onReload) {
      this.props.onReload();
      return;
    }
    if (typeof window !== 'undefined' && typeof window.location?.reload === 'function') {
      window.location.reload();
    }
  };

  override render() {
    if (this.state.hasError) {
      return <AdminLoadError onReload={this.handleReload} />;
    }
    return this.props.children;
  }
}

function AdminLoadError({ onReload }: { onReload: () => void }) {
  const t = usePublicTranslation().adminChunkError;
  return (
    <div className="admin-surface">
      <main className="center-screen">
        <div className="failure-panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <div className="brand-mark-wrap">
              <img src="/brand-mark.png" alt="" className="brand-mark-img" width="36" height="36" />
            </div>
            <LanguageSwitcher className="admin-error-lang-switcher" />
          </div>
          <h1>{t.title}</h1>
          <p className="error-copy">{t.desc}</p>
          <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', marginTop: '16px' }}>
            <button className="button button-primary" type="button" onClick={onReload}>
              {t.reloadBtn}
            </button>
            <a href="/" className="button button-secondary">
              {t.homeBtn}
            </a>
          </div>
        </div>
      </main>
    </div>
  );
}
