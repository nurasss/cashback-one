# Отчёт: Выкладка сервера — контент магазина без карты — 2026-11-06

**Дата:** 2026-11-06 (macOS).  
**Промпт:** `docs/PROMPT_DEPLOY_CLIENT_CONTENT_NO_CARD_2026-11-06.md`.  
**Коммит кода:** **`3a5da17`** (feat(backend): store content in its own app without a card).  
**Предыдущий коммит на VPS:** **`6a9fa18`**.  
**Статус:** **Успешно завершено.** Backend выложен на production, все проверки пройдены. Кабинет и сайт не затрагивались. База данных и схема не изменялись (`alembic` голова остаётся `0016_business_android_app_id`).

---

## 1. Сбои и нештатные ситуации в ходе работы

Сбоев и нештатных ситуаций не зафиксировано. Все команды и проверки выполнены в штатном режиме.

---

## 2. Шаг 1: Исходное состояние до выкладки

### Локальный репозиторий (Mac)
- `git log -1 --oneline`: `b9b4096 docs: deploy prompt for store content without card` (не старше `3a5da17`).
- `git diff --stat 6a9fa18 3a5da17 -- backend/app backend/migrations`:
  ```text
   backend/app/api/customer_app.py         | 18 ++----------------
   backend/app/services/content_service.py | 31 +++++++++++++++++++------------
   2 files changed, 21 insertions(+), 28 deletions(-)
  ```
  Изменены только `content_service.py` и `customer_app.py`. Миграции отсутствуют.

### Сервер VPS (`kz-vps`)
- Дисковое пространство:
  ```text
  Filesystem      Size  Used Avail Use% Mounted on
  /dev/sda2        40G   35G  3.1G  92% /
  ```
- Конфигурационные файлы:
  - `/opt/cashback-one/.env`: `-rw------- 1 ubuntu ubuntu 1679 Nov  4 19:49`, SHA-256 `a4df9bd96793327995622af31fca575820045228709e55f4a4cad90534f37db6`
  - `/opt/cashback-one/compose.yml`: `-rw-r--r-- 1 ubuntu ubuntu 2901 Nov  4 19:49`, SHA-256 `21fe1ed7010e083625c9669da12bd1aa766cf9a231958be35ba27615491a89b9`
  - `/opt/cashback-one/secrets/firebase-service-account.json`: `-rw------- 1 10001 10001 2400 Nov  4 19:21`, SHA-256 `677107719d64976980d59cc7c7cd9f4fa0bfa3d1b2d25666668e56b04f6f1cc1`
- Текущая ревизия Alembic:
  ```text
  INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
  INFO  [alembic.runtime.migration] Will assume transactional DDL.
  0016_business_android_app_id (head)
  ```
- Состояние базы данных (READ ONLY):
  ```text
       tbl      | cnt  
  --------------+------
   businesses   |    2
   cards        | 1714
   transactions | 9750
   users        |    4
   devices      |    5

    kind  | is_global | count 
  --------+-----------+-------
   banner | f         |     3
   offer  | f         |     1
   banner | t         |     1

           app_id         | count 
  ------------------------+-------
   kz.cashbackone.mobile  |     2
   kz.cashbackone.keremet |     3
  ```

---

## 3. Шаг 2: Сверка исходников на VPS с коммитом `6a9fa18`

Сверены 92 файла `backend/app` и `backend/migrations` на VPS со списком хешей коммита `6a9fa18` через `sha256sum -c --quiet`.  
Расхождений нет (0 файлов, код возврата 0). Количество файлов без pycache строго 92.

---

## 4. Шаг 3: Резервные копии и образ отката

- Метка времени: `20261106T094255Z`
- Каталог резервной копии: `/opt/cashback-one/backups/nocard-20261106T094255Z/`
- Файлы резервной копии:
  - `pg.sql.gz`: **627 006 байт**, SHA-256 `6ccddf27db5ccb75af829d922d9194591630c2d70d45784b319a04e87cd47f57`. Проверка `gzip -t` — успешно; строка завершения дампа подтверждена (`-- PostgreSQL database dump complete --`).
  - `env.bak`: **1 679 байт**, права `600`, SHA-256 `a4df9bd96793327995622af31fca575820045228709e55f4a4cad90534f37db6` (совпадает с `.env`).
  - `compose.yml.bak`: **2 901 байт**, права `600`, SHA-256 `21fe1ed7010e083625c9669da12bd1aa766cf9a231958be35ba27615491a89b9` (совпадает с `compose.yml`).
  - `backend-src.tgz`: **32 027 269 байт**, SHA-256 `bb621fdd7804bbc87a0056a4c435df0796a708273cb49b5ec5ec3d5c67786e4b`.
- Образ отката:
  - Тег: `cashback-backend:rollback-nocard-20261106T094255Z`
  - ID образа: `cd1634cc3f70` (соответствует образу `6a9fa18`).

---

## 5. Шаг 4: Архив и передача исходников `3a5da17`

- Архив сформирован из коммита `3a5da17` (`backend` без `tests`, `.env`, `.venv`):
  - Файл: `/tmp/cashback-backend-3a5da17.tgz`
  - Размер: **129 702 байта**
  - SHA-256 на Mac: `410fdeaab2a80f8cad9c5f23393ffaba9eff2b73526e1f6cc4ed0a3458929ab6`
  - SHA-256 на VPS: `410fdeaab2a80f8cad9c5f23393ffaba9eff2b73526e1f6cc4ed0a3458929ab6` (побайтно совпадает).
- Архив распакован в `/opt/cashback-one`.
- Сверка файлов после распаковки: все 92 файла `backend/app` и `backend/migrations` проверены против хешей коммита `3a5da17` (`sha256sum -c --quiet`), расхождений нет.

---

## 6. Шаг 5: Сборка и запуск

1. **Сборка Docker-образа `cashback-backend:local`:**
   ```text
   docker compose build migration
   #17 naming to docker.io/library/cashback-backend:local done
   migration Built
   ```
2. **Проверка контейнера миграций:**
   ```text
   docker compose up migration
   Container cashback-postgres  Running
   Container cashback-migration  Recreated
   Attaching to cashback-migration
   cashback-migration  | INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
   cashback-migration  | INFO  [alembic.runtime.migration] Will assume transactional DDL.
   cashback-migration exited with code 0
   ```
   Статус: `Exited (0)`.
3. **Перезапуск backend:**
   ```text
   docker compose up -d --no-build --force-recreate backend
   Container cashback-backend  Recreated
   Container cashback-backend  Starting
   Container cashback-backend  Started
   ```
   Контейнер `cashback-backend` запущен и перешёл в статус `healthy`.
4. **Проверка ревизии миграций:**
   `alembic current` внутри контейнера: `0016_business_android_app_id (head)` (не изменилась).

---

## 7. Шаг 6: Проверки после выкладки

1. **Готовность сервиса (`/health/ready`):**
   - Локально внутри контейнера: `HTTP/1.1 200 OK`, `{"status":"ready","components":{"database":"ok","redis":"ok"}}`.
   - Через публичный API Caddy: `HTTP/2 200`, `{"status":"ready","components":{"database":"ok","redis":"ok"}}`.
2. **Журнал контейнера `cashback-backend` за 10 минут:**
   - Ошибок уровня ERROR / CRITICAL нет (`No ERROR/CRITICAL lines found`).
   - Режим push-уведомлений: `push_provider_mode: fcm`, наличие ключей FCM подтверждено (`fcm_project_id: True`, `fcm_service_account_file: True`).
   - Запросы агента `POST /agent/heartbeat` возвращают HTTP 200 (`duration_ms` ~15 мс).
3. **Схема и данные БД (READ ONLY):**
   - `alembic current`: `0016_business_android_app_id (head)`.
   - Количества записей в точности равны значениям до выкладки:
     - `businesses`: 2
     - `cards`: 1714
     - `transactions`: 9750
     - `users`: 4
     - `devices`: 5 (`kz.cashbackone.mobile`: 2, `kz.cashbackone.keremet`: 3)
     - `promotions`: 5 (3 баннера магазина, 1 акция магазина, 1 глобальный баннер)
4. **Конфигурация:**
   SHA-256 файлов строго неизменны:
   - `/opt/cashback-one/.env`: `a4df9bd96793327995622af31fca575820045228709e55f4a4cad90534f37db6`
   - `/opt/cashback-one/compose.yml`: `21fe1ed7010e083625c9669da12bd1aa766cf9a231958be35ba27615491a89b9`
   - `/opt/cashback-one/secrets/firebase-service-account.json`: `677107719d64976980d59cc7c7cd9f4fa0bfa3d1b2d25666668e56b04f6f1cc1`
5. **Публичный API без авторизации:**
   - `GET /me/promotions?business_id=1ed257c3-0a4f-4569-9571-9b77b9b8d84b` → HTTP/2 401 `{"error":{"code":"UNAUTHORIZED","message":"Authorization header is required"}}`
   - `GET /me/app-content?business_id=1ed257c3-0a4f-4569-9571-9b77b9b8d84b` → HTTP/2 401 `{"error":{"code":"UNAUTHORIZED","message":"Authorization header is required"}}`
   - `POST /pos/redemptions` без ключа → HTTP/2 401 `{"error":{"code":"POS_KEY_MISSING","message":"X-Pos-Key header is required"}}`

---

## 8. План отката при необходимости

Миграций не было, схема базы данных не изменялась. Для отката на прежний образ backend достаточно выполнить на VPS `kz-vps` в каталоге `/opt/cashback-one`:
```bash
docker tag cashback-backend:rollback-nocard-20261106T094255Z cashback-backend:local
docker compose up -d --no-build --force-recreate backend
```

---

## 9. Что не проверено

Следующая проверка требует авторизованной сессии настоящего покупателя в клиентском мобильном приложении (например, KeremEt) на физическом устройстве:
- Отображение контента магазина (акции, баннеры, рассылки, бейджи, данные магазина `/me/app-content`) в приложении магазина под аккаунтом покупателя, у которого **нет карты** в данном магазине.
