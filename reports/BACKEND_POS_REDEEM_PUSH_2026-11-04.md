# Отчёт по задаче B: Ключи касс и подтверждение списания баллов через push-код (2026-11-04)

## 1. Контекст и цели

Задача выполнена в соответствии с `docs/PROMPT_BACKEND_POS_REDEEM_PUSH_2026-11-04.md` (Задача B) в рамках курса `docs/ROADMAP_PER_CLIENT_2026-11-04.md`.

### Основные изменения и архитектурные решения:
1. **Касса Cash обращается напрямую в облако:**
   Агент лояльности работает на сервере/компьютере оператора 1С:ONE, а не на каждой кассе. Поэтому кассовый терминал Cash взаимодействует **напрямую с облачным backend** по защищённому протоколу HTTPS (`/pos/*`).
2. **Изолированный ключ кассы (`X-Pos-Key`):**
   Ключ агента даёт права на запись карт и транзакций, поэтому его размещение на кассе создало бы риск подмены балансов при компрометации кассы. Ключ кассы (`pos_...`) имеет строго ограниченную область действия: он позволяет только инициировать запрос кода списания и проверять введённый код для карт своего бизнеса. В базе данных хранится только SHA-256 хеш ключа.
3. **Push-уведомление с кодом из 4 цифр:**
   При запросе списания покупателю отправляется push-уведомление через Firebase Cloud Messaging (`FakePushSender` в тестах, `FcmPushSender` в проде). Код не передаётся в поле `data` push-сообщения (только в тексте заголовка/тела push). Если у покупателя нет приложения или нет активных push-устройств, запрос отклоняется с кодом `CUSTOMER_NO_APP` без генерации кода.
4. **Уведомление в приложении (`Notification`):**
   Для покупателей, у которых системный push был скрыт или случайно смахнут, создаётся запись в таблице `notifications`, видимая в разделе уведомлений мобильного приложения.
5. **Строгая сверка с 1С:Cash (`cash_redeem_code.bsl`):**
   Реализация полностью соответствует контракту модуля `docs/integrations/cash_redeem_code.bsl` (эндпоинты, коды статусов 201/200, формат ответов, валидация и коды ошибок).
6. **Отключение устаревшего WhatsApp-канала:**
   Старый эндпоинт `/agent/redemptions` отключён по умолчанию (`REDEMPTION_WHATSAPP_ENABLED=false`) и возвращает HTTP 410 `REDEMPTION_CHANNEL_DISABLED`.
7. **Интерфейс в кабинете администратора:**
   На странице бизнеса суперадминистратору доступен блок «Кассы» с возможностью выпуска ключа (показывается один раз с кнопкой копирования и инструкцией по вводу в Cash), списком активных/отозванных касс и подтверждением отзыва. Поддерживаются русский и казахский языки, адаптивная вёрстка без горизонтального скролла на 320–1366 px, шрифт Roboto.

---

## 2. Изменённые и созданные файлы

### Бэкенд (`backend/`):
- `backend/migrations/versions/0014_pos_keys.py` *(новый)* — миграция Alembic: таблица `pos_keys` (`id`, `business_id`, `name`, `key_hash`, `created_at`, `last_used_at`, `revoked_at`), индексы `ix_pos_keys_key_hash`, `ix_pos_keys_business_created`, внешний ключ с каскадным удалением к `businesses.id`, обратимый `downgrade`.
- `backend/app/models/entities.py` — ORM-модель `PosKey` и отношение `pos_keys` в модели `Business`.
- `backend/app/models/__init__.py` — экспорт моделей `PosKey`, `BusinessStore`.
- `backend/app/core/config.py` — флаг конфигурации `redemption_whatsapp_enabled: bool = False`.
- `.env.example` — документирование переменной `REDEMPTION_WHATSAPP_ENABLED=false`.
- `backend/app/schemas/pos.py` — схемы `PosRedemptionRequest`, `PosRedemptionResponse`, `PosRedemptionVerifyRequest`.
- `backend/app/schemas/admin.py` — схемы `PosKeyItem`, `PosKeyCreateRequest`, `PosKeyCreateResponse`.
- `backend/app/services/pos_auth.py` *(новый)* — функции выпуска ключа `issue_pos_key`, хеширования `hash_pos_key`, аутентификации `authenticate_pos_key` (с троттлингом `last_used_at` 1 мин) и отзыва `revoke_pos_key`.
- `backend/app/services/pos_service.py` *(новый)* — сервисные методы `request_pos_redemption` (проверка карты, наличия push-устройства, лимитов, аннулирование старых кодов, отправка push, создание записи в `notifications`) и `verify_pos_redemption` (проверка 4-значного OTP, учет попыток, экспирация, защита от повторного подтверждения).
- `backend/app/services/admin_mutations.py` — методы создания ключа `create_pos_key_mutation` и отзыва `revoke_pos_key_mutation` с записью в `audit_log` (без раскрытия открытого ключа и хеша).
- `backend/app/services/admin_queries.py` — метод `list_pos_keys` (только суперадминистратор).
- `backend/app/api/admin.py` — эндпоинты `GET /businesses/{id}/pos-keys`, `POST /businesses/{id}/pos-keys`, `POST /pos-keys/{key_id}/revoke`.
- `backend/app/api/pos.py` *(новый)* — роутер `/pos` с эндпоинтами `POST /pos/redemptions` и `POST /pos/redemptions/{id}/verify`.
- `backend/app/api/agent_pos.py` — проверка `REDEMPTION_WHATSAPP_ENABLED` с возвратом HTTP 410 `REDEMPTION_CHANNEL_DISABLED`.
- `backend/app/main.py` — подключение `pos_router`.
- `backend/tests/test_admin_pos_keys.py` *(новый)* — 5 тестов: выдача ключа один раз, список без ключа/хеша, отзыв, разграничение прав ролей, аудит без утечки секрета.
- `backend/tests/test_pos_api.py` *(новый)* — 19 тестов: авторизация (отсутствие/неверный/отозванный ключ), изоляция тенантов, валидация штрихкодов и сумм (число/строка), отсутствие приложения у клиента (`CUSTOMER_NO_APP`), лимиты, откат при ошибке push, проверка кода, неверный код, 5 попыток, экспирация, аннулирование старого кода.
- `backend/tests/test_customer_app.py` — тесты legacy WhatsApp с monkeypatch настройки и проверка статуса 410 по умолчанию.

### Кабинет администратора (`admin/`):
- `admin/src/api/types.ts` — TypeScript-интерфейсы `PosKey`, `PosKeyDisclosure`.
- `admin/src/api/queries.ts` — хук React Query `usePosKeys`.
- `admin/src/features/BusinessPosKeys.tsx` *(новый)* — компонент «Кассы» с модальными окнами создания (`PosKeyCreateDialog`), раскрытия ключа один раз (`PosKeyDialog`), отзыва (`PosKeyRevokeDialog`), десктопной таблицей и мобильными карточками.
- `admin/src/pages/BusinessesPage.tsx` — интеграция `<BusinessPosKeys />` на странице `BusinessDetailPage` с ограничением `role === 'superadmin'`.
- `admin/src/styles/admin.css` — адаптивные стили для `.pos-keys-cards`, `.pos-key-card`, `.pos-keys-table-wrap`.
- `admin/src/i18n/admin.ts` — переводы всех элементов раздела «Кассы» на русский (`adminRu`) и казахский (`adminKk`).
- `admin/tests/pos-keys.test.tsx` *(новый)* — 6 тестов Vitest: отображение ключа один раз и копирование, создание с валидацией, отзыв, рендеринг таблицы для суперадмина, локализация на казахский язык, сокрытие блока от менеджера бизнеса.

### Документация и скриншоты:
- `docs/POS_REDEEM_API.md` *(новый)* — руководство по интеграции для разработчиков POSCENTER Cash с примерами `curl`, описанием всех кодов ошибок, сроков и лимитов.
- `reports/pos-redeem-2026-11-04/pos-keys-ru-1366.png` *(новый)* — десктопный скриншот блока «Кассы» на русском языке (1366 px).
- `reports/pos-redeem-2026-11-04/pos-keys-ru-390.png` *(новый)* — мобильный скриншот блока «Кассы» на русском языке (390 px).
- `reports/pos-redeem-2026-11-04/pos-keys-kk-1366.png` *(новый)* — десктопный скриншот блока «Кассы» на казахском языке (1366 px).
- `reports/pos-redeem-2026-11-04/pos-keys-kk-390.png` *(новый)* — мобильный скриншот блока «Кассы» на казахском языке (390 px).
- `reports/BACKEND_POS_REDEEM_PUSH_2026-11-04.md` *(этот документ)*.

---

## 3. Проверки до правок (Baseline)

Числа до правок (после принятия исправлений задачи G):
1. **Бэкенд тесты (`backend/.venv/bin/pytest -q`):**
   - Вывод: `397 passed, 36 skipped`
2. **Бэкенд линтер (`backend/.venv/bin/ruff check app`):**
   - Вывод: `All checks passed!`
3. **Бэкенд mypy (`backend/.venv/bin/mypy app`):**
   - Вывод: `Found 16 errors in 2 files` (только baseline в `media_storage.py` и `image_service.py`).
4. **Бэкенд PostgreSQL (`POSTGRES_TEST_URL="..." .venv/bin/pytest -k postgres`):**
   - Вывод: `37 passed, 396 deselected`
5. **Кабинет Vitest (`admin/` -> `npx vitest run --maxWorkers=1`):**
   - Вывод: `Test Files 21 passed (21), Tests 169 passed (169)`
6. **Кабинет typecheck, lint, build:**
   - Вывод: 0 ошибок, exit code 0.

---

## 4. Проверки после правок (Final)

### 4.1. Бэкенд тесты (`.venv/bin/pytest -q`)
```
422 passed, 36 skipped, 4 warnings in 75.03s (0:01:15)
```
*(Прирост: +25 пройденных тестов: 5 в `test_admin_pos_keys.py`, 19 в `test_pos_api.py`, 1 в `test_customer_app.py`).*

### 4.2. Бэкенд линтер (`.venv/bin/ruff check app`)
```
All checks passed!
```

### 4.3. Бэкенд статический анализ (`.venv/bin/mypy app`)
```
app/services/media_storage.py:137: error: Exception type must be derived from BaseException (or be a tuple of exception classes)  [misc]
app/services/media_storage.py:143: error: Exception type must be derived from BaseException (or be a tuple of exception classes)  [misc]
app/services/media_storage.py:155: error: Exception type must be derived from BaseException (or be a tuple of exception classes)  [misc]
app/services/media_storage.py:159: error: Exception type must be derived from BaseException (or be a tuple of exception classes)  [misc]
app/services/media_storage.py:164: error: Exception type must be derived from BaseException (or be a tuple of exception classes)  [misc]
app/services/media_storage.py:186: error: Exception type must be derived from BaseException (or be a tuple of exception classes)  [misc]
app/services/media_storage.py:188: error: Exception type must be derived from BaseException (or be a tuple of exception classes)  [misc]
app/services/media_storage.py:193: error: Exception type must be derived from BaseException (or be a tuple of exception classes)  [misc]
app/services/media_storage.py:261: error: Exception type must be derived from BaseException (or be a tuple of exception classes)  [misc]
app/services/image_service.py:57: error: Module "PIL.Image" does not explicitly export attribute "UnidentifiedImageError"  [attr-defined]
app/services/image_service.py:86: error: Module "PIL.Image" does not explicitly export attribute "UnidentifiedImageError"  [attr-defined]
app/services/image_service.py:101: error: Incompatible types in assignment (expression has type "Image", variable has type "ImageFile")  [assignment]
app/services/image_service.py:112: error: Incompatible types in assignment (expression has type "Image", variable has type "ImageFile")  [assignment]
app/services/image_service.py:114: error: Incompatible types in assignment (expression has type "Image", variable has type "ImageFile")  [assignment]
app/services/image_service.py:122: error: Incompatible types in assignment (expression has type "Image", variable has type "ImageFile")  [assignment]
app/services/image_service.py:124: error: Incompatible types in assignment (expression has type "Image", variable has type "ImageFile")  [assignment]
Found 16 errors in 2 files (checked 68 source files)
```
*(Ровно те же 16 baseline ошибок, 0 новых ошибок).*

### 4.4. Тесты PostgreSQL 16 (`-k postgres`)
```
================ 37 passed, 421 deselected, 1 warning in 19.38s ================
```

### 4.5. Тестирование миграции Alembic (upgrade -> downgrade -> upgrade)
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
...
INFO  [alembic.runtime.migration] Running upgrade 0013_business_app_content -> 0014_pos_keys, POS cash register access keys.
INFO  [alembic.runtime.migration] Running downgrade 0014_pos_keys -> 0013_business_app_content, POS cash register access keys.
INFO  [alembic.runtime.migration] Running upgrade 0013_business_app_content -> 0014_pos_keys, POS cash register access keys.
```
*(Двусторонний откат и накат прошли успешно без ошибок).*

### 4.6. Тесты кабинета Vitest (`admin/` -> `npx vitest run --maxWorkers=1`)
```
 Test Files  22 passed (22)
      Tests  175 passed (175)
   Start at  17:56:56
   Duration  73.62s
```
*(Прирост: +6 новых тестов в файле `tests/pos-keys.test.tsx`, 100% passed).*

### 4.7. Проверки кабинета: TypeScript, ESLint, сборка Vite
```
> cashback-one-admin@1.0.0 typecheck
> tsc --noEmit

> cashback-one-admin@1.0.0 lint
> eslint .

> cashback-one-admin@1.0.0 build
> tsc --noEmit && vite build
✓ built in 533ms
```
*(Все команды завершились с кодом 0).*

### 4.8. Проверка Git (`git diff --check`)
```
(exit code 0, no trailing spaces or blank lines at EOF)
```

---

## 5. Формат API для POS-касс Cash

Полная документация для разработчиков вынесена в `docs/POS_REDEEM_API.md`.

### 5.1. Заголовки авторизации
Каждый запрос кассы сопровождается заголовком:
```
X-Pos-Key: pos_<32+ случайных символов>
Content-Type: application/json; charset=utf-8
```

При отсутствии или ошибке ключа сервер возвращает HTTP 401:
- `POS_KEY_MISSING` — отсутствует заголовок `X-Pos-Key`;
- `POS_KEY_INVALID` — ключ не найден в базе данных;
- `POS_KEY_REVOKED` — ключ был отозван администратором.

### 5.2. `POST /pos/redemptions` — запрос кода списания (Шаг 1)
**Запрос:**
```json
{
  "barcode": "100000000001",
  "amount": "150.5"
}
```
*(Принимает `amount` как строку или число > 0, `barcode` от 4 до 13 цифр).*

**Успешный ответ (HTTP 201 Created):**
```json
{
  "redemption_id": "c8b417e2-4899-4d6b-9e4a-9ef85d0d8be3",
  "expires_at": "2026-11-04T12:05:00Z"
}
```
*(Телефон покупателя в ответе НЕ возвращается).*

**Ошибки:**
- `400 VALIDATION_ERROR`: неверный формат штрихкода или сумма <= 0;
- `404 CARD_NOT_FOUND`: карта не принадлежит бизнесу кассы или не существует;
- `409 CARD_BLOCKED`: карта заблокирована;
- `409 CUSTOMER_NO_APP`: карта не привязана к пользователю, либо у пользователя нет активных push-устройств (`has_active_device == False`);
- `429 RATE_LIMIT_EXCEEDED`: более 5 запросов кода на карту за 10 минут;
- `503 PUSH_DELIVERY_FAILED`: сбой доставки push (откат создания кода).

### 5.3. `POST /pos/redemptions/{id}/verify` — проверка кода (Шаг 2)
**Запрос:**
```json
{
  "code": "7294"
}
```
*(Строго 4 цифры).*

**Успешный ответ (HTTP 200 OK):**
```json
{
  "status": "confirmed",
  "barcode": "100000000001",
  "amount": "150.5000"
}
```

**Ошибки:**
- `400 VALIDATION_ERROR`: код не из 4 цифр;
- `400 INVALID_CODE`: неверный код (до 5 попыток ввода);
- `404 REDEMPTION_NOT_FOUND`: списание не найдено или принадлежит чужому бизнесу;
- `409 REDEMPTION_EXPIRED`: истёк срок 300 секунд;
- `409 REDEMPTION_MAX_ATTEMPTS_EXCEEDED`: исчерпаны 5 попыток ввода;
- `409 REDEMPTION_NOT_ACTIVE`: код аннулирован (выпущен более свежий код на эту карту);
- `409 REDEMPTION_ALREADY_CONFIRMED`: код уже был ранее подтверждён.

---

## 6. Результат сверки с `docs/integrations/cash_redeem_code.bsl`

Сверка показала **100% совпадение контракта без каких-либо расхождений**:
1. **Маршруты:** `/pos/redemptions` и `/pos/redemptions/` + `ИдЗапроса` + `/verify` в 1С соответствуют роутеру `/pos`.
2. **Заголовки:** В 1С передаются `Content-Type: application/json; charset=utf-8` и `X-Pos-Key: КлючКассы` — бэкенд ожидает именно их.
3. **Статусы ответов:** 1С ожидает HTTP 201 при запросе кода (`Ответ.Код = 201`) и HTTP 200 при верификации (`Ответ.Код = 200`).
4. **Поля ответа:**
   - Шаг 1: `redemption_id` читается через `Ответ.Данные.Свойство("redemption_id", ИдЗапроса)`.
   - Шаг 2: проверяются `status == "confirmed"`, `barcode` (строка, сохраняющая нули) и `amount` (строка с десятичной точкой).
5. **Коды ошибок в функции `ТекстОшибки` в 1С:**
   Все коды `CUSTOMER_NO_APP`, `INVALID_CODE`, `REDEMPTION_EXPIRED`, `REDEMPTION_MAX_ATTEMPTS_EXCEEDED`, `REDEMPTION_NOT_ACTIVE`, `REDEMPTION_ALREADY_CONFIRMED`, `CARD_NOT_FOUND`, `CARD_BLOCKED`, `RATE_LIMIT_EXCEEDED`, `PUSH_DELIVERY_FAILED`, `POS_KEY_MISSING`, `POS_KEY_INVALID`, `POS_KEY_REVOKED`, `VALIDATION_ERROR` возвращаются сервером в поле `error.code`.
6. Файл `docs/integrations/cash_redeem_code.bsl` оставлен **без изменений**.

---

## 7. Хранение кода в уведомлении (`Notification`) и стратегия очистки

### 7.1. Текущая ситуация
В соответствии с п. 2 задачи, при успешной отправке push-сообщения создаётся также запись в таблице `notifications` (`user_id`, `business_id`, заголовок и текст сообщения).
- Текст сообщения содержит 4-значный код: *«Код {code} для списания {сумма} баллов в «{название бизнеса}»...»*.
- В таблице `notifications` поле `body` хранится в открытом текстовом виде (в отличие от `redemption_codes.code_hash`, где хранится только SHA-256 хеш).

### 7.2. Зачем это нужно
Пользователи Android/iOS нередко отключают показ баннеров на заблокированном экране, используют режимы «Не беспокоить» или случайно смахивают входящий push. Дублирование кода в разделе «Уведомления» внутри мобильного приложения позволяет покупателю открыть приложение прямо у кассы и посмотреть код там.

### 7.3. Предлагаемая стратегия очистки (Retention Policy)
Поскольку код списания действителен только 300 секунд (5 минут) и одноразов:
1. **Немедленная очистка при подтверждении списания:**
   В методе `verify_pos_redemption` при переводе статуса списания в `confirmed` находить соответствующее уведомление покупателя по `business_id` и времени создания и:
   - либо заменять текст на безопасный: *«Списание {сумма} баллов успешно подтверждено на кассе»*;
   - либо удалять запись `Notification` из базы данных.
2. **Фоновый sweep по истечению срока (Celery / cron):**
   Раз в 10–15 минут запускать фоновую задачу очистки записей таблицы `notifications`, содержащих коды списаний (`type == 'redemption_code'` или по ключевому тексту), созданных более 15 минут назад.
3. Это предотвратит накопление открытых кодов в истории уведомлений пользователя.

---

## 8. Что необходимо для включения на Production

Для активации функционала подтверждения списания через push на продакшене потребуется:
1. **Применение миграций базы данных:**
   Выполнить на сервере:
   ```bash
   alembic upgrade head
   ```
   (Применяются миграции `0012_push_devices`, `0013_business_app_content`, `0014_pos_keys`).
2. **Настройка Firebase Cloud Messaging:**
   - В `.env` продакшена задать:
     ```env
     PUSH_PROVIDER_MODE=fcm
     FIREBASE_PROJECT_ID=<project-id>
     FIREBASE_CREDENTIALS_JSON=<json-строка-сервисного-аккаунта>
     ```
   - Убедиться, что мобильные приложения клиентов отправляют FCM-токены через `POST /me/push-device` (задача A).
3. **Выпуск ключей касс:**
   - Суперадминистратор заходит в кабинет `https://cashback-qr.poscenter.kz/admin/businesses/<id>`.
   - В блоке «Кассы» нажимает «Добавить кассу», указывает название (например, «Касса 1»).
   - Копирует сгенерированный один раз ключ вида `pos_live_...`.
4. **Настройка POS-терминала Cash:**
   - В настройках обработки Cashback One на кассе Cash указать:
     - `АдресОблака = "api.cashback-qr.poscenter.kz"`
     - `КлючКассы = pos_live_...`
5. **Проверка отключения WhatsApp:**
   - В `.env` оставить по умолчанию `REDEMPTION_WHATSAPP_ENABLED=false`.

---

## 9. Всё непроверенное

1. **Реальное сканирование на кассовом аппарате:**
   Интеграция протестирована на синтетических запросах, моках, юнит- и интеграционных тестах на PostgreSQL 16. Работа с физическим сканером штрихкодов в среде «1С:Предприятие 8.3 / POSCENTER Cash» требует натурного испытания с кассиром.
2. **Поведение сети кассы при обрыве связи:**
   В модуле `cash_redeem_code.bsl` предусмотрена обработка исключения соединения с кодом ошибки `CONNECTION_ERROR` и таймаутом 15 секунд. На реальной кассе поведение при нестабильном Wi-Fi канале должно быть проверено во время пилотного внедрения.

---

## 10. Скрытие кода в уведомлениях

### 10.1. Реализованные изменения

В соответствии с `docs/PROMPT_BACKEND_POS_REDEEM_CODE_HIDE_2026-11-04.md` устранено постоянное хранение открытого кода списания в уведомлениях покупателя:

1. **Связь уведомления со списанием в схеме данных:**
   - В сущность `Notification` (`backend/app/models/entities.py`) добавлено поле:
     `redemption_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("redemption_codes.id", ondelete="SET NULL"), nullable=True)`
   - Добавлен индекс `ix_notifications_redemption_id`.
   - Класс `RedemptionCode` в `entities.py` объявлен выше класса `Notification`, что обеспечивает корректный порядок создания таблиц и валидации внешних ключей в SQLite и PostgreSQL.
2. **Миграция Alembic `0015_notification_redemption`:**
   - Файл: `backend/migrations/versions/0015_notification_redemption.py`.
   - `down_revision`: `0014_pos_keys`.
   - Поддерживает безопасное и обратимое применение (`upgrade` и `downgrade`) через `batch_alter_table`.
3. **Обновление текста в базе данных при смене статуса (в той же транзакции):**
   - В `backend/app/services/pos_service.py`:
     - При создании кода (`request_pos_redemption`):
       - Если по карте были ожидающие (`pending`) списания, они переводятся в статус `superseded`, а текст связанных уведомлений сразу в БД обновляется на нейтральный: *«Код для списания {сумма} баллов в «{бизнес}» больше не действует.»*.
       - После добавления `RedemptionCode` выполняется `await session.flush()`, гарантируя наличие записи до создания `Notification(redemption_id=record_id)`.
     - При валидации кода на кассе (`verify_pos_redemption`):
       - При успешном списании (`confirmed`): текст связанного уведомления в БД заменяется на *«Списание {сумма} баллов в «{бизнес}» подтверждено на кассе.»*.
       - При исчерпании 5 попыток (`exhausted`) или при попытке ввода после истечения срока (`expired`): текст связанного уведомления в БД заменяется на *«Код для списания {сумма} баллов в «{бизнес}» больше не действует.»*.
       - Заголовок уведомления остаётся неизменным: *«Код для списания баллов»*.
4. **Пассивное истечение срока без обращения кассы (динамическая замена на лету):**
   - Если код истёк по таймеру TTL (300 секунд), но касса к нему не обращалась, статус в БД остаётся `pending`.
   - В `backend/app/services/content_service.py` функция `list_notifications` выполняет выборку с `outerjoin(RedemptionCode)` и `outerjoin(Business)`.
   - Если уведомление привязано к `redemption_id`, и при этом списание имеет статус отличный от `pending` либо срок `expires_at <= utcnow()`, в ответе API покупателю (`GET /me/notifications`) поле `body` динамически подменяется на нейтральный текст без кода.
   - Фоновые задачи (Celery/cron) не создавались, нагрузка на БД минимальна благодаря индексам.
5. **Особенность push-уведомлений на телефоне:**
   - Push-сообщение, уже доставленное на телефон покупателя через APNs/FCM операционной системой, остаётся в центре уведомлений устройства (так как стандартные уведомления не отзываются задним числом без специализированных silent/data payload и фонового кода приложения). Это штатное и ожидаемое поведение.
   - При этом в самом приложении и в API бэкенда код гарантированно скрыт и больше нигде не светится.

---

### 10.2. Изменённые и созданные файлы

1. `backend/app/models/entities.py` — добавлена колонка `redemption_id`, индекс `ix_notifications_redemption_id`, перемещён класс `RedemptionCode` перед `Notification`.
2. `backend/migrations/versions/0015_notification_redemption.py` — миграция схемы.
3. `backend/app/services/content_service.py` — хелперы `redemption_confirmed_text`, `redemption_inactive_text` и динамическая замена в `list_notifications`.
4. `backend/app/services/pos_service.py` — привязка уведомлений к кодам, `flush()`, немедленная замена текстов в БД при смене статусов (`confirmed`, `exhausted`, `expired`, `superseded`).
5. `backend/tests/test_pos_api.py` — добавлено 5 целевых тестов на скрытие кодов и пассивное истечение:
   - `test_notification_linked_and_cleared_on_confirm`
   - `test_notification_cleared_on_exhausted_attempts`
   - `test_notification_cleared_when_superseded_by_new_request`
   - `test_notification_passive_expiry_without_pos_request`
   - `test_ordinary_notifications_without_redemption_id_unaffected`

---

### 10.3. Сырой вывод проверок ДО правок

**1. Тесты pytest (baseline):**
```text
============================= test session starts ==============================
platform darwin -- Python 3.11.15, pytest-9.1.1, pluggy-1.7.0
rootdir: /Users/nuras/Desktop/cashback-one/backend
configfile: pyproject.toml
plugins: asyncio-1.4.0, anyio-4.15.1
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
422 passed, 36 skipped, 4 warnings in 52.54s
```

**2. Линтер ruff (baseline):**
```text
All checks passed!
```

**3. Тайпчекер mypy (baseline — ровно 16 ожидаемых ошибок в 2 файлах media_storage.py и image_service.py):**
```text
Found 16 errors in 2 files (checked 68 source files)
```

---

### 10.4. Сырой вывод проверок ПОСЛЕ правок

**1. Тесты POS API (`pytest tests/test_pos_api.py -v`):**
```text
tests/test_pos_api.py::test_pos_auth_missing_header PASSED               [  4%]
tests/test_pos_api.py::test_pos_auth_invalid_key PASSED                  [  8%]
tests/test_pos_api.py::test_pos_auth_revoked_key PASSED                  [ 12%]
tests/test_pos_api.py::test_pos_auth_updates_last_used_at_throttled PASSED [ 16%]
tests/test_pos_api.py::test_pos_redemption_success_push_and_notification PASSED [ 20%]
tests/test_pos_api.py::test_pos_redemption_amount_number_and_string PASSED [ 25%]
tests/test_pos_api.py::test_pos_redemption_customer_no_app_unbound_card PASSED [ 29%]
tests/test_pos_api.py::test_pos_redemption_customer_no_app_no_devices PASSED [ 33%]
tests/test_pos_api.py::test_pos_redemption_customer_no_app_all_devices_disabled PASSED [ 37%]
tests/test_pos_api.py::test_pos_redemption_card_not_found PASSED         [ 41%]
tests/test_pos_api.py::test_pos_redemption_card_blocked PASSED           [ 45%]
tests/test_pos_api.py::test_pos_redemption_rate_limit PASSED             [ 50%]
tests/test_pos_api.py::test_pos_redemption_push_delivery_failed_rolls_back PASSED [ 54%]
tests/test_pos_api.py::test_pos_redemption_validation_errors PASSED      [ 58%]
tests/test_pos_api.py::test_pos_verify_redemption_lifecycle PASSED       [ 62%]
tests/test_pos_api.py::test_pos_verify_max_attempts_exceeded PASSED      [ 66%]
tests/test_pos_api.py::test_pos_verify_code_expired PASSED               [ 70%]
tests/test_pos_api.py::test_pos_verify_superseded_after_new_request PASSED [ 75%]
tests/test_pos_api.py::test_pos_cross_tenant_isolation PASSED            [ 79%]
tests/test_pos_api.py::test_notification_linked_and_cleared_on_confirm PASSED [ 83%]
tests/test_pos_api.py::test_notification_cleared_on_exhausted_attempts PASSED [ 87%]
tests/test_pos_api.py::test_notification_cleared_when_superseded_by_new_request PASSED [ 91%]
tests/test_pos_api.py::test_notification_passive_expiry_without_pos_request PASSED [ 95%]
tests/test_pos_api.py::test_ordinary_notifications_without_redemption_id_unaffected PASSED [100%]

============================== 24 passed in 3.86s ==============================
```

**2. Полный прогон тестов бэкенда (`pytest -q`):**
```text
427 passed, 36 skipped, 4 warnings in 49.11s
```

**3. Линтер ruff (`ruff check app`):**
```text
All checks passed!
```

**4. Тайпчекер mypy (`mypy app`):**
```text
app/services/media_storage.py:137: error: Exception type must be derived from BaseException (or be a tuple of exception classes)  [misc]
app/services/media_storage.py:143: error: Exception type must be derived from BaseException (or be a tuple of exception classes)  [misc]
app/services/media_storage.py:155: error: Exception type must be derived from BaseException (or be a tuple of exception classes)  [misc]
app/services/media_storage.py:159: error: Exception type must be derived from BaseException (or be a tuple of exception classes)  [misc]
app/services/media_storage.py:164: error: Exception type must be derived from BaseException (or be a tuple of exception classes)  [misc]
app/services/media_storage.py:186: error: Exception type must be derived from BaseException (or be a tuple of exception classes)  [misc]
app/services/media_storage.py:188: error: Exception type must be derived from BaseException (or be a tuple of exception classes)  [misc]
app/services/media_storage.py:193: error: Exception type must be derived from BaseException (or be a tuple of exception classes)  [misc]
app/services/media_storage.py:261: error: Exception type must be derived from BaseException (or be a tuple of exception classes)  [misc]
app/services/image_service.py:57: error: Module "PIL.Image" does not explicitly export attribute "UnidentifiedImageError"  [attr-defined]
app/services/image_service.py:86: error: Module "PIL.Image" does not explicitly export attribute "UnidentifiedImageError"  [attr-defined]
app/services/image_service.py:101: error: Incompatible types in assignment (expression has type "Image", variable has type "ImageFile")  [assignment]
app/services/image_service.py:112: error: Incompatible types in assignment (expression has type "Image", variable has type "ImageFile")  [assignment]
app/services/image_service.py:114: error: Incompatible types in assignment (expression has type "Image", variable has type "ImageFile")  [assignment]
app/services/image_service.py:122: error: Incompatible types in assignment (expression has type "Image", variable has type "ImageFile")  [assignment]
app/services/image_service.py:124: error: Incompatible types in assignment (expression has type "Image", variable has type "ImageFile")  [assignment]
Found 16 errors in 2 files (checked 68 source files)
```
*(Ровно те же 16 baseline ошибок, 0 новых).*

**5. Интеграционные тесты на PostgreSQL 16 (`pytest -k postgres`):**
```text
================ 37 passed, 426 deselected, 1 warning in 15.23s ================
```

**6. Тест миграций Alembic (upgrade head -> downgrade -1 -> upgrade head на временной БД `pos_alembic_test_run`):**
```text
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 0001_initial_schema, Initial Stage 1 schema
...
INFO  [alembic.runtime.migration] Running upgrade 0014_pos_keys -> 0015_notification_redemption, Notification link to redemption code.
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running downgrade 0015_notification_redemption -> 0014_pos_keys, Notification link to redemption code.
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 0014_pos_keys -> 0015_notification_redemption, Notification link to redemption code.
```

**7. Проверка форматирования git diff (`git diff --check`):**
```text
Exit code: 0 (чисто, пробелов и переносов строк в конце файлов нет)
```

**8. Тесты админки (`vitest run --maxWorkers=1`):**
```text
 Test Files  22 passed (22)
      Tests  175 passed (175)
   Start at  21:33:00
   Duration  47.11s
```
