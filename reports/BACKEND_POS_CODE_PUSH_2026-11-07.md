# Отчёт: отправка кассой кода покупателю push-уведомлением (`POST /pos/code-push`)

**Дата:** 7 ноября 2026 г.  
**Инструкция:** `docs/PROMPT_BACKEND_POS_CODE_PUSH_2026-11-07.md` (включая «Дополнение 1»)  
**Исполнитель:** Gemini (backend)  
**Репозиторий:** `/Users/nuras/Desktop/cashback-one`, ветка `main`  

---

## 1. Контекст и суть изменений

Касса **POSCENTER Cash написана на 1С 7.7**. Для подтверждения списания бонусов на кассе вместо отправки кода в WhatsApp реализована прямая доставка кода покупателю push-уведомлением в мобильное приложение магазина:
- Касса Cash **сама** генерирует случайный 4-значный код (например, 4554) и отправляет его в облако Cashback One через `POST /pos/code-push`.
- Облако находит покупателя с картой этого магазина и доставляет push-уведомление в приложение магазина.
- Уведомление содержит 4-значный код и название магазина:  
  *«Ваш код для списания бонусов: 4554 в «<название бизнеса>». Назовите его кассиру, только если сейчас оплачиваете покупку.»*
- Код сохраняется в ленте уведомлений приложения покупателя. Через 5 минут (срок действия кода) код скрывается и заменяется нейтральным текстом без кода и без упоминания суммы.
- Покупатель называет код кассиру, а касса Cash **сама** сравнивает его со своим сгенерированным значением.
- Двухшаговые методы `/pos/redemptions` и `/pos/redemptions/{id}/verify` сохранены без изменений.
- Файл `docs/integrations/cash77_code_push.txt`, подготовленный куратором, не модифицировался («Дополнение 1»).

---

## 2. Протокол `POST /pos/code-push`

### 2.1. Запрос
- **Метод**: `POST`
- **Путь**: `/pos/code-push`
- **Заголовки**:
  - `Content-Type: application/json`
  - `X-Pos-Key: pos_<ключ_кассы>` (аутентификация через `app/services/pos_auth.py`, привязка к `business_id`)
- **Тело запроса**:
  ```json
  {
    "phone": "77011234567",
    "code": "4554"
  }
  ```
  - `phone` (строка): нормализуется через `app.core.phone.normalize_phone` (поддерживаются форматы `77…`, `+77…`, `87…`, `8 (701) …`).
  - `code` (строка): строго 4 десятичные цифры (`^\d{4}$`). Произвольный текст от кассы отклоняется (текст уведомления формирует сервер).

### 2.2. Порядок проверок на сервере
1. Push отключён (`sender.disabled == True`) → `503 PUSH_NOT_CONFIGURED`.
2. Валидация формата: код не 4 цифры или некорректный телефон → `400 VALIDATION_ERROR`.
3. Поиск покупателя и карты:
   - Покупатель с нормализованным телефоном (не удалён, `deleted_at IS NULL`) и его карта в бизнесе кассы (`UserCard` → `Card.business_id == pos_key.business_id`).
   - Если покупатель не найден или у него нет карты в этом бизнесе → `404 CARD_NOT_FOUND` (факт существования аккаунта не раскрывается).
   - Если у покупателя несколько карт в бизнесе — выбирается любая незаблокированная карта.
   - Если все карты покупателя заблокированы → `409 CARD_BLOCKED`.
4. Наличие активного устройства:
   - Проверка `has_active_device(session, owner.id, business_id=pos_key.business_id)` → если нет активных устройств с включёнными уведомлениями → `409 CUSTOMER_NO_APP`.
5. Рейт-лимит:
   - Не более 5 запросов за 10 минут на карту (`settings.redemption_card_request_limit`, `settings.redemption_card_rate_window_seconds`) → `429 RATE_LIMIT_EXCEEDED`.
6. Отправка push-уведомления:
   - `send_to_user(session, sender, user_id=owner.id, title=..., body=..., data=..., business_id=pos_key.business_id)`.
   - Если доставлено 0 устройств или возникло исключение отправки → транзакция откатывается, `503 PUSH_DELIVERY_FAILED`.

### 2.3. Успешный ответ (HTTP 200 OK)
```json
{
  "status": "sent",
  "expires_at": "2026-11-07T12:05:00Z"
}
```
- Ни телефон, ни код в журнал не пишутся (ни в INFO, ни в ошибках).

### 2.4. Коды ошибок API
| HTTP статус | Код ошибки (`error.code`) | Описание |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Код не состоит из 4 цифр или неверный формат телефона |
| 401 | `POS_KEY_MISSING` / `POS_KEY_INVALID` / `POS_KEY_REVOKED` | Ошибка авторизации ключа кассы |
| 404 | `CARD_NOT_FOUND` | Покупатель или карта в данном магазине не найдены |
| 409 | `CARD_BLOCKED` | Все карты покупателя в магазине заблокированы |
| 409 | `CUSTOMER_NO_APP` | Нет приложения магазина или отключены push-уведомления |
| 429 | `RATE_LIMIT_EXCEEDED` | Превышен лимит запросов кода для этой карты (5 за 10 мин) |
| 503 | `PUSH_NOT_CONFIGURED` | Push-сервис не настроен на сервере |
| 503 | `PUSH_DELIVERY_FAILED` | Ошибка отправки push-уведомления (0 доставок) |

---

## 3. Что изменено в тексте неактивного кода

В `app/services/content_service.py` функции `redemption_inactive_text` и `redemption_confirmed_text` обновлены для поддержки списаний без суммы (`amount == 0`):
- В модели `RedemptionCode.amount` поле `NOT NULL`, при отправке кода через `/pos/code-push` записывается `Decimal(0)`.
- Если `amount == 0`:
  - `redemption_inactive_text(0, business_name)` возвращает:  
    `Код для списания в «<бизнес>» больше не действует.` (или `Код больше не действует.`, если название пусто).
  - В тексте **полностью отсутствует сумма и фраза «0 баллов»**.
  - Исходный 4-значный код скрывается.
- При создании нового кода предыдущие коды в статусе `pending` по этой карте переводятся в `superseded`, а их текст в таблице `notifications` заменяется на неактивный без суммы.
- По истечении TTL (5 минут) в `GET /me/notifications` динамически возвращается неактивный текст без кода и без суммы.

---

## 4. Изменённые файлы

1. `backend/app/schemas/pos.py`:
   - Добавлены Pydantic-схемы `PosCodePushRequest` (`phone`, `code`) и `PosCodePushResponse` (`status="sent"`, `expires_at`).
2. `backend/app/services/content_service.py`:
   - `redemption_confirmed_text` и `redemption_inactive_text`: добавлена ветка для `amount == 0` (вывод без суммы).
3. `backend/app/services/pos_service.py`:
   - Реализована функция `send_pos_code_push` со всеми проверками, отправкой push, созданием `RedemptionCode` (amount=0) и `Notification`, переводом старых `pending` в `superseded`.
4. `backend/app/api/pos.py`:
   - Зарегистрирован эндпоинт `POST /pos/code-push` (status_code=200).
5. `docs/POS_REDEEM_API.md`:
   - Добавлена пометка в шапке (для 1С 8; для Cash 1С 7.7 — `cash77_code_push.txt` и `/pos/code-push`).
   - Добавлен раздел 3.3 с описанием метода `POST /pos/code-push`.
   - Добавлен пример вызова cURL (Пример 3) с ключом-заглушкой `pos_ВСТАВЬТЕ_КЛЮЧ`.
   - Обновлён раздел 6 о соответствии с реализацией 1С.
6. `docs/integrations/cash_redeem_code.bsl`:
   - Добавлена пометка в шапке модуля со ссылкой на `cash77_code_push.txt` и раздел `/pos/code-push`.
7. `backend/tests/test_pos_code_push.py` *(новый файл)*:
   - 32 модульных и интеграционных теста, покрывающих все сценарии и граничные условия.

---

## 5. Сводная таблица проверок

| Проверка | До правок (Baseline) | После правок | Разница |
|---|---|---|---|
| `pytest` (полный набор) | 459 passed, 37 skipped | **491 passed, 37 skipped** | +32 новых теста passed |
| `pytest -k postgres` (PostgreSQL 16) | 38 passed, 458 deselected | **38 passed, 490 deselected** | Все 38 тестов passed |
| `ruff check app` + новые тесты | All checks passed | **All checks passed** | 0 ошибок |
| `mypy app` | 16 legacy errors | **16 legacy errors** | 0 новых ошибок |
| `git diff --check` | 0 предупреждений | **0 предупреждений** | Пробелы и переносы чистые |

---

## 6. Сырой вывод проверок ДО правок

### 6.1. `pytest` (Baseline)
```text
============================= test session starts ==============================
platform darwin -- Python 3.11.15, pytest-9.1.1, pluggy-1.7.0
rootdir: /Users/nuras/Desktop/cashback-one/backend
configfile: pyproject.toml
testpaths: tests
plugins: asyncio-1.4.0, anyio-4.15.1
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 496 items

...
============ 459 passed, 37 skipped, 4 warnings in 95.02s (0:01:35) ============
```

### 6.2. `pytest -k postgres` (Baseline)
```text
============================= test session starts ==============================
platform darwin -- Python 3.11.15, pytest-9.1.1, pluggy-1.7.0
rootdir: /Users/nuras/Desktop/cashback-one/backend
configfile: pyproject.toml
testpaths: tests
plugins: asyncio-1.4.0, anyio-4.15.1
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 496 items / 458 deselected / 38 selected

tests/test_config.py .                                                   [  2%]
tests/test_migration_0016.py .                                           [  5%]
tests/test_postgres_admin_security.py .......                            [ 23%]
tests/test_postgres_agent_sync_concurrency.py ....                       [ 34%]
tests/test_postgres_bind_concurrency.py ....                             [ 44%]
tests/test_postgres_customer_auth_concurrency.py ......                  [ 60%]
tests/test_postgres_model_smoke.py .                                     [ 63%]
tests/test_postgres_sms_concurrency.py ....                              [ 73%]
tests/test_postgres_wallet_concurrency.py ......                         [ 89%]
tests/test_postgres_wappi_concurrency.py ....                            [100%]

================ 38 passed, 458 deselected, 1 warning in 14.12s ================
```

### 6.3. `ruff check app` (Baseline)
```text
All checks passed!
```

### 6.4. `mypy app` (Baseline)
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

---

## 7. Сырой вывод проверок ПОСЛЕ правок

### 7.1. `pytest` (полный)
```text
============================= test session starts ==============================
platform darwin -- Python 3.11.15, pytest-9.1.1, pluggy-1.7.0
rootdir: /Users/nuras/Desktop/cashback-one/backend
configfile: pyproject.toml
testpaths: tests
plugins: asyncio-1.4.0, anyio-4.15.1
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 528 items

tests/test_admin_business_app_id.py ....                                 [  0%]
tests/test_admin_cards_list.py .......                                   [  2%]
tests/test_admin_cli.py ..                                               [  2%]
tests/test_admin_config.py .........                                     [  4%]
tests/test_admin_content.py ...                                          [  4%]
tests/test_admin_manager_access.py ........                              [  6%]
tests/test_admin_media_upload.py ....................                    [ 10%]
tests/test_admin_mutations.py ..................                         [ 13%]
tests/test_admin_mvp.py .................                                [ 16%]
tests/test_admin_pos_keys.py .....                                       [ 17%]
tests/test_agent_auth.py ......                                          [ 18%]
tests/test_agent_heartbeat.py ..                                         [ 19%]
tests/test_agent_sync_cards.py .......                                   [ 20%]
tests/test_agent_sync_transactions.py ......                             [ 21%]
tests/test_auth_challenge.py ...............                             [ 24%]
tests/test_auth_confirmation.py ..........                               [ 26%]
tests/test_auth_logout.py ..                                             [ 26%]
tests/test_auth_tokens.py ..........                                     [ 28%]
tests/test_auto_bind.py ......                                           [ 29%]
tests/test_barcode_contract.py ............                              [ 32%]
tests/test_broadcast_push.py ..........                                  [ 33%]
tests/test_business_app_content.py ....                                  [ 34%]
tests/test_config.py ............................                        [ 39%]
tests/test_constraints.py ......                                         [ 41%]
tests/test_customer_api_multi_client.py ....                             [ 41%]
tests/test_customer_app.py ...................                           [ 45%]
tests/test_customer_avatar.py ...........                                [ 47%]
tests/test_customer_bind_card.py ....................                    [ 51%]
tests/test_customer_content_no_card.py .....                             [ 52%]
tests/test_customer_jwt_auth.py ..........                               [ 54%]
tests/test_customer_wallet.py ................                           [ 57%]
tests/test_health.py .                                                   [ 57%]
tests/test_migration_0016.py .s                                          [ 57%]
tests/test_phone.py ....                                                 [ 58%]
tests/test_platform_banners.py .....                                     [ 59%]
tests/test_pos_api.py ........................                           [ 64%]
tests/test_pos_code_push.py ................................             [ 70%]
tests/test_postgres_admin_security.py sssssss                            [ 71%]
tests/test_postgres_agent_sync_concurrency.py ssss                       [ 72%]
tests/test_postgres_bind_concurrency.py ssss                             [ 72%]
tests/test_postgres_customer_auth_concurrency.py ssssss                  [ 74%]
tests/test_postgres_model_smoke.py s                                     [ 74%]
tests/test_postgres_sms_concurrency.py ....                              [ 75%]
tests/test_postgres_wallet_concurrency.py ssssss                         [ 76%]
tests/test_postgres_wappi_concurrency.py ssss                            [ 76%]
tests/test_production_runtime.py ....................................... [ 84%]
...........                                                              [ 86%]
tests/test_push_notifications.py ..........                              [ 88%]
tests/test_push_per_client.py ...                                        [ 88%]
tests/test_rate_limiter.py .......                                       [ 90%]
tests/test_runtime_dependencies.py .                                     [ 90%]
tests/test_sms_auth.py ......................                            [ 94%]
tests/test_wallet_passes.py .........                                    [ 96%]
tests/test_wappi_webhook_auth.py ........                                [ 97%]
tests/test_wappi_webhook_parser.py ............                          [100%]

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
================= 491 passed, 37 skipped, 4 warnings in 47.12s =================
```

### 7.2. `pytest -k postgres` (PostgreSQL 16)
```text
============================= test session starts ==============================
platform darwin -- Python 3.11.15, pytest-9.1.1, pluggy-1.7.0
rootdir: /Users/nuras/Desktop/cashback-one/backend
configfile: pyproject.toml
testpaths: tests
plugins: asyncio-1.4.0, anyio-4.15.1
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 528 items / 490 deselected / 38 selected

tests/test_config.py .                                                   [  2%]
tests/test_migration_0016.py .                                           [  5%]
tests/test_postgres_admin_security.py .......                            [ 23%]
tests/test_postgres_agent_sync_concurrency.py ....                       [ 34%]
tests/test_postgres_bind_concurrency.py ....                             [ 44%]
tests/test_postgres_customer_auth_concurrency.py ......                  [ 60%]
tests/test_postgres_model_smoke.py .                                     [ 63%]
tests/test_postgres_sms_concurrency.py ....                              [ 73%]
tests/test_postgres_wallet_concurrency.py ......                         [ 89%]
tests/test_postgres_wappi_concurrency.py ....                            [100%]

=============================== warnings summary ===============================
tests/test_postgres_agent_sync_concurrency.py::test_pg_conc_03_concurrent_transaction_replay
  /Users/nuras/Desktop/cashback-one/backend/app/api/agent_sync.py:44: SADeprecationWarning: The Result.tuples() method is deprecated, Row now behaves like a tuple and can unpack types directly. (deprecated since: 2.1.0)
    ).tuples().all()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================ 38 passed, 490 deselected, 1 warning in 13.22s ================
```

### 7.3. `ruff check app tests/test_pos_code_push.py`
```text
All checks passed!
```

### 7.4. `mypy app`
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

### 7.5. `git diff --check`
```text
(вывод пустой, код возврата 0 — пробелы и переносы чистые)
```

### 7.6. `git diff --stat`
```text
 backend/app/api/pos.py                  |  20 +++-
 backend/app/schemas/pos.py              |  12 +++
 backend/app/services/content_service.py |  16 +++-
 backend/app/services/pos_service.py     | 163 +++++++++++++++++++++++++++++++-
 docs/POS_REDEEM_API.md                  |  80 ++++++++++++++--
 docs/integrations/cash_redeem_code.bsl  |   1 +
 6 files changed, 282 insertions(+), 10 deletions(-)
```
