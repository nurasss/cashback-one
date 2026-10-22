export function PrivacyPolicyPage() {
  return (
    <div className="landing-page legal-page">
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
          <nav className="landing-nav" aria-label="Навигация">
            <a href="/" className="landing-nav-link">Главная</a>
            <a href="/terms" className="landing-nav-link">Условия использования</a>
            <a href="/admin/login" className="landing-btn landing-btn-secondary landing-btn-sm">Вход для бизнеса</a>
          </nav>
        </div>
      </header>

      <main className="landing-main legal-main">
        <div className="landing-container">
          <article className="legal-article">
            <span className="landing-kicker">ЮРИДИЧЕСКАЯ ИНФОРМАЦИЯ</span>
            <h1 className="legal-title">Политика конфиденциальности и использования данных</h1>
            <p className="legal-meta">Редакция от 22 октября 2026 года</p>

            <section className="legal-section">
              <h2>1. Общие положения</h2>
              <p>
                Настоящая Политика определяет порядок обработки и защиты персональной информации пользователей
                сервиса <strong>Cashback One</strong> (далее — Сервис), предоставляемого в рамках программной экосистемы
                POSCENTER.KZ для взаимодействия покупателей и магазинов, использующих кассовое ПО POSCENTER Cash
                и учётную систему POSCENTER ONE.
              </p>
            </section>

            <section className="legal-section">
              <h2>2. Категории обрабатываемых данных и принцип минимизации</h2>
              <p>
                Мы придерживаемся принципа минимизации данных и обрабатываем только те сведения, которые
                необходимы для функционирования дисконтной и бонусной программы. Обрабатываемые данные разделяются
                на обязательные технические и дополнительные анкетные поля.
              </p>
              <h3>Обязательные данные для функционирования сервиса:</h3>
              <ul>
                <li><strong>Номер телефона покупателя</strong> — используется для аутентификации через проверочный код WhatsApp OTP и идентификации пользователя;</li>
                <li><strong>Язык интерфейса</strong> — выбор языка обслуживания (русский или казахский);</li>
                <li><strong>Номер карты лояльности (штрихкод)</strong> — уникальная цифровая последовательность от 6 до 15 знаков, привязанная к карте покупателя;</li>
                <li><strong>Баланс бонусов и статус карты</strong> — текущий остаток баллов, статус блокировки (is_blocked) и статус видимости карты в приложении;</li>
                <li><strong>История операций лояльности</strong> — дата проведения, вид движения (начисление или списание) и размер бонусов, зеркалируемые из POSCENTER ONE при закрытии кассовой смены.</li>
              </ul>
              <h3>Дополнительные поля профиля (могут заполняться покупателем в мобильном приложении):</h3>
              <ul>
                <li><strong>Имя и фамилия</strong> (first_name, last_name);</li>
                <li><strong>Адрес электронной почты</strong> (email);</li>
                <li><strong>Пол</strong> (gender) и <strong>дата рождения</strong> (birth_date);</li>
                <li><strong>Индивидуальный идентификационный номер Республики Казахстан</strong> (ИИН, 12 цифр с проверкой контрольного разряда);</li>
                <li><strong>Город</strong> (city), <strong>адрес</strong> (address) и <strong>организация</strong> (company).</li>
              </ul>
              <p>
                Поля профиля не являются обязательными для базового участия в программе и применения карты на кассе.
                Фактический перечень запрашиваемых полей и цели их обработки определяются правилами конкретной розничной сети.
                Сервис не запрашивает и не хранит данные платёжных банковских карт и данные о геолокации.
              </p>
            </section>

            <section className="legal-section">
              <h2>3. Политика в отношении файлов cookie</h2>
              <p>
                На публичном сайте Cashback One (<code className="legal-code">/</code>, <code className="legal-code">/privacy</code>, <code className="legal-code">/terms</code>)
                <strong>не используются</strong> сторонние маркетинговые, рекламные или поведенческие трекеры
                (включая внешние рекламные пиксели и рекламные сети).
              </p>
              <p>
                Технические файлы cookie применяются исключительно в закрытой административной панели бизнеса
                (<code className="legal-code">/admin/*</code>) в виде защищённых HttpOnly/SameSite сессионных идентификаторов
                для авторизации сотрудников.
              </p>
              <p>
                Необходимость показа информационного баннера согласия зависит от применимых требований законодательства
                конкретной юрисдикции и правил хостинг-провайдера. Окончательное решение о применении баннера подлежит
                юридической верификации оператором платформы при вводе в эксплуатацию.
              </p>
            </section>

            <section className="legal-section">
              <h2>4. Защита информации и безопасность каналов связи</h2>
              <p>
                Внешний сетевой обмен между клиентскими интерфейсами (мобильное приложение, административный веб-кабинет)
                и облачным сервером Cashback One осуществляется по защищённому протоколу HTTPS с шифрованием TLS.
              </p>
              <p>
                Взаимодействие внутри торговой точки (между кассовым аппаратом POSCENTER Cash, учётной системой POSCENTER ONE
                и локальным агентом синхронизации) протекает в закрытом локальном контуре магазина. Программный агент
                синхронизации магазина выполняет чтение данных (read-only) без создания документов или проводок в учётной
                системе POSCENTER ONE. Данный режим работы заложен в логику агента и не подменяет собой настройку прав доступа
                пользователей в самой системе 1С.
              </p>
            </section>

            <section className="legal-section">
              <h2>5. Права пользователей и управление картами</h2>
              <p>
                Покупатель вправе в любой момент скорректировать данные своего профиля в мобильном приложении,
                а также скрыть отображение карты лояльности в интерфейсе.
              </p>
              <p>
                <strong>Обратите внимание:</strong> действие «скрыть карту» в мобильном приложении управляет
                исключительно отображением карты на экране смартфона и не означает отвязку карты на сервере
                или удаление информации о покупках из учётной системы магазина. Для полной отвязки карты
                или прекращения участия в программе покупатель обращается непосредственно в розничную сеть,
                выдавшую карту.
              </p>
            </section>

            <section className="legal-section">
              <h2>6. Статус документа и сведения об операторе</h2>
              <p>
                Настоящий текст является рабочим черновиком (проектом) и не содержит финальных юридических обязательств.
                Наименование оператора, точные реквизиты юридического лица, контакты лица, ответственного за обработку данных,
                и применимые регламенты подлежат утверждению владельцем сервиса до открытия публичного доступа.
              </p>
            </section>
          </article>
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
          <div className="landing-footer-links">
            <a href="/">Главная</a>
            <a href="/terms">Условия использования</a>
            <a href="/admin/login">Кабинет бизнеса</a>
          </div>
          <div className="landing-footer-copy">
            <small>© Cashback One. Платформа лояльности для решений POSCENTER.</small>
          </div>
        </div>
      </footer>
    </div>
  );
}

export function TermsPage() {
  return (
    <div className="landing-page legal-page">
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
          <nav className="landing-nav" aria-label="Навигация">
            <a href="/" className="landing-nav-link">Главная</a>
            <a href="/privacy" className="landing-nav-link">Конфиденциальность</a>
            <a href="/admin/login" className="landing-btn landing-btn-secondary landing-btn-sm">Вход для бизнеса</a>
          </nav>
        </div>
      </header>

      <main className="landing-main legal-main">
        <div className="landing-container">
          <article className="legal-article">
            <span className="landing-kicker">ЮРИДИЧЕСКАЯ ИНФОРМАЦИЯ</span>
            <h1 className="legal-title">Условия использования платформы и правила лояльности</h1>
            <p className="legal-meta">Редакция от 22 октября 2026 года</p>

            <section className="legal-section">
              <h2>1. Предмет соглашения</h2>
              <p>
                Платформа <strong>Cashback One</strong> обеспечивает информационный обмен между розничными магазинами,
                использующими учётную систему POSCENTER ONE и кассы POSCENTER Cash, и покупателями — держателями карт лояльности.
              </p>
            </section>

            <section className="legal-section">
              <h2>2. Порядок начисления бонусов и синхронизация баланса</h2>
              <p>
                Правила начисления, списания и размер бонусов или кешбэка устанавливаются индивидуально каждым
                магазином — участником программы. Единственным источником информации о правилах и балансах
                является учётная система POSCENTER ONE соответствующего магазина.
              </p>
              <div className="landing-sync-highlight" style={{ margin: '16px 0' }}>
                <p className="landing-sync-statement">
                  Баланс обновляется не сразу. Новые начисления и списания появятся, когда магазин передаст данные.
                </p>
              </div>
              <p>
                Операции на кассе и движения по картам фиксируются в учётной системе POSCENTER ONE при закрытии кассовой смены,
                после чего агент синхронизации магазина передаёт обновлённые данные в сервис Cashback One.
              </p>
            </section>

            <section className="legal-section">
              <h2>3. Правила возврата товаров и корректировки бонусов</h2>
              <p>
                Порядок возврата товаров, гарантийные обязательства и правила корректировки бонусного баланса
                при возврате покупки определяются применимым законодательством и внутренними регламентами каждого конкретного магазина.
              </p>
              <p>
                Платформа Cashback One не является стороной договора купли-продажи розничных товаров, не производит денежных выплат
                и банковских операций, а отображает баланс и операции на основании данных, переданных из учётной системы магазина.
              </p>
            </section>

            <section className="legal-section">
              <h2>4. Доступ для представителей бизнеса</h2>
              <p>
                Доступ к панели управления бизнесом (<code className="legal-code">/admin/login</code>) предоставляется
                только уполномоченным менеджерам торговых сетей.
              </p>
              <p>
                При первичном создании доступа менеджера пароль отображается администратору в интерфейсе однократно
                (режим однократного раскрытия реквизитов) для безопасной передачи сотруднику. Сам сформированный пароль
                сохраняется в виде криптографического хеша и остаётся действительным для регулярного входа до момента смены
                или отзыва доступа. Пользователь кабинета обязуется соблюдать конфиденциальность учётных данных.
              </p>
            </section>

            <section className="legal-section">
              <h2>5. Статус документа и ограничение ответственности</h2>
              <p>
                Настоящий текст является рабочим черновиком условий использования. Условия носят предварительный характер
                и подлежат обязательной юридической проверке владельцем платформы перед открытием доступа.
              </p>
            </section>
          </article>
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
          <div className="landing-footer-links">
            <a href="/">Главная</a>
            <a href="/privacy">Конфиденциальность</a>
            <a href="/admin/login">Кабинет бизнеса</a>
          </div>
          <div className="landing-footer-copy">
            <small>© Cashback One. Платформа лояльности для решений POSCENTER.</small>
          </div>
        </div>
      </footer>
    </div>
  );
}
