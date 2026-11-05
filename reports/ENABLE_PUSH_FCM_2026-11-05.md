# Отчёт: Включение push через Firebase на production — 2026-11-05

Дата: 2026-11-05 (macOS).  
Выполнено по задаче: `docs/PROMPT_ENABLE_PUSH_FCM_2026-11-05.md`.  
Статус: **СТОП на шаге 7 по правилу: «Если backend не стартовал — сразу верни env.bak и compose из копий, перезапусти, СТОП». Выполнен автоматический возврат конфигурации, production полностью работоспособен.**

---

## 1. Шаг 1. Проверка файла сервисного аккаунта на Mac
Файл: `~/.cashback-one-keys/firebase-service-account.json`
- Файл существует: `True`
- Размер: **2400 байт**
- Права: `0o600` (`-rw-------`, `is_600: True`)
- SHA-256: `677107719d64976980d59cc7c7cd9f4fa0bfa3d1b2d25666668e56b04f6f1cc1`
- Валидный JSON: `True`
- `type == "service_account"`: `True`
- `project_id == "cashback-one-loyalty"`: `True`
- Проверка на утечку ключа: `private_key_id` **не** начинается на скомпрометированный префикс `6e66f2a7` (`is_leaked_key: False`).
- Файл не отслеживается git (`git status --short` чист относительно ключей).

---

## 2. Шаг 2. Состояние VPS до изменений
- Контейнеры:
  - `cashback-backend`: `Up About an hour (healthy)`, образ `cashback-backend:local`
  - `cashback-postgres`: `Up 2 weeks (healthy)`
  - `cashback-redis`: `Up 2 weeks (healthy)`
- `/health/ready`: `HTTP 200` `{"status":"ready","components":{"database":"ok","redis":"ok"}}`
- Текущий образ backend: `sha256:37b2882a66a1b7fa0f21f63128d2ba881bf463eeb82cf8a045e4999bd0fd4b2e`
- Пользователь процесса в контейнере: `uid=10001(appuser) gid=10001(appgroup) groups=10001(appgroup)`
- Подключение `.env` в `compose.yml`: через директиву `env_file: .env`
- Переменные `PUSH_*` и `FCM_*` в `.env`: **отсутствуют** (0 переменных).

---

## 3. Шаг 3. Резервные копии на VPS
- Отметка времени: `20261104T192034Z`
- Каталог: `/opt/cashback-one/backups/push-20261104T192034Z/`
- Файлы копий:
  - `env.bak`: 1 552 байта, права `600`, SHA-256 `f49bf4829b1a524998ce2f14373c12a6a1daa4480bf1aad67eddce81399e72ec` (совпадает с `.env`)
  - `compose.yml`: 2 668 байт, SHA-256 `9c0516300ad796641b595f59df621f25193d42aafda83ccc11308e08efa5fd0b`

---

## 4. Шаг 4. Установка файла на VPS
1. Файл скопирован через `scp` в `/tmp/firebase-service-account.json`. Хеш на VPS совпал: `677107719d64976980d59cc7c7cd9f4fa0bfa3d1b2d25666668e56b04f6f1cc1`.
2. Каталог `/opt/cashback-one/secrets/` настроен с правами `700` (`drwx------`) и владельцем `10001:10001`.
3. Файл перемещён в `/opt/cashback-one/secrets/firebase-service-account.json` с правами `600` (`-rw-------`) и владельцем `10001:10001`.
4. Итоговый SHA-256: `677107719d64976980d59cc7c7cd9f4fa0bfa3d1b2d25666668e56b04f6f1cc1`.
5. Временный файл в `/tmp` удалён.

---

## 5. Шаг 5. Подключение монтирования в `compose.yml`
В сервисе `backend` добавлено монтирование только для чтения (сервис `migration` не менялся согласно инструкции):

```diff
--- /opt/cashback-one/backups/push-20261104T192034Z/compose.yml
+++ /opt/cashback-one/compose.yml
@@ -61,6 +61,7 @@
     env_file: .env
     volumes:
       - ./secrets:/app/secrets:ro
+      - /opt/cashback-one/secrets/firebase-service-account.json:/run/secrets/firebase-service-account.json:ro
     depends_on:
       postgres:
         condition: service_healthy
```

---

## 6. Шаг 6. Настройка `.env`
В `/opt/cashback-one/.env` добавлены три переменные (все существующие 37 строк сохранены побайтно без изменений):

```text
Old lines count: 37
New lines count: 40
=== Added lines in .env ===
+ PUSH_PROVIDER_MODE=fcm
+ FCM_PROJECT_ID=cashback-one-loyalty
+ FCM_SERVICE_ACCOUNT_FILE=/run/secrets/firebase-service-account.json
```

---

## 7. Шаг 7. Попытка перезапуска и обнаруженная проблема

### Команда:
`docker compose up -d --no-build --force-recreate backend`

### Сырой вывод ошибки:
```text
 Container cashback-redis  Running
 Container cashback-postgres  Running
 Container cashback-migration  Recreate
 Container cashback-migration  Recreated
 Container cashback-backend  Recreate
 Container cashback-backend  Recreated
 Container cashback-postgres  Waiting
 Container cashback-postgres  Healthy
 Container cashback-migration  Starting
 Container cashback-migration  Started
 Container cashback-redis  Waiting
 Container cashback-migration  Waiting
 Container cashback-postgres  Waiting
 Container cashback-postgres  Healthy
 Container cashback-redis  Healthy
 Container cashback-migration  service "migration" didn't complete successfully: exit 1
service "migration" didn't complete successfully: exit 1
```

### Лог контейнера `cashback-migration`:
```text
Traceback (most recent call last):
  File "/usr/local/bin/alembic", line 6, in <module>
    sys.exit(main())
...
  File "/app/migrations/env.py", line 10, in <module>
    from app.core.config import settings
  File "/app/app/core/config.py", line 508, in <module>
    settings = get_settings()
  File "/app/app/core/config.py", line 505, in get_settings
    return Settings()
...
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
  Value error, FCM_SERVICE_ACCOUNT_FILE not found or not a regular file: /run/secrets/firebase-service-account.json [type=value_error, input_value={'app_env': 'production', ... 'fcm_service_account_file': '/run/secrets/firebase-service-account.json'}, input_type=dict]
```

### Причина сбоя:
1. В `compose.yml` сервис `backend` имеет зависимость:
   ```yaml
   depends_on:
     migration:
       condition: service_completed_successfully
   ```
2. При вызове `docker compose up -d --force-recreate backend`, Docker Compose сначала запускает контейнер `cashback-migration`.
3. Сервис `migration` использует `env_file: .env`, поэтому получает переменные `PUSH_PROVIDER_MODE=fcm` и `FCM_SERVICE_ACCOUNT_FILE=/run/secrets/firebase-service-account.json`.
4. При запуске Alembic (`migrations/env.py`) импортирует `settings = get_settings()`, где Pydantic валидирует наличие файла `FCM_SERVICE_ACCOUNT_FILE`.
5. Так как в сервисе `migration` монтирование файла ключа **отсутствовало** (в соответствии с запретом промпта: *«Сервис миграции не трогать»*), валидатор Pydantic в контейнере `migration` упал с ошибкой `FCM_SERVICE_ACCOUNT_FILE not found or not a regular file: /run/secrets/firebase-service-account.json`.
6. Падение `cashback-migration` с кодом 1 заблокировало запуск контейнера `backend`.

---

## 8. Немедленный откат по правилу задачи

Согласно пункту 7 промпта:
> *«Если backend не стартовал — сразу верни `env.bak` и compose из копий, перезапусти, СТОП.»*

Были немедленно выполнены команды восстановления:
```bash
cp /opt/cashback-one/backups/push-20261104T192034Z/env.bak /opt/cashback-one/.env
cp /opt/cashback-one/backups/push-20261104T192034Z/compose.yml /opt/cashback-one/compose.yml
docker compose up -d --no-build --force-recreate backend
```

### Статус после восстановления:
- `docker ps`:
  - `cashback-backend`: `Up 12 seconds (healthy)`
  - `cashback-postgres`: `Up 2 weeks (healthy)`
  - `cashback-redis`: `Up 2 weeks (healthy)`
- `/health/ready`: HTTP 200 `{"status":"ready","components":{"database":"ok","redis":"ok"}}`.
- Файл ключа в `/opt/cashback-one/secrets/firebase-service-account.json` (права `600`, владелец `10001:10001`) сохранён на VPS для следующей попытки.

---

## 9. Рекомендация для успешного подключения

Чтобы `docker compose` мог запускать `backend` (и при необходимости `migration`), требуется одно из двух решений:

1. **Рекомендуемое решение:** Добавить такое же монтирование секрета в сервис `migration` в `compose.yml`:
   ```yaml
     migration:
       build:
         context: ./backend
         dockerfile: Dockerfile
       image: cashback-backend:local
       container_name: cashback-migration
       command: ["alembic", "upgrade", "head"]
       env_file: .env
       volumes:
         - /opt/cashback-one/secrets/firebase-service-account.json:/run/secrets/firebase-service-account.json:ro
   ```
2. **Альтернативное решение:** Запускать перезапуск backend с флагом `--no-deps`:
   `docker compose up -d --no-build --no-deps --force-recreate backend`.
   *(Однако при любом будущем запуске `migration` с существующим `.env` валидация Pydantic снова потребует файл ключа, поэтому вариант 1 надёжнее).*

---

## 10. Повторная попытка (2026-11-05)

Выполнено по задаче: `docs/PROMPT_ENABLE_PUSH_FCM_RETRY_2026-11-05.md`.  
Куратор утвердил решение: монтировать файл секрета только для чтения в **оба** сервиса (`backend` и `migration`). Флаг `--no-deps` не используется.

### 10.1. Проверка исходного состояния до повторной попытки
1. Контейнеры:
   - `cashback-backend`: `Up 26 minutes (healthy)`
   - `cashback-postgres`: `Up 2 weeks (healthy)`
   - `cashback-redis`: `Up 2 weeks (healthy)`
2. Готовность `/health/ready`: HTTP 200 `{"status":"ready","components":{"database":"ok","redis":"ok"}}`.
3. Сверка хешей:
   - `.env`: `f49bf4829b1a524998ce2f14373c12a6a1daa4480bf1aad67eddce81399e72ec` (совпадает с `backups/push-20261104T192034Z/env.bak`).
   - `compose.yml`: `9c0516300ad796641b595f59df621f25193d42aafda83ccc11308e08efa5fd0b` (совпадает с `backups/push-20261104T192034Z/compose.yml`).
   Откат подтверждён как полный.
4. Пользователь в образе:
   `docker run --rm --entrypoint id cashback-backend:local`
   Вывод: `uid=10001(appuser) gid=10001(appgroup) groups=10001(appgroup)` (пользователь процесса совпадает).

### 10.2. Резервная копия перед повторной попыткой
- Каталог: `/opt/cashback-one/backups/push-20261104T194927Z-retry/`
- `env.bak`: 1 552 байта, права `600`, SHA-256 `f49bf4829b1a524998ce2f14373c12a6a1daa4480bf1aad67eddce81399e72ec`.
- `compose.yml`: 2 668 байт, SHA-256 `9c0516300ad796641b595f59df621f25193d42aafda83ccc11308e08efa5fd0b`.

### 10.3. Изменения в `compose.yml`
Монтирование `/opt/cashback-one/secrets/firebase-service-account.json:/run/secrets/firebase-service-account.json:ro` добавлено в сервисы `migration` и `backend`:

```diff
--- /opt/cashback-one/backups/push-20261104T194927Z-retry/compose.yml
+++ /opt/cashback-one/compose.yml
@@ -46,6 +46,8 @@
     container_name: cashback-migration
     command: ["alembic", "upgrade", "head"]
     env_file: .env
+    volumes:
+      - /opt/cashback-one/secrets/firebase-service-account.json:/run/secrets/firebase-service-account.json:ro
     depends_on:
       postgres:
         condition: service_healthy
@@ -61,6 +63,7 @@
     env_file: .env
     volumes:
       - ./secrets:/app/secrets:ro
+      - /opt/cashback-one/secrets/firebase-service-account.json:/run/secrets/firebase-service-account.json:ro
     depends_on:
       postgres:
         condition: service_healthy
```

### 10.4. Изменения в `.env`
В `/opt/cashback-one/.env` добавлены те же три переменные (все исходные 37 строк сохранены без изменений):
```text
Old lines count: 37
New lines count: 40
=== Added lines in .env ===
+ PUSH_PROVIDER_MODE=fcm
+ FCM_PROJECT_ID=cashback-one-loyalty
+ FCM_SERVICE_ACCOUNT_FILE=/run/secrets/firebase-service-account.json
```

### 10.5. Перезапуск
Команда: `docker compose up -d --no-build --force-recreate backend`

**Сырой вывод:**
```text
 Container cashback-postgres  Running
 Container cashback-redis  Running
 Container cashback-migration  Recreate
 Container cashback-migration  Recreated
 Container cashback-backend  Recreate
 Container cashback-backend  Recreated
 Container cashback-postgres  Waiting
 Container cashback-postgres  Healthy
 Container cashback-migration  Starting
 Container cashback-migration  Started
 Container cashback-redis  Waiting
 Container cashback-migration  Waiting
 Container cashback-postgres  Waiting
 Container cashback-redis  Healthy
 Container cashback-postgres  Healthy
 Container cashback-migration  Exited
 Container cashback-backend  Starting
 Container cashback-backend  Started
```

- Статус `cashback-migration`: `Exited (0)`.
  Лог `docker logs cashback-migration`:
  ```text
  INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
  INFO  [alembic.runtime.migration] Will assume transactional DDL.
  ```
  Миграций нет (голова уже `0015`), валидация Pydantic Settings прошла успешно.
- Статус `cashback-backend`: `Up (healthy)`.
  Лог `docker logs cashback-backend`:
  ```text
  INFO:     Started server process [1]
  INFO:     Waiting for application startup.
  INFO:     Application startup complete.
  INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
  ```
  Ошибок конфигурации нет, запросы к `/health/ready` и `/agent/heartbeat` отдаются со статусом 200.

### 10.6. Проверка авторизации в Firebase (без отправки покупателям)
Проверка выполнена внутри контейнера `cashback-backend` одноразовой командой Python через существующий `FcmPushSender`:

1. **Получение OAuth2 токена доступа через сервисный аккаунт:**
   - Вывод: `Access token: ok, token retrieved successfully`
   - Токен успешно подписан по RS256 и получен от `https://oauth2.googleapis.com/token`.
2. **Запрос FCM v1 с `"validate_only": true` на несуществующий токен (`invalid-token-for-validation`):**
   - HTTP статус: `400`
   - `error.status`: `INVALID_ARGUMENT`
   - `errorCode`: `INVALID_ARGUMENT`
   - Ответ не является 401 (Unauthorized) или 403 (Forbidden) — авторизация в проекте Google Cloud / Firebase `cashback-one-loyalty` подтверждена; сообщение физически никуда не отправлялось.

### 10.7. Проверки API и БД после включения
- `GET /health/ready`: HTTP 200 `{"status":"ready","components":{"database":"ok","redis":"ok"}}`.
- `POST /pos/redemptions` без `X-Pos-Key`: HTTP 401 `{"error":{"code":"POS_KEY_MISSING","message":"X-Pos-Key header is required"}}`.
- Количество записей в таблице `devices` (READ ONLY): **`0`**.

---

## 11. План отката при необходимости

Если потребуется отключить push:
```bash
# На VPS kz-vps в каталоге /opt/cashback-one:
cp /opt/cashback-one/backups/push-20261104T194927Z-retry/env.bak /opt/cashback-one/.env
cp /opt/cashback-one/backups/push-20261104T194927Z-retry/compose.yml /opt/cashback-one/compose.yml
docker compose up -d --no-build --force-recreate backend
```
Файл `/opt/cashback-one/secrets/firebase-service-account.json` остаётся в защищённом каталоге.

