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

## 🚀 Текущее состояние (TASK-001 + TASK-002)

### Реализовано в рамках TASK-001 (Фундамент и модель данных):
* Базовый монорепозиторий и `.gitignore`.
* FastAPI бэкенд с эндпоинтом `GET /health` (`{"status": "ok"}`).
* Схема данных Stage 1 в SQLAlchemy 2.0 (asyncio):
  * `businesses`, `agents`, `cards`, `users`, `user_cards`, `transactions`, `login_challenges`, `otp_codes`, `consents`, `devices`, `audit_log`.
* Поддержка точных типов `Numeric(18, 4)` / `Decimal` (полное отсутствие `float` в балансах и суммах).
* Асинхронные миграции Alembic (`0001_initial_schema.py`) с проверенным циклом отката и наката.

### Реализовано в рамках TASK-002 (Agent Authentication + Cloud Sync API):
* **Аутентификация агентов:**
  * Заголовок `X-Agent-Key` (или `Authorization: Bearer <key>`).
  * Безопасное хранение ключей в БД в виде SHA-256 хэшей (открытый ключ никогда не сохраняется).
  * Сервисы выпуска, ротации и отзыва ключей (`backend/app/services/agent_auth.py`).
  * Строгая изоляция тенантов: `business_id` определяется исключительно по аутентифицированному агенту.
* **Нормализация телефонов РК/СНГ:**
  * Приведение форматов `8701...`, `7701...`, `+7 701...` к каноническому E.164 `+7701...`.
  * Валидация недопустимых символов и длины.
* **Агентские эндпоинты Cloud Sync API (`backend/app/api/agent_sync.py`):**
  * `POST /agent/sync/cards`: батчевый upsert карт (лимит 500), защита от устаревших данных по `updated_at`, нормализация номеров телефонов.
  * `POST /agent/sync/transactions`: батчевая вставка транзакций (лимит 1000), детерминированная идемпотентность по `(card_id, external_id)`, валидация принадлежности карты тенанту агента.
  * `POST /agent/heartbeat`: фиксация активности агента, серверное время `last_seen_at = utcnow()`, обновление `version`, `last_sync_at`, `last_error`.
* **Единый протокол ошибок:**
  * Структурированные ответы `{ "error": { "code": "...", "message": "...", "details": ... } }`.
* **Спецификация API:**
  * Полный контракт обмена ONE Agent → Cloud Backend задокументирован в [`docs/AGENT_API.md`](docs/AGENT_API.md).
* **Миграции Alembic:**
  * `0002_agent_heartbeat_fields.py`: добавление полей `last_sync_at` и `last_error` в таблицу `agents`.
* **Тестирование:**
  * Полный набор тестов (`pytest`, 29 тестов), включая интеграционные тесты на PostgreSQL 16.

### Отложено до следующих задач:
* Авторизация покупателей через WhatsApp (обратная схема Wappi) и SMS OTP flow (TASK-003).
* Привязка карт покупателем (`/me/cards`, QR/штрихкод, SMS OTP) (TASK-004).
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
