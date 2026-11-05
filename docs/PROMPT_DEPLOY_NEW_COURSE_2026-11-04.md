# Промпт исполнителю (Gemini): выкладка облака и кабинета нового курса — 2026-11-04

**Упало или неожиданно — СТОП и сырой вывод; без самостоятельных исправлений; секреты и ПДн скрыть.**

Общайся и пиши отчёт по-русски.

## Контекст

Папка `/Users/nuras/Desktop/cashback-one`. Владелец поручил выложить на production принятые задачи нового курса из коммита **`2c73120`** (backend и кабинет — в `4dcbef4`, документы — в `2c73120`):

- push-уведомления (миграция `0012_push_devices`);
- магазины и тексты приложения в кабинете (`0013_business_app_content`);
- ключи касс и код списания через push, `/pos/*` (`0014_pos_keys`);
- скрытие использованного кода в уведомлениях (`0015_notification_redemption`);
- кабинет: блоки «Кассы», «Магазины и инфо», формулировки ключа агента, CORS с `PUT`.

Production: VPS `kz-vps`, `/opt/cashback-one`, контейнеры `cashback-backend`, `cashback-migration`; API `https://api.cashback-qr.poscenter.kz`; сайт и кабинет `https://cashback-qr.poscenter.kz` (FTPS-хостинг).

**Push остаётся выключенным** (`PUSH_PROVIDER_MODE` по умолчанию `disabled`): файла сервисного аккаунта Firebase ещё нет. До его появления `/pos/redemptions` отвечает 503 `PUSH_NOT_CONFIGURED` — это ожидаемо. `.env` на VPS в этой задаче **не менять**.

Образцы прежних выкладок: backend с миграцией — `reports/BACKEND_LOGIN_AVATAR_DEPLOY_2026-11-01.md`, сайт — `reports/LANDING_ROBOTO_DEPLOY_2026-11-02.md`, откаты — там же.

## Запреты

- Не печатать `.env`, `.env.hosting.local`, ключи, пароли, строки подключения, телефоны и имена покупателей. В отчёт — только количества.
- 1С и агент не трогать. Caddy, `.htaccess`, `app/`, `demo/`, `media/` на хостинге не менять. Ничего на хостинге не удалять.
- `scripts/upload_admin.py` не использовать. Команду архива из `docs/DEPLOY_VPS.md` не использовать (не исключает `.venv`) — только `git archive`.
- Не выдавать ключи касс и агентов, не создавать бизнесы и магазины, не писать в production-базу ничего, кроме миграций. Проверки — только чтение или запросы, которые ничего не создают.
- Без commit/push, без изменений кода.

## Часть 1. Backend

1. **Состояние.** `git log -1 --oneline` = `2c73120`, `git status --short` для `backend/` пуст. На VPS: текущий образ, `alembic current` (ожидается `0011_customer_avatar`), количества (READ ONLY): бизнесов, агентов, карт, операций, покупателей, акций, уведомлений, `devices`. `df -h` на VPS. Расхождение с ожиданием — СТОП.
2. **Сверка исходников.** Файлы `backend/app` и `backend/migrations` на VPS побайтно совпадают с коммитом прежней выкладки (`098da49` для backend). Если нет — СТОП и список отличий.
3. **Копии** в `backups/newcourse-<UTC>/`: `pg.sql.gz` (проверка `gzip -t` и строки завершения дампа — учти, что после неё идёт `\unrestrict`), `env.bak` (права 600, равен `.env` по SHA-256, содержимое не выводить), `backend-src.tgz`. Образ отката: `cashback-backend:rollback-newcourse-<UTC>`. Выведи размеры и хеши.
4. **Архив** из `git archive 2c73120 backend` без `tests`, `.env`, `.venv`; SHA-256 на Mac и на VPS совпадают.
5. **Сборка и миграция** тем же способом, что в прежней выкладке. Ожидается `cashback-migration` Exited (0) и `0011 → 0015`. Иначе — СТОП, не перезапускать backend, план отката.
6. **Проверки после:**
   - `/health/ready`: database ok, redis ok, ожидаемая голова alembic совпадает; журнал backend без ошибок;
   - READ ONLY: `alembic current` = `0015_notification_redemption`; таблицы `pos_keys`, `business_stores` есть; новые колонки `devices.app_id`, `devices.last_seen_at`, `devices.disabled_at`, `businesses.app_texts`, `notifications.redemption_id`; количества из шага 1 не изменились (кроме ожидаемого удаления дубликатов в `devices`, если они были — тогда выведи сколько);
   - публичный API без авторизации и без побочных эффектов: `POST /pos/redemptions` без `X-Pos-Key` → 401 `POS_KEY_MISSING`; с ключом `pos_invalid_xxx` → 401 `POS_KEY_INVALID`; `PUT /me/push-token` без токена → 401; `GET /me/app-content?business_id=<любой uuid>` без токена → 401; `POST /agent/redemptions` с заведомо неверным `X-Agent-Key` → 401 (не 500);
   - preflight `OPTIONS` от `https://cashback-qr.poscenter.kz` с `Access-Control-Request-Method: PUT` к `/admin/businesses/<uuid>/app-texts` → разрешено.

## Часть 2. Кабинет и сайт

Только после успешной части 1.

1. Текущий `index.html` на сайте: SHA-256 должен быть `c4d8a0ce86927d3b…`. Иначе — СТОП.
2. Из `admin/`: `npx vitest run --maxWorkers=1` (ожидается 175 passed), `npm run typecheck`, `npm run lint`, `VITE_API_BASE_URL=https://api.cashback-qr.poscenter.kz VITE_ALLOW_INSECURE_HTTP=0 npm run build`. В `dist`: есть `https://api.cashback-qr.poscenter.kz`, нет `localhost`, ссылка на APK — `1.0.10`.
3. Таблица `dist`: путь, размер, SHA-256, «новый»/«совпадает» (по SHA-256 и длине; сервер отвечает 200 на несуществующие пути). К загрузке ожидаются новые `assets/*` и `index.html`. Что-то из запретов — СТОП.
4. Копия в `~/.local/share/cashback-one/backups/landing-<UTC>-newcourse/`: текущий `index.html` с сайта, хеш сверен.
5. FTPS: TLS 1.2, проверка сертификата (`SSL_CERT_FILE=/etc/ssl/cert.pem`), `PROT P`, `TYPE I`, возврат в корень перед сменой папки. Сначала `assets/*`, `index.html` последним. Каждый файл: временное имя → скачать обратно и сверить → переименовать. Сбой — остановиться, `index.html` не загружать.
6. Проверка: каждый загруженный файл по HTTPS с `Cache-Control: no-cache` — SHA-256, длина, `Content-Type`; живой `index.html` = локальный; временных файлов нет; `app/version.json` по-прежнему `7e1c460a…`; `app/cashback-one-1.0.10.apk` и `app/cashback-one-1.0.11-test.apk` по длине прежние.
7. В настоящем браузере без входа: главная RU и ҚАЗ открывается, ошибок в консоли нет; `/admin/login` — форма видна, шрифт Roboto. Настоящий вход не выполнять.

## Откат

- Backend: `docker tag cashback-backend:rollback-newcourse-<UTC> cashback-backend:local` и `docker compose up -d --no-build --force-recreate backend`. Новые таблицы и колонки старому образу не мешают; чтобы снять расхождение версии в `/health/ready`, сначала `alembic downgrade 0011_customer_avatar` из нового образа — **только если ещё не выданы ключи касс и не внесены магазины**, иначе данные потеряются.
- Сайт: вернуть `index.html` из копии.

Сам не откатывай без поручения: при сбое — СТОП, сырой вывод и план.

## Отчёт

`reports/DEPLOY_NEW_COURSE_2026-11-04.md`: сырой вывод частей 1 и 2 без секретов и ПДн, копии и образ отката с размерами и хешами, таблица загруженных файлов, новый хеш `index.html`, план отката, что не проверено (вход в кабинет, выдача ключа кассы, настоящий push — выключен).
