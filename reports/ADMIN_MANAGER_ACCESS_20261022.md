# Отчёт: Автоматическое создание и сброс доступа менеджера бизнеса (business_manager)

**Дата:** 2026-10-22  
**Исполнитель:** Gemini(general)  
**Репозиторий:** `C:\Users\ШОУРУМ\Desktop\cashback-one`

---

## 1. Что изменено (файлы)

### Backend
1. **`backend/app/core/config.py`**
   - Добавлена настройка `admin_public_url: str = Field(default="")`.
   - В `validate_configuration` задано значение по умолчанию: первый источник из `ADMIN_ALLOWED_ORIGINS` или `"https://cashback-qr.poscenter.kz"`. В production валидируется протокол HTTPS.
2. **`backend/app/schemas/admin.py`**
   - Добавлена схема `ManagerAccessDisclosure` (`login: str`, `password: str`, `login_url: str`, `one_time: Literal[True] = True`).
   - В `BusinessCreateRequest` добавлено опциональное поле `create_manager: bool = True`.
   - Добавлен ответ `BusinessCreatedResponse(BusinessDetail)` с полем `manager_access: ManagerAccessDisclosure | None = None`.
3. **`backend/app/services/admin_security.py`**
   - Таблица транслитерации кириллицы в латиницу `CYRILLIC_TO_LATIN` (русские буквы + расширения казахского алфавита).
   - Функции `transliterate_business_name` и `generate_base_login` для формирования чистого базового логина `[a-z0-9._@-]` длиной 3–40 символов (при пустом/нечитаемом названии — `biz-<slug>`).
   - Функция `generate_manager_password(length: int = 16)`: генератор пароля через `secrets`, длина ≥ 16, только буквы и цифры без неоднозначных символов (`0`, `O`, `1`, `l`, `I`), обязательно содержащий строчные, заглавные буквы и цифры.
4. **`backend/app/services/admin_mutations.py`**
   - В `_KNOWN_ADMIN_ACTIONS` добавлены действия `business_manager_created` и `business_manager_password_reset`.
   - В `_project_action_snapshot` добавлена безопасная проекция аудита для этих действий: сохраняются только `id` и `login` (пароли и хеши гарантированно отсекаются).
   - `generate_unique_manager_login`: проверка коллизий в базе данных и добавление уникального случайного суффикса (например, `-k7f2`) с валидацией через `normalize_admin_login`.
   - `create_business`: создание бизнеса и при `create_manager=True` создание `AdminUser(role="business_manager", business_id=business.id, is_active=True)`, запись аудита `business_manager_created`, возврат кортежа `(business, manager_access)` в единой транзакции.
   - `reset_or_create_business_manager`: создание или сброс пароля основного (самого раннего) менеджера бизнеса, обновление `password_hash`, включение `is_active=True`, немедленный отзыв всех активных сессий (`AdminSession.revoked_at = utcnow()`), аудит `business_manager_password_reset` и возврат `ManagerAccessDisclosure`.
5. **`backend/app/api/admin.py`**
   - `POST /admin/businesses`: ответ `BusinessCreatedResponse`, заголовок `Cache-Control: no-store`.
   - `POST /admin/businesses/{business_id}/manager-access`: доступен только суперадмину (`require_superadmin`), ответ `ManagerAccessDisclosure`, заголовок `Cache-Control: no-store`.
6. **`backend/tests/test_admin_mutations.py`**
   - Актуализированы проверки событий аудита с учётом нового штатного создания менеджера при создании бизнеса.
7. **`backend/tests/test_admin_manager_access.py`** (новый)
   - 8 комплексных тестов на все требования ТЗ.

### Frontend (Admin)
1. **`admin/src/api/types.ts`**
   - Добавлены интерфейсы `ManagerAccessDisclosure` и `BusinessCreatedResponse`.
2. **`admin/src/features/AdminMutations.tsx`**
   - `BusinessEditorDialog`: при создании бизнеса принимает `BusinessCreatedResponse` и передаёт `manager_access` в `onSaved(manager_access)`.
   - `ManagerAccessDialog`: доступное модальное окно (`role="dialog"`, trap focus, закрытие по `Escape` и кнопке) с предупреждением о разовом показе, отображением ссылки, логина и пароля в моноширинном блоке `.secret-key`, кнопкой «Скопировать всё» (в 3 строки) и «Закрыть».
3. **`admin/src/pages/BusinessesPage.tsx`**
   - В `BusinessesPage`: показ `ManagerAccessDialog` сразу после создания бизнеса и удаление данных доступа из состояния при закрытии.
   - В `BusinessDetailPage`: кнопка суперадмина «Выдать доступ / Сбросить пароль» с подтверждением через `window.confirm`, вызовом `POST /admin/businesses/{id}/manager-access` и показом `ManagerAccessDialog`. Кнопка скрыта от роли `business_manager`.
4. **`admin/tests/manager-access.test.tsx`** (новый)
   - 4 теста vitest: рендеринг диалога раскрытия, копирование всех строк в буфер, очистка данных из DOM после закрытия, сброс пароля на странице бизнеса, скрытие кнопки от менеджера.

---

## 2. Эндпоинты и поля ответа

### `POST /admin/businesses`
- **Доступ:** только `superadmin` (`require_superadmin`)
- **Заголовки ответа:** `Cache-Control: no-store`
- **Тело запроса (`BusinessCreateRequest`):**
  - `name: str` (обязательно)
  - `logo_url: str | None = None`
  - `colors: dict | None = None`
  - `barcode_prefixes: list[str] | None = None`
  - `status: "active" | "inactive" = "active"`
  - `create_manager: bool = True` (опционально)
- **Тело ответа (`BusinessCreatedResponse`):**
  - Все поля `BusinessDetail` (`id`, `name`, `logo_url`, `colors`, `barcode_prefixes`, `status`, `cards_count`, `unblocked_cards_count`, `customers_with_cards_count`, `agents_count`, `created_at`, `updated_at`)
  - `manager_access: ManagerAccessDisclosure | None`

### `POST /admin/businesses/{business_id}/manager-access`
- **Доступ:** только `superadmin` (`require_superadmin`), при вызове менеджером — 403 `ADMIN_FORBIDDEN`
- **Заголовки ответа:** `Cache-Control: no-store`
- **Тело ответа (`ManagerAccessDisclosure`):**
  - `login: str`
  - `password: str` (разово)
  - `login_url: str`
  - `one_time: true`

---

## 3. Примеры запросов и ответов (без секретов)

### Создание бизнеса с автоматическим созданием менеджера
```http
POST /admin/businesses HTTP/1.1
Host: api.cashback-qr.poscenter.kz
Origin: https://cashback-qr.poscenter.kz
X-Admin-Request: 1
Authorization: Bearer <superadmin_token>
Content-Type: application/json

{
  "name": "Кофейня Аромат",
  "status": "active"
}
```

**Ответ (201 Created):**
```http
HTTP/1.1 201 Created
Cache-Control: no-store
Content-Type: application/json

{
  "id": "e6f42b31-8bc4-41d3-a4c3-18ef5591d29a",
  "name": "Кофейня Аромат",
  "status": "active",
  "logo_url": null,
  "colors": null,
  "barcode_prefixes": null,
  "cards_count": 0,
  "unblocked_cards_count": 0,
  "customers_with_cards_count": 0,
  "agents_count": 0,
  "created_at": "2026-10-22T05:50:00Z",
  "updated_at": "2026-10-22T05:50:00Z",
  "manager_access": {
    "login": "kofeynya-aromat",
    "password": "<GENERATED_PASSWORD_16_CHARS>",
    "login_url": "https://cashback-qr.poscenter.kz",
    "one_time": true
  }
}
```

### Сброс пароля / выдача доступа существующему бизнесу
```http
POST /admin/businesses/e6f42b31-8bc4-41d3-a4c3-18ef5591d29a/manager-access HTTP/1.1
Host: api.cashback-qr.poscenter.kz
Origin: https://cashback-qr.poscenter.kz
X-Admin-Request: 1
Authorization: Bearer <superadmin_token>
```

**Ответ (200 OK):**
```http
HTTP/1.1 200 OK
Cache-Control: no-store
Content-Type: application/json

{
  "login": "kofeynya-aromat",
  "password": "<NEW_GENERATED_PASSWORD_16_CHARS>",
  "login_url": "https://cashback-qr.poscenter.kz",
  "one_time": true
}
```

### Формат скопированного текста кнопки «Скопировать всё»:
```text
Ссылка: https://cashback-qr.poscenter.kz
Логин: kofeynya-aromat
Пароль: <GENERATED_PASSWORD_16_CHARS>
```

---

## 4. Git diff --stat

```text
 admin/src/api/types.ts                  |   9 ++
 admin/src/features/AdminMutations.tsx   |  54 ++++++++++-
 admin/src/pages/BusinessesPage.tsx      |  43 +++++++-
 backend/app/api/admin.py                |  30 +++++-
 backend/app/core/config.py              |  15 +++
 backend/app/schemas/admin.py            |  14 +++
 backend/app/services/admin_mutations.py | 167 ++++++++++++++++++++++++++++++--
 backend/app/services/admin_security.py  |  59 +++++++++++
 backend/tests/test_admin_mutations.py   |  22 +++--
 9 files changed, 397 insertions(+), 16 deletions(-)

Новые файлы тестов:
 admin/tests/manager-access.test.tsx
 backend/tests/test_admin_manager_access.py
```

---

## 5. Итоговые строки проверок

### 5.1. Backend тесты
```powershell
& 'C:\cashback-backend-venv\Scripts\python.exe' -m pytest backend/tests/test_admin_manager_access.py backend/tests/test_admin_mutations.py backend/tests/test_admin_cli.py -q
```
**Результат:** `28 passed in 34.44s` (100% зелёные)

### 5.2. Backend линтер Ruff
```powershell
& 'C:\cashback-venv\Scripts\ruff.exe' check backend/app backend/tests/test_admin_manager_access.py
```
**Результат:** `All checks passed!`

### 5.3. Admin Typecheck
```powershell
npm run --prefix admin typecheck
```
**Результат:** `tsc --noEmit` — 0 ошибок, код 0.

### 5.4. Admin Vitest тесты
```powershell
npm test --prefix admin -- --run --testTimeout=10000
```
**Результат:** `Test Files 11 passed (11), Tests 57 passed (57)` (100% зелёные)

### 5.5. Admin Production Build
```powershell
npm run --prefix admin build
```
**Результат:**
```text
dist/index.html                   0.57 kB │ gzip:   0.35 kB
dist/assets/index-CKyKwx7j.css   22.68 kB │ gzip:   5.65 kB
dist/assets/index--vdAybt5.js   382.69 kB │ gzip: 113.31 kB
✓ built in 931ms
```

---

## 6. Как проверить на тестовом бизнесе после деплоя куратором

1. Войти в админку под суперадмином: `https://cashback-qr.poscenter.kz/login`.
2. Перейти в раздел «Бизнесы» (`/businesses`).
3. Нажать «Создать бизнес», ввести тестовое название (например, «Тест Кафе») и нажать «Создать»:
   - Открывается окно «Доступ клиента к админке» с текстом предупреждения.
   - Отображаются ссылка для входа, сгенерированный логин `test-kafe` и пароль из 16 символов.
   - Нажать «Скопировать всё» → всплывает «Скопировано в буфер обмена».
   - Нажать «Закрыть» → окно закрывается, пароль исчезает из DOM.
4. Открыть созданный бизнес в карточке (`/businesses/{id}`):
   - Нажать кнопку «Выдать доступ / Сбросить пароль».
   - Появляется подтверждение браузера («Старый пароль перестанет работать, активные входы менеджера будут завершены.»).
   - Нажать «ОК» → открывается то же окно «Доступ клиента к админке» с новым паролем.
5. Проверить вход менеджера:
   - В режиме инкогнито открыть `https://cashback-qr.poscenter.kz/login`.
   - Ввести логин менеджера и скопированный пароль.
   - Вход успешен; менеджер видит только свой бизнес, не имеет доступа к разделу «Бизнесы» и не видит кнопку «Выдать доступ / Сбросить пароль».
