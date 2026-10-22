export function LandingPage() {
  return (
    <div className="landing-page">
      {/* Шапка */}
      <header className="landing-header">
        <div className="landing-container landing-header-inner">
          <a href="/" className="landing-brand" aria-label="Cashback One — на главную">
            <div className="landing-brand-mark">
              <img src="/brand-mark.png" alt="" width="36" height="36" />
            </div>
            <div className="landing-brand-copy">
              <strong>Cashback One</strong>
              <small>POSCENTER</small>
            </div>
          </a>

          <nav className="landing-nav" aria-label="Разделы страницы">
            <a href="#how-it-works" className="landing-nav-link">Как начать</a>
            <a href="#balance-sync" className="landing-nav-link">Синхронизация</a>
            <a href="#business" className="landing-nav-link">Для бизнеса</a>
            <a href="#faq" className="landing-nav-link">Вопросы</a>
          </nav>

          <div className="landing-header-actions">
            <a href="/admin/login" className="landing-btn landing-btn-secondary landing-btn-sm">
              Вход для бизнеса
            </a>
          </div>
        </div>
      </header>

      <main className="landing-main">
        {/* Первый экран (Hero) */}
        <section className="landing-hero" aria-labelledby="hero-title">
          <div className="landing-container">
            <div className="landing-hero-content">
              <div className="landing-pill">
                <span className="landing-pill-dot" aria-hidden="true" />
                <span>Программа лояльности POSCENTER</span>
              </div>

              <h1 id="hero-title" className="landing-title">
                Карта магазина<br />
                <em>в вашем телефоне</em>
              </h1>

              <p className="landing-lead">
                Cashback One — приложение для карт лояльности магазинов с POSCENTER Cash и POSCENTER ONE.
                Открывайте свою карту, смотрите баланс и историю операций.
              </p>

              <div className="landing-hero-actions">
                <a
                  href="/app/cashback-one-1.0.3.apk"
                  className="landing-btn landing-btn-primary landing-btn-lg"
                  download
                >
                  <svg className="landing-btn-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="7 10 12 15 17 10" />
                    <line x1="12" y1="15" x2="12" y2="3" />
                  </svg>
                  <span>Скачать для Android</span>
                </a>

                <a href="/admin/login" className="landing-btn landing-btn-secondary landing-btn-lg">
                  Вход для бизнеса
                </a>
              </div>

              <div className="landing-version-note">
                <span>Android · APK 1.0.3</span>
              </div>

              {/* Утвержденный текст — заметно на первом экране */}
              <div className="landing-notice-card" role="note" aria-label="Информация об обновлении баланса">
                <div className="landing-notice-icon" aria-hidden="true">
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="8" x2="12" y2="12" />
                    <line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                </div>
                <div className="landing-notice-body">
                  <strong>Баланс обновляется не сразу. Новые начисления и списания появятся, когда магазин передаст данные.</strong>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Как пользоваться */}
        <section id="how-it-works" className="landing-section" aria-labelledby="how-title">
          <div className="landing-container">
            <div className="landing-section-header">
              <span className="landing-kicker">ПОШАГОВО</span>
              <h2 id="how-title" className="landing-section-title">Как начать пользоваться</h2>
              <p className="landing-section-subtitle">
                Три простых шага для установки карты магазина на телефон.
              </p>
            </div>

            <div className="landing-steps-grid">
              <article className="landing-step-card">
                <div className="landing-step-num" aria-hidden="true">1</div>
                <h3>Установите приложение</h3>
                <p>
                  Скачайте APK-файл на телефон Android и откройте его для установки. Если операционная система
                  запросит разрешение на установку из браузера, предоставьте его для этого файла.
                </p>
              </article>

              <article className="landing-step-card">
                <div className="landing-step-num" aria-hidden="true">2</div>
                <h3>Войдите по номеру</h3>
                <p>
                  Введите ваш номер телефона при запуске. Одноразовый проверочный код для безопасного входа
                  поступит в WhatsApp.
                </p>
              </article>

              <article className="landing-step-card">
                <div className="landing-step-num" aria-hidden="true">3</div>
                <h3>Откройте карту</h3>
                <p>
                  В приложении доступны карта магазина, текущий остаток бонусов и история операций.
                  Порядок начисления и списания определяет магазин.
                </p>
              </article>
            </div>

            <div className="landing-subnote">
              <p>Возможность использования штрихкода на кассе уточняйте в магазине.</p>
            </div>
          </div>
        </section>

        {/* Заметный блок синхронизации баланса */}
        <section id="balance-sync" className="landing-section landing-section-alt" aria-labelledby="sync-title">
          <div className="landing-container">
            <div className="landing-feature-card">
              <div className="landing-feature-header">
                <span className="landing-kicker">СИНХРОНИЗАЦИЯ С КАССОЙ</span>
                <h2 id="sync-title" className="landing-feature-title">
                  Когда обновляется баланс
                </h2>
              </div>

              <div className="landing-sync-highlight">
                <p className="landing-sync-statement">
                  Баланс обновляется не сразу. Новые начисления и списания появятся, когда магазин передаст данные.
                </p>
              </div>

              <div className="landing-feature-text">
                <p>
                  Операции с кассы POSCENTER Cash поступают в учётную базу POSCENTER ONE при закрытии кассовой смены.
                  Затем агент синхронизации передаёт обновлённые данные в облачный сервис Cashback One,
                  после чего новый баланс и операции отображаются в приложении покупателя.
                </p>
                <p className="landing-caption">
                  Если компьютер магазина выключен или временно отсутствует связь, данные сохраняются
                  в системе магазина и передаются при следующем сеансе связи.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Для бизнеса */}
        <section id="business" className="landing-section" aria-labelledby="business-title">
          <div className="landing-container">
            <div className="landing-business-grid">
              <div className="landing-business-info">
                <span className="landing-kicker">ДЛЯ РОЗНИЧНЫХ СЕТЕЙ</span>
                <h2 id="business-title" className="landing-section-title">
                  Лояльность на базе POSCENTER
                </h2>
                <p className="landing-section-lead">
                  Cashback One связывает мобильное приложение покупателя с базой POSCENTER ONE.
                  Для синхронизации используется агент на компьютере магазина с доступом к учётной системе.
                </p>

                <div className="landing-business-points">
                  <div className="landing-point">
                    <span className="landing-point-bullet" aria-hidden="true">✓</span>
                    <div>
                      <strong>ONE — источник правды</strong>
                      <p>Агент читает данные базы в режиме read-only. Карты, балансы и правила начислений остаются в вашей учётной системе.</p>
                    </div>
                  </div>

                  <div className="landing-point">
                    <span className="landing-point-bullet" aria-hidden="true">✓</span>
                    <div>
                      <strong>Защищённый кабинет</strong>
                      <p>Управление доступом менеджеров, просмотр статусов синхронизации и карт в личном кабинете.</p>
                    </div>
                  </div>
                </div>

                <div className="landing-business-cta">
                  <a href="/admin/login" className="landing-btn landing-btn-secondary landing-btn-lg">
                    Войти в кабинет
                  </a>
                  <span className="landing-business-note">
                    Доступ к кабинету выдаётся администратором сети
                  </span>
                </div>
              </div>

              <div className="landing-business-box">
                <div className="landing-box-inner">
                  <span className="landing-box-label">СХЕМА РАБОТЫ</span>
                  <div className="landing-flow">
                    <div className="landing-flow-item">
                      <span className="landing-flow-tag">Касса</span>
                      <strong>POSCENTER Cash</strong>
                      <small>Сканирование карты и проведение покупки</small>
                    </div>
                    <div className="landing-flow-arrow" aria-hidden="true">↓ закрытие смены</div>
                    <div className="landing-flow-item">
                      <span className="landing-flow-tag">Учёт</span>
                      <strong>POSCENTER ONE</strong>
                      <small>Источник карт, балансов и операций</small>
                    </div>
                    <div className="landing-flow-arrow" aria-hidden="true">↓ агент read-only</div>
                    <div className="landing-flow-item">
                      <span className="landing-flow-tag">Облако</span>
                      <strong>Cashback One</strong>
                      <small>Приложение покупателя и кабинет бизнеса</small>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Вопросы и ответы (FAQ) */}
        <section id="faq" className="landing-section landing-section-alt" aria-labelledby="faq-title">
          <div className="landing-container">
            <div className="landing-section-header">
              <span className="landing-kicker">СПРАВКА</span>
              <h2 id="faq-title" className="landing-section-title">Вопросы и ответы</h2>
              <p className="landing-section-subtitle">
                Ответы на главные вопросы покупателей и партнёров.
              </p>
            </div>

            <div className="landing-faq-list">
              <details className="landing-faq-item">
                <summary className="landing-faq-question">
                  <span>Что такое Cashback One?</span>
                  <span className="landing-faq-toggle" aria-hidden="true">+</span>
                </summary>
                <div className="landing-faq-answer">
                  <p>
                    Это приложение для карт лояльности магазинов, использующих кассовую программу POSCENTER Cash
                    и учётную систему POSCENTER ONE. Приложение хранит карту покупателя, баланс и историю операций.
                  </p>
                </div>
              </details>

              <details className="landing-faq-item">
                <summary className="landing-faq-question">
                  <span>Как установить приложение?</span>
                  <span className="landing-faq-toggle" aria-hidden="true">+</span>
                </summary>
                <div className="landing-faq-answer">
                  <p>
                    Нажмите кнопку «Скачать для Android», дождитесь загрузки APK-файла и откройте его на телефоне.
                    Сейчас приложение распространяется напрямую через официальный сайт.
                  </p>
                </div>
              </details>

              <details className="landing-faq-item">
                <summary className="landing-faq-question">
                  <span>Есть ли версия для iPhone?</span>
                  <span className="landing-faq-toggle" aria-hidden="true">+</span>
                </summary>
                <div className="landing-faq-answer">
                  <p>
                    Сейчас на сайте доступно приложение для Android. Ссылки на версию для iPhone пока нет.
                  </p>
                </div>
              </details>

              <details className="landing-faq-item">
                <summary className="landing-faq-question">
                  <span>Для чего нужен WhatsApp?</span>
                  <span className="landing-faq-toggle" aria-hidden="true">+</span>
                </summary>
                <div className="landing-faq-answer">
                  <p>
                    Через WhatsApp приходит одноразовый код для входа покупателя в приложение.
                    Отдельного WhatsApp-кода для подтверждения списания бонусов на кассе нет.
                  </p>
                </div>
              </details>

              <details className="landing-faq-item">
                <summary className="landing-faq-question">
                  <span>Почему баланс не изменился сразу после покупки?</span>
                  <span className="landing-faq-toggle" aria-hidden="true">+</span>
                </summary>
                <div className="landing-faq-answer">
                  <p>
                    <strong>Баланс обновляется не сразу. Новые начисления и списания появятся, когда магазин передаст данные.</strong>
                  </p>
                  <p>
                    Кассовые операции поступают в базу ONE после закрытия смены, после чего синхронизируются
                    с приложением. Если смена закрыта, но баланс не обновился, уточните состояние карты в магазине.
                  </p>
                </div>
              </details>

              <details className="landing-faq-item">
                <summary className="landing-faq-question">
                  <span>Можно использовать карту в любом магазине?</span>
                  <span className="landing-faq-toggle" aria-hidden="true">+</span>
                </summary>
                <div className="landing-faq-answer">
                  <p>
                    Карта относится к конкретной программе лояльности соответствующей торговой сети.
                    Возможность её использования и правила начисления или списания уточняйте в магазине.
                  </p>
                </div>
              </details>

              <details className="landing-faq-item">
                <summary className="landing-faq-question">
                  <span>Как бизнесу получить доступ?</span>
                  <span className="landing-faq-toggle" aria-hidden="true">+</span>
                </summary>
                <div className="landing-faq-answer">
                  <p>
                    Учётную запись менеджера или руководителя выдаёт администратор платформы.
                    Если доступ уже выдан, используйте раздел «Вход для бизнеса».
                  </p>
                </div>
              </details>

              <details className="landing-faq-item">
                <summary className="landing-faq-question">
                  <span>Что нужно для синхронизации?</span>
                  <span className="landing-faq-toggle" aria-hidden="true">+</span>
                </summary>
                <div className="landing-faq-answer">
                  <p>
                    Нужны база POSCENTER ONE и включённый Windows-компьютер с настроенным агентом.
                    Если компьютер выключен или временно нет связи, данные сохраняются в базе ONE и синхронизируются
                    после восстановления соединения.
                  </p>
                </div>
              </details>
            </div>
          </div>
        </section>

        {/* Повторный CTA блок внизу */}
        <section className="landing-cta-section" aria-labelledby="cta-title">
          <div className="landing-container">
            <div className="landing-cta-card">
              <h2 id="cta-title" className="landing-cta-title">
                Установите Cashback One
              </h2>
              <p className="landing-cta-subtitle">
                Карта лояльности магазина всегда под рукой в вашем телефоне.
              </p>

              <div className="landing-cta-actions">
                <a
                  href="/app/cashback-one-1.0.3.apk"
                  className="landing-btn landing-btn-primary landing-btn-lg"
                  download
                >
                  <svg className="landing-btn-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="7 10 12 15 17 10" />
                    <line x1="12" y1="15" x2="12" y2="3" />
                  </svg>
                  <span>Скачать для Android</span>
                </a>

                <a href="/admin/login" className="landing-btn landing-btn-secondary landing-btn-lg">
                  Вход для бизнеса
                </a>
              </div>

              <div className="landing-cta-note">
                <strong>Баланс обновляется не сразу. Новые начисления и списания появятся, когда магазин передаст данные.</strong>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Подвал */}
      <footer className="landing-footer">
        <div className="landing-container landing-footer-inner">
          <div className="landing-footer-brand">
            <div className="landing-brand-mark">
              <img src="/brand-mark.png" alt="" width="28" height="28" />
            </div>
            <span><strong>Cashback One</strong> · POSCENTER</span>
          </div>

          <div className="landing-footer-links">
            <a href="#how-it-works">Как начать</a>
            <a href="#balance-sync">Синхронизация</a>
            <a href="#business">Для бизнеса</a>
            <a href="#faq">Вопросы</a>
            <a href="/admin/login">Кабинет</a>
          </div>

          <div className="landing-footer-copy">
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
            <div className="landing-brand-mark">
              <img src="/brand-mark.png" alt="" width="36" height="36" />
            </div>
            <div className="landing-brand-copy">
              <strong>Cashback One</strong>
              <small>POSCENTER</small>
            </div>
          </a>
          <nav className="landing-nav" aria-label="Навигация">
            <a href="/admin/login" className="landing-btn landing-btn-secondary landing-btn-sm">
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
              <a href="/admin/login" className="landing-btn landing-btn-secondary">
                Вход для бизнеса
              </a>
            </div>
          </div>
        </div>
      </main>

      <footer className="landing-footer">
        <div className="landing-container landing-footer-inner">
          <div className="landing-footer-brand">
            <div className="landing-brand-mark">
              <img src="/brand-mark.png" alt="" width="28" height="28" />
            </div>
            <span><strong>Cashback One</strong> · POSCENTER</span>
          </div>
          <div className="landing-footer-copy">
            <small>© Cashback One. Платформа лояльности для решений POSCENTER.</small>
          </div>
        </div>
      </footer>
    </div>
  );
}
