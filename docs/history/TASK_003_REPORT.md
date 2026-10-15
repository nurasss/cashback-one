# TASK-003 Report

**Дата отчета:** 29 сентября 2026 г.  
**Задача:** TASK-003: Customer Authentication Core  
**Исполнитель:** Senior Software Architect / Backend Engineer / QA Auditor  
**Нормативный документ:** `TZ_loyalty_app_v1.1`  
**Предыдущий коммит:** `ca43df227fa05a3d6d33e476df605d06fa65aba6`  
**Ветка:** `main`  

---

## 1. Implemented (Что реализовано)

В рамках задачи TASK-003 создано серверное ядро обратной WhatsApp-аутентификации без предположений о реальном формате вебхуков Wappi:
1. **Эндпоинт генерации challenge (`POST /auth/challenge`):**
   - Прием `device_id` мобильного устройства.
   - Проверка лимитов частоты запросов (rate limiting).
   - Генерация криптографически случайного 8-значного кода из безопасного алфавита.
   - Вычисление HMAC-SHA256 хэша от кода (`code_hash`) и сохранение в БД со статусом `pending` и TTL 3 минуты.
   - Формирование ссылки `wa.me` с текстом кода для перехода в WhatsApp.
2. **Эндпоинт опроса и обмена на токены (`GET /auth/challenge/{id}`):**
   - Проверка обязательного заголовка `X-Device-Id`.
   - Защита от подмены устройства (`DEVICE_MISMATCH`).
   - Возврат статуса `pending` или `expired`.
   - При статусе `confirmed` — атомарный однократный обмен на пользовательскую сессию (`AuthSession`), выпуск пары Access JWT + Refresh Token и перевод статуса в `consumed`.
   - Защита от повторного использования (`CHALLENGE_ALREADY_CONSUMED`).
3. **Внутренний провайдер-независимый сервис подтверждения (`app.services.auth_confirmation`):**
   - Функция `confirm_login_challenge(session, code, sender_phone)`.
   - Нормализация кода и номера телефона (E.164).
   - Атомарный перевод статуса `pending` $\rightarrow$ `confirmed` с фиксацией телефона отправителя.
   - Защита от гонок и запрет перехвата подтверждения вторым телефоном.
4. **Идентификация покупателя (`User Identity`):**
   - Реализация инварианта `one normalized phone -> one User`.
   - Dialect-aware atomic upsert в сервисе `get_or_create_user_by_phone`.
5. **Токены и сессии:**
   - Access JWT (HS256, 15 минут TTL) со стандартными клеймами (`sub`, `sid`, `typ=access`, `iat`, `exp`).
   - Refresh Token (30 дней TTL, 48 байт энтропии, в БД хранится исключительно SHA-256 хэш).
   - Эндпоинт ротации refresh-токенов (`POST /auth/refresh`) с защитой от одновременных вызовов (`with_for_update`).
   - Эндпоинт выхода (`POST /auth/logout`) с отзывом сессии (`revoked_at`).
6. **Ограничение частоты запросов (Rate Limiting):**
   - Абстракция `RateLimiter`.
   - Продакшн-реализация `RedisRateLimiter` (мультипроцессная безопасность через Redis pipeline INCR + EXPIRE).
   - Тестовая реализация `InMemoryRateLimiter` (детерминированное скользящее окно).
7. **Миграции базы данных:**
   - Миграция `0003_customer_auth_core.py` (создание `auth_sessions`, уникальность `users.phone`, поле `confirmed_at`).

---

## 2. Challenge Lifecycle (Жизненный цикл Challenge)

- **`pending`:** Код сгенерирован, открытый текст кода возвращен мобильному приложению, HMAC-SHA256 хэш сохранен в БД. Срок жизни — 180 секунд.
- **`confirmed`:** Входящее сообщение обработано через `confirm_login_challenge`. Номер телефона отправителя сохранен в `phone`, зафиксировано время `confirmed_at`.
- **`consumed`:** Мобильное приложение опросило `GET /auth/challenge/{id}` с верным `X-Device-Id`. Токены выданы. Challenge закрыт навсегда.
- **`expired`:** Прошло более 180 секунд с момента генерации. Попытка подтверждения или обмена отклоняется.

---

## 3. Rate Limiting (Ограничение частоты)

- Проверка выполняется перед созданием challenge:
  - По ключу устройства: `dev:{device_id}` (лимит `auth_challenge_device_limit = 5`).
  - По IP-адресу клиента: `ip:{client_ip}` (лимит `auth_challenge_ip_limit = 20`).
  - Скользящее окно: `auth_challenge_rate_window_seconds = 300` (5 минут).
- При превышении порога возвращается статус `429 Too Many Requests` (`RATE_LIMIT_EXCEEDED`).

---

## 4. Device Binding (Привязка к устройству)

- Challenge жестко ассоциирован с `device_id`.
- Запрос `GET /auth/challenge/{id}` обязан содержать HTTP-заголовок `X-Device-Id`.
- При несовпадении заголовка с владельцем challenge возвращается `403 Forbidden` (`DEVICE_MISMATCH`). Чужое устройство не может получить токены сессии.

---

## 5. User Identity (Идентичность пользователя)

- Инвариант: один нормализованный номер телефона соответствует ровно одной учетной записи `User`.
- На таблицу `users` наложено ограничение `UNIQUE(phone)` (`uq_users_phone`).
- Сервис `get_or_create_user_by_phone` использует `INSERT ... ON CONFLICT (phone) DO UPDATE ... RETURNING id`, исключая дублирование пользователей при конкурентной авторизации.

---

## 6. Access JWT (Токены доступа)

- Алгоритм: `HS256`.
- Подпись: секретный ключ `JWT_SIGNING_KEY` (проверяется минимальная длина 32 символа).
- Срок действия: 15 минут (900 секунд).
- Клеймы:
  - `sub`: UUID пользователя.
  - `sid`: UUID сессии (`AuthSession.id`).
  - `typ`: `"access"`.
  - `iat`: время выдачи.
  - `exp`: время истечения.

---

## 7. Refresh Token Rotation (Ротация refresh-токенов)

- Формат: криптографическая случайная строка (префикс `rfr_`, 48 байт энтропии).
- В таблице `auth_sessions` хранится **только SHA-256 хэш** токена.
- При вызове `POST /auth/refresh`:
  - Строка сессии блокируется (`with_for_update`).
  - Проверяется отсутствие отзыва (`revoked_at is None`) и срок годности.
  - Выпускается новый refresh-токен, его хэш записывается в сессию, старый токен моментально становится недействительным.
  - Из двух параллельных запросов с одинаковым refresh-токеном побеждает ровно один. Второй отклоняется с `401 INVALID_REFRESH_TOKEN`.

---

## 8. Logout (Выход из системы)

- Вызов `POST /auth/logout` с refresh-токеном находит сессию и фиксирует `revoked_at = utcnow()`.
- После отзыва попытки использования refresh-токена отклоняются с кодом 401.
- Выход из одной сессии не инвалидирует другие сессии и устройства того же пользователя.

---

## 9. Database Migration (Миграция БД)

- Файл: `backend/migrations/versions/0003_customer_auth_core.py`.
- Изменения:
  - Таблица `auth_sessions` (PK, `user_id`, `device_id`, `refresh_token_hash`, таймстемпы, FK на `users.id ON DELETE CASCADE`, уникальный индекс на `refresh_token_hash`).
  - Уникальный констрейнт `uq_users_phone` на `users(phone)`.
  - Поле `confirmed_at` в таблице `login_challenges`.
- Проверочный цикл на PostgreSQL 16:
  `alembic upgrade head` $\rightarrow$ `alembic downgrade -1` $\rightarrow$ `alembic upgrade head` $\rightarrow$ `alembic check` ("No new upgrade operations detected").

---

## 10. PostgreSQL Concurrency Tests

Фактически выполнены против реального инстанса PostgreSQL 16.15 (`POSTGRES_TEST_URL`):

```text
PostgreSQL Customer Auth Concurrency:
4 passed, 0 failed, 0 skipped
```

- **`test_pg_auth_01_concurrent_confirmation`:** Два одновременных события подтверждения одного кода завершаются без ошибок, в базе сохраняется единое детерминированное состояние.
- **`test_pg_auth_02_concurrent_same_phone_user_creation`:** Два одновременных процесса создания/получения пользователя по одному телефону создают ровно одну запись `User`.
- **`test_pg_auth_03_concurrent_refresh_rotation`:** Два параллельных HTTP-запроса ротации с одним refresh-токеном: ровно один победитель (200 OK), второй отклонен (401 INVALID_REFRESH_TOKEN), 0 ошибок 500.
- **`test_pg_auth_04_unique_phone_constraint`:** Прямая попытка вставки дубликата телефона блокируется `IntegrityError` на уровне ядра PostgreSQL.

---

## 11. Redis (Ограничение частоты)

- `RedisRateLimiter`: протестирован юнит-тестом с моком атомарного конвейера pipeline (INCR + EXPIRE).
- `InMemoryRateLimiter`: протестирован на соблюдение лимитов, независимость ключей и сброс окна.
- В окружении тестов используется `InMemoryRateLimiter`, исключая зависимость юнит-тестов от запущенного Redis-сервера.

---

## 12. Результаты тестов (Pytest)

```text
============================= test session starts ==============================
rootdir: /Users/nuras/Desktop/cashback-one/backend
configfile: pyproject.toml
collected 73 items

tests/test_agent_auth.py (6 passed)
tests/test_agent_heartbeat.py (2 passed)
tests/test_agent_sync_cards.py (5 passed)
tests/test_agent_sync_transactions.py (6 passed)
tests/test_auth_challenge.py (10 passed)
tests/test_auth_confirmation.py (5 passed)
tests/test_auth_logout.py (2 passed)
tests/test_auth_tokens.py (7 passed)
tests/test_config.py (7 passed)
tests/test_constraints.py (6 passed)
tests/test_health.py (1 passed)
tests/test_phone.py (3 passed)
tests/test_postgres_agent_sync_concurrency.py (4 passed)
tests/test_postgres_customer_auth_concurrency.py (4 passed)
tests/test_postgres_model_smoke.py (1 passed)
tests/test_rate_limiter.py (4 passed)

============================= 73 passed in 19.54s ==============================
```

---

## 13. Качество кода

- **Ruff:** `All checks passed!`
- **Mypy (Strict mode):** `Success: no issues found in 24 source files`
- **Compileall:** `0 errors`

---

## 14. Security Checks (Проверка безопасности)

- Коды подтверждения в БД хранятся только как HMAC-SHA256 digests.
- Refresh-токены хранятся только как SHA-256 хэши.
- Секретные ключи (`JWT_SIGNING_KEY`, `AUTH_CHALLENGE_HASH_KEY`) отсутствуют в коде репозитория и настраиваются через окружение.
- Проверяется минимальная длина секретов ($\ge 32$ символов).
- Отсутствуют токены и открытые коды в логах.
- Несовпадение `device_id` блокирует доступ к сессии (`403 DEVICE_MISMATCH`).

---

## 15. Wappi Boundary (Граница провайдера)

> **Примечание:**
> Фактический формат вебхука Wappi и механизм его аутентификации должны быть проверены на реальном профиле/документации Wappi перед началом задачи TASK-004.
> На текущем этапе создан только нейтральный сервис `confirm_login_challenge`.

---

## 16. Deviations & Known Limitations (Отклонения и ограничения)

- Отклонений от ТЗ нет.
- Схема вебхука Wappi и прием входящих HTTP-запросов от Wappi не реализовывались (перенесены в TASK-004).
- Автоматический поиск и привязка карт покупателя к пользователю не выполнялись (перенесены в задачу Card Binding).
- SMS OTP fallback не реализовывался.

---

## 17. Git Status

- **Ветка:** `main`
- **Рабочее дерево:** чистое перед фиксацией коммита.
