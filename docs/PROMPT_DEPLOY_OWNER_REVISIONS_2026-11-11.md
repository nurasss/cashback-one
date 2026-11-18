# Gemini: правки кабинета владельца 11.11 — lint, показ владельцу, выкладка

Прочитать `AGENTS.md` (особенно §1.1), `CLAUDE.md`, `reports/ADMIN_OWNER_REVISIONS_2026-11-11.md`, `reports/ADMIN_OWNER_REVISIONS_REVIEW_2026-11-11.md`. За образец процедуры взять `docs/PROMPT_DEPLOY_FINAL_CABINET_0019_2026-11-10.md` и `reports/DEPLOY_FINAL_CABINET_0019_2026-11-10.md`.

Задача из двух этапов. **После этапа A — СТОП, ждать слова владельца.** К этапу B без его явного «выкладывай» не переходить.

**Упало или неожиданно — СТОП и сырой вывод; без самостоятельных исправлений и повторных мутаций; секреты и ПДн скрыть.** Секреты не печатать и не передавать в CLI, проверку TLS не отключать. Без APK, без изменения `version.json`/`keremet-version.json`/кнопки лендинга, без push и GitHub Releases. Изменения `mobile/` не трогать и не коммитить.

## Исходное состояние (проверено куратором 2026-11-11)

- Рабочее дерево после `23b4fd8`, правки admin/backend не закоммичены.
- Backend: 545 passed / 40 skipped. Один старый нестабильный тест `test_admin_mutations.py::test_trusted_new_admin_event_retains_safe_structured_snapshot` упал однажды (вероятно, «999» в случайном UUID). **Не чинить в этой задаче.** Если упадёт снова, указать в отчёте с сырым выводом и не считать регрессией без анализа.
- Admin: 255 passed, typecheck и build чистые. **Lint: 8 errors, 4 warnings.**
- Новых миграций нет; production на `0019_coords_and_loyalty_tiers`.

## Этап A — локально, без production

1. **Lint.** Исправить только эти замечания, поведение не менять:
   - ошибки в тестах: `any` в `tests/app-splash.test.tsx:47`, `tests/document-title.test.tsx:23`, `tests/favicon.test.tsx:8`, `tests/statuses.test.tsx:153,220`; неиспользуемые `act`, `Route`, `Routes` в `tests/favicon.test.tsx`;
   - предупреждения exhaustive-deps в `src/pages/DashboardPage.tsx:119` и `src/pages/OperationsPage.tsx:46`: вынести роль в отдельную переменную и указать её в зависимостях. Логику выбора бизнеса и фавикона не менять.
   После правок: `npm --prefix admin run lint` — **0 errors, 0 warnings**; затем последовательно `tests/favicon.test.tsx`, `tests/compact-admin.test.tsx`, `tests/cards-list.test.tsx`, полный `npx vitest run --maxWorkers=1`, typecheck, production build (`VITE_API_BASE_URL=https://api.cashback-qr.poscenter.kz VITE_ALLOW_INSECURE_HTTP=0`).
2. **Показ владельцу (AGENTS.md §1.1).** Локальный preview собранного кабинета с моками, 1366×768 и 390×844, RU. Снимки сохранить в `reports/owner-revisions-2026-11-11/final/`:
   - сайдбар с уменьшенным логотипом и без `LOYALTY · ADMIN`;
   - таблица с более чем 7 строками: свёрнута (7 и кнопка «Все (N)») и раскрыта;
   - «Клиенты»: поиск карты по последним цифрам (несколько совпадений) и список пользователей по умолчанию;
   - дашборд с некорректным годом (кнопка заблокирована);
   - настройки с выровненным заголовком;
   - для фавикона — фактический `href` у менеджера Keremet и у суперадминистратора после выбора другого бизнеса (DOM вручную не менять).
   Каждый снимок открыть и просмотреть самому; в отчёте одна строка о том, что на нём видно, и SHA-256.
3. **Локальный коммит, без push.** Отдельным коммитом зафиксировать только admin/backend этой задачи (`admin/`, `backend/`, `scripts/capture_owner_revisions_20261111.*`, `reports/ADMIN_OWNER_REVISIONS*`, снимки). `mobile/`, `AGENTS.md`, `CLAUDE.md` и прочее не включать. Перед коммитом показать `git diff --cached --stat`. Сверить, что в коммите нет `.env*`, ключей, `dist/`, `node_modules/`, `C:/`.
4. Дополнить `reports/ADMIN_OWNER_REVISIONS_2026-11-11.md` разделом «Этап A» (команды, сырые итоги, SHA коммита, список снимков) и **остановиться**. Владелец смотрит снимки и отвечает.

## Этап B — после явного «выкладывай» владельца

5. **Backend.** VPS `kz-vps`, `/opt/cashback-one`: свободно ≥2 ГБ, `/health/ready` в порядке, alembic **0019**. Сверить `backend/app` и миграции на VPS с `23b4fd8`; при другом исходном состоянии — СТОП. READ ONLY агрегатные количества (бизнесы/карты/операции/пользователи/уведомления/ключи/устройства) без ПДн. Копия БД с проверкой gzip, копия исходников и конфигов, rollback-тег образа с UTC. `git archive <новый SHA> backend` без tests, сверка SHA-256 Mac/VPS до распаковки, штатная сборка образа. **Миграцию не запускать** (её нет). Если `alembic heads` ≠ 0019 — СТОП. Пересоздать только backend: ready (database+redis), один scheduler, нет свежих ошибок. Конфиги и `.env`/compose/Caddy/Firebase по хешам прежние. Без авторизации поиск `/admin/*` даёт 401. Количества после совпадают.
6. **Кабинет.** Собрать из того же коммита. FTPS по существующей процедуре (`SSL_CERT_FILE=/etc/ssl/cert.pem`, TLS ≤1.2, `scripts/upload_admin.py` не использовать): копия прежнего index и manifest, assets сначала, `keremet-favicon.png`, index последним через временное имя → SHA-256 → rename. `.htaccess`, `app/`, `demo/`, `media/`, старые assets и APK не трогать. По HTTPS сверить целиком (тип, длина, SHA-256) все новые JS/CSS/PNG и index; сервер отвечает 200 на несуществующие пути, поэтому одного кода 200 мало. В браузере: главная RU/KK, `/admin/login`, title, нет ошибок в console.
7. `app/version.json`, `app/keremet-version.json` и опубликованные APK до и после должны совпадать по SHA-256.
8. Настоящий вход менеджера считать проверенным, только если он реально выполнен. Учётные данные в чат не просить.

## Отчёт и откат

`reports/DEPLOY_OWNER_REVISIONS_2026-11-11.md`: исходный SHA, копии и rollback-образ, проверки до/после, хеши файлов сайта, безопасный сырой вывод, что сделано и что не проверено. Откат: прежний образ и прежний index из копии. БД не восстанавливать без отдельного поручения.
