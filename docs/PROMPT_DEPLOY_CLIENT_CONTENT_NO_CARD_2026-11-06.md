# Промпт исполнителю (Gemini): выкладка сервера — контент магазина без карты — 2026-11-06

**Упало или неожиданно — СТОП и сырой вывод; без самостоятельных исправлений; секреты и ПДн скрыть.** Общайся и пиши отчёт по-русски.

## Контекст

Папка `/Users/nuras/Desktop/cashback-one`. Владелец поручил выложить на production принятую куратором правку **`3a5da17`** (отчёт `reports/BACKEND_CLIENT_CONTENT_NO_CARD_2026-11-06.md`): в приложении магазина (`business_id=B`) баннеры, акции, рассылки и бейджи магазина видны без карты; `/me/app-content` больше не требует карты. Меняются `backend/app/services/content_service.py` и `backend/app/api/customer_app.py` (и тесты, документация).

**Только backend. Миграций нет** (голова остаётся `0016_business_android_app_id`). Кабинет и сайт **не выкладывать**.

Прежняя выкладка — `6a9fa18` по `docs/PROMPT_DEPLOY_PLATFORM_BANNERS_2026-11-06.md`, отчёт `reports/DEPLOY_PLATFORM_BANNERS_2026-11-06.md`. Процедура та же, что в части 1 того промпта, с отличиями ниже. `.env`, `compose.yml`, `secrets/` не менять (push `fcm`, файл сервисного аккаунта смонтирован в `backend` и `migration`).


## Запреты

Все запреты из `docs/PROMPT_DEPLOY_PER_CLIENT_2026-11-05.md`. Не создавать и не менять акции и баннеры на production. Без commit/push.

## Шаги

1. **Состояние.** `git log -1` не старше `3a5da17`; `git diff --stat 6a9fa18 3a5da17 -- backend/app backend/migrations` — только `content_service.py` и `customer_app.py`. На VPS: `alembic current` = `0016_business_android_app_id`; количества (READ ONLY): бизнесов, карт, операций, покупателей, акций по `kind` и признаку `business_id IS NULL`, `devices`. SHA-256 и права `.env`, `compose.yml`, файла сервисного аккаунта. `df -h`.
2. **Сверка:** `backend/app` и `backend/migrations` на VPS побайтно равны `6a9fa18`. Нет — СТОП со списком отличий.
3. **Копии** в `backups/nocard-<UTC>/`: `pg.sql.gz` (`gzip -t`, строка завершения), `env.bak`, `compose.yml.bak` (600, SHA-256 равны оригиналам), `backend-src.tgz`. Образ отката `cashback-backend:rollback-nocard-<UTC>`.
4. **Архив** `git archive 3a5da17 backend` без `tests`, `.env`, `.venv`; SHA-256 на Mac и VPS совпадают.
5. **Сборка и запуск** тем же способом. `cashback-migration` Exited (0), голова **не изменилась** (`0016`). Иначе СТОП, план отката.
6. **Проверки после:**
   - `/health/ready` ok; журнал backend за 10 минут без ERROR/CRITICAL; режим push `fcm`;
   - READ ONLY: количества из шага 1 не изменились; `alembic current` = `0016`;
   - SHA-256 `.env`, `compose.yml`, файла сервисного аккаунта прежние;
   - без токена: `GET /me/promotions?business_id=<uuid>` → 401, `GET /me/app-content?business_id=<uuid>` → 401, `POST /pos/redemptions` без ключа → 401 `POS_KEY_MISSING`;
   - `/agent/heartbeat` в журнале отвечают 200.

## Откат

`docker tag cashback-backend:rollback-nocard-<UTC> cashback-backend:local` и `docker compose up -d --no-build --force-recreate backend`. Миграций нет, база не меняется. Сам не откатывай без поручения.

## Отчёт

`reports/DEPLOY_CLIENT_CONTENT_NO_CARD_2026-11-06.md`: сырой вывод шагов без секретов и ПДн, копии и образ отката с размерами и хешами, план отката, что не проверено (показ контента магазина в приложении под настоящим покупателем).
