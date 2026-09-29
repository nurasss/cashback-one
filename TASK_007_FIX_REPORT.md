# TASK-007 Fix Report: Review Hardening & Consistency Patch

**Date:** 2026-09-29  
**Branch:** `main`  
**Status:** COMPLETE (PATCH applied and verified)  
**Parent Task:** TASK-007 (SMS Fallback Authentication Core)

---

## 1. Обзор исправлений независимого ревью

В рамках данного патча устранены 3 архитектурных замечания:

1. **`SMS_OTP_HASH_KEY` как обязательный отдельный секрет:**
   * Полностью удален runtime-fallback `self.sms_otp_hash_key = self.auth_challenge_hash_key`.
   * Для `APP_ENV=development` и `APP_ENV=production` секрет `SMS_OTP_HASH_KEY` обязан быть явно передан и иметь длину $\ge 32$ символов.
   * Отсутствие `SMS_OTP_HASH_KEY` или его недостаточная длина приводят к немедленному `ValidationError` (fail-fast).
   * В окружении `APP_ENV=test` разрешен детерминированный тестовый секрет по умолчанию.

2. **Защита от использования FakeSmsProvider в dev/prod:**
   * В `app/core/config.py` режим `SMS_PROVIDER_MODE=fake` в `development`/`production` вызывает немедленный `ValidationError` при инициализации `Settings`.
   * В `app/services/sms_provider.py` метод `get_fake_sms_provider()` выбрасывает `RuntimeError` при попытке прямого вызова вне `APP_ENV=test`.
   * Зависимость `get_sms_provider()` в не-тестовом окружении не может вернуть фейковый провайдер.
   * Единственным допустимым режимом для `development` и `production` на текущем этапе является `disabled`. Неизвестные режимы (`twilio`, `foo`) вызывают fail-fast.

3. **Оптимизация порядка выполнения и сохранение квоты Rate Limiter:**
   * Если SMS-провайдер отключен (`DisabledSmsProvider`), проверка готовности провайдера выполняется **до** обращения к `RateLimiter`.
   * 10 запросов при `SMS_PROVIDER_MODE=disabled` возвращают `503 SMS_PROVIDER_NOT_CONFIGURED`, не расходуя квоту попыток в Redis.
   * Последующее переключение на рабочий провайдер не приводит к ложному срабатыванию `429 RATE_LIMIT_EXCEEDED`.

4. **Уточнение границ согласованности (Delivery Boundary):**
   * В документации и отчетах скорректирована формулировка:
     > **Provider-reported delivery failure rolls back OTP DB state. Cross-system atomic delivery is not claimed.**
   * Документировано, что сквозная распределенная атомарность между PostgreSQL и внешним SMS-шлюзом технически невозможна.
   * Сформулированы четкие требования к будущему production-адаптеру (сетевые таймауты, маппинг в 503, обработка ambiguous outcomes, использование idempotency keys).

---

## 2. Добавленные тесты

### `backend/tests/test_config.py`:
* `test_config_dev_without_sms_otp_hash_key_rejected`: проверка fail-fast при отсутствии ключа в dev.
* `test_config_prod_without_sms_otp_hash_key_rejected`: проверка fail-fast при отсутствии ключа в prod.
* `test_config_dev_short_sms_otp_hash_key_rejected`: проверка отклонения ключей короче 32 символов.
* `test_config_auth_challenge_key_does_not_substitute_sms_key`: проверка запрета неявного fallback с WhatsApp ключа.
* `test_config_dev_fake_provider_rejected`: проверка запрета `SMS_PROVIDER_MODE=fake` в dev.
* `test_config_prod_fake_provider_rejected`: проверка запрета `SMS_PROVIDER_MODE=fake` в prod.
* `test_config_test_fake_provider_allowed`: проверка допустимости `fake` в тестовом окружении.
* `test_config_unknown_provider_mode_rejected`: проверка отклонения неподдерживаемых режимов.

### `backend/tests/test_sms_auth.py`:
* `test_sms_request_disabled_provider_does_not_consume_rate_limit`: 10 вызовов при disabled возвращают 503; последующий вызов с fake провайдером возвращает 200 OK (квота не растрачена).
* `test_fake_sms_provider_forbidden_outside_test_env`: регрессионный тест, доказывающий невозможность получить `status='sent'` через фейк в dev/prod.

---

## 3. Проверка качества (Quality Gates)

1. **Unit & API тесты:**
   * 170 тестов успешно пройдено (`pytest -v -m "not slow"`).
2. **PostgreSQL Concurrency тесты:**
   * 29 тестов успешно пройдено на реальной СУБД PostgreSQL 16 (PG-SMS-01..04, PG-BIND-01..04, PG-AUTH-01..06, PG-WALLET-01..05, PG-WAPPI-01..04, PG-CONC-01..04).
3. **Статический анализ:**
   * `ruff check app tests migrations`: 0 errors.
   * `mypy app migrations`: 0 errors (41 source file checked).
   * `python -m compileall app tests migrations`: 0 errors.
4. **Схема базы данных и Alembic:**
   * Схема не менялась, новая миграция не создавалась.
   * `alembic check`: 0 schema drift (`No new upgrade operations detected`).
