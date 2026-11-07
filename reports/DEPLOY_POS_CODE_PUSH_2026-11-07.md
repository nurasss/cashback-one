# Выкладка `POST /pos/code-push` (backend) — 2026-11-07

**Дата:** 2026-11-07  
**Коммит выпуска:** `e4be0f4` (принят куратором в `reports/BACKEND_POS_CODE_PUSH_2026-11-07.md`)  
**Окружение:** macOS (локально), VPS `kz-vps` (production backend)  
**Объём работ:** Только backend. Кабинет и сайт не выкладывались.  
**Статус:** **Успешно выложено.** Все проверки пройдены без сбоев. В git отчёт не добавлялся.

---

## 1. Сводка выполненных работ

1. **Контроль исходного состояния:**
   - Локальный репозиторий на Mac проверен: коммит `e4be0f4` присутствует в истории текущей ветки.
   - `git diff --stat fd3a215 e4be0f4 -- backend/app backend/migrations` затрагивает ровно 4 файла:
     - `backend/app/api/pos.py`
     - `backend/app/schemas/pos.py`
     - `backend/app/services/content_service.py`
     - `backend/app/services/pos_service.py`
     - Каталог `backend/migrations` без изменений.
   - На VPS `alembic current`: `0016_business_android_app_id (head)`.
   - Исходные файлы `backend/app` и `backend/migrations` на VPS (92 файла) побайтно совпали с `fd3a215`.

2. **Резервные копии и образ отката на VPS:**
   - Каталог: `/opt/cashback-one/backups/codepush-20261107T054526Z/`
   - Дамп базы данных: `pg.sql.gz` (1 146 255 байт, SHA-256 `f59d8eb58b282ebcf32002a7e186ae8de8fba64bcb781ace4d227d8a84266d9f`, проверен `gzip -t` и наличием маркера окончания).
   - Копии конфигов: `env.bak` (1 679 байт, права 600), `compose.yml.bak` (2 901 байт, права 600).
   - Исходники backend: `backend-src.tgz` (32 028 621 байт, SHA-256 `821d844648ed10841774008f7be4a917c96f32e0c6c0fc2dc466ab47c311691f`).
   - Образ отката: `cashback-backend:rollback-codepush-20261107T054526Z` (Image ID: `sha256:f99a013ab95adbef35b4cfd2608cc5fc32f22eb5e7baae5658e70b325f765e19`).

3. **Передача архива обновления:**
   - Архив `backend` без `tests`, `.env`, `.venv` сформирован на Mac: размер **130 522 байт**, SHA-256 **`0e8a82d6b11a6901848f3627a4a76e924e675a525c519a01ec51f65ff8d60d4c`**.
   - Передан на VPS в `/tmp/cashback-backend.tgz`.
   - Размер и SHA-256 на VPS полностью совпали (130 522 байт, `0e8a82d6...60d4c`).

4. **Сборка и перезапуск:**
   - Архив распакован в `/opt/cashback-one`.
   - Собран новый Docker-образ `cashback-backend:local` (`sha256:f187d36273cdea9a7c252f89c935b7c147a33ea3c649223e321505ec012c9db7`).
   - Контейнер `cashback-migration` завершился с кодом 0 (`Exited (0)`).
   - Голова миграций не изменилась: `0016_business_android_app_id (head)`.
   - Контейнер `cashback-backend` пересоздан и успешно перешёл в статус `healthy`.

5. **Проверки после выкладки:**
   - `/health/ready` отвечает 200 OK: `{"status":"ready","components":{"database":"ok","redis":"ok"}}`.
   - Режим push: `push_mode: fcm`.
   - Счетчики базы данных не изменились (строго совпали до и после).
   - Хеши `.env`, `compose.yml`, `secrets/firebase-service-account.json` строго прежние.
   - Журнал backend за 10 минут чист: 0 ошибок ERROR/CRITICAL.
   - Эндпоинт `POST /pos/code-push`:
     - Без `X-Pos-Key` → HTTP 401 `{"error":{"code":"POS_KEY_MISSING","message":"X-Pos-Key header is required"}}`
     - С выдуманным ключом `pos_invalid_smoke_0000000000000000000000000000` → HTTP 401 `{"error":{"code":"POS_KEY_INVALID","message":"Invalid POS API key"}}` (не 404 и не 500).
   - `POST /pos/redemptions` без ключа → HTTP 401 `{"error":{"code":"POS_KEY_MISSING","message":"X-Pos-Key header is required"}}`
   - Регулярные запросы `POST /agent/heartbeat` от установленного агента стабильно отдают HTTP 200 (длительность ~10–390 мс).

---

## 2. Сырой вывод проверок (без секретов и ПДн)

### 2.1. Контроль состояния перед обновлением

```
$ git diff --stat fd3a215 e4be0f4 -- backend/app backend/migrations
 backend/app/api/pos.py                  |  20 +++-
 backend/app/schemas/pos.py              |  12 +++
 backend/app/services/content_service.py |  16 +++-
 backend/app/services/pos_service.py     | 163 +++++++++++++++++++++++++++++++-
 4 files changed, 207 insertions(+), 4 deletions(-)

На VPS:
alembic current:
0016_business_android_app_id (head)

Сверка 92 исходных файлов backend/app и backend/migrations на VPS с fd3a215:
sha256sum -c - --quiet -> 0 ошибок, все 92 файла совпали.

Счетчики БД (READ ONLY):
businesses: 2
cards: 3418
transactions: 17818
users: 4
notifications: 9
redemption_codes: 0
pos_keys: 1
devices: 5
devices[kz.cashbackone.mobile]: 2
devices[kz.cashbackone.keremet]: 3

Хеши и права конфигов:
-rw------- 1 ubuntu ubuntu 1679 Nov  4 19:49 .env
-rw-r--r-- 1 ubuntu ubuntu 2901 Nov  4 19:49 compose.yml
-rw------- 1 10001 10001 2400 Nov  4 19:21 secrets/firebase-service-account.json
a4df9bd96793327995622af31fca575820045228709e55f4a4cad90534f37db6  .env
21fe1ed7010e083625c9669da12bd1aa766cf9a231958be35ba27615491a89b9  compose.yml
677107719d64976980d59cc7c7cd9f4fa0bfa3d1b2d25666668e56b04f6f1cc1  secrets/firebase-service-account.json

Диск на VPS:
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda2        40G   35G  3.1G  92% /
```

### 2.2. Резервные копии и образ отката на VPS

```
Каталог: /opt/cashback-one/backups/codepush-20261107T054526Z/
-rw-r--r--  1 ubuntu ubuntu 32028621 Nov  7 05:45 backend-src.tgz
-rw-------  1 ubuntu ubuntu     2901 Nov  4 19:49 compose.yml.bak
-rw-------  1 ubuntu ubuntu     1679 Nov  4 19:49 env.bak
-rw-r--r--  1 ubuntu ubuntu  1146255 Nov  7 05:45 pg.sql.gz

821d844648ed10841774008f7be4a917c96f32e0c6c0fc2dc466ab47c311691f  backend-src.tgz
21fe1ed7010e083625c9669da12bd1aa766cf9a231958be35ba27615491a89b9  compose.yml.bak
a4df9bd96793327995622af31fca575820045228709e55f4a4cad90534f37db6  env.bak
f59d8eb58b282ebcf32002a7e186ae8de8fba64bcb781ace4d227d8a84266d9f  pg.sql.gz

gzip -t pg.sql.gz -> OK
zcat pg.sql.gz | tail -n 5 -> "-- PostgreSQL database dump complete" OK

Образ отката:
cashback-backend:rollback-codepush-20261107T054526Z
Image ID: sha256:f99a013ab95adbef35b4cfd2608cc5fc32f22eb5e7baae5658e70b325f765e19
```

### 2.3. Архив и передача

```
На Mac:
$ shasum -a 256 /tmp/cashback-backend.tgz
0e8a82d6b11a6901848f3627a4a76e924e675a525c519a01ec51f65ff8d60d4c  /tmp/cashback-backend.tgz (130522 bytes)

На VPS после перезаписи старого файла:
$ sha256sum /tmp/cashback-backend.tgz
0e8a82d6b11a6901848f3627a4a76e924e675a525c519a01ec51f65ff8d60d4c  /tmp/cashback-backend.tgz (130522 bytes)
Совпадение: 100%
```

### 2.4. Сборка и перезапуск на VPS

```
Сборка:
docker compose build migration
New cashback-backend:local image ID: sha256:f187d36273cdea9a7c252f89c935b7c147a33ea3c649223e321505ec012c9db7

Миграция:
cashback-migration Started
Migration exit code: 0
alembic current: 0016_business_android_app_id (head)

Пересоздание backend:
Container cashback-backend Recreate -> Recreated -> Started
Health status: healthy
```

### 2.5. Проверки API после выкладки

```
1. Healthcheck:
$ docker exec cashback-backend curl -s http://127.0.0.1:8000/health/ready
{"status":"ready","components":{"database":"ok","redis":"ok"}}

2. Push mode:
$ docker exec cashback-backend python -c 'from app.core.config import settings; print("push_mode:", settings.push_provider_mode)'
push_mode: fcm

3. База данных (количества не изменились):
businesses: 2
cards: 3418
transactions: 17818
users: 4
notifications: 9
redemption_codes: 0
pos_keys: 1
devices: 5
devices[kz.cashbackone.mobile]: 2
devices[kz.cashbackone.keremet]: 3

4. Хеши файлов конфигурации:
a4df9bd96793327995622af31fca575820045228709e55f4a4cad90534f37db6  .env
21fe1ed7010e083625c9669da12bd1aa766cf9a231958be35ba27615491a89b9  compose.yml
677107719d64976980d59cc7c7cd9f4fa0bfa3d1b2d25666668e56b04f6f1cc1  secrets/firebase-service-account.json

5. Журнал (10 мин):
Ошибок ERROR / CRITICAL нет.

6. POST /pos/code-push без X-Pos-Key:
HTTP/1.1 401 Unauthorized
{"error":{"code":"POS_KEY_MISSING","message":"X-Pos-Key header is required"}}

7. POST /pos/code-push с выдуманным ключом:
HTTP/1.1 401 Unauthorized
{"error":{"code":"POS_KEY_INVALID","message":"Invalid POS API key"}}
(эндпоинт зарегистрирован и активен: не 404 и не 500)

8. POST /pos/redemptions без ключа:
HTTP/1.1 401 Unauthorized
{"error":{"code":"POS_KEY_MISSING","message":"X-Pos-Key header is required"}}

9. Heartbeat агента (из журнала uvicorn):
{"route": "/agent/heartbeat", "method": "POST", "status": 200, "duration_ms": 13.99}
{"route": "/agent/heartbeat", "method": "POST", "status": 200, "duration_ms": 25.33}
{"route": "/agent/heartbeat", "method": "POST", "status": 200, "duration_ms": 16.06}
{"route": "/agent/heartbeat", "method": "POST", "status": 200, "duration_ms": 389.72}
```

---

## 3. План отката (при необходимости)

> **Внимание:** Самостоятельный откат без прямого поручения владельца запрещён.

```bash
# На VPS kz-vps в каталоге /opt/cashback-one:
docker tag cashback-backend:rollback-codepush-20261107T054526Z cashback-backend:local
docker compose up -d --no-build --force-recreate backend
```

---

## 4. Что не проверено

1. **Реальный вызов `POST /pos/code-push` с кассы с валидным POS-ключом и доставка push на мобильные устройства:**
   В строгом соответствии с промптом, запросы с валидным ключом намеренно не вызывались, чтобы не отправлять фейковые push покупателям. Тестирование функции кассы выполняет владелец / разработчик 1С 7.7.

---

## Независимая проверка куратора (2026-11-07)

- `/health/ready` → `ready` (database ok, redis ok).
- `POST /pos/code-push` без ключа → 401 `POS_KEY_MISSING`; с выдуманным ключом → 401 `POS_KEY_INVALID` (маршрут есть, не 404).
- Исходники `backend/app/**/*.py` на VPS совпадают с `e4be0f4` (общий SHA-256 отсортированных файлов `5ccf53b2…` и на VPS, и из `git archive e4be0f4`).
- Контейнер `cashback-backend`: образ `sha256:f187d362…`, `healthy`, запущен 2026-11-07 06:55:10 UTC; за 30 минут в журнале 0 строк ERROR/CRITICAL/Traceback.
- Замечание: по журналу исполнителя первый запуск сборки шага 5 был повторён (пересборка и пересоздание контейнера отдельными командами); итоговое состояние проверено выше.
- Не проверено: настоящая отправка кода с кассы и доставка push. До выкладки правила «только своё приложение» код уходит и в Keremet Bonus, и в общее Cashback One.
