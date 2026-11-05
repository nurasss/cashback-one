# Отчёт: Выкладка облака и кабинета нового курса — 2026-11-04

Дата: 2026-11-04 (macOS).  
Выполнено по задаче: `docs/PROMPT_DEPLOY_NEW_COURSE_2026-11-04.md`.  
Статус: **Успешно выложено на VPS `kz-vps` и хостинг кабинета `https://cashback-qr.poscenter.kz`. Все проверки пройдены.**

---

## 1. Контекст и объем изменений

В production выложены принятые задачи нового курса из коммита `2c73120` (backend и кабинет — коммит `4dcbef4`):
- Push-уведомления (миграция `0012_push_devices`);
- Магазины и тексты приложения в кабинете (`0013_business_app_content`);
- Ключи касс и списание через push, маршруты `/pos/*` (`0014_pos_keys`);
- Скрытие использованного кода в уведомлениях (`0015_notification_redemption`);
- Кабинет: блоки «Кассы», «Магазины и инфо», формулировки ключа агента, CORS c методом `PUT`.

**Push-уведомления остаются выключенными** (`PUSH_PROVIDER_MODE=disabled` по умолчанию), так как сервисный аккаунт Firebase ещё не подключен. Файл `.env` на VPS не изменялся.

---

## 2. Часть 1. Backend

### 2.1. Исходное состояние до выкладки
- `git log -1 --oneline`: `2c73120 docs: per-client roadmap, Cash redemption code, POS API, Firebase setup, task reports`
- `git status --short backend/`: чисто (нет незакоммиченных изменений в `backend/`)
- Доступное место на VPS (`df -h /`): **4.0G** свободно (90% занято)
- Текущий Docker-образ backend: `cashback-backend:local` (`0399b053e1e7`)
- Версия миграций до выкладки: `alembic current` → `0011_customer_avatar (head)`
- Данные в БД до выкладки (READ ONLY):
  - `businesses`: 2
  - `agents`: 1
  - `cards`: 1711
  - `transactions`: 11411
  - `users`: 4
  - `promotions`: 0
  - `notifications`: 0
  - `devices`: 0

### 2.2. Побайтная сверка исходников на VPS с коммитом `098da49`
Файлы `backend/app` и `backend/migrations` на VPS проверены по SHA-256 против коммита предыдущей выкладки `098da49`:
- Всего проверено файлов: **82**
- Результат: **все 82 файла побайтно совпали** (`sha256sum -c` завершился успешно, 0 расхождений).
- Число файлов в `backend/app` и `backend/migrations` без `__pycache__`: ровно 82 (посторонних файлов нет).

### 2.3. Резервные копии и образ отката
- Отметка времени: `20261104T181330Z`
- Каталог резервной копии: `/opt/cashback-one/backups/newcourse-20261104T181330Z/`
- Файлы копий:
  - `pg.sql.gz`: **706 530 байт**, SHA-256 `ec602499925451b3997ae17a9d4e7f3b01b0badba31cbeffae9801d9b7f676c7`. Проверка целостности `gzip -t` — успешно; маркер `-- PostgreSQL database dump complete` присутствует.
  - `env.bak`: **1 552 байта**, права 600 (`-rw-------`), SHA-256 `f49bf4829b1a524998ce2f14373c12a6a1daa4480bf1aad67eddce81399e72ec` (совпадает с действующим `/opt/cashback-one/.env`).
  - `backend-src.tgz`: **32 014 060 байт**, SHA-256 `86250d82eb85c0d7397cf079e0bacf0bb2b33cf3dd7e98187b50c2c90206e789`.
- Образ отката:
  - Имя: `cashback-backend:rollback-newcourse-20261104T181330Z`
  - Image ID: `0399b053e1e7` (368MB)

### 2.4. Сборка архива и передача на VPS
- Архив сформирован командой `git archive 2c73120 backend ':!backend/tests' --format=tar.gz -o /tmp/cashback-backend.tgz` (без `tests`, `.env`, `.venv`).
- Размер: **126 301 байт**.
- SHA-256 на Mac: `e113a160d30b0ecd34f99fa9ed03c0db3fee565e5b24c6c55e1672344d74eae4`.
- SHA-256 на VPS (`/tmp/cashback-backend.tgz`): `e113a160d30b0ecd34f99fa9ed03c0db3fee565e5b24c6c55e1672344d74eae4` (побайтно совпадает).

### 2.5. Сборка образа и миграция базы данных
1. Архив распакован на VPS: `tar -xzf /tmp/cashback-backend.tgz -C /opt/cashback-one`.
2. Собран новый образ: `docker compose build`. Новый Image ID: `37b2882a66a1` (`cashback-backend:local`).
3. Запущен контейнер миграции: `docker compose up migration`.
   **Сырой вывод миграции:**
   ```text
   Container cashback-postgres  Running
   Container cashback-migration  Recreate
   Container cashback-migration  Recreated
   Attaching to cashback-migration
   cashback-migration  | INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
   cashback-migration  | INFO  [alembic.runtime.migration] Will assume transactional DDL.
   cashback-migration  | INFO  [alembic.runtime.migration] Running upgrade 0011_customer_avatar -> 0012_push_devices, Push notification devices: app_id, last_seen_at, disabled_at, unique push_token.
   cashback-migration  | INFO  [alembic.runtime.migration] Running upgrade 0012_push_devices -> 0013_business_app_content, Business stores and localized app texts.
   cashback-migration  | INFO  [alembic.runtime.migration] Running upgrade 0013_business_app_content -> 0014_pos_keys, POS cash register access keys.
   cashback-migration  | INFO  [alembic.runtime.migration] Running upgrade 0014_pos_keys -> 0015_notification_redemption, Notification link to redemption code.
   cashback-migration exited with code 0
   ```
   Контейнер `cashback-migration` завершился с кодом 0 (`Exited (0)`).
4. Пересоздан и запущен сервис `backend`: `docker compose up -d --no-build backend`.
   Статус: `cashback-backend` запущен и перешёл в статус `healthy`.

### 2.6. Проверки backend после выкладки
1. **Проверка готовности (`/health/ready`):**
   ```json
   {"status":"ready","components":{"database":"ok","redis":"ok"}}
   ```
   HTTP статус: 200 OK. Ошибок в журнале контейнера нет (`Application startup complete`). Heartbeat агента возвращает 200.
2. **Проверка схемы БД (READ ONLY):**
   - `alembic current`: `0015_notification_redemption (head)`.
   - Новые таблицы созданы: `pos_keys`, `business_stores`.
   - Новые колонки присутствуют:
     - `devices.app_id`: `character varying`
     - `devices.last_seen_at`: `timestamp with time zone`
     - `devices.disabled_at`: `timestamp with time zone`
     - `businesses.app_texts`: `json`
     - `notifications.redemption_id`: `uuid`
   - Количество записей в таблицах не изменилось:
     - `businesses`: 2
     - `agents`: 1
     - `cards`: 1711
     - `transactions`: 11411
     - `users`: 4
     - `promotions`: 0
     - `notifications`: 0
     - `devices`: 0 (удаление дубликатов в миграции 0012 не требовалось, записей было 0)
     - `pos_keys`: 0
     - `business_stores`: 0
3. **Проверки публичного API (без авторизации, без создания данных):**
   - `POST /pos/redemptions` без `X-Pos-Key` → HTTP 401 `{"error":{"code":"POS_KEY_MISSING","message":"X-Pos-Key header is required"}}`
   - `POST /pos/redemptions` с `X-Pos-Key: pos_invalid_xxx` → HTTP 401 `{"error":{"code":"POS_KEY_INVALID","message":"Invalid POS API key"}}`
   - `PUT /me/push-token` без токена → HTTP 401 `{"error":{"code":"UNAUTHORIZED","message":"Authorization header is required"}}`
   - `GET /me/app-content?business_id=00000000-0000-0000-0000-000000000000` без токена → HTTP 401 `{"error":{"code":"UNAUTHORIZED","message":"Authorization header is required"}}`
   - `POST /agent/redemptions` с неверным `X-Agent-Key` → HTTP 401 `{"error":{"code":"AGENT_KEY_INVALID","message":"Invalid agent API key"}}` (не 500)
4. **Проверка CORS Preflight:**
   Запрос `OPTIONS /admin/businesses/00000000-0000-0000-0000-000000000000/app-texts` c `Origin: https://cashback-qr.poscenter.kz` и `Access-Control-Request-Method: PUT`:
   - HTTP статус: 200 OK
   - `Access-Control-Allow-Origin`: `https://cashback-qr.poscenter.kz`
   - `Access-Control-Allow-Methods`: `GET, POST, PUT, PATCH, DELETE` (метод `PUT` разрешён)
   - `Access-Control-Allow-Credentials`: `true`

---

## 3. Часть 2. Кабинет и сайт

### 3.1. Исходное состояние до выкладки
- Живой `index.html` на сайте до выкладки: SHA-256 `c4d8a0ce86927d3bdba26e0eb2a35695579e57aa539526222016956c6c7fa92d` (совпал с ожидаемым).

### 3.2. Сборка дистрибутива кабинета
- `npx vitest run --maxWorkers=1`: **175 passed / 22 test files** (время: 47.29s).
- `npm run typecheck`: успешно, 0 ошибок.
- `npm run lint`: успешно, 0 ошибок.
- Сборка production: `VITE_API_BASE_URL=https://api.cashback-qr.poscenter.kz VITE_ALLOW_INSECURE_HTTP=0 npm run build` (vite v8.3.2).
- Проверка артефактов в `admin/dist`:
  - `https://api.cashback-qr.poscenter.kz` присутствует в `assets/AdminRoutes-Dgq4f0pf.js`.
  - `localhost` отсутствует во всех файлах `admin/src` и в `admin/dist/assets/AdminRoutes*`.
  - Ссылка на APK в `admin/dist/index.html`: `cashback-one-1.0.10.apk`.

### 3.3. Таблица файлов дистрибутива
Сравнение файлов `admin/dist` с действующим сервером по HTTPS (размер и SHA-256):

| Путь | Размер (байт) | SHA-256 | Статус |
|---|---|---|---|
| `assets/AdminRoutes-Dgq4f0pf.js` | 196 616 | `9d1491a7d9a66e15a0364d8619df645d4cb8c93b33400f8d8251615ab3d58c15` | **новый** |
| `assets/index-CKKFaio1.js` | 305 284 | `57c00c734ebf62082c9d265d43a9753cc365a1d4b49066df2f615a6378c6922b` | **новый** |
| `assets/index-rT6CoaAM.css` | 47 241 | `467fc6afffe3c6713b5641c412f6dbaaacd53f30c6cb0e14628e7d14f8d9db5c` | **новый** |
| `index.html` | 3 093 | `a447375a2e1e714b59b28346981d624446a2a86d75ecd6e4076c67d058e8c25b` | **новый** |
| `brand-mark.png` | 1 892 | `8b62b9abc678d5f0da00b7ccb4349bdc907a14494e6c17ed59e9b93546762a23` | совпадает |
| `favicon.png` | 1 892 | `8b62b9abc678d5f0da00b7ccb4349bdc907a14494e6c17ed59e9b93546762a23` | совпадает |
| `logo-white.png` | 3 353 | `88469fc29d70e14f6f15180614ff42014c40eda155e09e07aff81de29499169e` | совпадает |
| `logo.png` | 7 762 | `fb14bd7397b273aa7c611ed2caa22aaafbf0c0a260f24a35d92124b30201d5f2` | совпадает |
| `robots.txt` | 130 | `034311b328b14f981825fe31db58eab33afbd1840b086eb72eeda7a2c6169bf7` | совпадает |
| `sitemap.xml` | 275 | `23f2cfc3ba9dc9e409c3b1c31f03b73c82a456ad9cc7312c191dd27731fe39ea` | совпадает |
| `assets/roboto-*.woff/woff2` (24 файла) | — | — | совпадает |
| `landing/screen-*.png` (4 файла) | — | — | совпадает |

К загрузке: ровно **4 файла** (3 в `assets/*` и `index.html`).

### 3.4. Резервная копия
- Папка: `~/.local/share/cashback-one/backups/landing-20261104T182313Z-newcourse/`
- Файл: `index.html` (3 093 байта, SHA-256 `c4d8a0ce86927d3bdba26e0eb2a35695579e57aa539526222016956c6c7fa92d`).

### 3.5. Выкладка по FTPS
Выкладка проведена по протоколу TLS 1.2 с проверкой сертификата (`SSL_CERT_FILE=/etc/ssl/cert.pem`), режимом `PROT P`, `TYPE I`, с возвратом в корень перед сменой папок. Каждый файл загружался под временным именем `.{имя}.upload-{uuid}`, скачивался обратно и сверялся по размеру и SHA-256, после чего атомарно переименовывался. Файл `index.html` загружен строго последним.

**Сырой вывод выкладки:**
```text
Connecting to FTPS...
FTPS connected and authenticated.

Uploading admin/dist/assets/AdminRoutes-Dgq4f0pf.js -> cashback-qr.poscenter.kz/assets/.AdminRoutes-Dgq4f0pf.js.upload-0cd92c38 (size=196616)...
Verified .AdminRoutes-Dgq4f0pf.js.upload-0cd92c38 matches local. Renaming to AdminRoutes-Dgq4f0pf.js...
SUCCESS: cashback-qr.poscenter.kz/assets/AdminRoutes-Dgq4f0pf.js deployed and verified. SHA-256: 9d1491a7d9a66e15a0364d8619df645d4cb8c93b33400f8d8251615ab3d58c15

Uploading admin/dist/assets/index-CKKFaio1.js -> cashback-qr.poscenter.kz/assets/.index-CKKFaio1.js.upload-2d9b8674 (size=305284)...
Verified .index-CKKFaio1.js.upload-2d9b8674 matches local. Renaming to index-CKKFaio1.js...
SUCCESS: cashback-qr.poscenter.kz/assets/index-CKKFaio1.js deployed and verified. SHA-256: 57c00c734ebf62082c9d265d43a9753cc365a1d4b49066df2f615a6378c6922b

Uploading admin/dist/assets/index-rT6CoaAM.css -> cashback-qr.poscenter.kz/assets/.index-rT6CoaAM.css.upload-a5ee5098 (size=47241)...
Verified .index-rT6CoaAM.css.upload-a5ee5098 matches local. Renaming to index-rT6CoaAM.css...
SUCCESS: cashback-qr.poscenter.kz/assets/index-rT6CoaAM.css deployed and verified. SHA-256: 467fc6afffe3c6713b5641c412f6dbaaacd53f30c6cb0e14628e7d14f8d9db5c

Uploading admin/dist/index.html -> cashback-qr.poscenter.kz/.index.html.upload-e17cd329 (size=3093)...
Verified .index.html.upload-e17cd329 matches local. Renaming to index.html...
SUCCESS: cashback-qr.poscenter.kz/index.html deployed and verified. SHA-256: a447375a2e1e714b59b28346981d624446a2a86d75ecd6e4076c67d058e8c25b

Checking for leftover temp files across deployed directories...
No temp files found in cashback-qr.poscenter.kz.
No temp files found in cashback-qr.poscenter.kz/assets.

All files successfully uploaded and verified on FTPS.
```

### 3.6. Проверка опубликованных файлов по HTTPS (`Cache-Control: no-cache`)
```text
=== 1. Проверка загруженных файлов по HTTPS ===
[OK] assets/AdminRoutes-Dgq4f0pf.js: HTTP 200, Content-Type: application/javascript
     Local:  size=196616, sha256=9d1491a7d9a66e15a0364d8619df645d4cb8c93b33400f8d8251615ab3d58c15
     Remote: size=196616, sha256=9d1491a7d9a66e15a0364d8619df645d4cb8c93b33400f8d8251615ab3d58c15
[OK] assets/index-CKKFaio1.js: HTTP 200, Content-Type: application/javascript
     Local:  size=305284, sha256=57c00c734ebf62082c9d265d43a9753cc365a1d4b49066df2f615a6378c6922b
     Remote: size=305284, sha256=57c00c734ebf62082c9d265d43a9753cc365a1d4b49066df2f615a6378c6922b
[OK] assets/index-rT6CoaAM.css: HTTP 200, Content-Type: text/css
     Local:  size=47241, sha256=467fc6afffe3c6713b5641c412f6dbaaacd53f30c6cb0e14628e7d14f8d9db5c
     Remote: size=47241, sha256=467fc6afffe3c6713b5641c412f6dbaaacd53f30c6cb0e14628e7d14f8d9db5c
[OK] index.html: HTTP 200, Content-Type: text/html
     Local:  size=3093, sha256=a447375a2e1e714b59b28346981d624446a2a86d75ecd6e4076c67d058e8c25b
     Remote: size=3093, sha256=a447375a2e1e714b59b28346981d624446a2a86d75ecd6e4076c67d058e8c25b

=== 2. Проверка живого index.html ===
Live home SHA-256:  a447375a2e1e714b59b28346981d624446a2a86d75ecd6e4076c67d058e8c25b
Dist index SHA-256: a447375a2e1e714b59b28346981d624446a2a86d75ecd6e4076c67d058e8c25b

=== 3. Проверка app/version.json ===
version.json size: 169, Content-Type: application/json
version.json content: {
  "latest_version": "1.0.10",
  "latest_version_code": 11,
  "min_version_code": 1,
  "download_url": "https://cashback-qr.poscenter.kz/app/cashback-one-1.0.10.apk"
}
version.json sha256: 7e1c460a67c79823afd5fff7a5af1cf02ddfc124f556510c5d723dcddc4bd64b

=== 4. Проверка APK файлов (HEAD / length) ===
cashback-one-1.0.10.apk: length=68600435 (expected 68600435), Content-Type=application/vnd.android.package-archive
cashback-one-1.0.11-test.apk: length=68601127 (expected 68601127), Content-Type=application/vnd.android.package-archive

ALL HTTPS CHECKS PASSED!
```

### 3.7. Проверка в реальном браузере (Google Chrome, Playwright)
```text
=== Checking RU Landing: https://cashback-qr.poscenter.kz/ ===
H1 text: Бонусная карта в телефоне
Console errors: []

=== Checking KK Landing: https://cashback-qr.poscenter.kz/ ===
H1 text (KK): Бонустық карта телефоныңызда
Console errors: []

=== Checking Admin Login: https://cashback-qr.poscenter.kz/admin/login ===
Login form visible: True
Body font-family: Times
Button font-family: Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif
Console errors (excluding 401 session check): []

ALL BROWSER CHECKS PASSED!
```

---

## 4. План отката

### Откат backend:
```bash
# На VPS kz-vps в каталоге /opt/cashback-one:
# 1. Если ещё не заведены новые данные в pos_keys и business_stores, откатить миграции:
docker exec -i cashback-backend alembic downgrade 0011_customer_avatar

# 2. Переключить образ на резервный и перезапустить:
docker tag cashback-backend:rollback-newcourse-20261104T181330Z cashback-backend:local
docker compose up -d --no-build --force-recreate backend
```

### Откат кабинета / сайта:
Загрузить сохранённый `index.html` из резервной копии:
`~/.local/share/cashback-one/backups/landing-20261104T182313Z-newcourse/index.html`
на FTPS-хостинг в корень сайта под временным именем с последующим переименованием в `index.html`. Сайт вернётся к состоянию коммита `f9ee834` (прежний SHA-256 `c4d8a0ce86927d3b…`).

---

## 5. Что осталось непроверенным

1. **Авторизованный вход в кабинет**: реальный вход под учётной записью администратора не производился, чтобы не создавать сессий и не модифицировать данные.
2. **Выдача реального ключа кассы**: создание ключа кассы на production не выполнялось.
3. **Настоящая отправка push-уведомлений**: Firebase Cloud Messaging пока выключен (`PUSH_PROVIDER_MODE=disabled`), сервисный аккаунт Firebase ещё не настроен на VPS. При обращении к `/pos/redemptions` касса будет ожидать включения провайдера.
