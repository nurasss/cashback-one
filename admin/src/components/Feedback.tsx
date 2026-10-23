import { Link } from 'react-router-dom';
import type { ReactNode } from 'react';
import { messageForError } from '../api/errors';
import { useLocale } from '../i18n/LocaleContext';

export function LoadingPage({ label }: { label?: string }) {
  const { locale } = useLocale();
  const defaultLabel = locale === 'kk' ? 'Қауіпсіз сессияны жүктеудеміз…' : 'Загружаем безопасную сессию…';
  return (
    <main className="center-screen" aria-live="polite">
      <span className="loading-mark" aria-hidden="true" />
      <p>{label ?? defaultLabel}</p>
    </main>
  );
}

export function ErrorNotice({ error, retry }: { error: unknown; retry?: () => void }) {
  const { locale } = useLocale();
  return (
    <section className="notice error-notice" role="alert">
      <span className="notice-mark" aria-hidden="true">!</span>
      <div>
        <strong>{locale === 'kk' ? 'Сұранысты орындау мүмкін болмады' : 'Не удалось выполнить запрос'}</strong>
        <p>{messageForError(error, locale)}</p>
      </div>
      {retry && (
        <button className="button button-secondary" type="button" onClick={retry}>
          {locale === 'kk' ? 'Қайталау' : 'Повторить'}
        </button>
      )}
    </section>
  );
}

export function QueryState({
  loading,
  error,
  retry,
  children,
}: {
  loading: boolean;
  error: unknown;
  retry: () => void;
  children: ReactNode;
}) {
  const { locale } = useLocale();
  if (loading) {
    return <LoadingPage label={locale === 'kk' ? 'Деректер жүктелуде…' : 'Загружаем данные…'} />;
  }
  if (error) return <ErrorNotice error={error} retry={retry} />;
  return <>{children}</>;
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="empty-state">
      <div className="empty-symbol" aria-hidden="true">◌</div>
      <h2>{title}</h2>
      <p>{detail}</p>
    </div>
  );
}

export function PageHeading({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle: string;
  actions?: ReactNode;
}) {
  return (
    <header className="page-heading">
      <div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      {actions && <div className="heading-actions">{actions}</div>}
    </header>
  );
}

export function AccessDenied() {
  const { locale } = useLocale();
  return (
    <main className="center-screen">
      <div className="notice error-notice">
        <strong>{locale === 'kk' ? 'Қолжетімсіз' : 'Нет доступа'}</strong>
        <p>{locale === 'kk' ? 'Тіркелгіңізде бұл бөлімге рұқсат жоқ.' : 'У вашей учётной записи нет доступа к этому разделу.'}</p>
        <Link className="button button-secondary" to="/admin">
          {locale === 'kk' ? 'Шолуға оралу' : 'Вернуться к обзору'}
        </Link>
      </div>
    </main>
  );
}

export function StatusPill({
  children,
  tone = 'neutral',
}: {
  children: ReactNode;
  tone?: 'neutral' | 'positive' | 'warning' | 'negative';
}) {
  return <span className={`status-pill tone-${tone}`}>{children}</span>;
}

export function Pagination({
  page,
  onChange,
}: {
  page: { limit: number; offset: number; has_more: boolean };
  onChange: (offset: number) => void;
}) {
  const { locale } = useLocale();
  const pageNum = Math.floor(page.offset / page.limit) + 1;
  return (
    <div className="pagination" aria-label={locale === 'kk' ? 'Нәтиже беттері' : 'Страницы результатов'}>
      <span>{locale === 'kk' ? `Бет ${pageNum}` : `Страница ${pageNum}`}</span>
      <div className="pagination-actions">
        <button
          className="button button-secondary"
          type="button"
          disabled={page.offset === 0}
          onClick={() => onChange(Math.max(0, page.offset - page.limit))}
        >
          {locale === 'kk' ? 'Артқа' : 'Назад'}
        </button>
        <button
          className="button button-secondary"
          type="button"
          disabled={!page.has_more}
          onClick={() => onChange(page.offset + page.limit)}
        >
          {locale === 'kk' ? 'Келесі' : 'Далее'}
        </button>
      </div>
    </div>
  );
}
