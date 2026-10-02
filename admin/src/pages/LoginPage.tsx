import { useEffect, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiError, messageForError } from '../api/errors';
import { useAdminSession } from '../auth/provider';
import { LoadingPage } from '../components/Feedback';

export function LoginPage() {
  const { session, view } = useAdminSession();
  const navigate = useNavigate();
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => { if (view.status === 'authenticated') navigate('/', { replace: true }); }, [view.status, navigate]);
  if (view.status === 'loading') return <LoadingPage />;
  if (view.status === 'signing_out' || view.status === 'logout_error') return <section className="center-screen"><div className="failure-panel">
    <span className="brand-mark">P</span><h1>Выход не подтверждён</h1><p className="error-copy">Сервер ещё не подтвердил завершение сессии.</p>
    <button className="button button-primary" type="button" onClick={() => { void session.logout(); }}>Повторить выход</button>
  </div></section>;
  if (view.status === 'authenticated') return <LoadingPage label="Открываем Admin…" />;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await session.login(login, password);
      setPassword('');
      navigate('/', { replace: true });
    } catch (cause) {
      setPassword('');
      setError(cause instanceof ApiError ? cause : new ApiError('UNKNOWN_ERROR'));
    } finally { setSubmitting(false); }
  }

  return <main className="login-screen">
    <div className="login-story"><div className="login-brand"><span className="brand-mark">P</span><span><b>POSCENTER</b><small>LOYALTY PLATFORM</small></span></div>
      <div className="story-copy"><span className="eyebrow">ADMIN CONSOLE</span><h1>Все показатели бизнеса.<br/><em>В одной системе.</em></h1>
        <p>Статус сети, данные карт и операции в облачной платформе лояльности.</p></div>
      <div className="story-footer"><span className="security-dot"/> Защищённая административная сессия</div>
    </div>
    <section className="login-card" aria-labelledby="login-title">
      <div className="login-card-heading"><span className="eyebrow">ДОБРО ПОЖАЛОВАТЬ</span><h2 id="login-title">Вход в систему</h2><p>Используйте выданную вам учётную запись.</p></div>
      <form aria-label="Вход в Admin" className="login-form" onSubmit={event => { void submit(event); }}>
        <label className="field-label" htmlFor="admin-login">Логин</label>
        <input id="admin-login" name="username" className="text-input" autoComplete="username" autoCapitalize="none" spellCheck={false}
          value={login} onChange={event => setLogin(event.target.value)} disabled={submitting} required maxLength={128} />
        <div className="password-label"><label className="field-label" htmlFor="admin-password">Пароль</label></div>
        <input id="admin-password" name="password" className="text-input" type="password" autoComplete="current-password"
          value={password} onChange={event => setPassword(event.target.value)} disabled={submitting} required maxLength={1024} />
        {error && <p className="form-error" role="alert">{messageForError(error)}</p>}
        <button className="button button-primary login-button" type="submit" disabled={submitting || !login.trim() || !password}>
          {submitting ? 'Проверяем доступ…' : 'Войти'} <span aria-hidden="true">→</span>
        </button>
      </form>
      <div className="login-card-footer"><span className="lock-icon" aria-hidden="true">▣</span>Доступ предоставляется администратором</div>
    </section>
    <footer className="mobile-login-footer">POSCENTER LOYALTY · SECURE ADMINISTRATION</footer>
  </main>;
}
