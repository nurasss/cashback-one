import { Component, type ReactNode } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
  onReload?: () => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: unknown;
}

export class AdminErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  override state: ErrorBoundaryState = { hasError: false, error: null };

  static getDerivedStateFromError(error: unknown): ErrorBoundaryState {
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
      return (
        <div className="admin-surface">
          <main className="center-screen">
            <div className="failure-panel">
              <div className="brand-mark-wrap">
                <img src="/brand-mark.png" alt="" className="brand-mark-img" width="36" height="36" />
              </div>
              <h1>Ошибка загрузки кабинета</h1>
              <p className="error-copy">Не удалось загрузить модуль управления. Проверьте соединение или обновите страницу.</p>
              <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', marginTop: '16px' }}>
                <button
                  className="button button-primary"
                  type="button"
                  onClick={this.handleReload}
                >
                  Перезагрузить страницу
                </button>
                <a href="/" className="button button-secondary">
                  На главную
                </a>
              </div>
            </div>
          </main>
        </div>
      );
    }
    return this.props.children;
  }
}
