# Отчёт по задаче: фото профиля на сервере — 2026-11-01

Среда: macOS Darwin arm64, Python `backend/.venv/bin/python`, Node/Jest в каталоге `mobile/`.
Ограничения соблюдены: без сборки APK, без деплоя, без применения миграций на production БД, без commit/push, без изменения версии приложения. Изменения затронули только каталоги `backend/` и `mobile/`.

---

## 1. Базовые проверки до правок (baseline)

Числа полностью совпали с показателями из `reports/APP_LOGIN_PROFILE_FIX_2026-11-01.md`:
1. `mobile` тесты: `npx jest` → **182 passed, 15 suites**.
2. `backend` тесты: `pytest` → **362 passed, 36 skipped, 4 warnings**.

---

## 2. Установленные пакеты зависимостей

Установка выполнена исключительно командой `npx expo install expo-image-picker expo-image-manipulator` в каталоге `mobile/`:
- `expo-image-picker`: `~55.0.24`
- `expo-image-manipulator`: `~55.0.21`

Проверка `git diff mobile/package.json` подтвердила: затронуты только эти две зависимости, `app.json` и `mobile/android/` не изменялись, `expo prebuild` не запускался.

---

## 3. Изменения по файлам

### 3.1. Backend

1. **`backend/app/models/entities.py`**:
   - В модель `User` добавлено поле `avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)`.

2. **`backend/migrations/versions/0011_customer_avatar.py`**:
   - Создана ревизия миграции `0011_customer_avatar` с предком `0010_customer_app_content`.
   - Реализованы методы `upgrade()` (`op.add_column("users", sa.Column("avatar_url", sa.String(512), nullable=True))`) и `downgrade()` (`op.drop_column("users", "avatar_url")`).
   - Автоматически учтена в определении головы миграций (`expected_alembic_head`).

3. **`backend/app/core/config.py`**:
   - Добавлены настройки:
     - `avatar_max_upload_bytes: int = 1_500_000` (лимит 1.5 МБ для аватарки)
     - `avatar_upload_user_limit: int = 10`
     - `avatar_upload_window_seconds: int = 3600`

4. **`backend/app/services/image_service.py`**:
   - Добавлено назначение `purpose="avatar"`.
   - Кроп центрального квадрата `min_dim = min(width, height)` и масштабирование строго в 512×512 LANCZOS.
   - Очистка метаданных: из `info` удаляются `exif`, `icc_profile`, `photoshop`, при сохранении в WebP метаданные не записываются.
   - Для анимированных изображений (GIF/WebP) извлекается только первый кадр (`img.seek(0)`).
   - Файлы сохраняются по пути `avatars/<uuid4hex>.webp`.
   - Аргументы `admin` и `db` сделаны опциональными: аудит-лог пишется при наличии контекста админа, загрузка покупателя проходит без создания записей в `AuditLog`.

5. **`backend/app/services/media_storage.py`**:
   - `SAFE_MEDIA_PATH_REGEX`: добавлен префикс `avatars` (`^(promotions|logos|avatars)/[0-9a-f]{32}\.webp$`).
   - `maybe_cleanup_old_media_file`: добавлена проверка наличия ссылок в таблице `User.avatar_url`. Если файл ещё используется другим профилем, удаление с хранилища не производится.

6. **`backend/app/schemas/customer_app.py`**:
   - В `ProfileResponse` добавлено поле `avatar_url: str | None = None`.
   - `ProfileUpdateRequest` оставлен без изменений (`extra="forbid"` гарантирует запрет передачи `avatar_url` через `PATCH /me/profile`).

7. **`backend/app/api/customer_app.py`**:
   - Добавлен `POST /me/avatar`:
     - Проверка ограничения частоты по `current_user.id` через `RateLimiter` (10 запросов / час); превышение: 429 `RATE_LIMIT_EXCEEDED`.
     - Потоковое чтение `UploadFile` порциями по 64 КБ с лимитом `avatar_max_upload_bytes = 1_500_000`; превышение: 413 `FILE_TOO_LARGE`.
     - Обработка и сохранение через `process_and_store_image(..., purpose="avatar")`.
     - Последовательность замены: сохранение нового файла → фиксация `user.avatar_url = new_url` в БД → best-effort удаление старого файла через `maybe_cleanup_old_media_file`.
     - В случае ошибки commit в БД выполняется best-effort откат (удаление только что загруженного нового файла).
   - Добавлен `DELETE /me/avatar`:
     - Обнуление `user.avatar_url = None`, commit в БД, best-effort удаление старого файла. Повторный вызов идемпотентен (200 OK).
   - В логах отсутствуют телефоны и имена пользователей.

8. **`backend/tests/test_customer_avatar.py`**:
   - Набор из 11 тестов, покрывающих все требования:
     - `test_avatar_upload_success_and_format`: сохранение 512×512 WebP в `avatars/...`, обновление профиля.
     - `test_avatar_upload_exif_gps_stripped`: проверка вырезания GPS и EXIF-тегов.
     - `test_avatar_upload_rgba_png_and_invalid_files`: корректная обработка RGBA PNG, отклонение не-изображений (415) и файлов свыше 1.5 МБ (413).
     - `test_avatar_replacement_deletes_old_file_and_tolerates_cleanup_error`: удаление предыдущего файла и толерантность к ошибкам хранилища при удалении старого.
     - `test_avatar_storage_failure_leaves_db_unchanged`: откат состояния при сбое хранилища.
     - `test_avatar_delete_endpoint`: удаление файла и идемпотентность `DELETE`.
     - `test_avatar_auth_and_rate_limit`: 401 без токена и 429 при исчерпании лимита 10/час.
     - `test_avatar_patch_rejected`: 422 при попытке передать `avatar_url` через PATCH.
     - `test_avatar_shared_reference_protection`: файл не удаляется, если на него ссылается другой пользователь.
     - `test_avatar_disabled_storage`: 503 `MEDIA_STORAGE_NOT_CONFIGURED` при выключенном хранилище.
     - `test_avatar_migration_upgrade_and_downgrade`: проверка выполнения `upgrade()` и `downgrade()` на таблице `users`.

---

### 3.2. Mobile

1. **`mobile/src/types/api.ts`**:
   - В интерфейс `Profile` добавлено поле `avatar_url?: string | null`.

2. **`mobile/src/api/client.ts`**:
   - Обновлен метод `send`: если `options.body` является экземпляром `FormData`, заголовок `Content-Type: application/json` не устанавливается (позволяя fetch проставить правильный `multipart/form-data; boundary=...`), а тело передаётся без `JSON.stringify`.

3. **`mobile/src/api/app.ts`**:
   - Добавлены и экспортированы вспомогательные функции `uploadAvatar(api, uri)` и `deleteAvatar(api)`.

4. **`mobile/src/demo/mockApi.ts`**:
   - Добавлена поддержка `POST /me/avatar` (сохраняет локальный URI в in-memory профиль) и `DELETE /me/avatar` (сбрасывает `avatar_url: null`). Реальные сетевые вызовы в демо-режиме отсутствуют.

5. **`mobile/src/i18n/ru.ts` и `mobile/src/i18n/kz.ts`**:
   - Добавлены переводы действий:
     - `avatarChange`: «Изменить фото» / «Фотоны өзгерту»
     - `avatarDelete`: «Удалить фото» / «Фотоны өшіру»
   - Добавлены переводы кодов ошибок backend: `FILE_TOO_LARGE`, `IMAGE_TOO_LARGE`, `UNSUPPORTED_MEDIA_TYPE`, `MEDIA_STORAGE_NOT_CONFIGURED`, `MEDIA_STORAGE_ERROR`.

6. **`mobile/src/features/profile.tsx`**:
   - Компонент `Avatar`:
     - Поддерживает отображение картинки из `avatar_url` через `<Image />`.
     - При отсутствии `avatar_url` или ошибке загрузки изображения (`onError`) отображает инициалы.
     - Является доступной кнопкой (`accessibilityRole="button"`, `accessibilityLabel={t('avatarChange')}`).
     - На краю круга отображает круглый бейдж с иконкой.
     - При активной загрузке (`loading`) блокирует нажатия и показывает индикатор активности.

7. **`mobile/app/(app)/(tabs)/profile.tsx`**:
   - Интегрирован процесс загрузки и удаления:
     - Нажатие при отсутствии фото: сразу открывается системная галерея через `launchImageLibraryAsync` (`mediaTypes: ['images']`, `allowsEditing: true`, `aspect: [1, 1]`) без предварительного запроса разрешений.
     - Нажатие при наличии фото: диалог `Alert.alert` с кнопками «Изменить фото», «Удалить фото», «Отмена».
     - Выбранное изображение масштабируется до ширины 512px в формате JPEG с качеством 0.8 с помощью `manipulateAsync`.
     - Отправка на `/me/avatar` через `uploadAvatar` с последующим обновлением кэша `keys.profile`.
     - Ошибки выводятся на экран через `ErrorNotice`. Старое фото при ошибке не пропадает.

8. **`mobile/tests/avatar.test.tsx`**:
   - 8 unit/integration тестов для клиента:
     - Отображение инициалов при отсутствии фото.
     - Отображение `Image` при наличии `avatar_url`.
     - Fallback на инициалы при событии `onError` изображения.
     - Непосредственный вызов галереи при отсутствии фото.
     - Отмена выбора фото не отправляет сетевых запросов.
     - Успешная обработка (512px JPEG), отправка `FormData` с Bearer-токеном и обновление профиля.
     - Ошибка сохранения оставляет прежнее фото и выводит `ErrorNotice`.
     - Диалог `Alert` при наличии фото с опциями изменения и удаления.

---

## 4. Сырые выводы проверок

### 4.1. `cd mobile && npx jest`
```text
PASS tests/homeArtwork.test.tsx
PASS tests/components.test.tsx (6.092 s)
PASS tests/flows.test.tsx (7.177 s)
PASS tests/cardScanner.test.tsx
PASS tests/avatar.test.tsx
PASS tests/qrScreen.test.tsx
PASS tests/promotionsArtwork.test.tsx
PASS tests/profileSave.test.tsx
PASS tests/wallet.test.tsx
PASS tests/core.test.ts
PASS tests/loginScreen.test.tsx
PASS tests/session.test.ts
PASS tests/levels.test.tsx
PASS tests/transport.test.ts
PASS tests/keyboardLift.test.ts
PASS tests/demo.test.ts

Test Suites: 16 passed, 16 total
Tests:       190 passed, 190 total
Snapshots:   0 total
Time:        13.361 s
Ran all test suites.
```

### 4.2. `cd mobile && npx tsc --noEmit`
```text
(Код возврата 0, вывод чистый)
```

### 4.3. `cd mobile && npx eslint .`
```text
/Users/nuras/Desktop/cashback-one/mobile/src/components/useKeyboardLift.ts
  62:20  warning  The ref value 'generation.current' will likely have changed by the time this effect cleanup function runs. If this ref points to a node rendered by React, copy 'generation.current' to a variable inside the effect, and use that variable in the cleanup function  react-hooks/exhaustive-deps

✖ 1 problem (0 errors, 1 warning)
```

### 4.4. `backend/.venv/bin/python -m pytest backend/tests -q -ra`
```text
........................................................................ [ 17%]
........................................................................ [ 35%]
........................................................................ [ 52%]
................................................ssssssssssssssssssssssss [ 70%]
ssssssssssss............................................................ [ 88%]
.................................................                        [100%]
=============================== warnings summary ===============================
tests/test_agent_sync_transactions.py::test_transactions_sync_initial_and_idempotent_replay
tests/test_agent_sync_transactions.py::test_transactions_same_external_id_on_different_cards
tests/test_customer_app.py::test_fresh_transaction_sync_notifies_card_owner
  /Users/nuras/Desktop/cashback-one/backend/app/api/agent_sync.py:44: SADeprecationWarning: The Result.tuples() method is deprecated, Row now behaves like a tuple and can unpack types directly. (deprecated since: 2.1.0)
    ).tuples().all()

tests/test_production_runtime.py::test_expected_alembic_head_is_derived_from_migration_scripts
  /Users/nuras/Desktop/cashback-one/backend/.venv/lib/python3.11/site-packages/alembic/config.py:604: DeprecationWarning: No path_separator found in configuration; falling back to legacy splitting on spaces, commas, and colons for prepend_sys_path.  Consider adding path_separator=os to Alembic config.
    util.warn_deprecated(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
SKIPPED [1] backend/tests/test_postgres_admin_security.py:56: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_admin_security.py:92: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_admin_security.py:130: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_admin_security.py:190: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_admin_security.py:229: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_admin_security.py:269: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_admin_security.py:331: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_agent_sync_concurrency.py:62: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_agent_sync_concurrency.py:121: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_agent_sync_concurrency.py:197: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_agent_sync_concurrency.py:262: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_bind_concurrency.py:47: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_bind_concurrency.py:134: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_bind_concurrency.py:211: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_bind_concurrency.py:302: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_customer_auth_concurrency.py:65: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_customer_auth_concurrency.py:117: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_customer_auth_concurrency.py:140: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_customer_auth_concurrency.py:175: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_customer_auth_concurrency.py:193: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_customer_auth_concurrency.py:221: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_model_smoke.py:20: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_sms_concurrency.py:53: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_sms_concurrency.py:121: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_sms_concurrency.py:187: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_sms_concurrency.py:258: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_wallet_concurrency.py:48: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_wallet_concurrency.py:128: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_wallet_concurrency.py:231: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_wallet_concurrency.py:279: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_wallet_concurrency.py:372: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_wallet_concurrency.py:480: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_wappi_concurrency.py:61: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_wappi_concurrency.py:146: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_wappi_concurrency.py:226: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_wappi_concurrency.py:257: POSTGRES_TEST_URL is not configured
373 passed, 36 skipped, 4 warnings in 37.73s
```

### 4.5. `backend/.venv/bin/python -m ruff check ...`
```text
All checks passed!
```

### 4.6. `git status --short` и `git diff --stat`
```text
$ git status --short
 M backend/app/api/auth.py
 M backend/app/api/customer_app.py
 M backend/app/core/config.py
 M backend/app/core/security.py
 M backend/app/models/entities.py
 M backend/app/schemas/auth.py
 M backend/app/schemas/customer_app.py
 M backend/app/services/image_service.py
 M backend/app/services/media_storage.py
 M backend/app/services/rate_limiter.py
 M backend/app/services/sms_auth_service.py
 M backend/tests/test_customer_app.py
 M backend/tests/test_rate_limiter.py
 M backend/tests/test_sms_auth.py
 M mobile/app/(app)/(tabs)/profile.tsx
 M mobile/app/login.tsx
 M mobile/package-lock.json
 M mobile/package.json
 M mobile/src/api/app.ts
 M mobile/src/api/client.ts
 M mobile/src/demo/mockApi.ts
 M mobile/src/features/profile.tsx
 M mobile/src/i18n/kz.ts
 M mobile/src/i18n/ru.ts
 M mobile/src/types/api.ts
 M mobile/src/utils/format.ts
 M mobile/tests/core.test.ts
 M mobile/tests/flows.test.tsx
 M mobile/tests/profileSave.test.tsx
?? C:/
?? backend/migrations/versions/0011_customer_avatar.py
?? backend/tests/test_customer_avatar.py
?? docs/PROMPT_APP_AVATAR_2026-11-01.md
?? docs/PROMPT_APP_LOGIN_PROFILE_2026-11-01.md
?? docs/PROMPT_APP_LOGIN_PROFILE_FIX_2026-11-01.md
?? mobile/tests/avatar.test.tsx
?? mobile/tests/loginScreen.test.tsx
?? reports/APP_AVATAR_2026-11-01.md
?? reports/APP_LOGIN_PROFILE_2026-11-01.md
?? reports/APP_LOGIN_PROFILE_FIX_2026-11-01.md
?? video/
```

```text
$ git diff --stat
 backend/app/api/auth.py                  |  16 +-
 backend/app/api/customer_app.py          | 116 +++++++++-
 backend/app/core/config.py               |  17 ++
 backend/app/core/security.py             |   7 +-
 backend/app/models/entities.py           |   1 +
 backend/app/schemas/auth.py              |  11 +-
 backend/app/schemas/customer_app.py      |   7 +-
 backend/app/services/image_service.py    |  94 +++++---
 backend/app/services/media_storage.py    |  13 +-
 backend/app/services/rate_limiter.py     |  24 ++
 backend/app/services/sms_auth_service.py |  43 +++-
 backend/tests/test_customer_app.py       |  41 ++++
 backend/tests/test_rate_limiter.py       |  33 +++
 backend/tests/test_sms_auth.py           | 184 +++++++++++++++
 mobile/app/(app)/(tabs)/profile.tsx      | 261 +++++++++++++++++----
 mobile/app/login.tsx                     |  21 +-
 mobile/package-lock.json                 |  35 +++
 mobile/package.json                      |   2 +
 mobile/src/api/app.ts                    |  23 +-
 mobile/src/api/client.ts                 |   7 +-
 mobile/src/demo/mockApi.ts               |  22 +-
 mobile/src/features/profile.tsx          |  82 ++++++-
 mobile/src/i18n/kz.ts                    |  12 +-
 mobile/src/i18n/ru.ts                    |  17 +-
 mobile/src/types/api.ts                  |   1 +
 mobile/src/utils/format.ts               |  65 ++++++
 mobile/tests/core.test.ts                |  67 +++++-
 mobile/tests/flows.test.tsx              |  10 +-
 mobile/tests/profileSave.test.tsx        | 373 +++++++++++++++++--------------
 29 files changed, 1294 insertions(+), 311 deletions(-)
```

---

## 5. Не проверено на этом этапе

В соответствии с требованиями задания, следующие проверки сознательно отложены:
- Настоящая загрузка на FTPS-хостинг (тесты проводились изолированно с `InMemoryMediaStorage`).
- Выбор фото через галерею на реальном Android/iOS устройстве (проверено в Jest с моками).
- Разрешения в AndroidManifest/APK (будут сверены при последующей сборке APK).
- Применение миграции `0011_customer_avatar` на production базе PostgreSQL.

## Приёмка куратора — 2026-11-01: принято с замечаниями

**Подтверждено независимо**

- Числа отчёта совпали: pytest 373 passed / 36 skipped, jest 190 passed, tsc и ruff чисто, eslint 1 предупреждение.
- Миграция на временном локальном PostgreSQL 16: `upgrade head` с нуля, `downgrade` до 0010, снова `upgrade`, `alembic check` без расхождений. Тест исполнителя проверяет только SQLite.
- 37 тестов `-k postgres` прошли на том же временном PostgreSQL, база удалена.
- Метаданные: JPEG, PNG, WebP и GIF с EXIF, XMP, ICC и комментариями. На выходе в WebP только графические блоки, образцов метаданных в байтах нет, размер 512×512, один кадр.
- FTPS сам создаёт `media/avatars/` (`_ensure_dir`). Лимит Caddy 2 МБ больше лимита загрузки 1,5 МБ, других ограничений тела для `/me/avatar` нет.
- Список файлов на хостинге закрыт: `media/` и `media/promotions/` отвечают 403.
- Кабинет не может загрузить `avatar`: `admin.py` пропускает только `promotion` и `logo`.

**Замечания**

1. Значок на круге — иконка `scan`, рамка сканера с чертой. Камеры и карандаша в `icons.tsx` нет. Выглядит как сканер, нужна своя иконка.
2. Сводка исполнителя о переводах ошибок для RU и KZ неверна. `errorMessages` существует только в `ru.ts`, поэтому на казахском ошибки фото показываются по-русски, как и все остальные ошибки приложения. Давняя особенность, не поломка этого этапа.
3. `manipulateAsync` в этой версии модуля помечен deprecated, но работает.
4. `expo-image-picker` добавит в APK `READ_EXTERNAL_STORAGE` и `WRITE_EXTERNAL_STORAGE` (до API 32). `CAMERA` уже есть. Решить при сборке, сверить итоговый манифест.
5. FTPS идёт внутри запроса: сохранение нового файла и удаление старого, у клиента таймаут 15 с. При медленном хостинге покупатель увидит ошибку, хотя фото сохранится. Замерить на сервере.
6. Мягкое удаление покупателя файл фото не убирает. Маршрута удаления аккаунта в API покупателя нет.

**Не проверено:** настоящая загрузка на хостинг, выбор фото на телефоне, миграция на production, итоговый манифест APK.
