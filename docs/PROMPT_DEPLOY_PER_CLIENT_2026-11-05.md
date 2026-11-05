# Промпт исполнителю (Gemini): выкладка сервера и кабинета для приложений клиентов — 2026-11-05

**Упало или неожиданно — СТОП и сырой вывод; без самостоятельных исправлений; секреты и ПДн скрыть.**

Общайся и пиши отчёт по-русски.

## Контекст

Папка `/Users/nuras/Desktop/cashback-one`. Владелец поручил выложить на production принятую куратором задачу I-backend: коммит **`0b9aae4`** (отчёт `reports/BACKEND_PER_CLIENT_APP_2026-11-05.md`):
- миграция `0016_business_android_app_id` (`businesses.android_app_id`, уникальное);
- push и `/pos/redemptions` (`CUSTOMER_NO_APP`) только в приложение бизнеса и общее (`PUSH_SHARED_APP_ID`, по умолчанию `kz.cashbackone.mobile`);
- необязательный `business_id` в `/me/*`;
- кабинет: поле «Пакет Android-приложения» у бизнеса (меняет только superadmin), менеджер видит страницу своего бизнеса.

Прежняя выкладка кода — `2c73120` (`reports/DEPLOY_NEW_COURSE_2026-11-04.md`), после неё код backend менялся только в `0b9aae4`. Потом включён push (`reports/ENABLE_PUSH_FCM_2026-11-05.md`): `PUSH_PROVIDER_MODE=fcm`, файл сервисного аккаунта смонтирован `:ro` в `backend` **и** `migration`. Эти настройки `.env` и `compose.yml` **сохранить как есть**, не менять.

Production: VPS `kz-vps`, `/opt/cashback-one`; API `https://api.cashback-qr.poscenter.kz`; сайт и кабинет `https://cashback-qr.poscenter.kz` (FTPS-хостинг).

**Не запускать одновременно** с `docs/PROMPT_TEST_BUSINESS_RESTORE_2026-11-05.md`: если та задача идёт, дождаться её конца.

## Запреты

Все запреты из `docs/PROMPT_DEPLOY_NEW_COURSE_2026-11-04.md`, раздел «Запреты». Дополнительно:
- **поле `android_app_id` ни у какого бизнеса не заполнять**: это сделает владелец в кабинете;
- `.env`, `compose.yml`, `secrets/` не менять и не выводить; печатать только SHA-256 и права;
- без commit/push.

## Часть 1. Backend

Порядок как в части 1 прежнего промпта, с отличиями:

1. **Состояние.** `git log -1 --oneline` — не старше `0b9aae4`, `git status --short` для `backend/` и `admin/src` пуст. На VPS: `alembic current` = `0015_notification_redemption`; количества (READ ONLY): бизнесов, агентов, карт, операций, покупателей, акций, уведомлений, `devices` по `app_id`, `pos_keys`. SHA-256 и права `.env`, `compose.yml`, файла сервисного аккаунта. `df -h`.
2. **Сверка исходников:** `backend/app` и `backend/migrations` на VPS побайтно равны коммиту `2c73120`. Нет — СТОП со списком отличий.
3. **Копии** в `backups/perclient-<UTC>/`: `pg.sql.gz` (`gzip -t`, строка завершения дампа; после неё идёт `\unrestrict`), `env.bak` и `compose.yml.bak` (права 600, SHA-256 равны оригиналам), `backend-src.tgz`. Образ отката `cashback-backend:rollback-perclient-<UTC>`. Размеры и хеши.
4. **Архив** `git archive 0b9aae4 backend` без `tests`, `.env`, `.venv`; SHA-256 на Mac и VPS совпадают.
5. **Сборка и миграция** тем же способом, что в прежней выкладке. Ожидается `cashback-migration` Exited (0), `0015 → 0016`. Иначе — СТОП, backend не перезапускать, план отката.
6. **Проверки после:**
   - `/health/ready`: database, redis ok, голова alembic совпадает; журнал backend без ошибок, в журнале запуска есть признак режима push `fcm` (как после включения push), без вывода секретов;
   - READ ONLY: `alembic current` = `0016_business_android_app_id`; колонка `businesses.android_app_id` есть, у всех бизнесов `NULL`; ограничение `uq_businesses_android_app_id` есть; количества из шага 1 не изменились;
   - SHA-256 `.env`, `compose.yml`, файла сервисного аккаунта прежние;
   - без авторизации и побочных эффектов: `GET /me/cards?business_id=<uuid>` без токена → 401; `GET /me/promotions?business_id=not-a-uuid` без токена → 401 или 422 (не 500, покажи какой); `POST /pos/redemptions` без `X-Pos-Key` → 401 `POS_KEY_MISSING`; `GET /admin/businesses/<uuid>` без токена → 401;
   - агент: в журнале backend за 10 минут после перезапуска запросы `/agent/heartbeat` отвечают 200, а не 401/5xx.

## Часть 2. Кабинет и сайт

Только после успешной части 1. Порядок как в части 2 прежнего промпта, с отличиями:
1. Текущий `index.html` на сайте: SHA-256 `a447375a2e1e714b59b28346981d624446a2a86d75ecd6e4076c67d058e8c25b`. Иначе — СТОП.
2. Из `admin/`: тесты (175 passed), typecheck, lint, production build с `VITE_API_BASE_URL=https://api.cashback-qr.poscenter.kz VITE_ALLOW_INSECURE_HTTP=0`. В `dist` ссылка на APK — `1.0.10`, нет `localhost`. Перед сборкой проверь свободное место на Mac (`df -h /`): меньше 1 ГБ — СТОП.
3. Таблица `dist`, копия `index.html` в `~/.local/share/cashback-one/backups/landing-<UTC>-perclient/`, FTPS-загрузка (`assets/*` сначала, `index.html` последним, временное имя → сверка → rename), проверка по HTTPS — как раньше. `app/version.json` по-прежнему `7e1c460a…`, APK на сайте по длине прежние.
4. В браузере без входа: главная RU/ҚАЗ без ошибок в консоли, `/admin/login` — форма видна. Настоящий вход не выполнять.

## Откат

- Backend: `docker tag cashback-backend:rollback-perclient-<UTC> cashback-backend:local` и `docker compose up -d --no-build --force-recreate backend`. Колонка `android_app_id` старому образу не мешает; чтобы снять расхождение головы в `/health/ready`, `alembic downgrade 0015_notification_redemption` из нового образа — безопасно, пока поле ни у кого не заполнено.
- Сайт: вернуть `index.html` из копии.

Сам не откатывай без поручения: при сбое — СТОП, сырой вывод и план.

## Отчёт

`reports/DEPLOY_PER_CLIENT_2026-11-05.md`: сырой вывод частей 1 и 2 без секретов и ПДн, копии и образ отката с размерами и хешами, таблица загруженных файлов, новый хеш `index.html`, план отката, что не проверено (вход в кабинет, заполнение поля, настоящий push в приложение клиента).
