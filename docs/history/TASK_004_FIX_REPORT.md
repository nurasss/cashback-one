# TASK-004-FIX Report

## Fixed Findings

В рамках патча TASK-004-FIX устранены следующие критические дефекты:
1. **Устранён silent swallow ошибок инфраструктуры/БД в `process_wappi_webhook()`:**
   - Ранее блок `except Exception as exc` перехватывал любые операционные сбои, откатывал транзакцию, пытался сохранить `result = "error"` и возвращал HTTP 200 с `ignored += 1`.
   - В результате провайдер Wappi получал 200 OK и не повторял доставку (no retry), что приводило к безвозвратной потере сообщения авторизации.
   - Теперь операционные сбои вызывают полный `ROLLBACK` незафиксированной резервации и возвращают контролируемый HTTP 503 (`WEBHOOK_PROCESSING_UNAVAILABLE`).
2. **Устранено сохранение неудачной резервации (`failed reservation`):**
   - Ранее попытка сохранить `result = "error"` после отката транзакции либо падала, либо создавала постоянный маркер дубликата, блокирующий повторную доставку сообщения провайдером.
   - Теперь при сбое БД откат отменяет саму резервацию `(profile_id, message_id)`. Сообщение остаётся пригодным для повторной обработки.
3. **Устранена утечка деталей исключений (`str(exc)`):**
   - Удалено поле `"error": str(exc)` из внешнего ответа API. Никакие SQL-запросы, имена таблиц, драйверные ошибки или строки подключения не попадают во внешний ответ.
4. **Удалён выдуманный дефолт auth-заголовка (`X-Wappi-Secret`):**
   - Поле `wappi_webhook_auth_header` теперь имеет `default=""` в классе `Settings`.
   - Для окружений `development` и `production` отсутствие или пустое значение заголовка вызывает немедленный fail-fast (`ValidationError`).
   - В тестовом окружении используется детерминированный `X-Test-Wappi-Auth`.
   - Документация и `.env.example` синхронизированы со статусом `WAPPI_AUTH_HEADER_NAME = NOT VERIFIED`.

---

## Auth Header Configuration

* **Конфигурация (`app/core/config.py`):**
  - Поле: `wappi_webhook_auth_header: str = Field(default="", description="Header name used to authenticate incoming Wappi webhooks (must be explicitly configured).")`
  - Валидатор: в dev/prod требует обязательного непустого значения, исключая неявные дефолты.
  - В test mode: детерминированное значение `X-Test-Wappi-Auth`.
* **.env.example:**
  - `WAPPI_WEBHOOK_AUTH_HEADER=<verified_wappi_header_name>` с явным комментарием о статусе не верифицированного публично имени заголовка.

---

## Webhook Error Semantics

Разграничены два класса исходов:
1. **Expected provider/domain outcomes:**
   - Несуществующий код (`not_found`), просроченный challenge (`expired`), использованный challenge (`consumed`), чужой номер на подтвержденном challenge (`already_confirmed_other_phone`), дубликат (`duplicate`), невалидный формат кода/отправителя, игнорируемые группы/события/профили.
   - Сохраняются в таблице `wappi_webhook_events` с соответствующим статусом.
   - Коммитятся в БД и возвращают HTTP 200 OK.
2. **Operational/internal failures:**
   - Сбои подключения к PostgreSQL (`SQLAlchemyError`, `DBAPIError`, `OperationalError`), таймауты (`TimeoutError`), сетевые сбои (`OSError`, `ConnectionError`), непредвиденные исключения.
   - Вызывают немедленный `await session.rollback()`.
   - Возвращают контролируемый HTTP 503:
     ```json
     {
       "error": {
         "code": "WEBHOOK_PROCESSING_UNAVAILABLE",
         "message": "Webhook could not be processed. Retry later."
       }
     }
     ```

---

## Transaction Atomicity

Для каждого входящего сообщения обработка выполняется по строгой транзакционной схеме:
```text
BEGIN
  reserve (profile_id, message_id) via ON CONFLICT DO NOTHING RETURNING id
  filter checks (wh_type, chat, dialog, sender, code alphabet)
  confirm_login_challenge(session, code, sender_phone, commit=False)
  update wappi_webhook_events.result = status
COMMIT
```
Если на любом этапе до `COMMIT` происходит ошибка:
```text
ROLLBACK
```
отменяет одновременно:
* резервацию записи в `wappi_webhook_events`;
* мутации `LoginChallenge`;
* обновление статуса события.

---

## Retry Safety

После выполнения `ROLLBACK`:
* В таблице `wappi_webhook_events` не остаётся записи с данным `(profile_id, message_id)`.
* Challenge остаётся в статусе `pending`.
* При поступлении повторного запроса от провайдера с тем же `message_id` запрос принимается и обрабатывается как первоначальный без коллизий.

---

## Internal Error Hygiene

* Полностью исключено включение `str(exc)` в тело HTTP-ответа.
* Во внешний ответ возвращается только фиксированный контролируемый JSON envelope с кодом `WEBHOOK_PROCESSING_UNAVAILABLE`.
* Внутреннее логирование выполняется через `logger.exception("Operational database failure processing Wappi message %s (type=%s)", message_id, wh_type)` без вывода чувствительных данных (секретов, открытых кодов, телефонов).

---

## Batch Failure Semantics

В батчевом контейнере `messages: [...]`:
* Каждое сообщение фиксируется атомарно.
* Если сообщение $N$ завершается инфраструктурным сбоем, ранее обработанные сообщения $1..N-1$ остаются зафиксированными (`committed`).
* Сообщение $N$ откатывается (`rolled back`), и весь вебхук-запрос отвечает статусом 503.
* При повторе всего батча провайдером сообщения $1..N-1$ идентифицируются как `duplicate`, а сообщение $N$ успешно завершает подтверждение.

---

## PG-WAPPI-04

Реализован и успешно выполнен тест на реальной PostgreSQL 16:
* **Файл:** `backend/tests/test_postgres_wappi_concurrency.py::test_pg_wappi_04_rollback_and_retry_atomicity`
* **Шаги проверки:**
  1. Создан pending challenge.
  2. Отправлен валидный вебхук Wappi с инжекцией operational DB failure во время подтверждения (после успешной резервации).
  3. Первый запрос вернул HTTP 503 (`WEBHOOK_PROCESSING_UNAVAILABLE`).
  4. Проверено состояние БД: `challenge.status == "pending"`, `COUNT(wappi_webhook_events for message_id) == 0`.
  5. Снят fault hook.
  6. Отправлен повторный запрос с тем же `message_id`, `profile_id`, `code`.
  7. Второй запрос вернул HTTP 200, `processed == 1`, `duplicates == 0`.
  8. Проверено состояние БД: `challenge.status == "confirmed"`, `phone == "+77017770001"`, `COUNT(wappi_webhook_events) == 1`, `result == "confirmed"`.

---

## PostgreSQL Tests

Все 4 конкурентных интеграционных теста на реальной PostgreSQL 16 пройдены (100%):
```text
tests/test_postgres_wappi_concurrency.py::test_pg_wappi_01_concurrent_duplicate_message_delivery PASSED
tests/test_postgres_wappi_concurrency.py::test_pg_wappi_02_concurrent_different_senders_same_code PASSED
tests/test_postgres_wappi_concurrency.py::test_pg_wappi_03_db_unique_constraint PASSED
tests/test_postgres_wappi_concurrency.py::test_pg_wappi_04_rollback_and_retry_atomicity PASSED
```

---

## Regression Tests

Добавлены unit/API регрессионные тесты:
* `tests/test_wappi_webhook_parser.py::test_wappi_webhook_db_failure_returns_503_and_no_leak` — проверка контролируемого ответа 503 и отсутствия утечки SQL/credentials.
* `tests/test_wappi_webhook_parser.py::test_wappi_webhook_batch_failure_semantics` — проверка корректной обработки смешанных батчей с повтором.
* `tests/test_config.py::test_config_dev_omitted_wappi_webhook_auth_header_rejected` — проверка rejection при отсутствии заголовка.
* `tests/test_config.py::test_config_test_mode_deterministic_test_header` — проверка test mode дефолта.
* `tests/test_config.py::test_no_hardcoded_x_wappi_secret_as_field_default` — проверка отсутствия hardcoded default в схеме.

Общее количество тестов в проекте: **122 passed, 0 failed, 0 skipped**.

---

## Migration Verification

* Новая миграция 0006 НЕ создавалась (схема БД полностью соответствует задаче).
* Проверена схема на PostgreSQL:
  ```bash
  alembic upgrade head
  alembic downgrade -1
  alembic upgrade head
  alembic check
  ```
  Результат: `No new upgrade operations detected.`

---

## Ruff

* Команда: `ruff check app tests migrations`
* Результат: `All checks passed!` (0 errors, 0 warnings).

---

## Mypy

* Команда: `mypy app`
* Результат: `Success: no issues found in 27 source files`.

---

## Compileall

* Команда: `python -m compileall app tests migrations`
* Результат: `Listing 'app'... Listing 'tests'... Listing 'migrations'...` (0 syntax errors).

---

## Security Checks

* [x] Webhook auth secret проверяется constant-time (`hmac.compare_digest`).
* [x] Secret, сырое тело запроса, открытый код и полный телефон не логируются в `logger.exception`.
* [x] В таблице `wappi_webhook_events` нет PII.
* [x] Ответы API при сбоях БД возвращают 503 без утечки системных данных.
* [x] Повторная обработка сообщения после сбоя подтверждена тестом `PG-WAPPI-04`.
* [x] Сторонние профили Wappi отсекаются без мутаций.
* [x] Групповые и не-chat сообщения отсекаются.
* [x] Атака вторым номером изолируется без раскрытия первого номера.

---

## Wappi Header Verification Status

```text
WAPPI_AUTH_HEADER_NAME = NOT VERIFIED
```
Имя заголовка в production задаётся строго через переменную среды deployment `WAPPI_WEBHOOK_AUTH_HEADER`. В коде отсутствуют фиктивные production defaults.

---

## Deviations

Отклонений от ТЗ `TZ_loyalty_app_v1.1` и инструкций TASK-004-FIX нет.

---

## Known Limitations

1. Реальное имя auth-заголовка сервиса Wappi требует наблюдения на живом трафике при подключении production-инстанса.
2. В соответствии со скоупом не реализован SMS fallback/OTP (запланирован на последующие этапы).

---

## Git Status

```text
On branch main
nothing to commit, working tree clean
```

---

## Branch

`main`

---

## HEAD

`bba404827e23281814158e12f6614e027aa9aad8` (коммит патча TASK-004-FIX).

