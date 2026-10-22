# Отчёт об устранении замечаний к сайту (Admin & Landing)

Дата: 2026-10-22  
Исполнитель: Gemini (general / site)  
Окружение: `admin/`, стек React 19 (19.2.0) + Vite + TypeScript, локально без публикации и деплоя.  
Мобильная часть (`mobile/`) оставлена нетронутой (закреплена за Claude).

---

## 1. Результаты проверок качества

Все проверки выполнены строго последовательно с однопоточным выполнением тестов (`--maxWorkers=1`):

### 1.1. Тестовый набор (`npm test -- --maxWorkers=1`)
- **Команда**: `cd admin && npm test -- --maxWorkers=1`
- **Код возврата**: `0`
- **Результат**: **12 passed (12 test files), 69 passed (69 tests)**, общее время 54.92s.
  - `tests/public-routing.test.tsx` (11 tests passed)
  - `tests/cards-list.test.tsx` (5 tests passed)
  - `tests/manager-access.test.tsx` (4 tests passed)
  - `src/auth/security.test.tsx` (5 tests passed)
  - `tests/mutations.test.tsx` (5 tests passed)
  - `tests/login-and-privacy.test.tsx` (3 tests passed)
  - `tests/content.test.tsx` (2 tests passed)
  - `tests/navigation.test.tsx` (3 tests passed)
  - `tests/transport.test.ts` (24 tests passed)
  - `tests/session.test.ts` (5 tests passed)
  - `tests/native-fetch.test.ts` (1 test passed)
  - `tests/css-integrity.test.ts` (1 test passed)

### 1.2. Статическая типизация TypeScript (`npm run typecheck`)
- **Команда**: `cd admin && npm run typecheck`
- **Код возврата**: `0`
- **Результат**: ошибок нет (`tsc --noEmit` чистый).

### 1.3. Сборка для публикации (`npm run build`)
- **Команда**: `cd admin && npm run build`
- **Код возврата**: `0`
- **Результат**:
  - `dist/index.html` (3.08 kB)
  - `dist/assets/index-CMAeFNGM.css` (36.17 kB)
  - `dist/assets/AdminRoutes-BGwVrVRN.js` (117.62 kB)
  - `dist/assets/index-Bfu0P5T2.js` (311.33 kB)
  - Время сборки: 458 мс.

---

## 2. Выполненные исправления

### 2.1. Вынос `AdminErrorBoundary` наружу ленивого чанка `AdminRoutesLazy`
- **Проблема**: Компонент `AdminErrorBoundary`, находясь внутри динамически импортируемого чанка `AdminRoutes`, не мог перехватывать сетевые сбои или ошибки загрузки самого файла чанка (`Failed to fetch dynamically imported module`).
- **Решение**:
  - Создан независимый компонент [`admin/src/layout/AdminErrorBoundary.tsx`](file:///Users/nuras/Desktop/cashback-one/admin/src/layout/AdminErrorBoundary.tsx).
  - В [`admin/src/layout/AppRouter.tsx`](file:///Users/nuras/Desktop/cashback-one/admin/src/layout/AppRouter.tsx) маршрут `/admin/*` обёрнут в `AdminErrorBoundary` снаружи `Suspense` и `AdminRoutesLazy`:
    ```tsx
    <Route
      path="/admin/*"
      element={
        <AdminErrorBoundary>
          <Suspense fallback={<div className="admin-surface"><LoadingPage label="Загружаем безопасную сессию…" /></div>}>
            <AdminRoutesLazy />
          </Suspense>
        </AdminErrorBoundary>
      }
    />
    ```
  - Протестирован сценарий отказа загрузки чанка, доступность кнопки «Повторить попытку», переход «На главную» (`/`) и полное восстановление при повторении попытки после устранения сбоя сети.

### 2.2. Реальная изоляция CSS кабинета и публичного лендинга
- **Проблема**: Файл `admin.css` подключался глобально в `main.tsx` и содержал неизолированные селекторы тегов (`body`, `button`, `input`, `select`, `textarea`, `a`, `table`, `th`, `td`), которые переопределяли стили публичных страниц.
- **Решение**:
  - В [`admin/src/styles/admin.css`](file:///Users/nuras/Desktop/cashback-one/admin/src/styles/admin.css) глобальные стили цветов и типографики для `body` перенесены в изолированный класс `.admin-surface`.
  - Все правила для интерактивных элементов (`button`, `input`, `select`, `textarea`, `a`) и таблиц (`table`, `th`, `td`) ограничены пространством имен `.admin-surface`.
  - Элементы страницы кабинета, диалоги мутаций и загрузочные экраны обёрнуты в контейнер `.admin-surface`.
  - Блок `:root{...}` с системными переменными сохранён в валидном формате, тест `tests/css-integrity.test.ts` пройден.

### 2.3. Точные тесты сохранения параметров редиректов (pathname, search, hash)
- **Проблема**: Ранее тест проверял только появление формы входа без верификации фактических URL.
- **Решение**:
  - В [`admin/tests/public-routing.test.tsx`](file:///Users/nuras/Desktop/cashback-one/admin/tests/public-routing.test.tsx) добавлен `LocationObserver`.
  - Написаны тесты с проверкой точных значений `pathname`, `search` и `hash`:
    - `/login?return_to=foo#section` → `/admin/login?return_to=foo#section`
    - `/businesses/biz-42/?tab=settings#anchor` → `/admin/businesses/biz-42?tab=settings#anchor`
    - `/operations?page=2&status=success` → `/admin/operations?page=2&status=success`
    - `/agents/ag-99?filter=active#logs` → `/admin/agents/ag-99?filter=active#logs`
    - `/cards/123456789` → `/admin/cards/123456789`
    - `/audit?limit=25` → `/admin/audit?limit=25`
    - `/content#news` → `/admin/content#news`

### 2.4. Корректировка формулировок на лендинге
- В [`admin/src/pages/LandingPage.tsx`](file:///Users/nuras/Desktop/cashback-one/admin/src/pages/LandingPage.tsx):
  - Обещание «чеки становятся видны в приложении» заменено на «новый баланс и операции отображаются в приложении покупателя».
  - «Мониторинг синхронизации и статусов карт в реальном времени» заменено на «просмотр статусов синхронизации и карт в личном кабинете».
  - «Пробитие чека и применение карты» заменено на «Сканирование карты и проведение покупки».

### 2.5. Пересъёмка мобильного скриншота первого экрана
- С помощью Chrome DevTools MCP выполнена эмуляция мобильного экрана 390×844 (scale 3, touch/mobile).
- Перед снимком принудительно вызван `window.scrollTo(0, 0)` с проверкой `scrollY === 0`.
- Скриншот первого экрана успешно перезаписан: [`reports/landing-preview/landing-390-hero.png`](file:///Users/nuras/Desktop/cashback-one/reports/landing-preview/landing-390-hero.png) (409 922 байт).

---

## 3. Юридические страницы (`/privacy`, `/terms`)

Тексты в [`admin/src/pages/LegalPages.tsx`](file:///Users/nuras/Desktop/cashback-one/admin/src/pages/LegalPages.tsx) полностью приведены в соответствие со схемой [`backend/app/schemas/customer_app.py`](file:///Users/nuras/Desktop/cashback-one/backend/app/schemas/customer_app.py) и фактической логикой системы:

1. **Категории обрабатываемых данных**:
   - Чётко разделены **обязательные данные**:
     - Номер телефона покупателя (аутентификация через WhatsApp OTP);
     - Язык интерфейса (`ru`/`kz`);
     - Номер карты лояльности (штрихкод от 6 до 15 цифр);
     - Баланс бонусов и статусы (`is_blocked`, `hidden_at`);
     - Движения и операции лояльности (зеркалируемые из POSCENTER ONE).
   - и **дополнительные поля профиля** (заполняемые добровольно в мобильном приложении):
     - Имя (`first_name`) и фамилия (`last_name`);
     - E-mail (`email`);
     - Пол (`gender`) и дата рождения (`birth_date`);
     - ИИН Республики Казахстан (12 цифр с проверкой mod-11);
     - Город (`city`), адрес (`address`) и компания (`company`).

2. **Безопасность сетевых каналов**:
   - Устранено неверное утверждение о том, что все каналы (включая кассу и 1С) используют HTTPS.
   - Зафиксировано: внешний обмен мобильного приложения, веб-кабинета и агента с облачным бэкендом защищён HTTPS/TLS. Локальный обмен в магазине (POSCENTER Cash — 1С POSCENTER ONE — служба синхронизации) протекает в изолированном локальном контуре магазина, где агент обращается к ONE строго в режиме `read-only`.

3. **Файлы cookie и баннер**:
   - Указано, что публичные страницы не используют трекеры. Cookie используются только для сессий в `/admin/*`.
   - Отмечено, что необходимость баннера согласия зависит от законодательства применимой юрисдикции и хостинга и подлежит правовой оценке владельцем.

4. **Скрытие карты лояльности**:
   - Явно разъяснено, что действие «скрыть карту» в мобильном приложении — это визуальная настройка отображения в интерфейсе покупателя, которая не удаляет карту из базы магазина и не отвязывает её на сервере. Отвязка или прекращение участия производятся через торговую сеть.

5. **Пароли доступа менеджеров**:
   - Уточнено, что однократным является показ реквизитов администратору (`one_time: true`), а сам пароль сохраняется в виде криптографического хеша и остаётся действующим для входа до его смены или блокировки.

6. **Проектный статус документов**:
   - Документы помечены как предварительные проекты. Указано, что полные реквизиты оператора, контактные данные и индивидуальные правила возврата товаров утверждаются владельцем сервиса перед открытием публичного доступа.
