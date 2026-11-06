# Отчёт: баннеры платформы в приложениях клиентов (2026-11-06)

**Дата:** 2026-11-06  
**Исполнитель:** Gemini (backend)  
**Куратор:** Antigravity  
**Промпт:** `docs/PROMPT_BACKEND_PLATFORM_BANNERS_2026-11-06.md`  

---

## 1. Контекст и цель

В экосистеме Cashback One суперадмин может создавать в панели управления баннеры с глобальной аудиторией («Все бизнесы», `promotions.business_id IS NULL`, `GLOBAL`) для системной рекламы POSCENTER / Cashback One.

Ранее при запросе с параметром `business_id=<uuid>` (клиентские приложения, такие как KeremEt):
- если у покупателя не было карты данного бизнеса — возвращался пустой список;
- иначе выводились только промо-акции с `Promotion.business_id == business_id`, а общие баннеры (`NULL`) не попадали в выдачу.

Согласно решению владельца:
1. Баннеры платформы выводятся **в общей карусели** приложения клиента вперемешку с баннерами магазина по общей сортировке (`sort_order`, затем `created_at desc`).
2. Баннеры платформы видят **все вошедшие покупатели**, даже если у них нет карты этого магазина или если бизнес не активен / не существует.
3. Показываются только элементы с типом **`banner`**. Общие акции (`kind == 'offer'` с `business_id IS NULL`) в клиентских приложениях не выводятся.
4. Без параметра `business_id` ответ остаётся **побайтно прежним** (полная обратная совместимость со старыми APK и общим приложением).

---

## 2. Изменённые и созданные файлы

| Файл | Статус | Описание |
|---|---|---|
| `backend/app/services/content_service.py` | Изменён | Обновлена логика формирования `where_clause` в `list_promotions` и условий в `get_promotion` при указании `business_id`. |
| `docs/CUSTOMER_API.md` | Изменён | Актуализирована спецификация эндпоинтов `GET /me/promotions` и `GET /me/promotions/{id}` с параметром `business_id`. |
| `backend/tests/test_platform_banners.py` | Создан | Набор интеграционных тестов для проверки всех сценариев показа баннеров платформы. |

---

## 3. Правило показа

При запросе с параметром `business_id=B`:
1. **`list_promotions(user, business_id=B)`**:
   - `banners`:
     - Если у покупателя **есть** активная карта бизнеса B: баннеры бизнеса B (`Promotion.business_id == B`) + активные баннеры платформы (`Promotion.business_id IS NULL` и `Promotion.kind == 'banner'`).
     - Если у покупателя **нет** карты бизнеса B (или бизнес B неактивен / не существует): только активные баннеры платформы.
     - Все попавшие баннеры сортируются единообразно: `sort_order asc`, затем `created_at desc`.
   - `offers`:
     - Только акции бизнеса B (`Promotion.business_id == B` и `Promotion.kind == 'offer'`) и только при наличии карты бизнеса B у покупателя.
     - Общие предложения платформы (`business_id IS NULL`, `kind == 'offer'`) в клиентском приложении не отображаются.
   - `has_new`: рассчитывается только по акциям магазина (`offers`).
2. **`get_promotion(id, business_id=B)`**:
   - Активный баннер платформы (`business_id IS NULL`, `kind == 'banner'`) открывается **всегда** (HTTP 200 OK).
   - Баннер или акция бизнеса B (`business_id == B`) открывается **только при наличии карты B** у покупателя (HTTP 200 OK).
   - Любые другие сущности (общий offer, акция/баннер чужого бизнеса C, промо бизнеса B при отсутствии карты, неактивные или просроченные промо) возвращают **HTTP 404 `PROMOTION_NOT_FOUND`**.
3. **`badges`**: без изменений по смыслу (считает новые акции магазина, баннеры платформы на него не влияют).
4. **Уведомления, `/me/cards`, `/me/app-content`, push**: не изменялись.
5. **Без параметра `business_id`**: выдача не изменилась, отображаются акции и баннеры всех бизнесов покупателя и общие материалы платформы.

---

## 4. Результаты проверок

### 4.1. Сводная таблица

| Проверка | До правок (Baseline) | После правок | Разница |
|---|---|---|---|
| `pytest` (полный набор) | 439 passed, 37 skipped | **444 passed, 37 skipped** | +5 новых тестов passed |
| `pytest -k postgres` (PostgreSQL 16) | 38 passed, 438 deselected | **38 passed, 443 deselected** | Все тесты PostgreSQL passed |
| `ruff check app` | All checks passed | **All checks passed** | Чисто (0 ошибок) |
| `mypy app` | 16 legacy errors | **16 legacy errors** | 0 новых ошибок |
| `git diff --check` | 0 предупреждений | **0 предупреждений** | Пробелы и переносы чистые |

---

### 4.2. Сырой вывод проверок ДО правок

#### `pytest`
```
============================= test session starts ==============================
platform darwin -- Python 3.11.15, pytest-9.1.1, pluggy-1.7.0
rootdir: /Users/nuras/Desktop/cashback-one/backend
configfile: pyproject.toml
testpaths: tests
plugins: asyncio-1.4.0, anyio-4.15.1
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 476 items                                                            

...
================= 439 passed, 37 skipped, 4 warnings in 49.22s =================
```

#### `pytest -k postgres`
```
============================= test session starts ==============================
platform darwin -- Python 3.11.15, pytest-9.1.1, pluggy-1.7.0
rootdir: /Users/nuras/Desktop/cashback-one/backend
configfile: pyproject.toml
testpaths: tests
plugins: asyncio-1.4.0, anyio-4.15.1
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 476 items / 438 deselected / 38 selected                             

...
================ 38 passed, 438 deselected, 1 warning in 14.75s ================
```

#### `ruff check app`
```
All checks passed!
```

#### `mypy app`
```
Found 16 errors in 2 files (checked 68 source files)
```

---

### 4.3. Сырой вывод проверок ПОСЛЕ правок

#### `pytest` (полный)
```
============================= test session starts ==============================
platform darwin -- Python 3.11.15, pytest-9.1.1, pluggy-1.7.0
rootdir: /Users/nuras/Desktop/cashback-one/backend
configfile: pyproject.toml
testpaths: tests
plugins: asyncio-1.4.0, anyio-4.15.1
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 481 items                                                            

tests/test_admin_business_app_id.py ....                                 [  0%]
tests/test_admin_cards_list.py .......                                   [  2%]
tests/test_admin_cli.py ..                                               [  2%]
tests/test_admin_config.py .........                                     [  4%]
tests/test_admin_content.py ...                                          [  5%]
tests/test_admin_manager_access.py ........                              [  6%]
tests/test_admin_media_upload.py ....................                    [ 11%]
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
tests/test_barcode_contract.py ............                              [ 35%]
tests/test_business_app_content.py ....                                  [ 35%]
tests/test_config.py ............................                        [ 41%]
tests/test_constraints.py ......                                         [ 43%]
tests/test_customer_api_multi_client.py ....                             [ 43%]
tests/test_customer_app.py ...................                           [ 47%]
tests/test_customer_avatar.py ...........                                [ 50%]
tests/test_customer_bind_card.py ....................                    [ 54%]
tests/test_customer_jwt_auth.py ..........                               [ 56%]
tests/test_customer_wallet.py ................                           [ 59%]
tests/test_health.py .                                                   [ 59%]
tests/test_migration_0016.py .s                                          [ 60%]
tests/test_phone.py ....                                                 [ 61%]
tests/test_platform_banners.py .....                                     [ 62%]
tests/test_pos_api.py ........................                           [ 67%]
tests/test_postgres_admin_security.py sssssss                            [ 68%]
tests/test_postgres_agent_sync_concurrency.py ssss                       [ 69%]
tests/test_postgres_bind_concurrency.py ssss                             [ 70%]
tests/test_postgres_customer_auth_concurrency.py ssssss                  [ 71%]
tests/test_postgres_model_smoke.py s                                     [ 71%]
tests/test_postgres_sms_concurrency.py ssss                              [ 72%]
tests/test_postgres_wallet_concurrency.py ssssss                         [ 73%]
tests/test_postgres_wappi_concurrency.py ssss                            [ 74%]
tests/test_production_runtime.py ....................................... [ 82%]
...........                                                              [ 85%]
tests/test_push_notifications.py ..........                              [ 87%]
tests/test_push_per_client.py ...                                        [ 87%]
tests/test_rate_limiter.py .......                                       [ 89%]
tests/test_runtime_dependencies.py .                                     [ 89%]
tests/test_sms_auth.py ......................                            [ 93%]
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
================= 444 passed, 37 skipped, 4 warnings in 50.34s =================
```

#### `pytest -k postgres` (PostgreSQL 16)
```
============================= test session starts ==============================
platform darwin -- Python 3.11.15, pytest-9.1.1, pluggy-1.7.0
rootdir: /Users/nuras/Desktop/cashback-one/backend
configfile: pyproject.toml
testpaths: tests
plugins: asyncio-1.4.0, anyio-4.15.1
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 481 items / 443 deselected / 38 selected                             

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
================ 38 passed, 443 deselected, 1 warning in 16.17s ================
```

#### `ruff check app`
```
All checks passed!
```

#### `mypy app`
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

#### `git diff --stat`
```
 backend/app/services/content_service.py | 54 +++++++++++++++++++++++++--------
 docs/CUSTOMER_API.md                    | 14 ++++-----
 2 files changed, 48 insertions(+), 20 deletions(-)
```

---

## 5. Что не проверялось

1. Отображение баннеров на физическом мобильном устройстве (приложение KeremEt).
2. Поведение при реальном сетевом взаимодействии с внешним хостингом.
3. Деплой на production-сервер (`kz-vps`).
