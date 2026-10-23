import { useEffect, useState, type KeyboardEvent } from 'react';
import { LanguageSwitcher } from '../i18n/LocaleContext';
import { usePublicTranslation } from '../i18n/public';

export function LandingPage() {
  const t = usePublicTranslation();
  const [activeScreen, setActiveScreen] = useState(0);

  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.title = t.pageTitle;
    }
  }, [t.pageTitle]);

  const screens = t.hero.screens;

  const handleTabKeyDown = (e: KeyboardEvent<HTMLButtonElement>, currentIndex: number) => {
    let nextIndex = currentIndex;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      nextIndex = (currentIndex + 1) % screens.length;
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      nextIndex = (currentIndex - 1 + screens.length) % screens.length;
    } else if (e.key === 'Home') {
      nextIndex = 0;
    } else if (e.key === 'End') {
      nextIndex = screens.length - 1;
    } else {
      return;
    }
    e.preventDefault();
    setActiveScreen(nextIndex);
    const target = screens[nextIndex] ?? screens[0];
    if (target) {
      const nextBtn = document.getElementById(`tab-${target.id}`);
      nextBtn?.focus();
    }
  };

  return (
    <div className="landing-page">
      {/* Шапка сайта */}
      <header className="landing-header">
        <div className="landing-container landing-header-inner">
          <a href="#top" className="landing-brand" aria-label={t.header.brandAria}>
            <img
              src="/brand-mark.png"
              alt=""
              width="36"
              height="36"
              className="landing-brand-logo"
            />
            <span className="landing-brand-name">Cashback One</span>
          </a>

          <nav className="landing-nav" aria-label={t.header.navAria}>
            <a href="#start" className="landing-nav-link">{t.header.navStart}</a>
            <a href="#bonus" className="landing-nav-link">{t.header.navBonus}</a>
            <a href="#business" className="landing-nav-link">{t.header.navBusiness}</a>
            <a href="#faq" className="landing-nav-link">{t.header.navFaq}</a>
          </nav>

          <div className="landing-header-actions">
            <LanguageSwitcher className="landing-lang-switcher" />
            <a href="#business" className="landing-btn landing-btn-outline landing-btn-sm landing-header-biz-btn">
              {t.header.businessBtn}
            </a>
            <a href="/admin/login" className="landing-btn landing-btn-ghost landing-btn-sm landing-header-login-btn">
              {t.header.loginBtn}
            </a>
          </div>
        </div>
      </header>

      <main id="top" className="landing-main">
        {/* Первый экран (Hero) */}
        <section className="landing-hero" aria-labelledby="hero-title">
          <div className="landing-container">
            <div className="landing-hero-grid">
              {/* Левая колонка: выгода и действие */}
              <div className="landing-hero-content">
                <p className="landing-kicker">{t.hero.kicker}</p>
                <h1 id="hero-title" className="landing-title">
                  {t.hero.title}
                </h1>
                <p className="landing-lead">
                  {t.hero.lead}
                </p>

                <div className="landing-hero-actions">
                  <a
                    href="/app/cashback-one-1.0.3.apk"
                    className="landing-btn landing-btn-primary landing-btn-lg"
                    download
                  >
                    <svg
                      className="landing-btn-icon"
                      width="20"
                      height="20"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      aria-hidden="true"
                    >
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="7 10 12 15 17 10" />
                      <line x1="12" y1="15" x2="12" y2="3" />
                    </svg>
                    <span>{t.hero.downloadBtn}</span>
                  </a>

                  <a href="#business" className="landing-btn landing-btn-secondary landing-btn-lg">
                    {t.hero.bizBtn}
                  </a>
                </div>
              </div>

              {/* Правая колонка: интерактивный телефон */}
              <div className="landing-hero-device">
                <div className="landing-phone-mockup" aria-hidden="true">
                  <div className="landing-phone-screen">
                    {screens.map((s, idx) => (
                      <img
                        key={s.id}
                        src={s.src}
                        alt={s.alt}
                        className={`landing-phone-img ${activeScreen === idx ? 'landing-phone-img-active' : ''}`}
                        loading={idx === 0 ? 'eager' : 'lazy'}
                      />
                    ))}
                  </div>
                </div>

                <div className="landing-screen-controls">
                  <div role="tablist" aria-label={t.hero.tabsAria} className="landing-screen-tabs">
                    {screens.map((s, idx) => (
                      <button
                        key={s.id}
                        type="button"
                        role="tab"
                        id={`tab-${s.id}`}
                        aria-selected={activeScreen === idx}
                        aria-controls={`panel-${s.id}`}
                        tabIndex={activeScreen === idx ? 0 : -1}
                        onClick={() => setActiveScreen(idx)}
                        onKeyDown={(e) => handleTabKeyDown(e, idx)}
                        className={`landing-screen-tab ${activeScreen === idx ? 'landing-screen-tab-active' : ''}`}
                      >
                        {s.tabLabel}
                      </button>
                    ))}
                  </div>

                  <div className="landing-screen-panels">
                    {screens.map((s, idx) => (
                      <div
                        key={s.id}
                        id={`panel-${s.id}`}
                        role="tabpanel"
                        aria-labelledby={`tab-${s.id}`}
                        hidden={activeScreen !== idx}
                        tabIndex={0}
                        className="landing-screen-panel"
                      >
                        <p className="landing-screen-desc">
                          <strong>{s.title}.</strong> {s.desc}
                        </p>
                      </div>
                    ))}
                  </div>

                  <p className="landing-screen-caption">
                    {t.hero.mockupCaption}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Начало работы: 3 шага и установка */}
        <section id="start" className="landing-section landing-section-start" aria-labelledby="start-title">
          <div className="landing-container">
            <h2 id="start-title" className="landing-section-title">
              {t.start.title}
            </h2>

            <ol className="landing-steps-list">
              <li className="landing-step-item">
                <span className="landing-step-num" aria-hidden="true">1</span>
                <h3 className="landing-step-title">{t.start.step1Title}</h3>
                <p className="landing-step-desc">
                  {t.start.step1Desc}
                </p>
              </li>

              <li className="landing-step-item">
                <span className="landing-step-num" aria-hidden="true">2</span>
                <h3 className="landing-step-title">{t.start.step2Title}</h3>
                <p className="landing-step-desc">
                  {t.start.step2Desc}
                </p>
              </li>

              <li className="landing-step-item">
                <span className="landing-step-num" aria-hidden="true">3</span>
                <h3 className="landing-step-title">{t.start.step3Title}</h3>
                <p className="landing-step-desc">
                  {t.start.step3Desc}
                </p>
              </li>
            </ol>

            <div className="landing-instructions-grid">
              <div className="landing-card landing-card-guide">
                <h3 className="landing-card-title">{t.start.guideTitle}</h3>
                <ol className="landing-guide-steps">
                  <li>{t.start.guideStep1}</li>
                  <li>{t.start.guideStep2}</li>
                  <li>{t.start.guideStep3}</li>
                  <li>{t.start.guideStep4}</li>
                </ol>
              </div>

              <div className="landing-card landing-card-notice">
                <h3 className="landing-card-title">{t.start.noticeTitle}</h3>
                <p className="landing-card-text">
                  {t.start.noticeText}
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Бонусы и синхронизация — утверждённый блок задержки баланса */}
        <section id="bonus" className="landing-section landing-section-bonus" aria-labelledby="bonus-title">
          <div className="landing-container">
            <div className="landing-bonus-grid">
              <div className="landing-bonus-hero">
                <h2 id="bonus-title" className="landing-bonus-title">
                  {t.bonus.title}
                </h2>
                <p className="landing-bonus-lead">
                  {t.bonus.lead}
                </p>
              </div>

              <div className="landing-bonus-card">
                <h3 className="landing-card-title">{t.bonus.pointsTitle}</h3>
                <p className="landing-card-text">
                  {t.bonus.pointsText1}
                </p>
                <p className="landing-card-text">
                  {t.bonus.pointsText2}
                </p>
                <p className="landing-card-text">
                  {t.bonus.pointsText3}
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Для бизнеса */}
        <section id="business" className="landing-section landing-section-biz" aria-labelledby="biz-title">
          <div className="landing-container">
            <p className="landing-kicker">{t.business.kicker}</p>
            <h2 id="biz-title" className="landing-section-title">
              {t.business.title}
            </h2>

            <div className="landing-biz-grid">
              <div className="landing-biz-points">
                <div className="landing-biz-point">
                  <h3>{t.business.point1Title}</h3>
                  <p>{t.business.point1Desc}</p>
                </div>

                <div className="landing-biz-point">
                  <h3>{t.business.point2Title}</h3>
                  <p>{t.business.point2Desc}</p>
                </div>

                <div className="landing-biz-point">
                  <h3>{t.business.point3Title}</h3>
                  <p>{t.business.point3Desc}</p>
                </div>
              </div>

              <div className="landing-biz-sidebar">
                <div className="landing-card landing-card-setup">
                  <h3 className="landing-card-title">{t.business.setupTitle}</h3>
                  <ul className="landing-setup-list">
                    <li>{t.business.setupItem1}</li>
                    <li>{t.business.setupItem2}</li>
                    <li>{t.business.setupItem3}</li>
                  </ul>
                  <p className="landing-card-subtext">
                    {t.business.setupSubtext}
                  </p>
                </div>

                <div className="landing-biz-cta-box">
                  <a href="/admin/login" className="landing-btn landing-btn-primary landing-btn-lg">
                    {t.business.ctaBtn}
                  </a>
                  <p className="landing-biz-cta-note">
                    {t.business.ctaNote}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Вопросы и ответы (FAQ) */}
        <section id="faq" className="landing-section landing-section-faq" aria-labelledby="faq-title">
          <div className="landing-container">
            <div className="landing-faq-header">
              <h2 id="faq-title" className="landing-section-title">
                {t.faq.title}
              </h2>
            </div>

            <div className="landing-faq-accordion">
              {t.faq.items.map((item, idx) => (
                <details key={item.q} className="landing-faq-item" open={idx === 0}>
                  <summary className="landing-faq-question">
                    <span>{item.q}</span>
                    <span className="landing-faq-toggle" aria-hidden="true">+</span>
                  </summary>
                  <div className="landing-faq-answer">
                    <p>{item.a}</p>
                  </div>
                </details>
              ))}
            </div>
          </div>
        </section>
      </main>

      {/* Подвал */}
      <footer className="landing-footer">
        <div className="landing-container">
          <div className="landing-footer-grid">
            <div className="landing-footer-brand-col">
              <strong className="landing-footer-brand-title">Cashback One</strong>
              <p className="landing-footer-brand-desc">
                {t.footer.brandDesc}
              </p>
              <img
                src="/logo-white.png"
                alt="POSCENTER.KZ"
                width="180"
                className="landing-footer-logo"
              />
            </div>

            <div className="landing-footer-nav-col">
              <strong className="landing-footer-heading">{t.footer.navHeading}</strong>
              <nav className="landing-footer-nav" aria-label={t.footer.navAria}>
                <a href="#start">{t.footer.navStart}</a>
                <a href="#bonus">{t.footer.navBonus}</a>
                <a href="#business">{t.footer.navBusiness}</a>
                <a href="#faq">{t.footer.navFaq}</a>
                <a href="/admin/login">{t.footer.navLogin}</a>
              </nav>
            </div>

            <div className="landing-footer-info-col">
              <strong className="landing-footer-heading">{t.footer.infoHeading}</strong>
              <p className="landing-footer-info-text">
                {t.footer.infoText}
              </p>
            </div>
          </div>

          <div className="landing-footer-bottom">
            <small>{t.footer.copyright}</small>
          </div>
        </div>
      </footer>
    </div>
  );
}

export function PublicNotFoundPage() {
  const t = usePublicTranslation();

  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.title = `${t.notFound.title} — Cashback One`;
    }
  }, [t.notFound.title]);

  return (
    <div className="landing-page not-found-page">
      <header className="landing-header">
        <div className="landing-container landing-header-inner">
          <a href="/" className="landing-brand" aria-label={t.header.brandAria}>
            <img src="/brand-mark.png" alt="" width="36" height="36" className="landing-brand-logo" />
            <span className="landing-brand-name">Cashback One</span>
          </a>
          <div className="landing-header-actions" aria-label={t.header.navAria}>
            <LanguageSwitcher className="landing-lang-switcher" />
            <a href="/admin/login" className="landing-btn landing-btn-outline landing-btn-sm">
              {t.notFound.loginBtn}
            </a>
          </div>
        </div>
      </header>

      <main className="landing-main not-found-main">
        <div className="landing-container">
          <div className="not-found-card">
            <span className="landing-kicker">{t.notFound.kicker}</span>
            <h1>{t.notFound.title}</h1>
            <p>{t.notFound.desc}</p>
            <div className="not-found-actions">
              <a href="/" className="landing-btn landing-btn-primary">
                {t.notFound.homeBtn}
              </a>
              <a href="/admin/login" className="landing-btn landing-btn-outline">
                {t.notFound.loginBtn}
              </a>
            </div>
          </div>
        </div>
      </main>

      <footer className="landing-footer">
        <div className="landing-container landing-footer-bottom">
          <small>{t.footer.copyright}</small>
        </div>
      </footer>
    </div>
  );
}
