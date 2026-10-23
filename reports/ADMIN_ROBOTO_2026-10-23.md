# Отчёт: подключение шрифта Roboto в админке — 2026-10-23

## 1. Что изменено, по файлам

1. `admin/package.json`:
   - Добавлена точная зависимость `"@fontsource/roboto": "5.3.0"` в секцию `dependencies`.
2. `admin/package-lock.json`:
   - Зафиксирована версия `@fontsource/roboto@5.3.0` с integrity-хешем и лицензией OFL-1.1.
3. `admin/src/layout/AdminRoutes.tsx`:
   - Добавлены точечные импорты начертаний и наборов Roboto:
     - `@fontsource/roboto/cyrillic-ext-400.css`, `cyrillic-400.css`, `latin-400.css`
     - `@fontsource/roboto/cyrillic-ext-500.css`, `cyrillic-500.css`, `latin-500.css`
     - `@fontsource/roboto/cyrillic-ext-600.css`, `cyrillic-600.css`, `latin-600.css`
     - `@fontsource/roboto/cyrillic-ext-700.css`, `cyrillic-700.css`, `latin-700.css`
   - Благодаря размещению в `AdminRoutes.tsx`, эти стили и шрифты компилируются исключительно в ленивый административный CSS-чанк `dist/assets/AdminRoutes-*.css`. Главный бандл лендинга (`index-*.js`, `index-*.css`) остаётся полностью чистым от шрифтов Roboto.
4. `admin/src/styles/admin.css`:
   - В селекторе `.admin-surface` заменён стек шрифтов с мертвого `Inter` на `Roboto`:
     ```css
     .admin-surface {
       font-family: Roboto, -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
       color: var(--ink);
       background: var(--surface-bg);
       min-height: 100vh;
     }
     ```
   - Правило `.admin-surface button, .admin-surface input, .admin-surface select, .admin-surface textarea { font: inherit; }` гарантирует наследование Roboto всеми элементами управления.
   - Моноширинные стеки (строки 829, 1386, 1407) сохранены без изменений.
   - Стили лендинга (`landing.css`), разметка `index.html` и все остальные стили не изменялись.

---

## 2. Версия пакета, начертания и наборы

- **Пакет:** `@fontsource/roboto@5.3.0` (OFL-1.1).
- **Подключенные наборы:** `latin`, `cyrillic`, `cyrillic-ext`.
  - Набор `cyrillic-ext` обеспечивает полную поддержку специфических казахских символов: `Ә Ғ Қ Ң Ө Ұ Ү Һ І`.
  - Лишние наборы (`greek`, `greek-ext`, `math`, `symbols`, `vietnamese`, `latin-ext`) исключены.
- **Подключенные начертания:**
  - `400` (normal): основной текст, инпуты, ссылки;
  - `500` (medium): метки, заголовки таблиц, второстепенные кнопки;
  - `600` (semi-bold): бейджи, заголовки карточек (в `admin.css` 16 использований `font-weight: 600`);
  - `700` (bold): основные заголовки страниц, кнопки действий (в `admin.css` 12 использований `font-weight: 700`).
- **Другие веса в `admin.css`:**
  - `font-weight: 300` (1 использование, `.context-divider` — разделитель контекста): браузер отображает через вес 400.
  - `font-weight: 650` (1 использование, `.numeric-value` — числовые показатели): браузер отображает через вес 700.
  - `font-weight: 800` (2 использования, логотип `.brand-mark` и иконка ошибки): отображается через вес 700.

---

## 3. Сырые выводы проверок

### 3.1. Свободное место на диске до начала работ

```
Filesystem    Size   Used  Avail Capacity iused     ifree %iused  Mounted on
/dev/disk3s1 460Gi  421Gi  2.9Gi    94% 3959146   4364000   48%   /System/Volumes/Data
```
Доступно 2.9 GiB (требование >= 1 GiB выполнено).

### 3.2. Baseline-тесты до правок

```
> cashback-one-admin@1.0.0 test
> vitest run --maxWorkers=1

 RUN  v4.1.11 /Users/nuras/Desktop/cashback-one/admin

 Test Files  16 passed (16)
      Tests  98 passed (98)
   Start at  11:03:50
   Duration  33.81s (transform 944ms, setup 3.32s, import 2.50s, tests 11.23s, environment 12.82s)
```

### 3.3. Проверка типов после правок (`npm run typecheck`)

```
> cashback-one-admin@1.0.0 typecheck
> tsc --noEmit
```
(Завершилось с кодом 0, ошибок нет).

### 3.4. Линтер после правок (`npm run lint`)

```
> cashback-one-admin@1.0.0 lint
> eslint .
```
(Завершилось с кодом 0, замечаний нет).

### 3.5. Тесты после правок (`npm test -- --maxWorkers=1`)

```
> cashback-one-admin@1.0.0 test
> vitest run --maxWorkers=1

 RUN  v4.1.11 /Users/nuras/Desktop/cashback-one/admin

 Test Files  16 passed (16)
      Tests  98 passed (98)
   Start at  11:13:19
   Duration  39.51s (transform 988ms, setup 3.42s, import 2.73s, tests 13.70s, environment 14.54s)
```
(Все 16 файлов и 98 тестов прошли успешно, код завершения 0).

### 3.6. Production-сборка

```
> cashback-one-admin@1.0.0 build
> tsc --noEmit && vite build

vite v8.3.2 building client environment for production...
transforming (51) src/api/transport.ts✓ 111 modules transformed.
rendering chunks (1)...rendering chunks (2)...computing gzip size...
dist/index.html                                              3.09 kB │ gzip:  1.29 kB
dist/assets/roboto-cyrillic-400-normal-BepgbcUK.woff        10.20 kB
dist/assets/roboto-cyrillic-600-normal-37yjrxaJ.woff        10.38 kB
dist/assets/roboto-cyrillic-500-normal-C8ZOEKN4.woff        10.39 kB
dist/assets/roboto-cyrillic-700-normal-D8g9KsRf.woff        10.39 kB
dist/assets/roboto-cyrillic-400-normal-CBPI_iaY.woff2       12.10 kB
dist/assets/roboto-cyrillic-600-normal-DIMkl7QA.woff2       12.28 kB
dist/assets/roboto-cyrillic-500-normal-CLao9AfR.woff2       12.35 kB
dist/assets/roboto-cyrillic-700-normal-C2o7G-SM.woff2       12.41 kB
dist/assets/roboto-cyrillic-ext-400-normal-DhDk0Xwi.woff    15.95 kB
dist/assets/roboto-cyrillic-ext-500-normal-SCgicl0l.woff    16.09 kB
dist/assets/roboto-cyrillic-ext-700-normal-BWOtdzfy.woff    16.09 kB
dist/assets/roboto-cyrillic-ext-600-normal-D1w7fEQ2.woff    16.12 kB
dist/assets/roboto-cyrillic-ext-400-normal-qHufge6k.woff2   17.37 kB
dist/assets/roboto-cyrillic-ext-500-normal-BWC_xYeb.woff2   17.59 kB
dist/assets/roboto-cyrillic-ext-700-normal-DmFxo5wj.woff2   17.62 kB
dist/assets/roboto-cyrillic-ext-600-normal-cho36S0w.woff2   17.62 kB
dist/assets/roboto-latin-400-normal-D27F5sTu.woff           21.06 kB
dist/assets/roboto-latin-500-normal-fsTFPL3E.woff           21.16 kB
dist/assets/roboto-latin-600-normal-X4S5XP0J.woff           21.20 kB
dist/assets/roboto-latin-700-normal-YuyVweIx.woff           21.21 kB
dist/assets/roboto-latin-400-normal-BqEyEoaF.woff2          21.88 kB
dist/assets/roboto-latin-500-normal-7RbcRiD8.woff2          22.20 kB
dist/assets/roboto-latin-600-normal-CzqH9ZEY.woff2          22.24 kB
dist/assets/roboto-latin-700-normal-BZpUvMxY.woff2          22.24 kB
dist/assets/AdminRoutes-CZzWuZob.css                         2.69 kB │ gzip:  0.44 kB
dist/assets/index-CK6mWq8J.css                              39.40 kB │ gzip:  8.51 kB
dist/assets/AdminRoutes-DXjwWHtc.js                        159.08 kB │ gzip: 39.77 kB
dist/assets/index-kVDMUDa7.js                              304.37 kB │ gzip: 94.05 kB

✓ built in 568ms
```

---

## 4. Анализ `dist/`

### 4.1. Список всех `*.woff2` файлов и их размеры

```
-rw-r--r--@ 1 nuras staff 12K Oct 23 11:14 admin/dist/assets/roboto-cyrillic-400-normal-CBPI_iaY.woff2
-rw-r--r--@ 1 nuras staff 12K Oct 23 11:14 admin/dist/assets/roboto-cyrillic-500-normal-CLao9AfR.woff2
-rw-r--r--@ 1 nuras staff 12K Oct 23 11:14 admin/dist/assets/roboto-cyrillic-600-normal-DIMkl7QA.woff2
-rw-r--r--@ 1 nuras staff 12K Oct 23 11:14 admin/dist/assets/roboto-cyrillic-700-normal-C2o7G-SM.woff2
-rw-r--r--@ 1 nuras staff 17K Oct 23 11:14 admin/dist/assets/roboto-cyrillic-ext-400-normal-qHufge6k.woff2
-rw-r--r--@ 1 nuras staff 17K Oct 23 11:14 admin/dist/assets/roboto-cyrillic-ext-500-normal-BWC_xYeb.woff2
-rw-r--r--@ 1 nuras staff 17K Oct 23 11:14 admin/dist/assets/roboto-cyrillic-ext-600-normal-cho36S0w.woff2
-rw-r--r--@ 1 nuras staff 17K Oct 23 11:14 admin/dist/assets/roboto-cyrillic-ext-700-normal-DmFxo5wj.woff2
-rw-r--r--@ 1 nuras staff 21K Oct 23 11:14 admin/dist/assets/roboto-latin-400-normal-BqEyEoaF.woff2
-rw-r--r--@ 1 nuras staff 22K Oct 23 11:14 admin/dist/assets/roboto-latin-500-normal-7RbcRiD8.woff2
-rw-r--r--@ 1 nuras staff 22K Oct 23 11:14 admin/dist/assets/roboto-latin-600-normal-CzqH9ZEY.woff2
-rw-r--r--@ 1 nuras staff 22K Oct 23 11:14 admin/dist/assets/roboto-latin-700-normal-BZpUvMxY.woff2
```

### 4.2. Из какого чанка ссылаются на шрифты

```bash
grep -rn "roboto-" admin/dist/
```
Вывод: шрифты подключены **только** в `admin/dist/assets/AdminRoutes-CZzWuZob.css:1`.
В главных бандлах `index-*.js` и `index-*.css` вхождений `roboto-` **нет** (`grep` вернул exit code 1).

### 4.3. Проверка на внешние CDN и Google Fonts

```bash
grep -rn "googleapis" admin/dist/ || echo "NO_GOOGLEAPIS"
grep -rn "gstatic" admin/dist/ || echo "NO_GSTATIC"
```
Вывод:
```
NO_GOOGLEAPIS
NO_GSTATIC
```
Никаких ссылок на `fonts.googleapis.com` или `fonts.gstatic.com` в сборке нет. Шрифты поставляются strictly self-hosted в соответствии с production CSP (`font-src 'self'`).

### 4.4. Сравнение размеров главных бандлов

| Файл | До подключения Roboto | После подключения Roboto | Разница |
|---|---|---|---|
| `dist/assets/index-*.js` | 305.62 kB (gzip 94.21 kB) | 304.37 kB (gzip 94.05 kB) | -1.25 kB (gzip -0.16 kB) |
| `dist/assets/index-*.css` | 39.14 kB (gzip 8.47 kB) | 39.40 kB (gzip 8.51 kB) | +0.26 kB (gzip +0.04 kB) |
| `dist/assets/AdminRoutes-*.js` | 159.08 kB (gzip 39.75 kB) | 159.08 kB (gzip 39.77 kB) | 0 kB (gzip +0.02 kB) |
| `dist/assets/AdminRoutes-*.css` | *отсутствовал* | 2.69 kB (gzip 0.44 kB) | +2.69 kB (новый ленивый чанк со стилями шрифта) |

Главный бандл лендинга `index-*.js` и `index-*.css` не получил ни байта шрифтов.

---

## 5. Браузерная верификация (`npm run preview`, Chrome DevTools)

### 5.1. Главная страница лендинга (`/`)
- **Шрифт `body`:** `"Times"` (дефолтный браузерный, перекрываемый внутри лендинга);
- **Шрифт заголовка Hero (`h1`):** `"-apple-system, \"system-ui\", \"Segoe UI\", Roboto, \"Helvetica Neue\", Arial, sans-serif"`;
- **Сетевые запросы на `/`:**
  - `GET /` [200]
  - `GET /assets/index-kVDMUDa7.js` [200]
  - `GET /assets/index-CK6mWq8J.css` [200]
  - `GET /brand-mark.png` [200]
  - `GET /landing/screen-home.png` [200]
  - `GET /logo-white.png` [200]
  - `GET /landing/screen-barcode.png` [200]
  - `GET /landing/screen-history.png` [200]
  - `GET /landing/screen-promotions.png` [200]
  - **Запросов к `AdminRoutes-*` и `*.woff2` / `*.woff` шрифтам Roboto: 0.**

### 5.2. Страница входа (`/admin/login`)
- **Computed `font-family` элементов входа:**
  - `.admin-surface`: `Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif`
  - `form`: `Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif`
  - `input`: `Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif`
  - `button[type="submit"]`: `Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif`
  - `h1`: `Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif`
- **Проверка готовности шрифта:** `document.fonts.check('16px Roboto')` === `true`.
- **Загруженные сетевые ресурсы:**
  - `GET /assets/roboto-latin-400-normal-BqEyEoaF.woff2` [200]
  - `GET /assets/roboto-cyrillic-400-normal-CBPI_iaY.woff2` [200]
  - `GET /assets/roboto-latin-600-normal-CzqH9ZEY.woff2` [200]
  - `GET /assets/roboto-latin-700-normal-BZpUvMxY.woff2` [200]
  - `GET /assets/roboto-cyrillic-600-normal-DIMkl7QA.woff2` [200]
  - `GET /assets/roboto-cyrillic-700-normal-C2o7G-SM.woff2` [200]
  - `GET /assets/roboto-cyrillic-ext-600-normal-cho36S0w.woff2` [200]
  Все шрифты отданы со своего origin (`http://localhost:4173/assets/`).

### 5.3. Казахский язык (ҚАЗ / `kk`)
- Переключение на ҚАЗ проверено в реальном браузере:
  - `document.documentElement.lang` = `"kk"`;
  - Заголовок: `Жүйеге кіру — Cashback One Admin`;
  - Заголовок истории: `Бизнестің барлық көрсеткіштері. Бір жүйеде.`;
  - Описание: `Бұлтты адалдық платформасында желі күйі, карталар мен операциялар деректері.`;
  - Кнопка: `Кіру →`.
- Казахские буквы (`Ә`, `Ғ`, `Қ`, `Ң`, `Ө`, `Ұ`, `Ү`, `Һ`, `І`) отображаются шрифтом Roboto без «тофу» (пустых прямоугольников) и без подмены системным шрифтом.

### 5.4. Адаптивность и вёрстка на 320 px
- Измерено через Chrome DevTools Emulation (viewport: `320x700x1,mobile,touch`):
  - `document.documentElement.scrollWidth`: 320 px;
  - `document.documentElement.clientWidth`: 320 px;
  - `hasHorizontalScroll`: `false`;
  - Элементов, выходящих за границы экрана (overflow): 0;
  - Поля ввода логина и пароля, а также кнопка входа полностью помещаются в пределах 320 px экрана.

---

## 6. Скриншоты

Скриншоты сохранены в `reports/screenshots/admin-roboto/`:
1. `reports/screenshots/admin-roboto/login-1366-ru.png` — форма входа на десктопе 1366 px (русский язык);
2. `reports/screenshots/admin-roboto/login-1366-kk.png` — форма входа на десктопе 1366 px (казахский язык);
3. `reports/screenshots/admin-roboto/login-320-ru.png` — форма входа на мобильном 320 px (русский язык, без горизонтального скролла);
4. `reports/screenshots/admin-roboto/login-320-kk.png` — форма входа на мобильном 320 px (казахский язык, без горизонтального скролла).

---

## 7. Что не проверено

1. **Вход внутрь закрытого кабинета (`/admin/*`) в реальном браузере:**
   - В соответствии с прямым указанием в промпте («Настоящий вход в кабинет не выполнять»), авторизация реальными учётными данными в production API не производилась.
   - Изолированных mock-серверов для браузерного preview в репозитории нет (все mock-тесты сосредоточены в Vitest/Node).
   - Внутренние компоненты кабинета (`DashboardPage`, `BusinessesPage`, `AgentsPage`, `OperationsPage`, `AuditPage`, `ContentPage`, `ManagerAccessDialog` и др.) проверены юнит- и интеграционными тестами (`npm test`, 98 passed), а также проверкой типов (`tsc --noEmit`, 0 ошибок) и линтером (`eslint`, 0 ошибок). Поскольку все страницы кабинета рендерятся внутри единого корневого контейнера `<div className="admin-surface">` компонента `AdminRoutes.tsx`, шрифт `Roboto` распространяется на них автоматически через CSS-наследование.

---

## 8. Итоговое состояние Git

```bash
git status --short
```
```
 M admin/package-lock.json
 M admin/package.json
 M admin/src/layout/AdminRoutes.tsx
 M admin/src/styles/admin.css
?? C:/
?? docs/PROMPT_GEMINI_ADMIN_ROBOTO_2026-10-23.md
?? reports/ADMIN_ROBOTO_2026-10-23.md
?? reports/screenshots/admin-roboto/
```

```bash
git diff --stat
```
```
 admin/package-lock.json          | 10 ++++++++++
 admin/package.json               |  1 +
 admin/src/layout/AdminRoutes.tsx | 12 ++++++++++++
 admin/src/styles/admin.css       |  2 +-
 4 files changed, 24 insertions(+), 1 deletion(-)
```
