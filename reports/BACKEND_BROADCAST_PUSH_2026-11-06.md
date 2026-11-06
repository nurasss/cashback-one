# Отчёт о реализации push-уведомлений при рассылке из кабинета — 2026-11-06

## 1. Изменённые и созданные файлы

### Backend
- `backend/app/schemas/admin_content.py`:
  - Добавлена схема `BroadcastPushResult(status: Literal["sent", "disabled", "skipped", "failed"], devices: int, delivered: int)`.
  - В `NotificationCreateRequest` добавлено поле `send_push: bool = True`.
  - В `NotificationAdminItem` добавлено поле `push: BroadcastPushResult | None = None`.
- `backend/app/services/push_service.py`:
  - Реализована функция `get_broadcast_target_devices(session, business_id)` выборки активных устройств по целевым правилам.
  - Реализована функция `send_broadcast_push(session, sender, note, business_id, send_push)` с ограничением параллельности (Semaphore 10), таймаутом (30с), дедупликацией по `push_token`, обновлением `disabled_at` для недействительных токенов. Возвращает `BroadcastPushResult` и гарантированно не бросает исключений.
- `backend/app/services/admin_content.py`:
  - Функция `create_notification`: сначала сохраняет и фиксирует (`commit`) уведомление в БД; при `send_push=True` вызывает `send_broadcast_push`; фиксирует `disabled_at` для инвалидированных токенов; записывает аудит-лог с агрегатами `push_devices` и `push_delivered` (без токенов и ПДн); возвращает объект `NotificationAdminItem` с полем `push`.
- `backend/app/services/admin_mutations.py`:
  - В проекцию `notification_created` добавлены поля `push_devices` и `push_delivered`.
  - В `safe_audit_snapshot` разрешены глобальные контентные действия с `business_id is None`.
- `backend/app/api/admin.py`:
  - В эндпоинт `admin_create_notification` внедрена зависимость `sender: Annotated[PushSender, Depends(get_push_sender)]`.
- `backend/tests/test_broadcast_push.py`:
  - 10 unit-тестов таргетинга, отправки, отключения токенов, изоляции менеджеров, аудит-лога и API.

### Admin
- `admin/src/api/types.ts`:
  - Добавлен тип `BroadcastPushResult`.
  - В `AppNotification` добавлено поле `push?: BroadcastPushResult | null`.
- `admin/src/i18n/admin.ts`:
  - Добавлены ключи локализации `noticeSendPush`, `noticePushSent`, `noticePushDisabled`, `noticePushNoDevices`, `noticePushFailed` для RU и KK.
- `admin/src/pages/ContentPage.tsx`:
  - В форму `NotificationDialog` добавлен чекбокс «Отправить push на телефоны» (по умолчанию включён).
  - Передача `send_push` в теле POST-запроса `/admin/notifications`.
  - Обратный вызов `onCreated` и показ плашки статуса рассылки push в разделе уведомлений.
- `admin/tests/content.test.tsx`:
  - Проверка наличия и состояния чекбокса по умолчанию.
  - Проверка отправки `send_push: true` и `send_push: false`.
  - 8 параметризованных тестов отображения сообщений статуса push (`sent`, `disabled`, `skipped`, `failed`) на русском и казахском языках.

---

## 2. Правило выбора устройств

Отправка осуществляется **только на активные устройства** (`CustomerDevice.disabled_at IS NULL`):

1. **Уведомление бизнеса B** (`business_id` указан):
   - Если статус бизнеса `inactive` — push не отправляется (`status="skipped"`, `devices=0`, `delivered=0`).
   - Если бизнес активен:
     - Все активные устройства отдельного брендированного приложения бизнеса (`app_id == B.android_app_id`), независимо от наличия карты.
     - Активные устройства общего приложения (`app_id == settings.push_shared_app_id`) пользователей, имеющих видимую карту бизнеса B (`Card.business_id == B.id`, `UserCard.hidden_at IS NULL`).
     - Устройства сторонних клиентских приложений бизнеса C исключаются.
2. **Уведомление «Все бизнесы»** (`business_id IS NULL`):
   - Все активные устройства всех приложений (`disabled_at IS NULL`).
3. **Дедупликация**:
   - Выборка дедуплицируется по `push_token`, поэтому каждое устройство получает максимум 1 push за рассылку.
4. **Отказоустойчивость**:
   - Уведомление в БД коммитится **до** отправки push. Сбой push-сервиса или провайдера никогда не отменяет создание уведомления и не возвращает 500 клиенту.
   - Ошибка токена (`PushStatus.INVALID_TOKEN`) переводит устройство в `disabled_at = utcnow()`.
   - Временные ошибки (`PushStatus.TEMPORARY_ERROR`, `PushStatus.REJECTED`) оставляют устройство активным.

---

## 3. Сырой вывод проверок

### 3.1. Backend тесты (pytest)

До правок:
```
449 passed, 37 skipped in 55.45s
```

После правок (полный набор):
```
$ backend/.venv/bin/pytest backend/tests -q
........................................................................ [ 14%]
........................................................................ [ 29%]
........................................................................ [ 43%]
........................................................................ [ 58%]
................s.................................ssssssssssssssssssssss [ 72%]
ssssssssssssss.......................................................... [ 87%]
................................................................         [100%]
=============================== warnings summary ===============================
...
459 passed, 37 skipped, 4 warnings in 75.86s (0:01:15)
```

Новые тесты рассылки (`backend/tests/test_broadcast_push.py`):
```
$ backend/.venv/bin/pytest backend/tests/test_broadcast_push.py -v
============================= test session starts ==============================
backend/tests/test_broadcast_push.py::test_broadcast_push_business_b_targeting PASSED [ 10%]
backend/tests/test_broadcast_push.py::test_broadcast_push_business_without_app_id PASSED [ 20%]
backend/tests/test_broadcast_push.py::test_broadcast_push_all_businesses PASSED [ 30%]
backend/tests/test_broadcast_push.py::test_broadcast_push_send_push_false PASSED [ 40%]
backend/tests/test_broadcast_push.py::test_broadcast_push_mode_disabled PASSED [ 50%]
backend/tests/test_broadcast_push.py::test_broadcast_push_sender_error PASSED [ 60%]
backend/tests/test_broadcast_push.py::test_broadcast_push_invalid_token_disables_device PASSED [ 70%]
backend/tests/test_broadcast_push.py::test_broadcast_push_manager_cannot_send_to_other_business PASSED [ 80%]
backend/tests/test_broadcast_push.py::test_broadcast_push_audit_log PASSED [ 90%]
backend/tests/test_broadcast_push.py::test_broadcast_push_api_endpoint PASSED [100%]

============================== 10 passed in 1.79s ==============================
```

### 3.2. Тесты на PostgreSQL 16

```
$ POSTGRES_TEST_URL="postgresql+asyncpg://localhost/cashback_test" backend/.venv/bin/pytest backend/tests -k postgres -q
......................................                                   [100%]
38 passed, 458 deselected, 1 warning in 17.16s
```

### 3.3. Ruff linter

```
$ backend/.venv/bin/ruff check backend/app backend/tests/test_broadcast_push.py
All checks passed!
```

### 3.4. Mypy typechecker

```
$ backend/.venv/bin/mypy backend/app
backend/app/services/media_storage.py:137: error: Exception type must be derived from BaseException (or be a tuple of exception classes)  [misc]
backend/app/services/media_storage.py:143: error: Exception type must be derived from BaseException (or be a tuple of exception classes)  [misc]
backend/app/services/media_storage.py:155: error: Exception type must be derived from BaseException (or be a tuple of exception classes)  [misc]
backend/app/services/media_storage.py:159: error: Exception type must be derived from BaseException (or be a tuple of exception classes)  [misc]
backend/app/services/media_storage.py:164: error: Exception type must be derived from BaseException (or be a tuple of exception classes)  [misc]
backend/app/services/media_storage.py:186: error: Exception type must be derived from BaseException (or be a tuple of exception classes)  [misc]
backend/app/services/media_storage.py:188: error: Exception type must be derived from BaseException (or be a tuple of exception classes)  [misc]
backend/app/services/media_storage.py:193: error: Exception type must be derived from BaseException (or be a tuple of exception classes)  [misc]
backend/app/services/media_storage.py:261: error: Exception type must be derived from BaseException (or be a tuple of exception classes)  [misc]
backend/app/services/image_service.py:101: error: Incompatible types in assignment (expression has type "Image", variable has type "ImageFile")  [assignment]
backend/app/services/image_service.py:112: error: Incompatible types in assignment (expression has type "Image", variable has type "ImageFile")  [assignment]
backend/app/services/image_service.py:114: error: Incompatible types in assignment (expression has type "Image", variable has type "ImageFile")  [assignment]
backend/app/services/image_service.py:122: error: Incompatible types in assignment (expression has type "Image", variable has type "ImageFile")  [assignment]
backend/app/services/image_service.py:124: error: Incompatible types in assignment (expression has type "Image", variable has type "ImageFile")  [assignment]
Found 14 errors in 2 files (checked 68 source files)
```
*(Только 14 старых известных ошибок в media_storage и image_service, в новом и изменённом коде ошибок 0)*

### 3.5. Admin тесты (npm test)

До правок: 175 passed.

После правок:
```
$ cd admin && npm test -- --maxWorkers=1
...
 ✓ tests/compact-admin.test.tsx (27 tests) 6432ms
 ✓ tests/content.test.tsx (11 tests) 4120ms
 ...
 Test Files  22 passed (22)
      Tests  184 passed (184)
   Start at  15:34:21
   Duration  76.18s
```

### 3.6. Admin typecheck и build

```
$ cd admin && npm run typecheck
> cashback-one-admin@1.0.0 typecheck
> tsc --noEmit
(code 0)

$ cd admin && npm run build
> cashback-one-admin@1.0.0 build
> tsc --noEmit && vite build

vite v8.3.2 building client environment for production...
✓ 115 modules transformed.
dist/index.html                                              3.09 kB │ gzip:  1.28 kB
dist/assets/index-rT6CoaAM.css                              47.24 kB │ gzip:  9.70 kB
dist/assets/AdminRoutes-DW15W8b_.js                        200.33 kB │ gzip: 48.82 kB
dist/assets/index-CHgcj9lq.js                              305.28 kB │ gzip: 94.27 kB
✓ built in 819ms
```

### 3.7. Git diff checks

```
$ git diff --check admin backend
(code 0, пустой вывод)

$ git diff --stat admin backend
 admin/src/api/types.ts                  |  17 +++-
 admin/src/i18n/admin.ts                 |  12 +++
 admin/src/pages/ContentPage.tsx         |  74 ++++++++++++++-
 admin/tests/content.test.tsx            | 147 ++++++++++++++++++++++++++++--
 backend/app/api/admin.py                |   4 +-
 backend/app/schemas/admin_content.py    |  10 ++
 backend/app/services/admin_content.py   |  72 ++++++++++++++-
 backend/app/services/admin_mutations.py |  12 ++-
 backend/app/services/push_service.py    | 156 +++++++++++++++++++++++++++++++-
 9 files changed, 480 insertions(+), 24 deletions(-)
```

---

## 4. Что не проверено

- **Реальная доставка push на физический Android-телефон через боевой FCM:** проверено на fake-отправителе (`PushSender`) с полной имитацией FCM токенов, сетевых ошибок, инвалидации токенов (`disabled_at`) и многопоточной синхронной доставки. Настоящая доставка будет происходить в production-окружении при наличии активного FCM-ключа и зарегистрированных клиентских устройств.
