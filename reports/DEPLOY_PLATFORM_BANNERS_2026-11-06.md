# Отчёт: Выкладка сервера — баннеры платформы в приложениях клиентов — 2026-11-06

**Дата:** 2026-11-06 (macOS).  
**Промпт:** `docs/PROMPT_DEPLOY_PLATFORM_BANNERS_2026-11-06.md`.  
**Коммит кода:** **`6a9fa18`** (правка `content_service.py` для отображения баннеров платформы при наличии `business_id`).  
**Статус:** **Успешно завершено.** Backend выложен на production, все проверки пройдены. Кабинет и сайт не затрагивались.

---

## 1. Сбои и нештатные ситуации в ходе работы

Сбоев и нештатных ситуаций не зафиксировано. Все команды и проверки выполнены с первого раза в штатном режиме.

---

## 2. Шаг 1: Исходное состояние до выкладки

- Локальный git:
  - `git log -1 --oneline`: `fddb9f9` (не старше `6a9fa18`).
  - `git diff --stat 0b9aae4 6a9fa18 -- backend/app backend/migrations`:
    ```
    backend/app/services/content_service.py | 54 +++++++++++++++++++++++++--------
    1 file changed, 41 insertions(+), 13 deletions(-)
    ```
    Изменён только файл `content_service.py`.
- VPS `kz-vps`:
  - `df -h /`: свободно **3.3G** (занято 35G из 40G, 92%).
  - Конфигурационные файлы:
    - `.env`: `-rw------- 1 ubuntu ubuntu 1679`, SHA-256 `a4df9bd96793327995622af31fca575820045228709e55f4a4cad90534f37db6`
    - `compose.yml`: `-rw-r--r-- 1 ubuntu ubuntu 2901`, SHA-256 `21fe1ed7010e083625c9669da12bd1aa766cf9a231958be35ba27615491a89b9`
    - `secrets/firebase-service-account.json`: `-rw------- 1 10001 10001 2400`, SHA-256 `677107719d64976980d59cc7c7cd9f4fa0bfa3d1b2d25666668e56b04f6f1cc1`
  - `alembic current`: `0016_business_android_app_id (head)`.
  - База данных (READ ONLY):
    - `businesses`: 2
    - `cards`: 1711
    - `transactions`: 11411
    - `users`: 4
    - `promotions`: 1 (`kind: banner`, `is_global: f`, привязан к бизнесу)
    - `devices`: 4 (`kz.cashbackone.mobile`: 2, `kz.cashbackone.keremet`: 2)

---

## 3. Шаг 2: Сверка исходников на VPS

- Сверены 92 файла `backend/app` и `backend/migrations` на VPS с коммитом `0b9aae4` через `sha256sum -c --quiet`.
- Расхождений нет (0 файлов).

---

## 4. Шаг 3: Резервные копии и образ отката

- Каталог резервных копий: `/opt/cashback-one/backups/banners-20261106T061703Z/`
- Файлы копий:
  - `pg.sql.gz`: **719 872 байт** (~703K), SHA-256 `decbbb64dd4b7522442137b81949845390a682f5a862f91dca1d6a8b4e1dc09d`. Проверка `gzip -t` — успешно; строка завершения дампа присутствует (count=1).
  - `env.bak`: **1 679 байт**, права `600`, SHA-256 `a4df9bd96793327995622af31fca575820045228709e55f4a4cad90534f37db6` (совпадает с `.env`).
  - `compose.yml.bak`: **2 901 байт**, права `600`, SHA-256 `21fe1ed7010e083625c9669da12bd1aa766cf9a231958be35ba27615491a89b9` (совпадает с `compose.yml`).
  - `backend-src.tgz`: **32 014 336 байт** (31M), SHA-256 `6c2b254669ba47ed3a4e599cbe4926b3448ec241937b4bda3b61eafceb5af8a1`.
- Образ отката:
  - Тег: `cashback-backend:rollback-banners-20261106T061703Z`
  - Image ID: `sha256:9783deafd9f3ee13fc938dae90c30cbe637aaa33dd3fc47d3b452676c3c5cd6d`

---

## 5. Шаг 4: Архив и сборка

- Архив сформирован из коммита `6a9fa18` (`backend` без `tests`, `.env`, `.venv`):
  - Путь: `/tmp/cashback-backend.tgz`
  - SHA-256 на Mac: `96ca5f34ad0520fdb8d3d6c8e0ef9ceed2b169c0153e6d98e7ab66f0b4942408`
  - SHA-256 на VPS: `96ca5f34ad0520fdb8d3d6c8e0ef9ceed2b169c0153e6d98e7ab66f0b4942408` (побайтно совпадает).
- Архив распакован в `/opt/cashback-one`.
- Сборка Docker-образа `cashback-backend:local`:
  ```
  Successfully built cd1634cc3f70
  Successfully tagged cashback-backend:local
  sha256:cd1634cc3f70f8ab6dca4517505598203989cd1f698f44f42afdd5a3eaf64f2b
  ```

---

## 6. Шаг 5: Проверка миграций и перезапуск backend

- Команда: `docker compose up migration`
- Сырой вывод:
  ```text
   Container cashback-postgres  Running
   Container cashback-migration  Recreate
   Container cashback-migration  Recreated
  Attaching to cashback-migration
  cashback-migration  | INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
  cashback-migration  | INFO  [alembic.runtime.migration] Will assume transactional DDL.
  cashback-migration exited with code 0
  ```
  Статус: `Exited (0)`. Голова alembic не изменилась: `0016_business_android_app_id`.
- Пересоздание контейнера: `docker compose up -d --no-build --force-recreate backend`
  Статус: `cashback-backend` запущен и перешёл в статус `healthy`.

---

## 7. Шаг 6: Проверки после выкладки

1. **Готовность сервиса (`/health/ready`):**
   ```json
   {"status":"ready","components":{"database":"ok","redis":"ok"}}
   ```
   HTTP статус: 200 OK.
2. **Журнал контейнера `cashback-backend`:**
   - Ошибок уровня ERROR / CRITICAL нет (`No ERROR/CRITICAL lines found`).
   - Режим push: `push_mode: fcm`.
   - Запросы `POST /agent/heartbeat` стабильно отдают HTTP 200 (`duration_ms` ~350 мс).
3. **Схема и данные БД (READ ONLY):**
   - `alembic current`: `0016_business_android_app_id (head)` (не изменился).
   - Количества записей в точности равны значениям до выкладки:
     - `businesses`: 2
     - `cards`: 1711
     - `transactions`: 11411
     - `users`: 4
     - `promotions`: 1
     - `devices`: 4 (`kz.cashbackone.mobile`: 2, `kz.cashbackone.keremet`: 2)
4. **Конфигурация:**
   SHA-256 `.env`, `compose.yml`, `secrets/firebase-service-account.json` строго прежние.
5. **Публичный API (без авторизации):**
   - `GET /me/promotions?business_id=1ed257c3-0a4f-4569-9571-9b77b9b8d84b` без токена → HTTP 401 `{"error":{"code":"UNAUTHORIZED","message":"Authorization header is required"}}`
   - `GET /me/promotions` без токена → HTTP 401 `{"error":{"code":"UNAUTHORIZED","message":"Authorization header is required"}}`
   - `POST /pos/redemptions` без ключа → HTTP 401 `{"error":{"code":"POS_KEY_MISSING","message":"X-Pos-Key header is required"}}`

---

## 8. План отката при необходимости

Миграций не было, схема базы данных не изменялась. Для отката на прежний образ backend достаточно выполнить на VPS `kz-vps` в каталоге `/opt/cashback-one`:
```bash
docker tag cashback-backend:rollback-banners-20261106T061703Z cashback-backend:local
docker compose up -d --no-build --force-recreate backend
```

---

## 9. Не проверено

Следующие проверки требуют авторизованной сессии настоящего покупателя и физического устройства:
1. Запрос `GET /me/promotions?business_id=<keremet_id>` с действующим JWT токеном покупателя и отображение баннера платформы в карусели акций мобильного приложения KeremEt.
2. Открытие карточки баннера платформы `GET /me/promotions/<banner_id>?business_id=<keremet_id>` в приложении клиента.
