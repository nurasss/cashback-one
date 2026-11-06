# Выкладка Push-рассылок (сервер и кабинет) — 2026-11-06

**Дата:** 2026-11-06  
**Коммит выпуска:** `fd3a215` (принят куратором в `reports/BACKEND_BROADCAST_PUSH_2026-11-06.md`)  
**Окружение:** macOS (локально), VPS `kz-vps` (backend), хостинг FTPS `cashback-qr.poscenter.kz` (кабинет и сайт)  
**Статус:** Успешно развёрнуто без сбоев. В git отчёт не добавлялся.

---

## 1. Сводка выполненных работ

1. **Часть 1 (Backend на VPS `kz-vps`):**
   - Проверено исходное состояние: код совпадает с `3a5da17` (92 файла), `alembic current` = `0016_business_android_app_id`.
   - Созданы резервные копии в `/opt/cashback-one/backups/bcast-20261106T110909Z/`:
     - Дамп PostgreSQL: `pg.sql.gz` (628 358 байт, SHA-256 `afaa299fe87bbc736a31c2d0ad196ef642007239d6165d9881a39a326f047f68`, проверен `gzip -t` и маркером окончания).
     - Конфигурация: `env.bak` (1 679 байт), `compose.yml.bak` (2 901 байт).
     - Исходники backend: `backend-src.tgz` (31 МБ, SHA-256 `152771e673137aa9041826f27bcfba500614bb647be75a7a7939894f64e326c2`).
     - Тег отката: `cashback-backend:rollback-bcast-20261106T110909Z` (`sha256:452f637ee3d59b635977df7d35dfa657ee583ef624cb26592909fffb5ec8e0c8`).
   - Собран архив `fd3a215` без тестов и окружения (SHA-256 `42b09ee5bb55acf8181b8c138af762317e183279d878dd3c422dd544643e3af6` совпал на Mac и VPS).
   - Сборка образа Docker `f99a013ab95a` (`cashback-backend:local`), контейнер `cashback-migration` завершился с кодом 0, контейнер `cashback-backend` пересоздан и перешёл в статус Healthy.
   - Проверки после развёртывания backend:
     - `/health/ready` отвечает 200 OK (`{"database": "ok", "redis": "ok"}`).
     - Логи push-сервиса: `push_mode: fcm`.
     - Голова миграций: `0016_business_android_app_id` (без изменений).
     - Счетчики БД не изменились: бизнесов: 2, карт: 1714, операций: 9750, пользователей: 4, уведомлений: 1, акций: 2, устройств: 5 (`kz.poscenter.cashback`: 4, `kz.keremet.cashback`: 1).
     - Хеши `.env`, `compose.yml`, `secrets/firebase-service-account.json` не изменились.
     - `POST /admin/notifications` без авторизации возвращает 401 `ADMIN_UNAUTHENTICATED` (не 500).
     - `GET /agent/heartbeat` возвращает 200 OK (287 мс).
     - Ошибок ERROR / CRITICAL в журнале backend нет.

2. **Часть 2 (Кабинет и сайт по FTPS):**
   - Проверен живой `index.html`: SHA-256 `9ee225772f6c725e5c08469ad1f3bad15406ab6061898266318f84736af54f0b` (полностью совпал).
   - Локальные тесты в `admin/`:
     - Свободное место на диске: 3.5 ГБ (> 1 ГБ).
     - `npx vitest run --maxWorkers=1`: **184 passed (184)**.
     - `npm run typecheck`: успешно, ошибок нет.
     - `npm run lint`: успешно, ошибок нет.
   - Production сборка `admin/dist`:
     - Переменные: `VITE_API_BASE_URL=https://api.cashback-qr.poscenter.kz VITE_ALLOW_INSECURE_HTTP=0`.
     - Проверка на `localhost`: 0 вхождений.
     - Ссылка на APK: `cashback-one-1.0.10.apk`.
   - Резервная копия `index.html`: сохранена в `~/.local/share/cashback-one/backups/landing-20261106T111532Z-bcast/index.html` (SHA-256 `9ee22577…4f0b`).
   - Загрузка по FTPS (схема «временное имя → контрольная сверка размера и SHA-256 → rename»):
     - `assets/AdminRoutes-B--uFplW.js`
     - `assets/index-p_9yjMyC.js`
     - `index.html`
   - Все остальные статические ресурсы (шрифты Roboto, CSS, логотипы, скриншоты) уже присутствуют на хостинге с идентичными хешами.
   - Проверка по HTTPS:
     - Все 3 загруженных файла отдаются с кодом 200 и правильными `Content-Type` / размерами / хешами.
     - `app/version.json` не затронут (код 200, SHA-256 `7e1c460a67c79823afd5fff7a5af1cf02ddfc124f556510c5d723dcddc4bd64b`).
     - Все опубликованные APK (`cashback-one-1.0.10.apk`, `1.0.9.apk`, `1.0.8.apk`, `keremet-cashback-1.0.12.apk`) не затронуты.
   - Проверка через Chrome DevTools:
     - Главная страница лендинга на казахском и русском языках открывается без ошибок в консоли (0 messages).
     - `/admin/login` отображает форму входа (логин, пароль, кнопка входа). Посторонних ошибок нет (единственный 401 — ожидаемый фоновый запрос `/admin/auth/me`).

---

## 2. Сырые выводы проверок (без секретов и ПДн)

### 2.1. Исходное состояние на VPS

```
root@kz-vps:/opt/cashback-one# docker exec cashback-backend alembic current
0016_business_android_app_id (head)

root@kz-vps:/opt/cashback-one# docker exec cashback-backend python -c "
from app.db.session import SessionLocal
from app.models.business import Business
from app.models.card import Card
from app.models.transaction import Transaction
from app.models.user import User
from app.models.notification import Notification
from app.models.promotion import Promotion
from app.models.device import Device
from sqlalchemy import func

db = SessionLocal()
print('businesses:', db.query(Business).count())
print('cards:', db.query(Card).count())
print('transactions:', db.query(Transaction).count())
print('users:', db.query(User).count())
print('notifications:', db.query(Notification).count())
print('promotions:', db.query(Promotion).count())
print('devices_total:', db.query(Device).count())
for app_id, cnt in db.query(Device.app_id, func.count(Device.id)).group_by(Device.app_id).all():
    print(f'devices[{app_id}]:', cnt)
db.close()
"
businesses: 2
cards: 1714
transactions: 9750
users: 4
notifications: 1
promotions: 2
devices_total: 5
devices[kz.poscenter.cashback]: 4
devices[kz.keremet.cashback]: 1

root@kz-vps:/opt/cashback-one# ls -la .env compose.yml
-rw-r--r-- 1 root root 1679 Nov  5 10:13 .env
-rw-r--r-- 1 root root 2901 Nov  5 09:24 compose.yml

root@kz-vps:/opt/cashback-one# ls -la secrets/firebase-service-account.json
-rw------- 1 10001 10001 2413 Nov  5 10:11 secrets/firebase-service-account.json

root@kz-vps:/opt/cashback-one# sha256sum .env compose.yml secrets/firebase-service-account.json
a4df9bd96793327995622af31fca575820045228709e55f4a4cad90534f37db6  .env
21fe1ed7010e083625c9669da12bd1aa766cf9a231958be35ba27615491a89b9  compose.yml
e515d9be26a45b98fecde43b0eb6ff655f2eb716b9b3294c77609a3dcad48e7f  secrets/firebase-service-account.json

root@kz-vps:/opt/cashback-one# df -h /
Filesystem      Size  Used Avail Use% Mounted on
/dev/root        20G   16G  3.1G  84% /
```

Сверка исходных файлов `backend/app` и `backend/migrations` на VPS с коммитом `3a5da17`:
- Все 92 файла побайтно совпали (0 расхождений).

### 2.2. Резервные копии и образ отката на VPS

```
Каталог: /opt/cashback-one/backups/bcast-20261106T110909Z/
-rw-r--r-- 1 root root    628358 Nov  6 11:09 pg.sql.gz
-rw------- 1 root root      1679 Nov  6 11:09 env.bak
-rw------- 1 root root      2901 Nov  6 11:09 compose.yml.bak
-rw-r--r-- 1 root root  32454641 Nov  6 11:09 backend-src.tgz

Проверка дампа:
gzip -t pg.sql.gz -> OK
tail marker -> "-- PostgreSQL database dump complete" OK

Образ отката:
cashback-backend:rollback-bcast-20261106T110909Z
ID: sha256:452f637ee3d59b635977df7d35dfa657ee583ef624cb26592909fffb5ec8e0c8
```

### 2.3. Сборка и перезапуск backend на VPS

```
Архив обновления fd3a215:
SHA-256 на Mac: 42b09ee5bb55acf8181b8c138af762317e183279d878dd3c422dd544643e3af6
SHA-256 на VPS: 42b09ee5bb55acf8181b8c138af762317e183279d878dd3c422dd544643e3af6
Совпадение: 100%

Сборка Docker:
#17 naming to docker.io/library/cashback-backend:local done
#17 writing image sha256:f99a013ab95ae54f3be51543d83151fa7c16c4f0393b4a2e5828daae82046db4 done

Контейнеры:
cashback-migration exited (0)
cashback-backend Healthy (Up 17 seconds, port 8000/tcp)

Проверка миграций после перезапуска:
docker exec cashback-backend alembic current
0016_business_android_app_id (head)
```

### 2.4. Проверка backend после развёртывания

```
1. Healthcheck:
docker exec cashback-backend curl -s http://127.0.0.1:8000/health/ready
{"database": "ok", "redis": "ok"}

2. Push mode:
docker exec cashback-backend python -c "from app.core.config import settings; print('push_mode:', settings.PUSH_MODE)"
push_mode: fcm

3. База данных (количества не изменились):
businesses: 2
cards: 1714
transactions: 9750
users: 4
notifications: 1
promotions: 2
devices_total: 5
devices[kz.poscenter.cashback]: 4
devices[kz.keremet.cashback]: 1

4. Хеши файлов конфигурации:
a4df9bd96793327995622af31fca575820045228709e55f4a4cad90534f37db6  .env
21fe1ed7010e083625c9669da12bd1aa766cf9a231958be35ba27615491a89b9  compose.yml
e515d9be26a45b98fecde43b0eb6ff655f2eb716b9b3294c77609a3dcad48e7f  secrets/firebase-service-account.json

5. Тест POST /admin/notifications без токена:
curl -i -X POST http://127.0.0.1:8000/admin/notifications -H "Content-Type: application/json" -d "{}"
HTTP/1.1 401 Unauthorized
{"detail": "ADMIN_UNAUTHENTICATED"}

6. Тест /agent/heartbeat:
curl -i -w "\nTime: %{time_total}s\n" http://127.0.0.1:8000/agent/heartbeat
HTTP/1.1 200 OK
Time: 0.287s
```

---

## 3. Таблица загруженных файлов кабинета и сайта (FTPS)

Резервная копия старого `index.html`: `~/.local/share/cashback-one/backups/landing-20261106T111532Z-bcast/index.html` (SHA-256 `9ee225772f6c725e5c08469ad1f3bad15406ab6061898266318f84736af54f0b`).

| Файл | Размер (байт) | SHA-256 | Content-Type | Статус на FTPS |
|---|---|---|---|---|
| `assets/AdminRoutes-B--uFplW.js` | 200 369 | `e84d50d652512db1360261098d89dadb5d75ba048ee6ec19866f68fec7e3f7ef` | `application/javascript` | Загружен первым, проверен |
| `assets/index-p_9yjMyC.js` | 305 284 | `348f8b7d2448964db7b266ae2ecd7edd38c194368fe3ffe1a99e022bd3e5c69c` | `application/javascript` | Загружен вторым, проверен |
| `index.html` | 3 093 | `8567d53de60f6755d2b0e2915d9e996d1d5c83c27f139e71905b26057eacf5e1` | `text/html` | Загружен последним, проверен |

### Неизменяемые контрольные файлы на сайте

| Файл | HTTP-статус | Размер (байт) | SHA-256 |
|---|---|---|---|
| `/app/version.json` | 200 OK | 169 | `7e1c460a67c79823afd5fff7a5af1cf02ddfc124f556510c5d723dcddc4bd64b` |
| `/app/cashback-one-1.0.10.apk` | 200 OK | 68 600 435 | сохранён неизменным |
| `/app/cashback-one-1.0.9.apk` | 200 OK | 67 951 855 | сохранён неизменным |
| `/app/cashback-one-1.0.8.apk` | 200 OK | 67 773 772 | сохранён неизменным |
| `/app/keremet-cashback-1.0.12.apk` | 200 OK | 63 668 358 | сохранён неизменным |

---

## 4. План отката (при необходимости)

> **Внимание:** Самостоятельный откат без прямого поручения владельца запрещён.

1. **Откат Backend на VPS:**
   ```bash
   ssh kz-vps "cd /opt/cashback-one && \
     docker tag cashback-backend:rollback-bcast-20261106T110909Z cashback-backend:local && \
     docker compose up -d --no-build --force-recreate backend"
   ```
2. **Откат сайта / кабинета на хостинге FTPS:**
   Восстановить `index.html` из копии `~/.local/share/cashback-one/backups/landing-20261106T111532Z-bcast/index.html` через FTPS на путь `index.html`.

---

## 5. Что не проверено

1. **Реальная отправка push-уведомлений покупателям на production:**
   В соответствии с промптом, новые уведомления на production **намеренно не создавались**, чтобы не производить реальную массовую рассылку push на телефоны покупателей. Проверку создания тестового уведомления с push выполнит владелец.
2. **Интерфейс создания уведомления с галочкой «Отправить push» под авторизованным аккаунтом:**
   Вход в кабинет администратора с действующими учетными данными не выполнялся (проверена только форма `/admin/login` в браузере без аутентификации).
