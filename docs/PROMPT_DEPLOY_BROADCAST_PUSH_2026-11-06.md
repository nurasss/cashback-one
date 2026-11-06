# Промпт исполнителю (Gemini): выкладка push для рассылок — сервер и кабинет — 2026-11-06

**Упало или неожиданно — СТОП и сырой вывод; без самостоятельных исправлений; секреты и ПДн скрыть.** Общайся и пиши отчёт по-русски.

## Контекст

Папка `/Users/nuras/Desktop/cashback-one`. Владелец поручил выложить принятую куратором правку **`fd3a215`** (отчёт `reports/BACKEND_BROADCAST_PUSH_2026-11-06.md`): при создании уведомления в кабинете отправляется push. Меняются backend (`admin.py`, `admin_content.py`, `admin_mutations.py`, `push_service.py`, схема `admin_content.py`) и кабинет (`ContentPage.tsx`, `admin.ts`, `types.ts`). **Миграций нет** (голова `0016`).

Порядок и запреты — как в `docs/PROMPT_DEPLOY_PER_CLIENT_2026-11-05.md` (часть 1 — backend, часть 2 — кабинет и сайт), с отличиями ниже. `.env`, `compose.yml`, `secrets/` не менять. Уведомления на production **не создавать** (это разошлёт push настоящим покупателям) — проверку отправки сделает владелец.

## Часть 1. Backend

1. `git log -1` не старше `fd3a215`; `git diff --stat 3a5da17 fd3a215 -- backend/app backend/migrations` — только перечисленные файлы, `migrations` без изменений. На VPS `alembic current` = `0016_business_android_app_id`; количества (READ ONLY): бизнесов, карт, операций, покупателей, уведомлений, акций, `devices` по `app_id`; SHA-256 и права `.env`, `compose.yml`, файла сервисного аккаунта; `df -h`.
2. `backend/app`, `backend/migrations` на VPS побайтно равны `3a5da17`, иначе СТОП.
3. Копии `backups/bcast-<UTC>/` (`pg.sql.gz` с проверкой, `env.bak`, `compose.yml.bak`, `backend-src.tgz`), образ `cashback-backend:rollback-bcast-<UTC>`.
4. Архив `git archive fd3a215 backend` без `tests`, `.env`, `.venv`; SHA-256 на Mac и VPS совпадают.
5. Сборка, `cashback-migration` Exited (0), голова не изменилась, backend `healthy`.
6. После: `/health/ready` ok; журнал 10 минут без ERROR/CRITICAL; push `fcm`; количества не изменились; хеши конфигурации прежние; без токена `POST /admin/notifications` → 401 (не 500); `/agent/heartbeat` → 200.

## Часть 2. Кабинет и сайт

1. Живой `index.html`: SHA-256 `9ee225772f6c725e…` (полный — в `reports/DEPLOY_PER_CLIENT_2026-11-05.md`). Иначе СТОП.
2. `admin/`: `npx vitest run --maxWorkers=1` (184), typecheck, lint, production build с `VITE_API_BASE_URL=https://api.cashback-qr.poscenter.kz VITE_ALLOW_INSECURE_HTTP=0`; в `dist` нет `localhost`, ссылка APK — `1.0.10`. Если тесты падают по тайм-ауту — повтори один раз и покажи оба результата; повторное падение — СТОП. Перед сборкой `df -h /` (меньше 1 ГБ — СТОП).
3. Таблица `dist`, копия `index.html` в `~/.local/share/cashback-one/backups/landing-<UTC>-bcast/`, FTPS (`assets/*` сначала, `index.html` последним, временное имя → сверка → rename), проверка по HTTPS. `app/version.json` (`7e1c460a…`) и APK на сайте не меняются.
4. В браузере без входа: главная RU/ҚАЗ без ошибок консоли, `/admin/login` — форма видна.

## Откат

Backend — образ `rollback-bcast-<UTC>`; сайт — `index.html` из копии. Сам не откатывай без поручения.

## Отчёт

`reports/DEPLOY_BROADCAST_PUSH_2026-11-06.md`: сырой вывод без секретов и ПДн, копии и образ отката, таблица загруженных файлов, новый хеш `index.html`, что не проверено (настоящая рассылка с push, галочка в кабинете под входом).
