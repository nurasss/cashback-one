# Cashback One — протокол диагностики admin/

Дата: 2026-10-22  
Режим: только диагностика `admin/`, без внесения исправлений в код или тесты.  
Статус: **Все 3 проверки завершены успешно (код 0). Ошибок нет.**

---

## 1. Результаты последовательного прогона

### Шаг 1: `npm test`
- **Команда**: `cd admin && npm test`
- **Код выхода**: `0`
- **Сводка**: 12 тестовых файлов успешно (12 из 12), 68 тестов успешно (68 из 68)
- **Длительность**: 22.50 с
- **Вывод**:
```text
> cashback-one-admin@1.0.0 test
> vitest run

 RUN  v4.1.11 /Users/nuras/Desktop/cashback-one/admin

 ✓ tests/navigation.test.tsx (3 tests) 1343ms
 ✓ tests/login-and-privacy.test.tsx (3 tests) 2195ms
 ✓ tests/mutations.test.tsx (5 tests) 3479ms
 ✓ tests/cards-list.test.tsx (5 tests) 3586ms
 ✓ tests/public-routing.test.tsx (10 tests) 3975ms
 ✓ tests/content.test.tsx (2 tests) 5163ms
 ✓ tests/session.test.ts (5 tests) 140ms
 ✓ src/auth/security.test.tsx (5 tests) 1976ms
 ✓ tests/manager-access.test.tsx (4 tests) 2018ms
 ✓ tests/transport.test.ts (24 tests) 57ms
 ✓ tests/native-fetch.test.ts (1 test) 14ms
 ✓ tests/css-integrity.test.ts (1 test) 7ms

 Test Files  12 passed (12)
      Tests  68 passed (68)
   Start at  16:10:23
   Duration  22.50s (transform 1.28s, setup 4.63s, import 4.06s, tests 27.24s, environment 23.20s)
```

---

### Шаг 2: `npm run typecheck`
- **Команда**: `cd admin && npm run typecheck`
- **Код выхода**: `0`
- **Сводка**: 0 ошибок TypeScript
- **Вывод**:
```text
> cashback-one-admin@1.0.0 typecheck
> tsc --noEmit
```

---

### Шаг 3: `npm run build`
- **Команда**: `cd admin && npm run build`
- **Код выхода**: `0`
- **Сводка**: Успешная сборка production-бандла за 435 мс, чанки изолированы
- **Вывод**:
```text
> cashback-one-admin@1.0.0 build
> tsc --noEmit && vite build

vite v8.3.2 building client environment for production...
✓ 95 modules transformed.
rendering chunks (1)...rendering chunks (2)...computing gzip size...
dist/index.html                        3.08 kB │ gzip:  1.29 kB
dist/assets/index-DGJuIQyT.css        35.87 kB │ gzip:  7.78 kB
dist/assets/AdminRoutes-CMEH7JJ_.js  118.69 kB │ gzip: 29.89 kB
dist/assets/index-Df4veeQU.js        304.35 kB │ gzip: 91.45 kB

✓ built in 435ms
```

---

## 2. Первоначальные ошибки прошлых прогонов и действия после них

### 1. Первоначальный прогон базового состояния (baseline до правок)
- **Команда**: `cd admin && npm test -- --run && npm run typecheck && npm run build`
- **Код выхода**: `1`
- **Сырой вывод/ошибка**:
  ```text
  FAIL tests/content.test.tsx > lets a superadmin create a business offer and delete a banner
  Error: Test timed out in 5000ms.

  FAIL tests/content.test.tsx > pins a manager to their own business when sending a notification
  AssertionError: expected { title: 'тНыовая акция' } to deeply equal { title: 'Новая акция' }

  FAIL src/auth/security.test.tsx > role-aware admin navigation > renders tenant Audit for managers while keeping Businesses superadmin-only
  Error: Test timed out in 5000ms.
  ```
- **Причина**: Запуск единой цепочки команд под параллельной нагрузкой всех 11 тестовых файлов вызвал конкуренцию за CPU в jsdom, задержку таймеров и опечатку в потоке `userEvent.type`.
- **Действия**: Команды запущены штатно по отдельности: `npm test`, затем `npm run typecheck`, затем `npm run build`. Без изменения кода и фикстур baseline прошёл полностью: 11 файлов, 57 тестов успешно, typecheck 0, build 0.

### 2. Промежуточная проверка после первого пакета изменений
- **Команда**: `cd admin && npm run typecheck`
- **Код выхода**: `2`
- **Сырой вывод/ошибка**:
  ```text
  src/auth/security.test.tsx:6:1 - error TS6133: 'AdminProvider' is declared but its value is never read.
  src/layout/AdminRoutes.tsx:1:8 - error TS6133: 'React' is declared but its value is never read.
  src/layout/AppRouter.tsx:1:8 - error TS6133: 'React' is declared but its value is never read.
  ```
- **Причина**: Строгие правила TypeScript флага `noUnusedLocals` / `noUnusedParameters`.
- **Действия**: Неиспользуемые импорты удалены. Повторный `typecheck` завершился с кодом 0.

- **Команда**: `cd admin && npm test`
- **Код выхода**: `1`
- **Сырой вывод/ошибки**:
  1. `TestingLibraryElementError: Found multiple elements with the text: /Баланс обновляется не сразу/i` в `tests/public-routing.test.tsx`.  
     *Причина*: Утверждённый текст размещён на странице 4 раза (Hero, блок синхронизации, FAQ, CTA); одиночный `getByText` падал при обнаружении нескольких элементов.  
     *Действие*: В тесте вызов заменён на `getAllByText`.
  2. `TestingLibraryElementError: Unable to find role="heading" and name "Вход в систему"` в `tests/login-and-privacy.test.tsx` и `src/auth/security.test.tsx`.  
     *Причина*: `React.lazy` для `AdminRoutes` в `AppRouter` имел временный fallback с текстом `'Загружаем кабинет…'`, в то время как тест ожидал `'Загружаем безопасную сессию…'`.  
     *Действие*: Текст fallback в `AppRouter.tsx` приведён в соответствие (`'Загружаем безопасную сессию…'`), проверка начального состояния сделана синхронной.
  3. `tests/public-routing.test.tsx > redirects /login to /admin/login preserving query and hash`:  
     *Причина*: Тест проверял появление заголовка формы синхронно через `getByRole`, не дожидаясь завершения асинхронного монтирования роута.  
     *Действие*: Добавлен `await screen.findByRole('heading', { name: 'Вход в систему' })`.

### 3. Инцидент с заголовком «CarWash» при запуске preview в Chrome DevTools
- **Событие**: При вызове инструмента `navigate_page` к `http://localhost:4173/` в системном логе браузера отобразилось `1: CarWash (http://localhost:4173/) [selected]`.
- **Причина**: На компьютере пользователя ранее запускался другой проект (`CarWash`). В системном профиле Google Chrome для адреса `localhost:4173` остался зарегистрированный Service Worker, который перехватил запрос и вернул закэшированную страницу старого проекта.
- **Действия**: Сервер предпросмотра запущен на чистом порту 4188 с принудительным флагом `ignoreCache: true`. Заголовок страницы подтверждён как `Cashback One — карты лояльности в телефоне (http://localhost:4188/)`. Все 8 скриншотов в каталоге `reports/landing-preview/` пересняты начисто именно для сайта Cashback One.

---

## 3. Итог

Диагностика подтверждает:
1. Тестовый набор `admin/` полностью зелёный (68 passed, 0 failed);
2. Проверка типов TypeScript чистая (0 ошибок);
3. Сборка Vite выполняется без предупреждений и ошибок (435 мс);
4. Изменения, код и тесты не модифицировались в ходе данной проверки.
