import { Link } from 'react-router-dom';
import type { ReactNode } from 'react';
import { messageForError } from '../api/errors';

export function LoadingPage({ label = 'Загружаем безопасную сессию…' }: { label?: string }) {
  return <main className="center-screen" aria-live="polite"><span className="loading-mark" aria-hidden="true" /><p>{label}</p></main>;
}

export function ErrorNotice({ error, retry }: { error: unknown; retry?: () => void }) {
  return (
    <section className="notice error-notice" role="alert">
      <span className="notice-mark" aria-hidden="true">!</span>
      <div><strong>Не удалось выполнить запрос</strong><p>{messageForError(error)}</p></div>
      {retry && <button className="button button-secondary" type="button" onClick={retry}>Повторить</button>}
    </section>
  );
}

export function QueryState({ loading, error, retry, children }: {
  loading: boolean; error: unknown; retry: () => void; children: ReactNode;
}) {
  if (loading) return <LoadingPage label="Загружаем данные…" />;
  if (error) return <ErrorNotice error={error} retry={retry} />;
  return <>{children}</>;
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className="empty-state"><div className="empty-symbol" aria-hidden="true">◌</div><h2>{title}</h2><p>{detail}</p></div>;
}

export function PageHeading({ eyebrow, title, subtitle, actions }: {
  eyebrow: string; title: string; subtitle: string; actions?: ReactNode;
}) {
  return <header className="page-heading">
    <div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{subtitle}</p></div>{actions && <div className="heading-actions">{actions}</div>}
  </header>;
}

export function AccessDenied() {
  return <main className="center-screen"><div className="notice error-notice"><strong>Нет доступа</strong><p>У вашей учётной записи нет доступа к этому разделу.</p><Link className="button button-secondary" to="/admin">Вернуться к обзору</Link></div></main>;
}

export function StatusPill({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'positive' | 'warning' | 'negative' }) {
  return <span className={`status-pill tone-${tone}`}>{children}</span>;
}

export function Pagination({ page, onChange }: { page: { limit: number; offset: number; has_more: boolean }; onChange: (offset: number) => void }) {
  return <div className="pagination" aria-label="Страницы результатов">
    <span>Страница {Math.floor(page.offset / page.limit) + 1}</span>
    <div className="pagination-actions">
      <button className="button button-secondary" type="button" disabled={page.offset === 0} onClick={() => onChange(Math.max(0, page.offset - page.limit))}>Назад</button>
      <button className="button button-secondary" type="button" disabled={!page.has_more} onClick={() => onChange(page.offset + page.limit)}>Далее</button>
    </div>
  </div>;
}
