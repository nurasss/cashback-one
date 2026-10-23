# Компактный интерфейс кабинета — 2026-10-23

## Итог: СТОП на baseline до правок

Прочитаны целиком `docs/PROMPT_ADMIN_UI_COMPACT_2026-10-23.md`, `CLAUDE.md` и `docs/HANDOFF_2026-10-21.md`.

Baseline не соответствует обязательному результату **110 passed / 17 файлов**: в полученном выводе есть падение теста, затем инструмент остановил ожидание команды по тайм-ауту 120000 мс. Полного результата Vitest нет. Согласно правилу «Упало или неожиданно — СТОП» повторный запуск, исправления и дальнейшие проверки не выполнялись.

## Изменения по файлам

- Создан только этот отчёт: `reports/ADMIN_UI_COMPACT_2026-10-23.md`.
- Исходники, словари, CSS, зависимости и тесты не изменялись.
- Существующие тесты и фикстуры не изменялись, включая `admin/src/test/setup.ts`.
- Деплой, commit/push и обращения к production не выполнялись.
- Уже существовавшие неотслеживаемые `C:/` и файл промпта не изменялись.

## Сырые выводы проверок

### Baseline

Рабочий каталог: `/Users/nuras/Desktop/cashback-one/admin`.

Команда: `npm test -- --maxWorkers=1`.

Тайм-аут инструмента: 120000 мс. **Код выхода процесса инструмент не вернул**; это не успешное завершение и не полный прогон. Ниже полный полученный текст ответа инструмента, без восстановления отсутствующего вывода:

```text

> cashback-one-admin@1.0.0 test
> vitest run --maxWorkers=1


 RUN  v4.1.11 /Users/nuras/Desktop/cashback-one/admin

(node:58865) Warning: `--localstorage-file` was provided without a valid path
(Use `node --trace-warnings ...` to show where the warning was created)
(node:58868) Warning: `--localstorage-file` was provided without a valid path
(Use `node --trace-warnings ...` to show where the warning was created)
(node:58870) Warning: `--localstorage-file` was provided without a valid path
(Use `node --trace-warnings ...` to show where the warning was created)
(node:58874) Warning: `--localstorage-file` was provided without a valid path
(Use `node --trace-warnings ...` to show where the warning was created)
(node:58876) Warning: `--localstorage-file` was provided without a valid path
(Use `node --trace-warnings ...` to show where the warning was created)
(node:58878) Warning: `--localstorage-file` was provided without a valid path
(Use `node --trace-warnings ...` to show where the warning was created)
(node:58884) Warning: `--localstorage-file` was provided without a valid path
(Use `node --trace-warnings ...` to show where the warning was created)
(node:58902) Warning: `--localstorage-file` was provided without a valid path
(Use `node --trace-warnings ...` to show where the warning was created)
(node:58908) Warning: `--localstorage-file` was provided without a valid path
(Use `node --trace-warnings ...` to show where the warning was created)
 ❯ tests/login-and-privacy.test.tsx (3 tests | 1 failed) 9525ms
   × keeps Login behind cookie bootstrap and then renders its labelled form 5198ms
(node:58946) Warning: `--localstorage-file` was provided without a valid path
(Use `node --trace-warnings ...` to show where the warning was created)


Command exceeded timeout of 120000 ms. Retry with a larger timeout if the command is expected to take longer.Timed out before completion
```

### Исходный git status

Рабочий каталог: `/Users/nuras/Desktop/cashback-one`.

Команда: `git status --short`. Код выхода: 0.

```text
?? C:/
?? docs/PROMPT_ADMIN_UI_COMPACT_2026-10-23.md
```

Дополнительно инструментом glob проверено наличие вложенных инструкций `**/AGENTS.md` в `admin/`: `No files found`. Это не shell-команда, код выхода неприменим.

## Не проверено / не выполнено

- Полный baseline и причина падения теста: стек ошибки не получен до тайм-аута; диагностика и повторный прогон не предпринимались.
- Компактные таблицы, общая логика раскрытия, пагинация, сохранение состояния при поиске и фильтрации, доступность.
- Удаление надзаголовков PageHeading и ключей RU/KK.
- Строчное написание бренда в кабинете и на входе.
- Новые тесты: не добавлялись; существующие тесты не обновлялись.
- Typecheck, lint, итоговые тесты, production build и сравнение размера `index-*.js`.
- Браузерный стенд: не создавался, API не подменялся, браузерная приёмка не проводилась.
- Снимки RU/KK на 1366/320 px и замеры `getBoundingClientRect().right`: не выполнены. Папка скриншотов не создавалась, изображений нет.

Продолжение реализации требует отдельного разрешения после этого СТОП; задача не объявляется выполненной.

## Финальное состояние Git

Рабочий каталог обеих команд: `/Users/nuras/Desktop/cashback-one`.

Команда: `git status --short`. Код выхода: 0.

```text
?? C:/
?? docs/PROMPT_ADMIN_UI_COMPACT_2026-10-23.md
?? reports/ADMIN_UI_COMPACT_2026-10-23.md
```

Команда: `git diff --stat`. Код выхода: 0. Вывод пустой (инструмент отображает его как `(no output)`): неотслеживаемые файлы в diff не включаются.

## Продолжение после СТОП

Обновлённый `docs/PROMPT_ADMIN_UI_COMPACT_2026-10-23.md` прочитан целиком (89 строк). Разрешение на продолжение учтено; раздел первой остановки выше оставлен как историческая запись. Новые результаты ниже отменяют прежний статус «baseline не пройден», но не означают завершения реализации.

### Нагрузка перед baseline

Рабочий каталог: `/Users/nuras/Desktop/cashback-one/admin`.

Команда: `uptime`. Код выхода: 0.

```text
14:45  up 1 day,  5:13, 1 user, load averages: 2.43 3.31 9.34
```

Нагрузка за минуту 2.43 ≤ 8, ожидание не требовалось.

Команда: `git status --short`, из `admin/`. Код выхода: 0.

```text
?? ../C:/
?? ../docs/PROMPT_ADMIN_UI_COMPACT_2026-10-23.md
?? ../reports/ADMIN_UI_COMPACT_2026-10-23.md
```

### Повторный baseline по новому разрешению

Команда: `npm test -- --maxWorkers=1`, из `admin/`. Тайм-аут инструмента **360000 мс**. Запущена через Python subprocess с объединением stdout/stderr и сохранением вывода в `/private/var/folders/ws/2yz96w190q34htgtvflq4bm00000gn/T/opencode/admin-compact-baseline.log`. Код выхода npm: **0** (также код выхода обёртки: 0). Сырой вывод:

```text

> cashback-one-admin@1.0.0 test
> vitest run --maxWorkers=1


 RUN  v4.1.11 /Users/nuras/Desktop/cashback-one/admin

(node:60449) Warning: `--localstorage-file` was provided without a valid path
(Use `node --trace-warnings ...` to show where the warning was created)
(node:60450) Warning: `--localstorage-file` was provided without a valid path
(Use `node --trace-warnings ...` to show where the warning was created)
(node:60464) Warning: `--localstorage-file` was provided without a valid path
(Use `node --trace-warnings ...` to show where the warning was created)
(node:60466) Warning: `--localstorage-file` was provided without a valid path
(Use `node --trace-warnings ...` to show where the warning was created)
(node:60468) Warning: `--localstorage-file` was provided without a valid path
(Use `node --trace-warnings ...` to show where the warning was created)
(node:60469) Warning: `--localstorage-file` was provided without a valid path
(Use `node --trace-warnings ...` to show where the warning was created)
(node:60472) Warning: `--localstorage-file` was provided without a valid path
(Use `node --trace-warnings ...` to show where the warning was created)
(node:60474) Warning: `--localstorage-file` was provided without a valid path
(Use `node --trace-warnings ...` to show where the warning was created)
(node:60476) Warning: `--localstorage-file` was provided without a valid path
(Use `node --trace-warnings ...` to show where the warning was created)
(node:60478) Warning: `--localstorage-file` was provided without a valid path
(Use `node --trace-warnings ...` to show where the warning was created)
(node:60479) Warning: `--localstorage-file` was provided without a valid path
(Use `node --trace-warnings ...` to show where the warning was created)
(node:60482) Warning: `--localstorage-file` was provided without a valid path
(Use `node --trace-warnings ...` to show where the warning was created)
(node:60484) Warning: `--localstorage-file` was provided without a valid path
(Use `node --trace-warnings ...` to show where the warning was created)
(node:60485) Warning: `--localstorage-file` was provided without a valid path
(Use `node --trace-warnings ...` to show where the warning was created)
(node:60486) Warning: `--localstorage-file` was provided without a valid path
(Use `node --trace-warnings ...` to show where the warning was created)
(node:60512) Warning: `--localstorage-file` was provided without a valid path
(Use `node --trace-warnings ...` to show where the warning was created)
(node:60523) Warning: `--localstorage-file` was provided without a valid path
(Use `node --trace-warnings ...` to show where the warning was created)

 Test Files  17 passed (17)
      Tests  110 passed (110)
   Start at  14:45:26
   Duration  48.12s (transform 971ms, setup 3.93s, import 3.29s, tests 15.33s, environment 20.50s)

EXIT_CODE=0
```

Повтор отдельного файла не потребовался. Тест входа, его тайм-ауты и `src/test/setup.ts` не изменялись.

### Новое неожиданное расхождение: пагинация ручной таблицы

**СТОП до изменений исходников.** В п. 1 промпта (строка 31) сказано, что у таблицы карт пользователя нет пагинации и нужны только «3 строки и Показать все / Свернуть». Фактический код `admin/src/pages/OperationsPage.tsx` уже содержит пагинацию: строки 563–583. Вот неизменённый фрагмент из чтения файла (префиксы номеров строк добавлены инструментом):

```text
563:         {user.cards.items.length > 0 && (
564:           <div className="pagination">
565:             <span>{t.operations.userCardsPaged}</span>
566:             <div className="pagination-actions">
567:               <button
568:                 className="button button-secondary"
569:                 disabled={page.offset === 0}
570:                 onClick={() => setPage(Math.max(0, page.offset - page.limit))}
571:               >
572:                 {t.feedback.prevPage}
573:               </button>
574:               <button
575:                 className="button button-secondary"
576:                 disabled={!user.cards.has_more}
577:                 onClick={() => setPage(page.offset + page.limit)}
578:               >
579:                 {t.feedback.nextPage}
580:               </button>
581:             </div>
582:           </div>
583:         )}
```

В этом же компоненте строка 494: `const query = useUser(userId, businessId, page);`. Поэтому удалить пагинацию — значит убрать существующий путь к следующим страницам карт. Сохранить её без уточнения — отойти от прямого требования «только … Показать все / Свернуть» для этой таблицы. При обязательном СТОП на неожиданностях решение самостоятельно не принималось.

**Предлагаемое уточнение владельцу:** сохранить существующую пагинацию карт пользователя; при >3 строк показывать её только после раскрытия, при ≤3 — оставить прежнее поведение. Серверные параметры и запросы не менять. Это предложение, не выполненная правка.

### Изменения и непроверенное в продолжении

- Дополнен только `reports/ADMIN_UI_COMPACT_2026-10-23.md`, предыдущий раздел не перезаписан.
- Изменений исходников и существующих тестов нет. Новые тесты не добавлялись.
- Новый baseline принят: 110 passed / 17 файлов. Причина первого падения самостоятельно не диагностировалась; объяснение нагрузки дано куратором в обновлённом промпте.
- Реализация всех трёх пунктов, новые тесты, typecheck/lint, итоговый прогон, build и сравнение JS, браузерный стенд/снимки/геометрия остаются **не выполнены / не проверены** из-за нового СТОП.
- Стенд не создавался; подмен API, production-запросов, деплоя, commit/push не было.
- Context7-инструмент искался по инструкции навыка, но в доступном каталоге отсутствует (поиск вернул `items: []`); обращения к нему не выполнялись. На результат baseline это не влияет.

### Финальные проверки Git после продолжения

Из `admin/`: `git status --short`, код выхода 0:

```text
?? ../C:/
?? ../docs/PROMPT_ADMIN_UI_COMPACT_2026-10-23.md
?? ../reports/ADMIN_UI_COMPACT_2026-10-23.md
```

Из `admin/`: `git diff --stat`, код выхода 0, вывод пустой (`(no output)` в ответе инструмента). Отчёт неотслеживаемый и в diff не входит.

## Продолжение после уточнения пагинации

Владелец подтвердил сохранение существующей пагинации карт пользователя, её скрытие при свёрнутой таблице с >3 строками и сохранение раскрытия при листании. Обновлённый промпт прочитан целиком (91 строка). Baseline по прямому указанию **не повторялся**, принят предыдущий результат 110 passed / 17 файлов. Предыдущие остановки выше сохранены как история.

### Внесённые изменения по файлам

- `admin/src/components/CompactTable.tsx` (новый): общие `useTableExpansion`, `useCompactRows`, `CompactTableToggle`; порог 3 строки, память React-компонента, общий RU/KK-контрол с `aria-expanded` и `aria-controls`.
- `admin/src/components/DataTable.tsx`: использует общую логику; 3 строки по умолчанию, раскрытие текущей страницы, скрытая пагинация при >3 строках в свёрнутом состоянии. При ≤3 строках прежняя пагинация сохранена. Поддерживает необязательное состояние раскрытия родителя.
- `admin/src/pages/OperationsPage.tsx`: общая логика применена к ручной таблице карт пользователя, её существующая пагинация сохранена. Состояния результатов карт и клиентов размещены в компоненте страницы, чтобы переживать временный демонтаж таблицы при запросах, переход списка в поиск и обратно.
- `admin/src/pages/BusinessesPage.tsx`, `AgentsPage.tsx`, `AuditPage.tsx`, `ContentPage.tsx`: добавлены только подключение общего состояния и передача его в DataTable; это необходимо, поскольку при `query.isPending` таблица демонтируется. В Content отдельное состояние каждой таблицы живёт в её родительском компоненте. Логика ограничения строк не копируется. Запросы и серверная пагинация не изменены.
- `admin/src/components/Feedback.tsx`: удалены проп `eyebrow` и его span из PageHeading.
- `admin/src/pages/BusinessesPage.tsx`, `AgentsPage.tsx`, `AuditPage.tsx`, `ContentPage.tsx`, `DashboardPage.tsx`, `OperationsPage.tsx`: удалены все 10 передач `eyebrow` в PageHeading, включая детали.
- `admin/src/i18n/admin.ts`: удалены 10 ключей надзаголовков в каждом словаре; добавлены `feedback.showAllRows` и `feedback.collapseRows` в RU/KK. Надзаголовки входа сохранены.
- `admin/src/layout/AdminLayout.tsx`, `admin/src/pages/LoginPage.tsx`: только текст рядом с P заменён на `poscenter.kz`; alt и подписи сохранены.
- `admin/src/styles/admin.css`: убран верхний margin 6 px у `.page-heading h1`; добавлены полноширинная `.table-toggle` и внутренний отступ фокусного контура, чтобы он не обрезался `.table-card { overflow: hidden }`. Правила `.eyebrow` не изменены. У прочитанных правил бренда и родителей не обнаружено uppercase-преобразования; отключение text-transform не добавлялось.

Это описание внесённого кода, **не доказательство его работоспособности**: после правок проверки ещё не выполнены из-за следующего СТОП.

### Изменённые существующие тесты

Только `admin/tests/cards-list.test.tsx`:

1. `immediately renders first page of all cards without requiring search input`: перед прежней проверкой 25-й карты добавлена проверка её отсутствия в свёрнутом состоянии и нажатие «Показать все (25)». Проверки ведущих нулей, всех колонок и пагинации сохранены.
2. `navigates next and previous pages properly with has_more handling`: перед доступом к «Далее» добавлено раскрытие таблицы. Наборы данных, ответы API и проверки листания не менялись.

Фикстуры прежних тестов, тест входа, его тайм-ауты и `src/test/setup.ts` **не изменялись**.

### Добавленные тесты (пока не запущены)

- `admin/tests/compact-table.test.tsx`: 25 → 3 → 25 → 3; отсутствие пагинации в свёрнутом состоянии; 1/2/3 строки; пустое состояние; aria-связь с tbody и переключение expanded; листание; изменение N и сохранение состояния; сброс после remount; KK-подписи.
- `admin/tests/compact-admin.test.tsx`: настоящий AppRouter/AdminProvider с подменой fetch на обезличенные ответы; отсутствие `.page-heading .eyebrow` и наличие h1 на всех 10 страницах × RU/KK; строчный бренд и сохранность надзаголовков входа; ручная таблица пользователя × RU/KK с листанием и сворачиванием; ≤3 строки; сохранение раскрытия при поиске/фильтре и сброс при смене раздела.

### Сборка ДО правок — база сравнения JS

Из `admin/`: `VITE_API_BASE_URL=https://api.cashback-qr.poscenter.kz VITE_ALLOW_INSECURE_HTTP=0 npm run build`. Запуск через Python subprocess с передачей этих переменных окружения, сохранением stdout/stderr в `/private/var/folders/ws/2yz96w190q34htgtvflq4bm00000gn/T/opencode/admin-compact-build-before.log` и выводом размера файла после успешной сборки. Тайм-аут инструмента 360000 мс. Код выхода **0**.

```text

> cashback-one-admin@1.0.0 build
> tsc --noEmit && vite build

vite v8.3.2 building client environment for production...
transforming...
✓ 112 modules transformed.
rendering chunks...
computing gzip size...
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
dist/assets/index-DnmPXAC2.css                              40.94 kB │ gzip:  8.76 kB
dist/assets/AdminRoutes-CmohQRGo.js                        164.50 kB │ gzip: 41.31 kB
dist/assets/index-CXKGYXHj.js                              305.60 kB │ gzip: 94.42 kB

✓ built in 684ms

dist/assets/index-CXKGYXHj.js 305601 bytes
EXIT_CODE=0
```

### Новый СТОП: браузер недоступен

При подготовке браузерной проверки вызван `chrome-devtools.list_pages` через execute. Сырой ответ:

```text
Could not connect to Chrome. Check if Chrome is running and remote debugging is enabled by going to chrome://inspect/#remote-debugging.
Cause: Could not find DevToolsActivePort for chrome at /Users/nuras/Library/Application Support/Google/Chrome/DevToolsActivePort
Cause:
```

Это MCP-вызов, не shell-команда; код выхода неприменим. По правилу «Упало или неожиданно — СТОП» Chrome не перенастраивался, альтернативный браузер не запускался, повторных подключений и дальнейших изменений исходников не было. Стенд не создан, API для браузера не подменялся, снимков и измерений нет. Успешную браузерную приёмку не заявляю.

В ходе чтения структуры также получен ответ инструмента read на отсутствующий `admin/src/AdminApp.tsx`: `File not found: /Users/nuras/Desktop/cashback-one/admin/src/AdminApp.tsx`. Это ошибочно предположенный путь при навигации по исходникам; настоящий маршрутизатор найден и прочитан по `admin/src/layout/AdminRoutes.tsx`. Никакой файл по ошибочному пути не создавался.

### Не проверено после внесённых правок

- Typecheck, lint, новые и существующие тесты, итоговая production build.
- Сравнение размера JS после правок: пока известен только размер ДО — **305601 байт**. Рост ≤1 кБ не подтверждён.
- Реальная вёрстка/фокус/геометрия и computed text-transform в браузере; RU/KK, 1366/320 px; снимки и замеры правых границ.
- Интеграция с настоящим backend и настоящий авторизованный вход (не проводились).

Исходники находятся в состоянии **«изменено, но ещё не проверено»**. Деплоя, commit/push и изменений backend/mobile/лендинга/секретных конфигов не было. Для продолжения потребуется разрешение после этого СТОП и доступный браузер либо согласованный способ браузерной проверки.

### Финальные проверки чтением Git

Все три команды из `admin/`.

`git status --short`, код выхода **0**:

```text
 M src/components/DataTable.tsx
 M src/components/Feedback.tsx
 M src/i18n/admin.ts
 M src/layout/AdminLayout.tsx
 M src/pages/AgentsPage.tsx
 M src/pages/AuditPage.tsx
 M src/pages/BusinessesPage.tsx
 M src/pages/ContentPage.tsx
 M src/pages/DashboardPage.tsx
 M src/pages/LoginPage.tsx
 M src/pages/OperationsPage.tsx
 M src/styles/admin.css
 M tests/cards-list.test.tsx
?? ../C:/
?? src/components/CompactTable.tsx
?? tests/compact-admin.test.tsx
?? tests/compact-table.test.tsx
?? ../docs/PROMPT_ADMIN_UI_COMPACT_2026-10-23.md
?? ../reports/ADMIN_UI_COMPACT_2026-10-23.md
```

`git diff --stat`, код выхода **0**:

```text
 admin/src/components/DataTable.tsx | 11 ++++++++---
 admin/src/components/Feedback.tsx  |  3 ---
 admin/src/i18n/admin.ts            | 24 ++++--------------------
 admin/src/layout/AdminLayout.tsx   |  2 +-
 admin/src/pages/AgentsPage.tsx     |  5 +++--
 admin/src/pages/AuditPage.tsx      |  4 +++-
 admin/src/pages/BusinessesPage.tsx |  5 +++--
 admin/src/pages/ContentPage.tsx    |  6 +++++-
 admin/src/pages/DashboardPage.tsx  |  2 +-
 admin/src/pages/LoginPage.tsx      |  2 +-
 admin/src/pages/OperationsPage.tsx | 23 +++++++++++++++++------
 admin/src/styles/admin.css         | 13 ++++++++++++-
 admin/tests/cards-list.test.tsx    |  4 ++++
 13 files changed, 62 insertions(+), 42 deletions(-)
```

Неотслеживаемые файлы в stat не включены.

`git diff --check`, код выхода **0**, вывод пустой (`(no output)` в ответе инструмента).

## Приёмка куратора и публикация — 2026-10-23

**Независимая проверка.** `npm run typecheck`, `npm run lint` — exit 0. `npm test -- --maxWorkers=1` — **144 passed / 19 файлов** (load average около 5). Production build: `index-DYD8ytrr.js` лендинга 305.54 kB, не вырос. Остатков `.page-heading .eyebrow` и `POSCENTER.KZ` рядом с логотипом нет. На экране входа оставлены «ДОБРО ПОЖАЛОВАТЬ» и «ADMIN CONSOLE»: они не входили в задачу.

**Браузер (встроенный браузер куратора).** Временный стенд: настоящие `main.tsx`, `AppRouter`, `AdminLayout`, стили и Roboto; подменён только `fetch` к фиктивному API на 25 обезличенных карт. После проверки стенд удалён.
- RU, 1366 px: «Карты и клиенты» показывает 3 строки и «Показать все (25)», пагинации нет. После нажатия 25 строк, пагинация, «Свернуть», `aria-expanded=true`. «Далее» загружает следующую страницу (первая карта 100025), таблица остаётся развёрнутой.
- KK, 320 px: «Барлығын көрсету (25)», границы кнопки x=15…305, таблицы x=14…306. Заголовок «Карталар мен клиенттер» без надзаголовка, бренд `poscenter.kz`.

**Публикация.** Копия: `~/.local/share/cashback-one/backups/landing-20261023T095854Z-9a9e5d/` (прежний index `9ce76cb3c2a1e7669012da2ce4cb6298d96f679d8cbcf1fe12f4edf861a7833b`). Загружены `AdminRoutes-Dwwq2dfH.js`, `index-DYD8ytrr.js`, `index-dz2Y9kFx.css` и `index.html` последним (`3747ed8df8786f730d7a7c1e1096e6eb1a454268571d8a9dc0086bedc9730dab`). Каждый файл загружался во временное имя, проверялся по SHA-256 и переименовывался. `.htaccess` не изменился. 39/39 файлов сверены по HTTPS. `/`, `/admin/login`, `/login`, `/demo/` — 200, APK 1.0.3 на месте. На живом входе бренд `poscenter.kz`, ошибок кроме ожидаемых 401 нет.

**Не проверено:** кабинет под настоящим администратором на production.

**Откат:** загрузить `index.html` из копии во временное имя, сверить `9ce76cb3…`, переименовать.
