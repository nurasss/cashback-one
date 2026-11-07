# Промпт исполнителю (Gemini): выкладка `POST /pos/code-push` — только backend — 2026-11-07

**Упало или неожиданно — СТОП и сырой вывод; без самостоятельных исправлений; секреты и ПДн скрыть.** Общайся и пиши отчёт по-русски.

## Контекст

Папка `/Users/nuras/Desktop/cashback-one`. Владелец поручил выложить принятую куратором правку **`e4be0f4`** (отчёт `reports/BACKEND_POS_CODE_PUSH_2026-11-07.md`): разработчик Cash уже проверяет функцию 1С 7.7 и получает 404. Меняются только `backend/app/api/pos.py`, `schemas/pos.py`, `services/content_service.py`, `services/pos_service.py`. **Миграций нет** (голова `0016`). Кабинет и сайт **не выкладывать**.

Порядок и запреты — как часть 1 в `docs/PROMPT_DEPLOY_BROADCAST_PUSH_2026-11-06.md` и отчёт `reports/DEPLOY_BROADCAST_PUSH_2026-11-06.md`, с отличиями ниже. `.env`, `compose.yml`, `secrets/` не менять. Push покупателям **не отправлять**: настоящий `/pos/code-push` с верным ключом не вызывать — проверку на кассе делает владелец.

## Шаги

1. `git log -1` не старше `e4be0f4`; `git diff --stat fd3a215 e4be0f4 -- backend/app backend/migrations` — только четыре файла выше, `migrations` без изменений. На VPS `alembic current` = `0016_business_android_app_id`; количества (READ ONLY): бизнесов, карт, операций, покупателей, уведомлений, `redemption_codes`, `pos_keys`, `devices` по `app_id`; SHA-256 и права `.env`, `compose.yml`, файла сервисного аккаунта; `df -h`.
2. `backend/app`, `backend/migrations` на VPS побайтно равны `fd3a215`, иначе СТОП.
3. Копии `backups/codepush-<UTC>/` (`pg.sql.gz` с проверкой, `env.bak`, `compose.yml.bak`, `backend-src.tgz`), образ `cashback-backend:rollback-codepush-<UTC>`.
4. Архив `git archive e4be0f4 backend` без `tests`, `.env`, `.venv`; SHA-256 на Mac и VPS совпадают.
5. Сборка, `cashback-migration` Exited (0), голова не изменилась, backend `healthy`.
6. После:
   - `/health/ready` ok; журнал 10 минут без ERROR/CRITICAL; push `fcm`; количества не изменились; хеши конфигурации прежние;
   - `POST /pos/code-push` **без** `X-Pos-Key` → 401 `POS_KEY_MISSING`; с выдуманным ключом `pos_invalid_smoke_0000000000000000000000000000` → 401 `POS_KEY_INVALID` (не 404 и не 500);
   - `POST /pos/redemptions` без ключа → 401 (как раньше); `/agent/heartbeat` → 200.

## Откат

Образ `rollback-codepush-<UTC>`. Сам не откатывай без поручения.

## Отчёт

`reports/DEPLOY_POS_CODE_PUSH_2026-11-07.md`: сырой вывод без секретов и ПДн, копии и образ отката, что не проверено (настоящая отправка кода с кассы и доставка push).
