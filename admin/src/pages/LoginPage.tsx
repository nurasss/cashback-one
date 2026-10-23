import { useEffect, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiError, messageForError } from '../api/errors';
import { useAdminSession } from '../auth/provider';
import { LoadingPage } from '../components/Feedback';
import { IconShield } from '../components/Icons';
import { LanguageSwitcher, useLocale } from '../i18n/LocaleContext';
import { useAdminTranslation } from '../i18n/admin';

export function LoginPage() {
  const { session, view } = useAdminSession();
  const { locale } = useLocale();
  const t = useAdminTranslation();
  const navigate = useNavigate();
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.title = `${t.login.cardTitle} — Cashback One Admin`;
    }
  }, [t.login.cardTitle]);

  useEffect(() => {
    if (view.status === 'authenticated') navigate('/admin', { replace: true });
  }, [view.status, navigate]);

  if (view.status === 'loading') return <LoadingPage label={t.routes.loadingSession} />;

  if (view.status === 'signing_out' || view.status === 'logout_error') {
    return (
      <section className="center-screen">
        <div className="failure-panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <div className="brand-mark-wrap">
              <img src="/brand-mark.png" alt="" className="brand-mark-img" width="36" height="36" />
            </div>
            <LanguageSwitcher className="login-lang-switcher" />
          </div>
          <h1>{t.login.logoutUnconfirmed}</h1>
          <p className="error-copy">{t.login.logoutErrorCopy}</p>
          <button className="button button-primary" type="button" onClick={() => { void session.logout(); }}>
            {t.login.retryLogout}
          </button>
        </div>
      </section>
    );
  }

  if (view.status === 'authenticated') return <LoadingPage label={t.login.openingAdmin} />;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await session.login(login, password);
      setPassword('');
      navigate('/admin', { replace: true });
    } catch (cause) {
      setPassword('');
      setError(cause instanceof ApiError ? cause : new ApiError('UNKNOWN_ERROR'));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-screen">
      <div className="login-story">
        <div className="login-brand">
          <div className="brand-mark-wrap">
            <img src="/brand-mark.png" alt="" className="brand-mark-img" width="36" height="36" />
          </div>
          <div>
            <b>POSCENTER.KZ</b>
            <small>LOYALTY PLATFORM</small>
          </div>
        </div>
        <div className="story-copy">
          <span className="eyebrow">{t.login.storyKicker}</span>
          <h1>
            {locale === 'kk' ? (
              <>
                Бизнестің барлық көрсеткіштері.<br />
                <em>Бір жүйеде.</em>
              </>
            ) : (
              <>
                Все показатели бизнеса.<br />
                <em>В одной системе.</em>
              </>
            )}
          </h1>
          <p>{t.login.storyCopy}</p>
        </div>
        <div className="story-footer">
          <span className="security-dot" aria-hidden="true" />
          <span>{t.login.storyFooter}</span>
        </div>
      </div>
      <section className="login-card" aria-labelledby="login-title">
        <div className="login-card-header-bar">
          <div className="login-card-brand">
            <img src="/logo.png" alt="POSCENTER.KZ" className="login-card-logo" />
          </div>
          <LanguageSwitcher className="login-lang-switcher" />
        </div>
        <div className="login-card-heading">
          <span className="eyebrow">{t.login.cardEyebrow}</span>
          <h2 id="login-title">{t.login.cardTitle}</h2>
          <p>{t.login.cardSubtitle}</p>
        </div>
        <form aria-label={t.login.formAria} className="login-form" onSubmit={event => { void submit(event); }}>
          <label className="field-label" htmlFor="admin-login">{t.login.loginLabel}</label>
          <input
            id="admin-login"
            name="username"
            className="text-input"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            value={login}
            onChange={event => setLogin(event.target.value)}
            disabled={submitting}
            required
            maxLength={128}
          />
          <div className="password-label">
            <label className="field-label" htmlFor="admin-password">{t.login.passwordLabel}</label>
          </div>
          <input
            id="admin-password"
            name="password"
            className="text-input"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={event => setPassword(event.target.value)}
            disabled={submitting}
            required
            maxLength={1024}
          />
          {error && <p className="form-error" role="alert">{messageForError(error, locale)}</p>}
          <button className="button button-primary login-button" type="submit" disabled={submitting || !login.trim() || !password}>
            {submitting ? t.login.submitting : t.login.submitBtn} <span aria-hidden="true">→</span>
          </button>
        </form>
        <div className="login-card-footer">
          <span className="lock-icon" aria-hidden="true"><IconShield /></span>
          <span>{t.login.cardFooter}</span>
        </div>
      </section>
      <footer className="mobile-login-footer">{t.login.mobileFooter}</footer>
    </main>
  );
}
