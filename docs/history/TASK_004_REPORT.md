# TASK-004: Wappi Incoming Webhook & Challenge Confirmation — Completion Report

**Task Status:** COMPLETED / READY FOR REVIEW  
**Base Commit:** `838f78d05e39c900bb195778d27f82df5d48e259`  
**Target Branch:** `main`  
**Application Version:** `0.4.0`  

---

## 1. Executive Summary

В рамках TASK-004 реализован production-ready адаптер входящего вебхука Wappi (`POST /webhooks/wappi`), связывающий входящие сообщения пользователей с 8-символьным кодом авторизации и существующим доменным ядром `confirm_login_challenge(...)`.

### Ключевые результаты:
1. **Анализ контракта Wappi:** Создан нормативный документ [`docs/WAPPI_WEBHOOK_CONTRACT.md`](file:///Users/nuras/Desktop/cashback-one/docs/WAPPI_WEBHOOK_CONTRACT.md) на основе официальной документации Wappi API (`https://wappi.pro/docs/`). Зафиксирован статус заголовка: `WAPPI_AUTH_HEADER_NAME = NOT VERIFIED`. Имя заголовка аутентификации полностью отвязано от кода и управляется через переменную окружения `WAPPI_WEBHOOK_AUTH_HEADER`.
2. **Carry-over Fix (TASK-003):** В `confirm_login_challenge` устранена возможность состояния `status = confirmed, phone = NULL`. Пустые/невалидные номера вызывают `422 INVALID_PHONE_FORMAT` до любых мутаций БД. Добавлен параметр `commit: bool = True` для координации атомарности.
3. **Безопасная аутентификация вебхука:** Секрет проверяется алгоритмом постоянного времени `hmac.compare_digest`. Отсутствующий или несовпадающий секрет возвращает `401 Unauthorized`.
4. **Защита от DoS (Payload Size Guard):** Тела запросов, превышающие `WAPPI_WEBHOOK_MAX_BODY_BYTES` (по умолчанию 64 КБ), отсекаются с кодом `413 Payload Too Large`.
5. **Изоляция профиля (Profile Isolation):** Сообщения от сторонних Wappi-профилей отклоняются без изменения состояния БД (`ignored_profile`).
6. **Фильтрация спама и групп:** Запросы из групповых чатов (`@g.us`, `chat_type != dialog`), не-текстовые сообщения (`type != "chat"`), сервисные уведомления (`wh_type != "incoming_message"`), а также JID с некорректным форматом отклоняются без ошибок 500.
7. **Атомарная идемпотентность без 500 ошибок:** Таблица `wappi_webhook_events` с уникальным ограничением `uq_wappi_webhook_events_profile_message` на `(profile_id, message_id)`. Concurrency-safe speculative insert (`ON CONFLICT (profile_id, message_id) DO NOTHING`) гарантирует: при параллельной или повторной доставке одного сообщения подтверждение выполняется ровно один раз, повторные вызовы возвращают `200 OK` (`result: "duplicate"`), с 0 `IntegrityError` и 0 HTTP 500.
8. **Изоляция чужих номеров (Second-Phone Attack):** При попытке подтвердить уже подтвержденный challenge другим номером возвращается `already_confirmed_other_phone` без раскрытия номера легитимного покупателя.
9. **Zero PII Storage:** В таблице `wappi_webhook_events` не сохраняются персональные данные (номера телефонов, коды, сырые тела запросов).

---

## 2. Архитектурные изменения и файлы

| Файл | Статус | Назначение |
|---|---|---|
| [`docs/WAPPI_WEBHOOK_CONTRACT.md`](file:///Users/nuras/Desktop/cashback-one/docs/WAPPI_WEBHOOK_CONTRACT.md) | Создан | Спецификация контракта Wappi, статус auth-заголовка, правила фильтрации. |
| [`backend/app/core/config.py`](file:///Users/nuras/Desktop/cashback-one/backend/app/core/config.py) | Модифицирован | Настройки Wappi (`wappi_login_profile_id`, `wappi_webhook_auth_header`, `wappi_webhook_auth_secret`, `wappi_webhook_max_body_bytes`), строгая валидация в dev/prod, bump версии до `0.4.0`. |
| [`.env.example`](file:///Users/nuras/Desktop/cashback-one/.env.example) | Модифицирован | Переменные окружения для конфигурации вебхука Wappi. |
| [`backend/app/models/entities.py`](file:///Users/nuras/Desktop/cashback-one/backend/app/models/entities.py) | Модифицирован | Сущность `WappiWebhookEvent` с `UniqueConstraint("profile_id", "message_id")`. |
| [`backend/app/models/__init__.py`](file:///Users/nuras/Desktop/cashback-one/backend/app/models/__init__.py) | Модифицирован | Экспорт `WappiWebhookEvent` в `__all__`. |
| [`backend/migrations/versions/0005_wappi_webhook_events.py`](file:///Users/nuras/Desktop/cashback-one/backend/migrations/versions/0005_wappi_webhook_events.py) | Создан | Миграция Alembic: создание таблицы `wappi_webhook_events` и индекса по `received_at`. |
| [`backend/app/schemas/wappi.py`](file:///Users/nuras/Desktop/cashback-one/backend/app/schemas/wappi.py) | Создан | Pydantic-схемы `WappiMessageItem`, `WappiWebhookPayload`, `WappiWebhookResponse`. |
| [`backend/app/services/auth_confirmation.py`](file:///Users/nuras/Desktop/cashback-one/backend/app/services/auth_confirmation.py) | Модифицирован | Carry-over fix: строгая валидация номера до мутаций, флаг `commit: bool = True`. |
| [`backend/app/services/wappi_webhook.py`](file:///Users/nuras/Desktop/cashback-one/backend/app/services/wappi_webhook.py) | Создан | Доменный процессор вебхука: фильтры, dialect-safe `ON CONFLICT DO NOTHING`, атомарный коммит подтверждения. |
| [`backend/app/api/webhooks.py`](file:///Users/nuras/Desktop/cashback-one/backend/app/api/webhooks.py) | Создан | Эндпоинт `POST /webhooks/wappi`: constant-time auth, проверка размера, делегирование. |
| [`backend/app/main.py`](file:///Users/nuras/Desktop/cashback-one/backend/app/main.py) | Модифицирован | Регистрация `webhooks_router`. |
| [`docs/AUTH.md`](file:///Users/nuras/Desktop/cashback-one/docs/AUTH.md) | Модифицирован | Обновление раздела 6 с описанием адаптера Wappi, гарантий безопасности и ссылкой на контракт. |
| [`README.md`](file:///Users/nuras/Desktop/cashback-one/README.md) | Модифицирован | Актуализация статуса монорепозитория, перенос Wappi из отложенных задач в выполненные. |

---

## 3. Результаты тестирования и верификации

### Сводка тестового покрытия:
* **Всего тестов в проекте:** 116 (100% пройдены успешно, 0 ошибок).
* **Тесты конфигурации (`test_config.py`):** 17 тестов (валидация dev/prod Wappi-переменных, проверка длины секрета >= 32, запрет пустого профиля).
* **Тесты аутентификации вебхука (`test_wappi_webhook_auth.py`):** 7 тестов (отсутствие заголовка -> 401, неверный секрет -> 401, валидный секрет -> 200, динамическое имя заголовка, ограничение размера тела Content-Length -> 413, ограничение размера тела без заголовка -> 413, невалидный JSON -> 400).
* **Тесты парсера и фильтрации (`test_wappi_webhook_parser.py`):** 10 тестов (успешное подтверждение challenge, последовательный дубликат `message_id`, чужой профиль, не-incoming события, не-chat тип, групповые чаты `@g.us` и `chat_type=group`, невалидный отправитель, невалидный формат кода, несуществующий код, атака вторым номером).
* **Тесты доменного сервиса (`test_auth_confirmation.py`):** 10 тестов (включая регрессионные тесты пустого/пробельного номера телефона, подтверждающие неизменность pending-статуса).
* **Интеграционные конкурентные тесты на PostgreSQL 16 (`test_postgres_wappi_concurrency.py`):**
  * `PG-WAPPI-01`: 5 параллельных запросов с идентичным `message_id` через `asyncio.gather`. Ровно 1 подтверждение, 4 дубликата, ровно 1 запись в `wappi_webhook_events`, 0 `IntegrityError`, 0 HTTP 500.
  * `PG-WAPPI-02`: Два параллельных запроса с одинаковым кодом от разных номеров. Ровно один победитель (`confirmed`), второй изолирован (`already_confirmed_other_phone`), данные победителя не утекли.
  * `PG-WAPPI-03`: Проверка прямого ограничения целостности `uq_wappi_webhook_events_profile_message` на уровне PostgreSQL.

### Линтеры и статический анализ:
* `python -m compileall app tests migrations`: 0 errors.
* `ruff check app tests migrations`: All checks passed! (0 warnings, 0 errors).
* `mypy app`: Success: no issues found in 27 source files.
* `alembic check`: No new upgrade operations detected.
* `alembic upgrade head -> downgrade -1 -> upgrade head`: Success.

---

## 4. Контроль рамок скоупа (Strict Scope Audit)

В строгом соответствии с требованиями ТЗ и задачи TASK-004:
* **SMS Fallback / OTP:** НЕ реализовывался.
* **Второй профиль Wappi:** НЕ подключался.
* **Автоматический failover на SMS:** НЕ реализовывался.
* **Мониторинг профилей и алерты:** НЕ реализовывались.
* **Мобильное приложение (React Native / Expo):** НЕ затрагивалось.
* **Привязка карт покупателем (`/me/cards`):** НЕ реализовывалась (запланирована на TASK-005).
* **Административная панель:** НЕ реализовывалась.
* **Windows-агент и COM `V83.COMConnector`:** НЕ реализовывались.
* **Stage 2 (Google Wallet / Push):** НЕ реализовывались.
