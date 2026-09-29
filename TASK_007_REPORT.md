# TASK-007 Implementation Report: SMS Fallback Authentication Core

**Date:** 2026-09-29  
**Branch:** `main`  
**Status:** COMPLETE (Ready for review)  
**Primary Specification:** `TZ_loyalty_app_v1.1` (Section 4 — Fallback SMS Authentication)

---

## 1. Executive Summary

В рамках TASK-007 полностью реализовано ядро резервной SMS-аутентификации (`SMS Fallback Authentication Core`) для клиентского входа в мобильное приложение POSCENTER Loyalty.

> [!IMPORTANT]
> **REAL_SMS_PROVIDER = NOT IMPLEMENTED**
>
> В соответствии со строгими границами задачи (Strict Scope), интеграция с конкретными внешними вендорами SMS (Twilio, SMSC, KazInfoTech и т.д.) **НЕ производилась**.
> Реализована строгая архитектурная абстракция (`SmsProvider` Protocol) со значением по умолчанию `SMS_PROVIDER_MODE=disabled`.
> **SMS authentication core is ready for provider adapter integration.**

---

## 2. Архитектура и реализованный Scope

### 2.1. Эндпоинты API
* **`POST /auth/sms/request`**:
  * Принимает `{ "phone": "+77011234567", "device_id": "..." }`.
  * Валидирует формат телефона (строгий E.164) и `device_id` (непустой, без пробелов, 1-128 символов).
  * Применяет многоуровневый Rate Limiting в Redis по хэшу телефона (`phone_fingerprint`), `device_id` и `client_ip`.
  * Инвалидирует (переводит в `superseded`) любые предыдущие `pending` OTP для данной пары `(phone, device_id)`.
  * Генерирует 6-значный криптографически стойкий OTP через `secrets.choice(string.digits)`.
  * Вызывает `SmsProvider.send_otp()` до фиксации транзакции.
  * Возвращает `{ "status": "sent", "expires_in": 300 }`.

* **`POST /auth/sms/verify`**:
  * Принимает `{ "phone": "+77011234567", "device_id": "...", "code": "123456" }`.
  * Захватывает эксклюзивную блокировку строки (`SELECT ... FOR UPDATE`), сериализуя попытки ввода и исключая гонки.
  * Проверяет срок жизни (TTL 300с / 5 минут); при истечении переводит статус в `expired` (HTTP 400 `OTP_EXPIRED`).
  * Проверяет лимит попыток (максимум 5); при превышении переводит статус в `exhausted` (HTTP 400 `OTP_MAX_ATTEMPTS_EXCEEDED`).
  * Сравнивает HMAC-SHA256 дайджест в константное время (`hmac.compare_digest`).
  * При успехе атомарно:
    * переводит статус в `consumed`, фиксирует `verified_at = utcnow()`;
    * создает или находит пользователя (`User`) через `get_or_create_user_by_phone`;
    * создает сессию `AuthSession` с SHA-256 хэшем refresh-токена;
    * выдает access JWT (HS256, 15 минут) и refresh-токен (30 дней).

### 2.2. Безопасность и криптографические инварианты
1. **Plaintext OTP:** Открытый 6-значный OTP **никогда не сохраняется в БД** и **никогда не логируется**.
2. **HMAC-SHA256 Digest:** В базе данных хранится исключительно 64-символьный хэш:
   $$\text{code\_hash} = \text{HMAC-SHA256}(\text{SMS\_OTP\_HASH\_KEY}, \text{phone} \mathbin{\Vert} \text{":"} \mathbin{\Vert} \text{otp})$$
3. **PII Protection в Rate Limiting:** В Redis не сохраняется открытый телефон; используется односторонний SHA-256 fingerprint: `sha256("phone:" + phone)[:32]`.
4. **Device Binding:** OTP привязан к паре `(phone, device_id)`. Проверка с чужого устройства отклоняется (`OTP_NOT_FOUND`).
5. **Single-Use:** Использованный код переходит в статус `consumed` и не может быть верифицирован повторно.

### 2.3. Обработка сбоев провайдера и границы согласованности (Delivery Boundary)
* **Provider-reported delivery failure rolls back OTP DB state. Cross-system atomic delivery is not claimed.**
* Если отправка SMS завершается ошибкой (сетевой сбой, таймаут, исключение провайдера), вызывается `await session.rollback()`, и в БД не остается незавершенных OTP-записей.
* При `SMS_PROVIDER_MODE=disabled` запрос отклоняется с HTTP 503 `SMS_PROVIDER_NOT_CONFIGURED` до изменения rate limit и создания записи в БД.
* При сбое транспорта/сети возвращается HTTP 503 `SMS_DELIVERY_UNAVAILABLE`.
* Внешняя доставка оператором связи не может быть автоматически отозвана после коммита БД; production-адаптер должен учитывать этот boundary (идемпотентность, таймауты).

### 2.4. Concurrency Safety
* На PostgreSQL одновременные вызовы `POST /auth/sms/request` для одной пары `(phone, device_id)` сериализуются с помощью транзакционного advisory-лока:
  `SELECT pg_advisory_xact_lock(hashtext(:phone), hashtext(:device_id))`.
  Это гарантирует, что при параллельных запросах ровно один код остается в статусе `pending`, а остальные корректно помечаются как `superseded`.
* Верификация защищена row-level блокировкой `FOR UPDATE`, что полностью предотвращает атаку параллельного подбора (bypass max 5 attempts) и двойной выпуск сессий.

---

## 3. Изменения схемы БД и миграции Alembic

* Создана миграция `0007_sms_auth_core.py` (ревизия `0006_user_card_visibility` $\rightarrow$ `0007_sms_auth_core`).
* Расширена таблица `otp_codes`:
  * Добавлена колонка `device_id VARCHAR(128) NOT NULL DEFAULT ''`.
  * Добавлена колонка `status VARCHAR(32) NOT NULL DEFAULT 'pending'`.
  * Добавлена колонка `verified_at TIMESTAMPTZ NULL`.
  * Сужена колонка `code_hash` с `VARCHAR(255)` до `VARCHAR(64)` (ровно 64 hex-символа HMAC-SHA256).
  * Создан составной индекс `ix_otp_codes_phone_device_id` на `(phone, device_id)`.
  * Удален устаревший одиночный индекс `ix_otp_codes_phone`.
* **Верификация миграции:**
  * `alembic upgrade head` $\rightarrow$ успешно;
  * `alembic downgrade -1` $\rightarrow$ успешно;
  * `alembic upgrade head` $\rightarrow$ успешно;
  * `alembic check` $\rightarrow$ `No new upgrade operations detected` (0 drift).

---

## 4. Регрессионная защита TASK-006

В `backend/tests/test_customer_bind_card.py` добавлен расширенный тест `test_bind_card_foreign_owner_cannot_be_stolen_even_if_card_phone_changed_to_new_user`:
* Пользователь A привязал карту с телефоном A.
* Позже в зеркале ONE телефон карты обновляется на телефон пользователя B.
* Пользователь B пытается привязать карту через `POST /me/cards/bind`.
* Запрос пользователя B строго отклоняется с `409 CARD_BIND_NOT_ALLOWED`.
* Владелец карты в `user_cards` остается неизменным (User A).

---

## 5. Метрики тестирования и Quality Gates

### Результаты автоматических тестов:
1. **Unit & API Suite:** 166 тестов пройдено (включая 14 новых тестов в `test_sms_auth.py`).
2. **PostgreSQL Concurrency Suite:** 29 тестов пройдено на реальной СУБД PostgreSQL 16:
   * `PG-SMS-01`: Конкурентные запросы OTP оставляют ровно 1 активный код.
   * `PG-SMS-02`: Конкурентные неверные попытки не могут обойти лимит 5 попыток.
   * `PG-SMS-03`: Конкурентная успешная верификация создает ровно 1 сессию.
   * `PG-SMS-04`: Сбой доставки атомарно откатывает транзакцию и не оставляет повисших OTP.
   * `PG-BIND-01..04`: Конкурентная привязка карт.
   * `PG-AUTH-01..06`: Конкурентная WhatsApp-авторизация.
   * `PG-WALLET-01..05`: Конкурентный кошелек и автопривязка.
   * `PG-WAPPI-01..04`: Конкурентные вебхуки Wappi.
   * `PG-CONC-01..04`: Конкурентная синхронизация агентов.
3. **Статический анализ и компиляция:**
   * `ruff check app tests migrations`: 0 errors.
   * `mypy app migrations`: 0 errors (41 source file checked).
   * `python -m compileall app tests migrations`: 0 errors.
   * `alembic check`: 0 drift.

---

## 6. Затронутые и созданные файлы

### Созданные файлы:
* `backend/app/services/sms_provider.py` — протокол `SmsProvider`, `DisabledSmsProvider`, `FakeSmsProvider`.
* `backend/app/services/sms_auth_service.py` — доменная логика запроса и верификации SMS OTP.
* `backend/migrations/versions/0007_sms_auth_core.py` — миграция Alembic для таблицы `otp_codes`.
* `backend/tests/test_sms_auth.py` — 14 тестов логики SMS OTP, валидаций, лимитов и безопасности.
* `backend/tests/test_postgres_sms_concurrency.py` — 4 теста PostgreSQL concurrency (PG-SMS-01..04).
* `docs/SMS_PROVIDER_CONTRACT.md` — спецификация контракта провайдера, руководство по интеграции.
* `TASK_007_REPORT.md` — данный отчет.

### Модифицированные файлы:
* `backend/app/core/config.py` — параметры SMS OTP, валидация ключей и fallback на `auth_challenge_hash_key`.
* `backend/app/core/security.py` — генерация 6-значных OTP, HMAC-SHA256 хэширование и константная проверка.
* `backend/app/models/entities.py` — расширение сущности `OtpCode`.
* `backend/app/schemas/auth.py` — Pydantic схемы `SmsOtpRequest`, `SmsOtpRequestResponse`, `SmsOtpVerifyRequest`.
* `backend/app/api/auth.py` — маршруты `POST /auth/sms/request` и `POST /auth/sms/verify`.
* `backend/tests/test_customer_bind_card.py` — регрессионный тест для TASK-006.
* `backend/.env.example` — переменные окружения `SMS_PROVIDER_MODE`, `SMS_OTP_HASH_KEY`, лимиты OTP.
* `docs/AUTH.md` — раздел 7 с описанием SMS Fallback flow и инвариантов.
* `README.md` — обновление статусов реализации монорепозитория.
