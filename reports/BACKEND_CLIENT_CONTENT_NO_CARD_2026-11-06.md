# Отчёт: контент магазина в приложении клиента без карты

**Дата:** 6 ноября 2026 г.  
**Инструкция:** `docs/PROMPT_BACKEND_CLIENT_CONTENT_NO_CARD_2026-11-06.md`  
**Исполнитель:** Gemini (backend)  
**Репозиторий:** `/Users/nuras/Desktop/cashback-one`, ветка `main`  

---

## 1. Контекст и суть изменений

По решению владельца: покупатель, установивший приложение магазина (с параметром `business_id=B`), видит информацию этого магазина **всегда**, независимо от наличия у него карты лояльности:
- карта лояльности требуется **только** для баланса, статуса, истории транзакций и генерации динамического QR;
- акции, баннеры, рассылки магазина, адреса магазинов и тексты интерфейса доступны сразу после регистрации/входа в приложение клиента.

---

## 2. Новые правила показа контента

### 2.1. Режим с параметром `business_id=B` (приложение клиента)
1. **`GET /me/promotions` и `GET /me/promotions/{id}`**:
   - Баннеры и акции (`offers`) бизнеса B доступны **без проверки наличия карты**.
   - Дополнительно отображаются общие баннеры платформы (`business_id IS NULL`, `kind == 'banner'`).
   - Общие предложения платформы (`kind == 'offer'`) в приложениях клиентов не отображаются.
   - Окно активности (`is_active == True`, `starts_at <= now < ends_at`) сохраняется.
   - Если бизнес B не существует или не активен (`status != 'active'`) — возвращаются только общие баннеры, а детальный запрос акции бизнеса B возвращает `404 PROMOTION_NOT_FOUND`.
2. **`GET /me/notifications` и `POST /me/notifications/read`**:
   - Рассылки бизнеса B (`user_id IS NULL`, `business_id = B`, `created_at >= user.created_at`) отображаются без наличия карты.
   - Личные уведомления покупателя (`user_id == customer.id`, `business_id = B`) отображаются как раньше.
   - Если бизнес B не существует или не активен — возвращается `{items: [], unread_count: 0}`.
3. **`GET /me/badges`**:
   - Бейджи непрочитанных уведомлений и новых акций рассчитываются для бизнеса B без требования карты.
   - Если бизнес B не существует или не активен — `{promotions_new: false, notifications_unread: 0}`.
4. **`GET /me/app-content?business_id=B`**:
   - Устранено требование наличия активной видимой карты бизнеса B (`Card` + `UserCard`).
   - Требуется только существование и активность бизнеса (`Business.status == 'active'`), иначе `404 CUSTOMER_RESOURCE_NOT_FOUND`.
   - Поддержка ETag / `304 Not Modified` сохранена в полном объёме.

### 2.2. Режим без параметра `business_id` (общее приложение Cashback One и старые APK)
- `/me/promotions`, `/me/notifications`, `/me/badges`: поведение и ответ **побайтно прежние** (фильтрация по бизнесам активных карт покупателя).

---

## 3. Изменённые файлы

1. **`backend/app/api/customer_app.py`**:
   - В функции `get_app_content` удалена проверка наличия карты у покупателя (шаг 1).
2. **`backend/app/services/content_service.py`**:
   - Добавлен хелпер `_is_active_business(session, business_id)`.
   - В `list_promotions`, `get_promotion`, `list_notifications`, `_unread_notifications`, `badges` логика с `business_id` переведена на проверку активности бизнеса вместо наличия карты у покупателя.
3. **`docs/CUSTOMER_API.md`**:
   - Обновлены разделы 3.9 (Promotions, notifications, badges), 3.13 (App-content), 3.14 (Multi-tenant API filtering).
4. **`backend/tests/test_platform_banners.py`**:
   - Тест `test_platform_banners_without_card` обновлён: покупатель без карты теперь видит акции и баннеры бизнеса B.
5. **`backend/tests/test_business_app_content.py`**:
   - Тест `test_customer_app_content_endpoint` обновлён: подтверждено получение 200 OK без карты и 404 только при неактивном или несуществующем бизнесе.
6. **`backend/tests/test_customer_content_no_card.py`** *(новый файл)*:
   - 5 интеграционных тестов, покрывающих все требования промпта.

---

## 4. Сводная таблица проверок

| Проверка | До правок (Baseline) | После правок | Разница |
|---|---|---|---|
| `pytest` (полный набор) | 444 passed, 37 skipped | **449 passed, 37 skipped** | +5 новых тестов passed |
| `pytest -k postgres` (PostgreSQL 16) | 38 passed, 443 deselected | **38 passed, 448 deselected** | Все 38 тестов passed |
| `ruff check app` | All checks passed | **All checks passed** | Чисто (0 ошибок) |
| `mypy app` | 16 legacy errors | **16 legacy errors** | 0 новых ошибок |
| `git diff --check` | 0 предупреждений | **0 предупреждений** | Пробелы и переносы чистые |

---

## 5. Сырой вывод проверок ДО правок

### 5.1. `pytest`
```text
============================= test session starts ==============================
platform darwin -- Python 3.11.15, pytest-9.1.1, pluggy-1.7.0
rootdir: /Users/nuras/Desktop/cashback-one/backend
configfile: pyproject.toml
testpaths: tests
plugins: asyncio-1.4.0, anyio-4.15.1
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 481 items                                                            

...
=========== 444 passed, 37 skipped, 4 warnings in 171.12s (0:02:51) ============
```

### 5.2. `pytest -k postgres`
```text
============================= test session starts ==============================
platform darwin -- Python 3.11.15, pytest-9.1.1, pluggy-1.7.0
rootdir: /Users/nuras/Desktop/cashback-one/backend
configfile: pyproject.toml
testpaths: tests
plugins: asyncio-1.4.0, anyio-4.15.1
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 481 items / 443 deselected / 38 selected                             

...
================ 38 passed, 443 deselected, 1 warning in 27.64s ================
```

### 5.3. `ruff check app`
```text
All checks passed!
```

### 5.4. `mypy app`
```text
Found 16 errors in 2 files (checked 68 source files)
```

---

## 6. Сырой вывод проверок ПОСЛЕ правок

### 6.1. `pytest` (полный)
```text
============================= test session starts ==============================
platform darwin -- Python 3.11.15, pytest-9.1.1, pluggy-1.7.0
rootdir: /Users/nuras/Desktop/cashback-one/backend
configfile: pyproject.toml
testpaths: tests
plugins: asyncio-1.4.0, anyio-4.15.1
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 486 items                                                            

tests/test_admin_business_app_id.py ....                                 [  0%]
tests/test_admin_cards_list.py .......                                   [  2%]
tests/test_admin_cli.py ..                                               [  2%]
tests/test_admin_config.py .........                                     [  4%]
tests/test_admin_content.py ...                                          [  5%]
tests/test_admin_manager_access.py ........                              [  6%]
tests/test_admin_media_upload.py ....................                    [ 10%]
tests/test_admin_mutations.py ..................                         [ 14%]
tests/test_admin_mvp.py .................                                [ 18%]
tests/test_admin_pos_keys.py .....                                       [ 19%]
tests/test_agent_auth.py ......                                          [ 20%]
tests/test_agent_heartbeat.py ..                                         [ 20%]
tests/test_agent_sync_cards.py .......                                   [ 22%]
tests/test_agent_sync_transactions.py ......                             [ 23%]
tests/test_auth_challenge.py ...............                             [ 26%]
tests/test_auth_confirmation.py ..........                               [ 28%]
tests/test_auth_logout.py ..                                             [ 29%]
tests/test_auth_tokens.py ..........                                     [ 31%]
tests/test_auto_bind.py ......                                           [ 32%]
tests/test_barcode_contract.py ............                              [ 34%]
tests/test_business_app_content.py ....                                  [ 35%]
tests/test_config.py ............................                        [ 41%]
tests/test_constraints.py ......                                         [ 42%]
tests/test_customer_api_multi_client.py ....                             [ 43%]
tests/test_customer_app.py ...................                           [ 47%]
tests/test_customer_avatar.py ...........                                [ 49%]
tests/test_customer_bind_card.py ....................                    [ 53%]
tests/test_customer_content_no_card.py .....                             [ 54%]
tests/test_customer_jwt_auth.py ..........                               [ 56%]
tests/test_customer_wallet.py ................                           [ 60%]
tests/test_health.py .                                                   [ 60%]
tests/test_migration_0016.py .s                                          [ 60%]
tests/test_phone.py ....                                                 [ 61%]
tests/test_platform_banners.py .....                                     [ 62%]
tests/test_pos_api.py ........................                           [ 67%]
tests/test_postgres_admin_security.py sssssss                            [ 68%]
tests/test_postgres_agent_sync_concurrency.py ssss                       [ 69%]
tests/test_postgres_bind_concurrency.py ssss                             [ 70%]
tests/test_postgres_customer_auth_concurrency.py ssssss                  [ 71%]
tests/test_postgres_model_smoke.py s                                     [ 72%]
tests/test_postgres_sms_concurrency.py ssss                              [ 72%]
tests/test_postgres_wallet_concurrency.py ssssss                         [ 74%]
tests/test_postgres_wappi_concurrency.py ssss                            [ 74%]
tests/test_production_runtime.py ....................................... [ 82%]
...........                                                              [ 85%]
tests/test_push_notifications.py ..........                              [ 87%]
tests/test_push_per_client.py ...                                        [ 87%]
tests/test_rate_limiter.py .......                                       [ 89%]
tests/test_runtime_dependencies.py .                                     [ 89%]
tests/test_sms_auth.py ......................                            [ 94%]
tests/test_wallet_passes.py .........                                    [ 95%]
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
============ 449 passed, 37 skipped, 4 warnings in 90.10s (0:01:30) ============
```

### 6.2. `pytest -k postgres` (PostgreSQL 16)
```text
============================= test session starts ==============================
platform darwin -- Python 3.11.15, pytest-9.1.1, pluggy-1.7.0
rootdir: /Users/nuras/Desktop/cashback-one/backend
configfile: pyproject.toml
testpaths: tests
plugins: asyncio-1.4.0, anyio-4.15.1
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 486 items / 448 deselected / 38 selected                             

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
================ 38 passed, 448 deselected, 1 warning in 18.84s ================
```

### 6.3. `ruff check app`
```text
All checks passed!
```

### 6.4. `mypy app`
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

### 6.5. `git diff --stat backend/ docs/CUSTOMER_API.md`
```text
 backend/app/api/customer_app.py            | 18 ++---------------
 backend/app/services/content_service.py    | 31 ++++++++++++++++++-----------
 backend/tests/test_business_app_content.py | 27 +++++++++++++------------
 backend/tests/test_platform_banners.py     | 32 +++++++++++++++++-------------
 docs/CUSTOMER_API.md                       | 22 ++++++++++----------
 5 files changed, 64 insertions(+), 66 deletions(-)
```

### 6.6. `git diff --check`
```text
(0 предупреждений, чисто)
```
