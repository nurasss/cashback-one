# POSCENTER Loyalty (cashback-one)

Мобильное приложение и облачная платформа лояльности (кешбэк, бонусный баланс, QR-карта для кассы и история операций) с интеграцией в **POSCENTER ONE** (1С:Предприятие 8.3).

---

## 📌 Главный архитектурный принцип (Core Invariant)

> **POSCENTER ONE is the source of truth for loyalty balances and transactions.**
>
> Облачный бэкенд хранит зеркало данных. Мобильное приложение только отображает актуальное состояние карт, балансы и историю операций. Начисление, списание и корректировка бонусов производятся на кассе в POSCENTER ONE. Бэкенд не является автономным бонусным движком.

---

## ⚠️ Статус интеграции Stage 0

> **Stage 0 metadata mapping for POSCENTER ONE is not yet finalized.**
>
> Точные имена объектов 1С (справочник карт, поля штрихкода/телефона/ФИО, регистр накопления бонусов, реквизиты движений) будут зафиксированы после проведения discovery на реальной копии информационной базы клиента (см. [`docs/STAGE0_PENDING.md`](docs/STAGE0_PENDING.md)).

---

## 🏗 Архитектурные компоненты

```text
       POSCENTER ONE (1C 8.3)
                 │
                 ▼ (COM V83.COMConnector, read-only)
             ONE Agent (Windows Service) [agent/]
                 │
                 ▼ (Outbound HTTPS push: /agent/sync/*, /agent/heartbeat)
           Cloud Backend (FastAPI, PostgreSQL, Redis) [backend/]
                 │
        ┌────────┴────────┐
        ▼                 ▼
   Mobile App        Admin Panel
(React Native/Expo)   (Web UI)
    [mobile/]         [admin/]
```

### Структура монорепозитория

* `backend/` — Cloud API на Python / FastAPI / SQLAlchemy / Alembic / PostgreSQL.
* `agent/` — Windows-агент COM-синхронизации (реализация запланирована на последующие этапы).
* `mobile/` — клиентское мобильное приложение на React Native / Expo (реализация запланирована на последующие этапы).
* `admin/` — административная веб-панель (реализация запланирована на последующие этапы).
* `docs/` — архитектурная документация и чек-листы Stage 0.

---

## 🚀 Текущее состояние (TASK-001 + TASK-002 + TASK-003)

### Реализовано в рамках TASK-001 (Фундамент и модель данных):
* Базовый монорепозиторий и `.gitignore`.
* FastAPI бэкенд с эндпоинтом `GET /health` (`{"status": "ok"}`).
* Схема данных Stage 1 в SQLAlchemy 2.0 (asyncio):
  * `businesses`, `agents`, `cards`, `users`, `user_cards`, `transactions`, `login_challenges`, `otp_codes`, `consents`, `devices`, `audit_log`.
* Поддержка точных типов `Numeric(18, 4)` / `Decimal` (полное отсутствие `float` в балансах и суммах).
* Асинхронные миграции Alembic (`0001_initial_schema.py`) с проверенным циклом отката и наката.

### Реализовано в рамках TASK-002 (Agent Authentication + Cloud Sync API):
* **Отказоустойчивая конфигурация (Fail-Fast):**
  * `DATABASE_URL` обязателен через окружение / `.env`. Отсутствуют неявные fallback-значения на localhost или SQLite в dev/prod.
* **Аутентификация агентов:**
  * Строго фиксированный заголовок `X-Agent-Key: <key>` (Bearer заголовок исключен).
  * Безопасное хранение ключей в БД в виде SHA-256 хэшей (открытый ключ никогда не сохраняется).
  * Сервисы выпуска, ротации и отзыва ключей (`backend/app/services/agent_auth.py`).
  * Строгая изоляция тенантов: `business_id` определяется исключительно по аутентифицированному агенту.
* **Конкурентность и атомарность на уровне БД:**
  * Захват транзакционной блокировки уровня тенанта (`SELECT id FROM businesses WHERE id = :business_id FOR UPDATE`) при пакетной синхронизации.
  * Гарантия защиты от дублирования карт и транзакций при параллельных HTTP-запросах.
  * Конкурентная защита от устаревших данных (`stale data protection`): старый снимок карты никогда не перезаписывает новый.
  * Атомарность пакета транзакций: при наличии неизвестной карты запрос отклоняется (`422 UNKNOWN_CARD_FOR_TRANSACTION`), ни одна запись из пакета не сохраняется.
* **Агентские эндпоинты Cloud Sync API (`backend/app/api/agent_sync.py`):**
  * `POST /agent/sync/cards`: батчевый upsert карт (лимит 500).
  * `POST /agent/sync/transactions`: батчевая выгрузка транзакций (лимит 1000) с идемпотентностью `(card_id, external_id)`.
  * `POST /agent/heartbeat`: фиксация активности агента, серверное время `last_seen_at = utcnow()`.
* **Миграции Alembic:**
  * `0002_agent_heartbeat_fields.py`: добавление полей `last_sync_at` и `last_error` в таблицу `agents`.

### Реализовано в рамках TASK-003 (Customer Authentication Core):
* **Обратная WhatsApp-аутентификация (Reverse Flow):**
  * `POST /auth/challenge`: генерация криптостойкого 8-значного кода (алфавит без неоднозначных символов), формирование ссылки `wa.me`, фиксация TTL 3 минуты.
  * Хранение кодов только в виде HMAC-SHA256 digests (`login_challenges.code_hash`).
  * Привязка к устройству (`device_id`) и проверка через заголовок `X-Device-Id`.
* **Rate Limiting:**
  * Ограничение запросов на устройство и IP-адрес через Redis (`RedisRateLimiter`) с детерминированным in-memory бекендом для тестов (`InMemoryRateLimiter`).
* **Доменный сервис подтверждения:**
  * Provider-independent сервис `confirm_login_challenge(session, code, sender_phone)` для обработки входящих сообщений от провайдера с атомарной защитой от race condition.
* **Идентификация покупателей и модель сессий:**
  * Инвариант `one normalized phone -> one User` с уникальным ограничением `uq_users_phone`.
  * Таблица `auth_sessions` с безопасным хранением refresh-токенов в виде SHA-256 хэшей.
  * Access JWT (HS256, 15 минут TTL) со стандартными клеймами `sub`, `sid`, `typ=access`.
* **Эндпоинты работы с токенами:**
  * `GET /auth/challenge/{id}`: однократный обмен подтвержденного challenge на сессию и токены.
  * `POST /auth/refresh`: ротация refresh-токенов с защитой от одновременных повторных запросов.
  * `POST /auth/logout`: отзыв текущей сессии (`revoked_at != null`).
* **Миграции Alembic:**
  * `0003_customer_auth_core.py`: создание таблицы `auth_sessions`, добавление `uq_users_phone`, расширение `login_challenges`.
* **Тестирование:**
  * 73 автоматических теста (100% passing), включая специализированные конкурентные тесты на PostgreSQL 16.

### Отложено до следующих задач:
* Адаптер вебхуков Wappi (`POST /webhooks/wappi`) (TASK-004).
* Привязка карт покупателем (`/me/cards`, QR/штрихкод, SMS OTP) (TASK-005).
* Резервный SMS OTP flow.
* Windows-служба агента и COM `V83.COMConnector`.
* Мобильное приложение Expo/React Native.
* Административная панель.
* Google Wallet / Apple Wallet / Push-уведомления (Stage 2).


---

## 🛠 Локальный запуск и разработка

### 1. Настройка окружения

```bash
cd backend
cp ../.env.example .env
```

### 2. Применение миграций

```bash
alembic upgrade head
```

Проверка отката и наката:
```bash
alembic downgrade base
alembic upgrade head
```

### 3. Запуск сервера разработки

```bash
uvicorn app.main:app --reload --port 8000
```

Проверка эндпоинта:
```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

Документация Swagger UI доступна по адресу: `http://localhost:8000/docs`.

### 4. Запуск автоматических тестов

```bash
pytest -v
```

Запуск линтера:
```bash
ruff check app tests
```

Запуск проверки типов:
```bash
mypy app
```
