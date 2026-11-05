# Промпт исполнителю (Gemini): повторное включение push — 2026-11-05

**Упало или неожиданно — СТОП и сырой вывод; без самостоятельных исправлений; секреты и ПДн скрыть.**

Общайся и пиши отчёт по-русски.

## Контекст

Продолжение `docs/PROMPT_ENABLE_PUSH_FCM_2026-11-05.md`, отчёт `reports/ENABLE_PUSH_FCM_2026-11-05.md`. Первая попытка правильно остановилась на шаге 7: сервис `migration` читает тот же `.env`, при `PUSH_PROVIDER_MODE=fcm` проверка настроек требует файл, а в `migration` он не смонтирован. Откат выполнен, куратор подтвердил: `cashback-backend` healthy, `/health/ready` 200, в `.env` нет `PUSH_*`/`FCM_*`. Файл `/opt/cashback-one/secrets/firebase-service-account.json` (600, `10001:10001`) на месте.

**Решение куратора:** монтировать файл только для чтения в **оба** сервиса — `backend` и `migration`. Флаг `--no-deps` не использовать: следующая выкладка снова запустит `migration` с тем же `.env` и упадёт.

Все запреты первого промпта действуют: содержимое файла и `.env` не выводить, настоящих уведомлений не отправлять, в базу не писать, код не менять, без commit/push.

## Шаги

1. Состояние: `docker ps` для `cashback-*`, `/health/ready`, SHA-256 `.env` и compose-файла равны копиям в `backups/push-20261104T192034Z/` (то есть откат полный). Иначе — СТОП. Пользователь процесса в образе миграции тот же `10001`? (`docker run --rm --entrypoint id cashback-backend:local` или как устроен сервис). Если другой — СТОП и опиши, права файла не менять самостоятельно.
2. Новая копия в `backups/push-<UTC>-retry/`: `env.bak` (600) и compose-файл, хеши.
3. Compose: в `backend` и `migration` одинаковое монтирование `/opt/cashback-one/secrets/firebase-service-account.json:/run/secrets/firebase-service-account.json:ro`. Покажи `diff` против копии: только эти строки.
4. `.env`: те же три переменные, что в первой попытке. Покажи, что изменились/добавились только они (имена).
5. `docker compose up -d --no-build --force-recreate backend` (без `--no-deps`). Ожидается: `cashback-migration` Exited (0) — миграций нет, голова уже `0015`; backend healthy; журнал без ошибок. Иначе — сразу откат `.env` и compose из копии шага 2, перезапуск, СТОП.
6. Шаги 8–9 первого промпта: токен доступа `ok`; `validate_only` на заведомо неверный токен → ошибка токена (`INVALID_ARGUMENT`/`UNREGISTERED`), не 401/403; `/health/ready` 200; `POST /pos/redemptions` без ключа → 401 `POS_KEY_MISSING`; число `devices`.

## Отчёт

Допиши в `reports/ENABLE_PUSH_FCM_2026-11-05.md` раздел «Повторная попытка»: сырой вывод, хеши копий, `diff` compose, результат проверки Firebase, план отката.
