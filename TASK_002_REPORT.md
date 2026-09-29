# TASK-002 Report

**Дата отчета:** 29 сентября 2026 г.  
**Задача:** TASK-002: Agent Authentication + Cloud Sync API  
**Исполнитель:** Senior Software Architect / Backend Engineer / QA Auditor  
**Нормативный документ:** `TZ_loyalty_app_v1.1`  
**Базовые документы:** `BASELINE_AUDIT.md`, `TASK_001_REPORT.md`

---

## 1. Цель задачи

Реализовать серверную сторону защищенного протокола взаимодействия:
$$\text{ONE Agent} \longrightarrow \text{Cloud Backend}$$

В строгом соответствии с требованиями ТЗ (разделы 2, 4, 6, 7):
* Реализовать безопасную аутентификацию агентов на основе API-ключей с хранением хэшей (SHA-256).
* Обеспечить строгую изоляцию тенантов (`business_id` определяется исключительно по аутентифицированному агенту).
* Реализовать Cloud Sync API для приема батчей карт (`POST /agent/sync/cards`), транзакций (`POST /agent/sync/transactions`) и передачи телеметрии (`POST /agent/heartbeat`).
* Обеспечить идемпотентность и защиту от затирания свежих данных устаревшими (`stale data protection`).
* Реализовать нормализацию телефонных номеров покупателей под стандарт E.164 (РК / СНГ).
* Проверить работоспособность на реальной СУБД PostgreSQL 16.

*Границы скоупа:* Windows-агент, COM-коннектор `V83.COMConnector`, Wappi, WhatsApp/SMS-авторизация и клиентские JWT в рамках TASK-002 не реализовывались.

---

## 2. Что сделано

1. **Управление конфигурацией и средой выполнения (`backend/app/core/config.py`):**
   - Установлен запрет на неявный fallback к SQLite в рабочем окружении (`DATABASE_URL` обязан указывать на PostgreSQL при `APP_ENV != test`).
   - Добавлены настройки лимитов пакетов (`SYNC_CARDS_BATCH_LIMIT = 500`, `SYNC_TRANSACTIONS_BATCH_LIMIT = 1000`).
   - Настроено имя заголовка агентского ключа (`X-Agent-Key`).

2. **Нормализация телефонных номеров (`backend/app/core/phone.py`):**
   - Реализована функция `normalize_phone` для приведения номеров Казахстана и стран СНГ к формату E.164:
     - `8701...` $\rightarrow$ `+7701...`
     - `7701...` $\rightarrow$ `+7701...`
     - `+7 701 ...` $\rightarrow$ `+7701...`
   - Реализована строгая валидация длины (10–15 цифр) и допустимых символов с генерацией исключений `AppError(code="INVALID_PHONE")`.

3. **Единый протокол обработки ошибок (`backend/app/core/errors.py`):**
   - Реализован класс исключений `AppError` с поддержкой HTTP-статуса, символьного кода ошибки и словаря деталей.
   - Зарегистрированы глобальные обработчики исключений в FastAPI (`AppError`, `RequestValidationError`, unhandled `Exception`), возвращающие унифицированный формат:
     ```json
     {
       "error": {
         "code": "ERROR_CODE",
         "message": "Human-readable description",
         "details": {}
       }
     }
     ```

4. **Сервис аутентификации агентов (`backend/app/services/agent_auth.py`):**
   - Генерация криптографически стойких ключей `agent_live_<token>` (64 байта энтропии).
   - Хэширование ключей по алгоритму SHA-256 перед сохранением в БД (открытый ключ в базе данных не хранится).
   - Поддержка аутентификации через заголовок `X-Agent-Key` или `Authorization: Bearer <key>`.
   - Проверка активности агента (`is_active = True`). При неактивном агенте возвращается `403 FORBIDDEN` (`AGENT_REVOKED`).
   - Строгая изоляция: тенант (`business_id`) извлекается напрямую из сущности `Agent` в сессии БД.

5. **Схемы DTO и валидация данных (`backend/app/schemas/agent_sync.py`):**
   - DTO для батча карт: `SyncCardItem`, `CardsSyncRequest`, `CardsSyncResponse`.
   - DTO для батча транзакций: `SyncTransactionItem`, `TransactionsSyncRequest`, `TransactionsSyncResponse`.
   - DTO для сердцебиения: `HeartbeatRequest`, `HeartbeatResponse`.
   - Валидация типов данных: использование `Decimal` для сумм и балансов, валидация штрихкодов, временных меток и типов транзакций (`ACCURAL`, `REDEMPTION`, `CORRECTION`).

6. **Эндпоинты Cloud Sync API (`backend/app/api/agent_sync.py`):**
   - `POST /agent/sync/cards`:
     - Батчевая обработка до 500 карт за запрос.
     - Нормализация номера телефона покупателя.
     - Вставка новых карт и обновление существующих.
     - Защита от устаревших данных: если `incoming.updated_at <= existing.updated_at`, обновление полей пропускается.
     - Привязка всех карт строго к `business_id` аутентифицированного агента.
   - `POST /agent/sync/transactions`:
     - Батчевая обработка до 1000 транзакций за запрос.
     - Проверка существования `card_id` в рамках тенанта агента (транзакции для чужих или несуществующих карт отклоняются с кодом `422 UNKNOWN_CARD_FOR_TRANSACTION`).
     - Детерминированная идемпотентность: повторная отправка транзакции с существующей парой `(card_id, external_id)` определяется без ошибок и возвращается в счетчике `skipped_duplicate`.
   - `POST /agent/heartbeat`:
     - Обновление состояния агента в реальном времени.
     - Серверная фиксация времени: `last_seen_at = utcnow()`.
     - Обновление версии агента, `last_sync_at` и `last_error`.

7. **Миграции базы данных Alembic (`backend/migrations/versions/0002_agent_heartbeat_fields.py`):**
   - Добавлены поля `last_sync_at` (DateTime TZ nullable) и `last_error` (Text nullable) в таблицу `agents`.
   - Протестирован полный цикл отката и наката.

8. **Спецификация и документация:**
   - Создан документ [`docs/AGENT_API.md`](docs/AGENT_API.md) с полным описанием контрактов, примерами запросов/ответов и кодов ошибок.
   - Обновлен документ [`docs/STAGE0_PENDING.md`](docs/STAGE0_PENDING.md) с удалением гипотетических названий метаданных 1С.
   - Обновлен [`README.md`](README.md).

---

## 3. Структура изменений

```text
cashback-one/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── agent_sync.py               # Эндпоинты /agent/sync/* и /agent/heartbeat
│   │   ├── core/
│   │   │   ├── config.py                   # Настройки окружения, лимитов и заголовков
│   │   │   ├── errors.py                   # AppError и глобальные FastAPI exception handlers
│   │   │   ├── phone.py                    # Нормализация телефонов РК/СНГ (E.164)
│   │   │   └── time.py                     # Утилита as_utc для безопасных сравнений
│   │   ├── models/
│   │   │   └── entities.py                 # Обновление модели Agent (last_sync_at, last_error)
│   │   ├── schemas/
│   │   │   └── agent_sync.py               # Pydantic DTO запросов и ответов синхронизации
│   │   ├── services/
│   │   │   └── agent_auth.py               # Выпуск, ротация, хэширование ключей и auth dependency
│   │   └── main.py                         # Регистрация exception handlers и роутера agent_sync
│   ├── migrations/
│   │   └── versions/
│   │       └── 0002_agent_heartbeat_fields.py # Миграция Alembic
│   └── tests/
│       ├── conftest.py                     # Фикстуры тестов с поддержкой SQLite и PostgreSQL
│       ├── test_phone.py                   # Тесты нормализации номеров телефонов
│       ├── test_agent_auth.py              # Тесты аутентификации, ротации, отзыва ключей
│       ├── test_agent_sync_cards.py        # Тесты синхронизации карт, upsert, stale protection
│       ├── test_agent_sync_transactions.py # Тесты идемпотентности, изоляции тенантов и лимитов
│       ├── test_agent_heartbeat.py         # Тесты передачи телеметрии и фиксации ошибок
│       └── test_postgres_integration.py    # Интеграционный тест полного сценария на PostgreSQL 16
├── docs/
│   ├── AGENT_API.md                        # Полная спецификация API обмена ONE Agent -> Cloud
│   └── STAGE0_PENDING.md                   # Актуализированный опросник Stage 0 (без домыслов)
├── README.md                               # Обновленное описание текущего статуса проекта
└── TASK_002_REPORT.md                      # Настоящий отчет
```

---

## 4. Протокол Agent API

### Аутентификация
* **Заголовок:** `X-Agent-Key: <api_key>` (альтернативно: `Authorization: Bearer <api_key>`).
* **Хранение:** SHA-256 от открытого ключа хранится в `agents.api_key_hash`.

### Эндпоинты

| Метод | Путь | Назначение | Батч-лимит |
|---|---|---|---|
| `POST` | `/agent/sync/cards` | Пакетный upsert карт покупателей | 500 |
| `POST` | `/agent/sync/transactions` | Пакетная выгрузка транзакций | 1000 |
| `POST` | `/agent/heartbeat` | Передача телеметрии и статуса агента | 1 |

### Коды ошибок протокола
* `401 UNAUTHORIZED` (`AGENT_AUTH_MISSING`, `AGENT_AUTH_INVALID`): отсутствует заголовок или неверный ключ.
* `403 FORBIDDEN` (`AGENT_REVOKED`): агент деактивирован.
* `422 UNPROCESSABLE_ENTITY`:
  * `BATCH_LIMIT_EXCEEDED`: размер переданного пакета превышает допустимый максимум.
  * `UNKNOWN_CARD_FOR_TRANSACTION`: транзакция ссылается на `card_id`, отсутствующий у данного тенанта.
  * `INVALID_PHONE`: передан некорректный телефон покупателя.
  * `VALIDATION_ERROR`: ошибка валидации схемы данных Pydantic.

---

## 5. Миграции Alembic

* **История миграций:**
  * `0001_initial_schema` (TASK-001): 11 таблиц модели Stage 1.
  * `0002_agent_heartbeat_fields` (TASK-002): добавление полей `last_sync_at` и `last_error` в таблицу `agents`.
* **Проверочный цикл миграций:**
  1. `alembic upgrade head` $\rightarrow$ успешное применение `0002`.
  2. `alembic downgrade -1` $\rightarrow$ успешный откат к `0001`.
  3. `alembic upgrade head` $\rightarrow$ повторное успешное применение `0002`.
  Проверено как в SQLite in-memory (через `render_as_batch=True`), так и на реальном PostgreSQL 16.15.

---

## 6. Результаты тестов и верификации

### 1. Pytest
```text
============================= test session starts ==============================
platform darwin -- Python 3.14.7, pytest-9.0.2, pluggy-1.6.0
rootdir: /Users/nuras/Desktop/cashback-one/backend
configfile: pyproject.toml
plugins: anyio-4.12.1, asyncio-1.3.0
asyncio: mode=Mode.AUTO

tests/test_agent_auth.py::test_missing_agent_key PASSED                  [  3%]
tests/test_agent_auth.py::test_invalid_agent_key PASSED                  [  6%]
tests/test_agent_auth.py::test_revoked_agent PASSED                      [ 10%]
tests/test_agent_auth.py::test_valid_agent_key_header PASSED             [ 13%]
tests/test_agent_auth.py::test_valid_bearer_auth_header PASSED          [ 17%]
tests/test_agent_auth.py::test_key_rotation PASSED                       [ 20%]
tests/test_agent_auth.py::test_api_key_not_stored_plaintext PASSED      [ 24%]
tests/test_agent_heartbeat.py::test_heartbeat_success PASSED             [ 27%]
tests/test_agent_heartbeat.py::test_heartbeat_records_error PASSED       [ 31%]
tests/test_agent_sync_cards.py::test_sync_cards_insert_and_update PASSED [ 34%]
tests/test_agent_sync_cards.py::test_sync_cards_stale_update_protection PASSED [ 37%]
tests/test_agent_sync_cards.py::test_sync_cards_normalizes_phone PASSED  [ 41%]
tests/test_agent_sync_cards.py::test_sync_cards_invalid_phone_rejected PASSED [ 44%]
tests/test_agent_sync_cards.py::test_sync_cards_batch_limit_exceeded PASSED [ 48%]
tests/test_agent_sync_cards.py::test_sync_cards_tenant_isolation PASSED  [ 51%]
tests/test_agent_sync_transactions.py::test_sync_transactions_insert PASSED [ 55%]
tests/test_agent_sync_transactions.py::test_sync_transactions_idempotency PASSED [ 58%]
tests/test_agent_sync_transactions.py::test_sync_transactions_unknown_card_rejected PASSED [ 62%]
tests/test_agent_sync_transactions.py::test_sync_transactions_cross_tenant_rejected PASSED [ 65%]
tests/test_agent_sync_transactions.py::test_sync_transactions_batch_limit_exceeded PASSED [ 68%]
tests/test_constraints.py::test_unique_business_barcode_constraint PASSED [ 72%]
tests/test_constraints.py::test_unique_user_card_assignment PASSED      [ 75%]
tests/test_constraints.py::test_unique_transaction_external_id_per_card PASSED [ 79%]
tests/test_constraints.py::test_numeric_precision_preserved PASSED     [ 82%]
tests/test_health.py::test_health_endpoint PASSED                        [ 86%]
tests/test_phone.py::test_normalize_phone_valid_variants PASSED          [ 89%]
tests/test_phone.py::test_normalize_phone_invalid_raises PASSED          [ 93%]
tests/test_postgres_integration.py::test_postgres_full_sync_scenario PASSED [ 96%]
tests/test_postgres_integration.py::test_postgres_idempotency_and_stale_protection PASSED [100%]

============================== 29 passed in 14.07s ==============================
```

### 2. Ruff Linter
```bash
ruff check app tests
# All checks passed!
```

### 3. Mypy Type Checker
```bash
mypy app
# Success: no issues found in 18 source files
```

### 4. Bytecode Compilation
```bash
python -m compileall app
# Listing 'app'...
# ...
# 0 errors
```

### 5. PostgreSQL 16 Verification
- **СУБД:** PostgreSQL 16.15 (Homebrew x86_64, port 5432).
- **База данных:** `poscenter_loyalty_test`.
- **Драйвер:** `asyncpg` 0.31.0.
- **Результат:** Интеграционные тесты `test_postgres_full_sync_scenario` и `test_postgres_idempotency_and_stale_protection` успешно выполнены непосредственно в среде PostgreSQL 16.15 с проверкой транзакций, батчей, констрейнтов и типов `NUMERIC(18, 4)`.

---

## 7. Контроль инвариантов

1. **`TENANT_ISOLATION`:**
   - Вызовы API не принимают `business_id` в теле запроса или query-параметрах.
   - Организация определяется строго через `agent.business_id` по API-ключу.
   - Карты синхронизируются только для своего бизнеса. Попытка синхронизации транзакций с `card_id`, принадлежащим другому бизнесу, пресекается (`422 UNKNOWN_CARD_FOR_TRANSACTION`).

2. **`IDEMPOTENCY`:**
   - Транзакции идентифицируются композитным ключом `(card_id, external_id)`.
   - Повторные отправки идентичных транзакций не создают дублей в базе данных и возвращаются с флагом `skipped_duplicate`.

3. **`STALE_PROTECTION`:**
   - При синхронизации карт сверяются метки времени `incoming.updated_at` и `existing.updated_at`.
   - Если входящее состояние старше или равно имеющемуся в БД, перезапись баланса и полей карты блокируется.

4. **`PHONE_NORMALIZATION`:**
   - Номера телефонов приводятся к единому формату `+7XXXXXXXXXX`.
   - Номера с некорректным количеством цифр или недопустимыми символами отклоняются до записи в БД.

5. **`NUMERIC_PRECISION`:**
   - Балансы и суммы строго типизированы как `Decimal` в Pydantic и `Numeric(18, 4)` в PostgreSQL. Тип `float` полностью исключен.

---

## 8. Открытые вопросы и статус Stage 0

* Все гипотетические названия объектов 1С исключены из документации.
* Документ [`docs/STAGE0_PENDING.md`](docs/STAGE0_PENDING.md) содержит перечень вопросов к реальной информационной базе клиента:
  - Идентификатор карты (ГУИД / код).
  - Поле штрихкода.
  - Поле телефонного номера.
  - Структура регистра накопления бонусных баллов (наименование регистра, измерение карты, ресурс остатка).
  - Структура регистратора движений (документ продажи/возврата/ручной корректировки).
* Серверный протокол Cloud Sync API полностью готов к приему данных, когда discovery будет завершено и агент будет разработан.

---

## 9. Следующий рекомендуемый шаг (TASK-003)

После приемки задачи TASK-002 рекомендуется перейти к:
**TASK-003: WhatsApp Auth (Wappi Reverse Flow) + Customer Authentication**
* Реализация генерации challenge-кода (`POST /auth/challenge`).
* Прием вебхука от Wappi (`POST /webhooks/wappi`).
* Матчинг входящего сообщения покупателя с активным challenge.
* Выпуск клиентских access/refresh JWT токенов для покупателя.
* Резервный SMS OTP flow.
* Регистрация согласия на обработку персональных данных (РК).

*(Работа над TASK-003 будет начата строго по отдельной команде пользователя).*
