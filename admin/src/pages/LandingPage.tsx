import { useState, type KeyboardEvent } from 'react';

interface ScreenItem {
  id: string;
  tabLabel: string;
  title: string;
  desc: string;
  src: string;
  alt: string;
}

const SCREENS: ScreenItem[] = [
  {
    id: 'home',
    tabLabel: 'Карта',
    title: 'Карта и баланс',
    desc: 'Бонусный баланс карты выбранного магазина.',
    src: '/landing/screen-home.png',
    alt: 'Скриншот экрана приложения: Карта и баланс Cashback One',
  },
  {
    id: 'barcode',
    tabLabel: 'Штрихкод',
    title: 'Штрихкод',
    desc: 'Штрихкод карты — на экране телефона.',
    src: '/landing/screen-barcode.png',
    alt: 'Скриншот экрана приложения: Штрихкод карты в Cashback One',
  },
  {
    id: 'history',
    tabLabel: 'История',
    title: 'История операций',
    desc: 'Начисления и списания по карте.',
    src: '/landing/screen-history.png',
    alt: 'Скриншот экрана приложения: История операций Cashback One',
  },
  {
    id: 'promotions',
    tabLabel: 'Акции',
    title: 'Акции и сообщения',
    desc: 'Предложения и новости магазина.',
    src: '/landing/screen-promotions.png',
    alt: 'Скриншот экрана приложения: Акции и спецпредложения в Cashback One',
  },
];

interface FaqItem {
  q: string;
  a: string;
}

const FAQS: FaqItem[] = [
  {
    q: 'Не пришёл код',
    a: 'Проверьте правильность введённого номера телефона и убедитесь, что на телефоне установлен WhatsApp и есть доступ к интернету. Подождите минуту и запросите код повторно.',
  },
  {
    q: 'Не появилась карта',
    a: 'Существующая карта может появиться по номеру телефона, на который она оформлена в магазине. Если карты нет — уточните оформление в магазине. Приложение не выпускает новые карты автоматически.',
  },
  {
    q: 'Баланс не изменился',
    a: 'Баланс обновляется не сразу. Новые начисления и списания появятся, когда магазин передаст данные. Кассовые операции поступают в базу ONE после закрытия смены, после чего синхронизируются с приложением.',
  },
  {
    q: 'Где действует карта',
    a: 'Каждая карта принадлежит конкретному магазину или розничной сети и действует только там. Список магазинов и правила начисления или списания бонусов определяет сам магазин.',
  },
  {
    q: 'Есть ли версия для iPhone',
    a: 'Опубликованной версии для iPhone нет. Сейчас приложение доступно для Android через установку APK-файла.',
  },
  {
    q: 'Как подключить магазин',
    a: 'Нужны касса POSCENTER Cash, учётная система POSCENTER ONE и Windows-компьютер с агентом синхронизации. Подключение настраивается с администратором платформы, учётные данные выдаются при настройке.',
  },
];

const DEFAULT_SCREEN: ScreenItem = {
  id: 'home',
  tabLabel: 'Карта',
  title: 'Карта и баланс',
  desc: 'Бонусный баланс карты выбранного магазина.',
  src: '/landing/screen-home.png',
  alt: 'Скриншот экрана приложения: Карта и баланс Cashback One',
};

export function LandingPage() {
  const [activeScreen, setActiveScreen] = useState(0);

  const handleTabKeyDown = (e: KeyboardEvent<HTMLButtonElement>, currentIndex: number) => {
    let nextIndex = currentIndex;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      nextIndex = (currentIndex + 1) % SCREENS.length;
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      nextIndex = (currentIndex - 1 + SCREENS.length) % SCREENS.length;
    } else if (e.key === 'Home') {
      nextIndex = 0;
    } else if (e.key === 'End') {
      nextIndex = SCREENS.length - 1;
    } else {
      return;
    }
    e.preventDefault();
    setActiveScreen(nextIndex);
    const nextScreen = SCREENS[nextIndex] ?? DEFAULT_SCREEN;
    const nextBtn = document.getElementById(`tab-${nextScreen.id}`);
    nextBtn?.focus();
  };

  return (
    <div className="landing-page">
      {/* Шапка сайта */}
      <header className="landing-header">
        <div className="landing-container landing-header-inner">
          <a href="#top" className="landing-brand" aria-label="Cashback One — на главную">
            <img
              src="/brand-mark.png"
              alt=""
              width="36"
              height="36"
              className="landing-brand-logo"
            />
            <span className="landing-brand-name">Cashback One</span>
          </a>

          <nav className="landing-nav" aria-label="Разделы страницы">
            <a href="#start" className="landing-nav-link">Начало работы</a>
            <a href="#bonus" className="landing-nav-link">Бонусы</a>
            <a href="#business" className="landing-nav-link">Для бизнеса</a>
            <a href="#faq" className="landing-nav-link">Помощь</a>
          </nav>

          <div className="landing-header-actions">
            <a href="#business" className="landing-btn landing-btn-outline landing-btn-sm landing-header-biz-btn">
              Для бизнеса
            </a>
            <a href="/admin/login" className="landing-btn landing-btn-ghost landing-btn-sm landing-header-login-btn">
              Вход для бизнеса
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
                <p className="landing-kicker">Приложение для покупателей</p>
                <h1 id="hero-title" className="landing-title">
                  Карта магазина в&nbsp;телефоне
                </h1>
                <p className="landing-lead">
                  Баланс, история и штрихкод карты — без пластика в кармане.
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
                    <span>Скачать для Android</span>
                  </a>

                  <a href="#business" className="landing-btn landing-btn-secondary landing-btn-lg">
                    Для бизнеса →
                  </a>
                </div>

                <p className="landing-hero-note">
                  Версии для iPhone пока нет.
                </p>
              </div>

              {/* Правая колонка: интерактивный телефон */}
              <div className="landing-hero-device">
                <div className="landing-phone-mockup" aria-hidden="true">
                  <div className="landing-phone-screen">
                    {SCREENS.map((s, idx) => (
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
                  <div role="tablist" aria-label="Экраны приложения" className="landing-screen-tabs">
                    {SCREENS.map((s, idx) => (
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
                    {SCREENS.map((s, idx) => (
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
                    Данные на экранах — пример. Каждая карта принадлежит одному магазину или сети.
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
              Три шага до карты в телефоне
            </h2>

            <ol className="landing-steps-list">
              <li className="landing-step-item">
                <span className="landing-step-num" aria-hidden="true">1</span>
                <h3 className="landing-step-title">Установите приложение</h3>
                <p className="landing-step-desc">
                  Скачайте файл для Android и откройте его. Подробная инструкция — ниже.
                </p>
              </li>

              <li className="landing-step-item">
                <span className="landing-step-num" aria-hidden="true">2</span>
                <h3 className="landing-step-title">Войдите через WhatsApp</h3>
                <p className="landing-step-desc">
                  Введите номер телефона — проверочный код придёт в WhatsApp.
                </p>
              </li>

              <li className="landing-step-item">
                <span className="landing-step-num" aria-hidden="true">3</span>
                <h3 className="landing-step-title">Откройте карту магазина</h3>
                <p className="landing-step-desc">
                  Если карта уже оформлена на ваш номер, она появится в приложении. Если карты нет — уточните оформление в магазине. Приложение не выпускает новые карты само.
                </p>
              </li>
            </ol>

            <div className="landing-instructions-grid">
              <div className="landing-card landing-card-guide">
                <h3 className="landing-card-title">Как установить APK</h3>
                <ol className="landing-guide-steps">
                  <li>Нажмите «Скачать для Android» на телефоне.</li>
                  <li>Откройте скачанный файл <code>cashback-one-1.0.3.apk</code>.</li>
                  <li>
                    Если Android спросит, разрешите установку из этого источника — только для браузера или файлового менеджера, через который вы открываете файл.
                  </li>
                  <li>Нажмите «Установить» и откройте приложение.</li>
                </ol>
              </div>

              <div className="landing-card landing-card-notice">
                <h3 className="landing-card-title">Про защиту Android</h3>
                <p className="landing-card-text">
                  Не отключайте защиту телефона целиком (например, Play Защиту). Разрешение на установку нужно выдать один раз для конкретного приложения и при желании отозвать после установки.
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
                  Баланс обновляется не сразу
                </h2>
                <p className="landing-bonus-lead">
                  Баланс обновляется не сразу. Новые начисления и списания появятся, когда магазин передаст данные.
                </p>
                <p className="landing-bonus-explanation">
                  Операции с кассы POSCENTER Cash поступают в учётную базу POSCENTER ONE при закрытии кассовой смены, после чего агент синхронизации передаёт данные в облако.
                </p>
              </div>

              <div className="landing-bonus-card">
                <h3 className="landing-card-title">Как работают баллы</h3>
                <p className="landing-card-text">
                  Правила начисления, списания и использования баллов определяет конкретный магазин. Приложение их не меняет.
                </p>
                <p className="landing-card-text">
                  Источник данных о балансе — POSCENTER ONE магазина. Приложение показывает копию, которую передаёт агент на компьютере магазина, и само ничего не начисляет.
                </p>
                <p className="landing-card-text">
                  Курс, сроки и ограничения уточняйте у магазина.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Для бизнеса */}
        <section id="business" className="landing-section landing-section-biz" aria-labelledby="biz-title">
          <div className="landing-container">
            <p className="landing-kicker">Для владельцев магазинов</p>
            <h2 id="biz-title" className="landing-section-title">
              Карта лояльности вашего магазина — в телефоне покупателя
            </h2>

            <div className="landing-biz-grid">
              <div className="landing-biz-points">
                <div className="landing-biz-point">
                  <h3>Кому подходит</h3>
                  <p>Магазинам и розничным сетям, которые работают с POSCENTER Cash и POSCENTER ONE и ведут бонусную программу.</p>
                </div>

                <div className="landing-biz-point">
                  <h3>Что получает магазин</h3>
                  <p>Карту лояльности в приложении покупателя, штрихкод карты, каналы для акций и сообщений.</p>
                </div>

                <div className="landing-biz-point">
                  <h3>Что получает покупатель</h3>
                  <p>Баланс, историю операций, штрихкод и акции магазина — всегда под рукой.</p>
                </div>
              </div>

              <div className="landing-biz-sidebar">
                <div className="landing-card landing-card-setup">
                  <h3 className="landing-card-title">Что нужно для подключения</h3>
                  <ul className="landing-setup-list">
                    <li>Касса POSCENTER Cash</li>
                    <li>Учётная система POSCENTER ONE</li>
                    <li>Windows-компьютер с агентом синхронизации данных</li>
                  </ul>
                  <p className="landing-card-subtext">
                    Подключение выполняется с настройкой. Учётные данные выдаёт администратор платформы.
                  </p>
                </div>

                <div className="landing-biz-cta-box">
                  <a href="/admin/login" className="landing-btn landing-btn-primary landing-btn-lg">
                    Войти в кабинет
                  </a>
                  <p className="landing-biz-cta-note">
                    Для уже подключённых магазинов доступен личный кабинет. Доступ выдаётся администратором сети при настройке.
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
                Частые вопросы
              </h2>
            </div>

            <div className="landing-faq-accordion">
              {FAQS.map((item, idx) => (
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
                Приложение покупателя для карт лояльности магазинов POSCENTER.
              </p>
              <img
                src="/logo-white.png"
                alt="POSCENTER.KZ"
                width="180"
                className="landing-footer-logo"
              />
            </div>

            <div className="landing-footer-nav-col">
              <strong className="landing-footer-heading">Навигация</strong>
              <nav className="landing-footer-nav" aria-label="Навигация в подвале">
                <a href="#start">Начало работы</a>
                <a href="#bonus">Бонусы</a>
                <a href="#business">Для бизнеса</a>
                <a href="#faq">Помощь</a>
                <a href="/admin/login">Вход в кабинет</a>
              </nav>
            </div>

            <div className="landing-footer-info-col">
              <strong className="landing-footer-heading">О платформе</strong>
              <p className="landing-footer-info-text">
                Синхронизация данных с кассовой программой POSCENTER Cash и учётной системой POSCENTER ONE на базе 1С.
              </p>
            </div>
          </div>

          <div className="landing-footer-bottom">
            <small>© Cashback One. Платформа лояльности для решений POSCENTER.</small>
          </div>
        </div>
      </footer>
    </div>
  );
}

export function PublicNotFoundPage() {
  return (
    <div className="landing-page not-found-page">
      <header className="landing-header">
        <div className="landing-container landing-header-inner">
          <a href="/" className="landing-brand" aria-label="Cashback One">
            <img src="/brand-mark.png" alt="" width="36" height="36" className="landing-brand-logo" />
            <span className="landing-brand-name">Cashback One</span>
          </a>
          <nav className="landing-header-actions" aria-label="Навигация">
            <a href="/admin/login" className="landing-btn landing-btn-outline landing-btn-sm">
              Вход для бизнеса
            </a>
          </nav>
        </div>
      </header>

      <main className="landing-main not-found-main">
        <div className="landing-container">
          <div className="not-found-card">
            <span className="landing-kicker">ОШИБКА 404</span>
            <h1>Страница не найдена</h1>
            <p>Запрошенный адрес не существует. Возможно, ссылка устарела или содержит опечатку.</p>
            <div className="not-found-actions">
              <a href="/" className="landing-btn landing-btn-primary">
                На главную страницу
              </a>
              <a href="/admin/login" className="landing-btn landing-btn-outline">
                Вход для бизнеса
              </a>
            </div>
          </div>
        </div>
      </main>

      <footer className="landing-footer">
        <div className="landing-container landing-footer-bottom">
          <small>© Cashback One. Платформа лояльности для решений POSCENTER.</small>
        </div>
      </footer>
    </div>
  );
}
