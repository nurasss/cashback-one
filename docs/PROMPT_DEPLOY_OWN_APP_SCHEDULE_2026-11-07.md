# Промпт исполнителю (Gemini): выкладка «push только в своё приложение» и отложенных уведомлений — 2026-11-07

**Упало или неожиданно — СТОП и сырой вывод; без самостоятельных исправлений; секреты и ПДн скрыть.** Общайся и пиши отчёт по-русски.

## Контекст

Папка `/Users/nuras/Desktop/cashback-one`. Владелец поручил выложить принятую куратором правку **`ebb28fc`** (отчёт `reports/BACKEND_PUSH_OWN_APP_SCHEDULE_2026-11-07.md`): push бизнеса со своим приложением уходят только в него; отложенная отправка уведомлений из кабинета. **Есть миграция `0017_scheduled_notifications`** (две колонки и индекс в `notifications`). Меняются backend и кабинет.

Порядок и запреты — как в `docs/PROMPT_DEPLOY_BROADCAST_PUSH_2026-11-06.md` (часть 1 — backend, часть 2 — кабинет и сайт) и отчёт `reports/DEPLOY_POS_CODE_PUSH_2026-11-07.md`, с отличиями ниже. `.env`, `compose.yml`, `secrets/` не менять. Уведомления на production **не создавать** (ни сразу, ни отложенные) — проверку делает владелец.

## Часть 1. Backend

1. `git log -1` не старше `ebb28fc`; `git diff --stat e4be0f4 ebb28fc -- backend/app backend/migrations` — покажи. На VPS `alembic current` = `0016_business_android_app_id`; количества (READ ONLY): бизнесов, карт, операций, покупателей, уведомлений, `redemption_codes`, `pos_keys`, `devices` по `app_id`; `android_app_id` у бизнесов; SHA-256 и права `.env`, `compose.yml`, файла сервисного аккаунта; `df -h` (меньше 2 ГБ — СТОП). Команда запуска backend в `compose.yml` — сколько процессов uvicorn (`--workers`); перепиши как есть.
2. `backend/app`, `backend/migrations` на VPS побайтно равны `e4be0f4`, иначе СТОП.
3. Копии `backups/schedule-<UTC>/` (`pg.sql.gz` с проверкой, `env.bak`, `compose.yml.bak`, `backend-src.tgz`), образ `cashback-backend:rollback-schedule-<UTC>`.
4. Архив `git archive ebb28fc backend` без `tests`, `.env`, `.venv`; SHA-256 на Mac и VPS совпадают **до** распаковки. Если связь оборвётся — СТОП, без повторов.
5. Сборка, `cashback-migration` Exited (0), `alembic current` = **`0017_scheduled_notifications (head)`**, backend `healthy`. Сборку один раз; если не прошла — СТОП.
6. После:
   - `/health/ready` ok; push `fcm`; количества не изменились; хеши конфигурации прежние;
   - в `notifications` есть колонки `scheduled_at`, `push_sent_at` (все NULL у существующих строк) и индекс `ix_notifications_scheduled_pending`;
   - в журнале backend строка `Starting scheduled notifications worker (interval=30.0s)` (по одной на процесс); 10 минут без ERROR/CRITICAL/Traceback;
   - без токена `POST /admin/notifications` → 401; `POST /pos/code-push` без ключа → 401 `POS_KEY_MISSING`; `/agent/heartbeat` → 200.

## Часть 2. Кабинет и сайт

1. Живой `index.html`: SHA-256 `8567d53d…` (полный — в `reports/DEPLOY_BROADCAST_PUSH_2026-11-06.md`). Иначе СТОП.
2. `admin/`: `npx vitest run --maxWorkers=1` (190), typecheck, lint, production build с `VITE_API_BASE_URL=https://api.cashback-qr.poscenter.kz VITE_ALLOW_INSECURE_HTTP=0`; в `dist` нет `localhost`, ссылка APK — `1.0.10`. Тайм-аут тестов — повтори один раз и покажи оба результата. Перед сборкой `df -h /` (меньше 1 ГБ — СТОП).
3. Таблица `dist`, копия `index.html` в `~/.local/share/cashback-one/backups/landing-<UTC>-schedule/`, FTPS (`assets/*` сначала, `index.html` последним, временное имя → сверка → rename), проверка по HTTPS. `app/version.json` (`7e1c460a…`), `app/*.apk`, `.htaccess` не меняются (наличие `app/.htaccess` — 403 с телом 146 байт).
4. В браузере без входа: главная RU/ҚАЗ без ошибок консоли, `/admin/login` — форма видна.

## Откат

Backend — образ `rollback-schedule-<UTC>` **и** `alembic downgrade 0016_business_android_app_id` (колонки новые, данных в них нет) — только по поручению; сайт — `index.html` из копии.

## Отчёт

`reports/DEPLOY_OWN_APP_SCHEDULE_2026-11-07.md`: сырой вывод без секретов и ПДн, копии и образ отката, таблица загруженных файлов, новый хеш `index.html`, что не проверено (настоящая рассылка, отложенная отправка, код с кассы — делает владелец).
