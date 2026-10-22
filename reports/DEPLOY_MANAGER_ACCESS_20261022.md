# Отчёт о деплое: доступ менеджера бизнеса и автосоздание учётки

**Дата**: 22 октября 2026 г.  
**Время**: ~11:04 – 11:11 (UTC+5)  
**Исполнитель**: Gemini(general)  
**Контур**: Production (VPS `kz-vps`, хостинг Bitrix/FTPS)

---

## 1. Состав и цель изменений

1. **Backend**:
   - Автоматическое создание учётной записи менеджера (`business_manager`) при регистрации бизнеса суперадминистратором (`POST /admin/businesses`), возвращающее сгенерированные реквизиты доступа однократно.
   - Новый эндпоинт `POST /admin/businesses/{id}/manager-access` для сброса пароля или первичной выдачи доступа существующему бизнесу.
   - Затронутые модули:
     - `backend/app/api/admin.py`
     - `backend/app/core/config.py`
     - `backend/app/schemas/admin.py`
     - `backend/app/services/admin_mutations.py`
     - `backend/app/services/admin_security.py`
2. **Admin (SPA)**:
   - Модальное окно с отображением сгенерированных реквизитов менеджера при создании бизнеса.
   - Кнопка «Выдать доступ клиенту / Сбросить пароль» в списке и карточке бизнеса (`BusinessDetailPage.tsx`, `BusinessesPage.tsx`).
   - Новая production-сборка `dist` (ассет `assets/index--vdAybt5.js`).

---

## 2. Предварительные проверки и резервное копирование

1. **Локальный статус репозитория**:
   - Git status проверен: изменены только согласованные файлы backend и тесты (`api/admin.py`, `core/config.py`, `schemas/admin.py`, `services/admin_mutations.py`, `services/admin_security.py`, `tests/test_admin_mutations.py`, `tests/test_admin_manager_access.py`).
2. **Проверка работоспособности VPS до деплоя**:
   - `curl http://127.0.0.1:8000/health/ready` вернул `{"status":"ready","components":{"database":"ok","redis":"ok"}}`.
3. **Rollback-тег образа backend**:
   - Образ сохранён: `docker tag cashback-backend:local cashback-backend:rollback-20261022`
   - ID образа: `sha256:d384cf4a6c10e82a5ee155bbf827838883308b1d69e40133ca51fd6e74d4e2e3`.
4. **Резервная копия PostgreSQL на VPS**:
   - Команда: `docker exec cashback-postgres sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > /opt/cashback-one/backups/pg_20261022_060622.sql.gz`
   - Путь: `/opt/cashback-one/backups/pg_20261022_060622.sql.gz`
   - Размер: 604 KB
   - Права доступа: `chmod 600`.

---

## 3. Деплой Backend (VPS `kz-vps`)

1. **Подготовка архива без секретов и кэша**:
   - Собран архив исходников backend (`tar`) без `.env*`, `.venv`, `.pytest_cache`, `.ruff_cache`, `__pycache__` и `tests`.
   - Проверено отсутствие секретных файлов в архиве (`tar -tf` показал 0 совпадений по `.env`). Размер архива: 107 891 байт.
2. **Перенос и сборка на VPS**:
   - Архив скопирован в `kz-vps:/tmp/cashback.tgz` и распакован в `/opt/cashback-one/backend`.
   - Выполнена сборка образа: `docker compose build backend`.
   - ID нового образа `cashback-backend:local`: `sha256:638f3eebde96512f8a0355fc965d590fc60e916ece1b001a070248f44edeaf91`.
3. **Запуск и миграции**:
   - `docker compose up -d --no-deps migration`: контейнер миграций отработал со статусом `0` (новые миграции отсутствовали, изменений схемы не требовалось).
   - `docker compose up -d --no-deps backend`: контейнер пересоздан и успешно запущен.
4. **Проверка backend**:
   - Внутренний health check: `http://127.0.0.1:8000/health/ready` → `{"status":"ready","components":{"database":"ok","redis":"ok"}}`.
   - Публичный API: `GET https://api.cashback-qr.poscenter.kz/health/ready` → HTTP 200 OK.
   - Проверка нового эндпоинта без токена:
     `POST https://api.cashback-qr.poscenter.kz/admin/businesses/00000000-0000-0000-0000-000000000000/manager-access` → HTTP 401 Unauthorized (`{"detail":"ADMIN_UNAUTHENTICATED"}`). Роут успешно зарегистрирован и защищён.

---

## 4. Деплой Admin SPA (Хостинг Bitrix / FTPS)

1. **Резервная копия `index.html`**:
   - Текущий production `index.html` скачан и сохранён локально в `C:\cashback-stage0\backup_admin_20261022_061008\index.html` (577 байт).
2. **Загрузка по FTPS через `scripts/upload_admin.py`**:
   - Предварительный сухой прогон (`--dry-run`): проверен план загрузки (только обновлённый JS-ассет, CSS и картинки совпадают по размеру, `.htaccess` не затрагивается).
   - Боевая загрузка:
     - `assets/index--vdAybt5.js` (382 696 байт) — загружен успешно.
     - `assets/index-CKyKwx7j.css` (22 688 байт) — пропущен (без изменений).
     - Изображения `brand-mark.png`, `logo.png`, `logo-white.png`, `favicon.png` — пропущены (без изменений).
     - `index.html` (577 байт) — загружен последним через временный файл `.index.html.upload.tmp` с атомарным переименованием.
   - `.htaccess`, папки `demo/` и `app/` не модифицировались.

---

## 5. Проверка опубликованного результата (Production Verification)

1. **SPA и статические ассеты**:
   - `GET https://cashback-qr.poscenter.kz/` → **HTTP 200** (577 байт, подтверждены ссылки на `assets/index--vdAybt5.js` и `assets/index-CKyKwx7j.css`).
   - `GET https://cashback-qr.poscenter.kz/assets/index--vdAybt5.js` → **HTTP 200** (382 696 байт, `Content-Type: application/javascript`).
   - `GET https://cashback-qr.poscenter.kz/assets/index-CKyKwx7j.css` → **HTTP 200** (22 688 байт, `Content-Type: text/css`).
   - `GET https://cashback-qr.poscenter.kz/businesses` → **HTTP 200** (корректная маршрутизация SPA).
2. **Сохранность раздачи мобильного приложения**:
   - `GET https://cashback-qr.poscenter.kz/app/cashback-one-1.0.1.apk` → **HTTP 200** (51 154 339 байт).
   - `GET https://cashback-qr.poscenter.kz/app/cashback-one-1.0.2.apk` → **HTTP 200** (51 160 387 байт).
3. **API статус**:
   - `GET https://api.cashback-qr.poscenter.kz/health/ready` → **HTTP 200** (`{"status":"ready","components":{"database":"ok","redis":"ok"}}`).

---

## 6. Безопасность и регламент

- Содержимое `.env`, `.env.hosting.local`, `docker-compose.yml`, пароли и токены нигде не выводились и в логи не попадали.
- Никаких изменений данных в базе PostgreSQL на продакшене не выполнялось (SQL strict READ ONLY).
- Кнопка «Выдать доступ клиенту» и создание тестовых бизнесов/админов на боевом сервере намеренно не вызывались в автоматическом режиме во избежание генерации нежелательных данных; тестирование будет выполнено пользователем через браузер.
- Git commit и push не производились.
