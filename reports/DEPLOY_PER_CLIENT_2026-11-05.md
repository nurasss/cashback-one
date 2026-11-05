# Отчёт: Выкладка сервера и кабинета для приложений клиентов — 2026-11-05

Дата: 2026-11-05 (macOS).  
Выполнено по задаче: `docs/PROMPT_DEPLOY_PER_CLIENT_2026-11-05.md`.  
Коммит кода: **`0b9aae4`** (миграция `0016_business_android_app_id`, per-client apps).  
Статус: **Успешно завершено.** Backend и кабинет выложены на production, все проверки пройдены.

---

## 1. Сбои и нештатные ситуации в ходе работы

1. **Шаг 1.1 (проверка прав и хеша сервисного аккаунта):** Команда `ls -l secrets/firebase-service-account.json` от пользователя `ubuntu` вернула `Permission denied`, так как каталог `secrets/` защищён правами `0700` с владельцем `10001:10001` (согласно отчету включения push). Проверка выполнена через `sudo ls -l` и `sudo sha256sum`. Хеш и права полностью совпали с ожидаемыми.
2. **Шаг 2.3 (проверка HTTPS в Python 3.14):** Первичный запуск скрипта проверки ассетов завершился с ошибкой `CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`, так как стандартный Python 3.14 Homebrew на Mac требует явного указания системного хранилища сертификатов. Скрипт перезапущен с `SSL_CERT_FILE=/etc/ssl/cert.pem` и контекстом `ssl.create_default_context(cafile="/etc/ssl/cert.pem")` — все проверки завершились успешно.

---

## 2. Часть 1. Backend

### 2.1. Исходное состояние до выкладки
- `git log -1 --oneline`: `a9bc7db` (HEAD, не старше `0b9aae4`).
- `git status --short backend/ admin/src`: пуст.
- `df -h /` на VPS: `3.3G` свободно (40G всего, 35G занято).
- Хеши и права конфигурационных файлов на VPS:
  - `.env`: `-rw------- 1 ubuntu ubuntu 1679`, SHA-256 `a4df9bd96793327995622af31fca575820045228709e55f4a4cad90534f37db6`
  - `compose.yml`: `-rw-r--r-- 1 ubuntu ubuntu 2901`, SHA-256 `21fe1ed7010e083625c9669da12bd1aa766cf9a231958be35ba27615491a89b9`
  - `secrets/firebase-service-account.json`: `-rw------- 1 10001 10001 2400`, SHA-256 `677107719d64976980d59cc7c7cd9f4fa0bfa3d1b2d25666668e56b04f6f1cc1`
- `alembic current` на VPS: `0015_notification_redemption (head)`.
- Количества в базе данных (READ ONLY):
  - `businesses`: 2
  - `agents`: 1
  - `cards`: 1711
  - `transactions`: 11411
  - `users`: 4
  - `promotions`: 0
  - `notifications`: 0
  - `devices` by `app_id`: `kz.cashbackone.mobile`: 2 (всего: 2)
  - `pos_keys`: 0

### 2.2. Сверка исходников на VPS
- Проверены все 91 файл в `backend/app` и `backend/migrations` на VPS против коммита прежней выкладки `2c73120` через `sha256sum -c --quiet`.
- Расхождений нет (0 файлов отличаются).

### 2.3. Резервные копии и образ отката
- Каталог резервных копий: `/opt/cashback-one/backups/perclient-20261105T174601Z/`
- Файлы копий:
  - `pg.sql.gz`: **717 388 байт** (701K), SHA-256 `bc1650db4e6214ba8544311e4c8f0d0d836cc754c8203904f5f1b02c4b6dfdc8`. Проверка `gzip -t` — успешно; маркер `-- PostgreSQL database dump complete` присутствует (count=1).
  - `env.bak`: **1 679 байт**, права `600`, SHA-256 `a4df9bd96793327995622af31fca575820045228709e55f4a4cad90534f37db6` (совпадает с `.env`).
  - `compose.yml.bak`: **2 901 байт**, права `600`, SHA-256 `21fe1ed7010e083625c9669da12bd1aa766cf9a231958be35ba27615491a89b9` (совпадает с `compose.yml`).
  - `backend-src.tgz`: **32 014 336 байт** (31M), SHA-256 `cef7d2378ae1a7312e6748ef021080c80870e4d60831ae013fa9c2d198876711`.
- Образ отката:
  - Тег: `cashback-backend:rollback-perclient-20261105T174601Z`
  - Image ID: `sha256:37b2882a66a1b7fa0f21f63128d2ba881bf463eeb82cf8a045e4999bd0fd4b2e`

### 2.4. Архив и сборка
- Архив из коммита `0b9aae4` (`backend` без `tests`, `.env`, `.venv`):
  - Путь: `/tmp/cashback-backend.tgz`
  - SHA-256 на Mac: `9018b465e43c4ba388d7b2a4037f87319a56a8402bf2b82fe6634929d1245450`
  - SHA-256 на VPS: `9018b465e43c4ba388d7b2a4037f87319a56a8402bf2b82fe6634929d1245450` (побайтно совпадает).
- Архив распакован в `/opt/cashback-one`.
- Сборка нового образа `cashback-backend:local`: `Successfully built 9783deafd9f3`.

### 2.5. Миграция базы данных
Команда: `docker compose up migration`  
Сырой вывод:
```text
 Container cashback-postgres  Running
 Container cashback-migration  Recreate
 Container cashback-migration  Recreated
Attaching to cashback-migration
cashback-migration  | INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
cashback-migration  | INFO  [alembic.runtime.migration] Will assume transactional DDL.
cashback-migration  | INFO  [alembic.runtime.migration] Running upgrade 0015_notification_redemption -> 0016_business_android_app_id, Add android_app_id to businesses table.
cashback-migration exited with code 0
```
Статус контейнера: `Exited (0)`.

### 2.6. Перезапуск backend
Команда: `docker compose up -d --no-build --force-recreate backend`  
Статус: `cashback-backend` запущен и перешёл в статус `healthy`.

### 2.7. Проверки backend после выкладки
1. **Готовность сервиса (`/health/ready`):**
   ```json
   {"status":"ready","components":{"database":"ok","redis":"ok"}}
   ```
   HTTP статус: 200 OK.
2. **Журнал запуска backend:**
   Ошибок нет (`Application startup complete`, `Uvicorn running on http://0.0.0.0:8000`).  
   Режим push: `push_mode: fcm`.
3. **Схема БД (READ ONLY):**
   - `alembic current`: `0016_business_android_app_id (head)`
   - Колонка `businesses.android_app_id`: тип `character varying`, nullable `YES`.
   - Ограничение уникальности `uq_businesses_android_app_id`: присутствует (`contype = 'u'`).
   - Значения `android_app_id` у всех существующих бизнесов: `NULL`.
   - Количества записей в таблицах не изменились:
     - `businesses`: 2
     - `agents`: 1
     - `cards`: 1711
     - `transactions`: 11411
     - `users`: 4
     - `promotions`: 0
     - `notifications`: 0
     - `devices`: 2 (`kz.cashbackone.mobile`: 2)
     - `pos_keys`: 0
4. **Конфигурация:**
   SHA-256 `.env`, `compose.yml`, `secrets/firebase-service-account.json` строго прежние.
5. **Проверки публичного API (без авторизации, без создания данных):**
   - `GET /me/cards?business_id=1ed257c3-0a4f-4569-9571-9b77b9b8d84b` без токена → HTTP 401 `{"error":{"code":"UNAUTHORIZED","message":"Authorization header is required"}}`
   - `GET /me/promotions?business_id=not-a-uuid` без токена → HTTP 401 `{"error":{"code":"UNAUTHORIZED","message":"Authorization header is required"}}`
   - `POST /pos/redemptions` без `X-Pos-Key` → HTTP 401 `{"error":{"code":"POS_KEY_MISSING","message":"X-Pos-Key header is required"}}`
   - `GET /admin/businesses/1ed257c3-0a4f-4569-9571-9b77b9b8d84b` c заголовками админки без токена → HTTP 401 `{"error":{"code":"ADMIN_UNAUTHENTICATED","message":"Admin authentication required"}}`
6. **Heartbeat агента:**
   В журнале backend после перезапуска запросы `POST /agent/heartbeat` стабильно отдают HTTP 200 (`duration_ms` ~11-105 мс).

---

## 3. Часть 2. Кабинет и сайт

### 3.1. Исходное состояние до выкладки
- Живой `index.html` на сайте до выкладки: SHA-256 `a447375a2e1e714b59b28346981d624446a2a86d75ecd6e4076c67d058e8c25b` (совпал с ожидаемым).
- Свободное место на Mac (`df -h /`): 1.8 GiB (> 1 ГБ).

### 3.2. Сборка кабинета
- `npx vitest run --maxWorkers=1`: **175 passed / 22 test files** (время: 45.95s).
- `npm run typecheck`: успешно, 0 ошибок.
- `npm run lint`: успешно, 0 ошибок.
- Сборка production: `VITE_API_BASE_URL=https://api.cashback-qr.poscenter.kz VITE_ALLOW_INSECURE_HTTP=0 npm run build` (vite v8.3.2).
- Проверка артефактов в `admin/dist`:
  - `https://api.cashback-qr.poscenter.kz` присутствует в `AdminRoutes-DzFcOW6B.js`.
  - `localhost` отсутствует в `admin/src` и в `AdminRoutes-DzFcOW6B.js`.
  - Ссылка на APK в `admin/dist/index.html`: `cashback-one-1.0.10.apk`.

### 3.3. Таблица файлов `admin/dist`

| Путь | Размер (байт) | SHA-256 | Статус на сервере |
|---|---|---|---|
| `assets/AdminRoutes-DzFcOW6B.js` | 198 745 | `d1c38d1cb5b3b54055b0dd4a7f81019fa47e7e667a927bbc360c11caaf68eea1` | **новый** |
| `assets/index-BgEdHIYg.js` | 305 284 | `e1ffe00153e61999860faf872f365dd562e092cc29ada6e247e95f92a08c0f93` | **новый** |
| `index.html` | 3 093 | `9ee225772f6c725e5c08469ad1f3bad15406ab6061898266318f84736af54f0b` | **новый** |
| `assets/index-rT6CoaAM.css` | 47 241 | `467fc6afffe3c6713b5641c412f6dbaaacd53f30c6cb0e14628e7d14f8d9db5c` | совпадает |
| `brand-mark.png` | 1 892 | `8b62b9abc678d5f0da00b7ccb4349bdc907a14494e6c17ed59e9b93546762a23` | совпадает |
| `favicon.png` | 1 892 | `8b62b9abc678d5f0da00b7ccb4349bdc907a14494e6c17ed59e9b93546762a23` | совпадает |
| `logo-white.png` | 3 353 | `88469fc29d70e14f6f15180614ff42014c40eda155e09e07aff81de29499169e` | совпадает |
| `logo.png` | 7 762 | `fb14bd7397b273aa7c611ed2caa22aaafbf0c0a260f24a35d92124b30201d5f2` | совпадает |
| `robots.txt` | 130 | `034311b328b14f981825fe31db58eab33afbd1840b086eb72eeda7a2c6169bf7` | совпадает |
| `sitemap.xml` | 275 | `23f2cfc3ba9dc9e409c3b1c31f03b73c82a456ad9cc7312c191dd27731fe39ea` | совпадает |
| `landing/screen-*.png` (4 файла) | — | — | совпадает |
| `assets/roboto-*.woff/woff2` (24 файла) | — | — | совпадает |

К загрузке: ровно **3 файла** (`assets/AdminRoutes-DzFcOW6B.js`, `assets/index-BgEdHIYg.js`, `index.html`).

### 3.4. Резервная копия `index.html`
- Каталог: `~/.local/share/cashback-one/backups/landing-20261105T175135Z-perclient/`
- Файл: `index.html` (3 093 байта, SHA-256 `a447375a2e1e714b59b28346981d624446a2a86d75ecd6e4076c67d058e8c25b`).

### 3.5. Выкладка по FTPS
Выкладка проведена по протоколу TLS 1.2 с проверкой сертификата (`SSL_CERT_FILE=/etc/ssl/cert.pem`), режимом `PROT P`, `TYPE I`, с возвратом в корень перед сменой папок. Каждый файл загружался под временным именем `.{имя}.upload-{uuid}`, скачивался обратно и сверялся по размеру и SHA-256, после чего атомарно переименовывался. Файл `index.html` загружен строго последним.

Сырой вывод выкладки:
```text
Connecting to FTPS...
FTPS connected and authenticated.

Uploading assets/AdminRoutes-DzFcOW6B.js -> assets/.AdminRoutes-DzFcOW6B.js.upload-9edcd23b (size=198745)...
Verified .AdminRoutes-DzFcOW6B.js.upload-9edcd23b matches local. Renaming to AdminRoutes-DzFcOW6B.js...
SUCCESS: AdminRoutes-DzFcOW6B.js deployed and verified. SHA-256: d1c38d1cb5b3b54055b0dd4a7f81019fa47e7e667a927bbc360c11caaf68eea1

Uploading assets/index-BgEdHIYg.js -> assets/.index-BgEdHIYg.js.upload-ee7d9e52 (size=305284)...
Verified .index-BgEdHIYg.js.upload-ee7d9e52 matches local. Renaming to index-BgEdHIYg.js...
SUCCESS: index-BgEdHIYg.js deployed and verified. SHA-256: e1ffe00153e61999860faf872f365dd562e092cc29ada6e247e95f92a08c0f93

Uploading index.html -> ./.index.html.upload-02e4367c (size=3093)...
Verified .index.html.upload-02e4367c matches local. Renaming to index.html...
SUCCESS: index.html deployed and verified. SHA-256: 9ee225772f6c725e5c08469ad1f3bad15406ab6061898266318f84736af54f0b

Checking for leftover temp files across deployed directories...
No temp files found in cashback-qr.poscenter.kz.
No temp files found in cashback-qr.poscenter.kz/assets.

All files successfully uploaded and verified on FTPS.
```

### 3.6. Проверка опубликованных файлов по HTTPS (`Cache-Control: no-cache`)
1. **Загруженные файлы:**
   - `assets/AdminRoutes-DzFcOW6B.js`: HTTP 200, Content-Type: `application/javascript`, size=198745, SHA-256 `d1c38d1cb5b3b54055b0dd4a7f81019fa47e7e667a927bbc360c11caaf68eea1`.
   - `assets/index-BgEdHIYg.js`: HTTP 200, Content-Type: `application/javascript`, size=305284, SHA-256 `e1ffe00153e61999860faf872f365dd562e092cc29ada6e247e95f92a08c0f93`.
   - `index.html`: HTTP 200, Content-Type: `text/html`, size=3093, SHA-256 `9ee225772f6c725e5c08469ad1f3bad15406ab6061898266318f84736af54f0b` (новый хеш).
2. **Файл обновлений приложения:**
   - `app/version.json`: HTTP 200, SHA-256 `7e1c460a67c79823afd5fff7a5af1cf02ddfc124f556510c5d723dcddc4bd64b` (начинается с `7e1c460a…`).
3. **APK файлы на сайте:**
   - `app/cashback-one-1.0.10.apk`: HTTP 200, Content-Length: 68 600 435 байт.
   - `app/cashback-one-1.0.9.apk`: HTTP 200, Content-Length: 67 951 855 байт.
   - `app/cashback-one-1.0.8.apk`: HTTP 200, Content-Length: 67 773 772 байта.
4. **Проверка в браузере (Chrome DevTools):**
   - Главная страница RU (`https://cashback-qr.poscenter.kz/`): 0 ошибок в консоли.
   - Главная страница ҚАЗ (переключение языка): 0 ошибок в консоли, текст на казахском языке отображается корректно.
   - Страница `/admin/login`: форма входа видна (поля логина, пароля, кнопка «Кіру»), шрифт Roboto. Настоящий вход не выполнялся.

---

## 4. План отката при необходимости

### 4.1. Backend
```bash
# На VPS kz-vps в каталоге /opt/cashback-one:
docker tag cashback-backend:rollback-perclient-20261105T174601Z cashback-backend:local
docker compose up -d --no-build --force-recreate backend
```
Колонка `businesses.android_app_id` старому образу не мешает. Если потребуется снять расхождение головы в `/health/ready`, выполнить `alembic downgrade 0015_notification_redemption` из нового образа (безопасно, пока поле `android_app_id` остаётся `NULL` у всех бизнесов).

### 4.2. Сайт и кабинет
Восстановить `index.html` из локальной резервной копии:
`~/.local/share/cashback-one/backups/landing-20261105T175135Z-perclient/index.html`
(загрузить по FTPS в корень сайта).

---

## 5. Не проверено

Следующие проверки требуют авторизации под реальным пользователем и физических устройств:
1. **Авторизованный вход в кабинет**: вход супер-администратором или менеджером бизнеса с валидными учетными данными.
2. **Заполнение поля пакета Android**: сохранение значения `android_app_id` в карточке бизнеса через форму кабинета.
3. **Отправка push в клиентское приложение**: генерация кода списания и доставка FCM push-уведомления в установленное приложение с кастомным `app_id` (`kz.cashbackone.keremet`).
