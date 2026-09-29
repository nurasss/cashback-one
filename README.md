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

## 🚀 Текущее состояние (TASK-001)

### Реализовано в рамках TASK-001:
* Базовый монорепозиторий и `.gitignore`.
* FastAPI бэкенд с эндпоинтом `GET /health` (`{"status": "ok"}`).
* Схема данных Stage 1 в SQLAlchemy 2.0 (asyncio):
  * `businesses`: организации-тенанты, логотипы, цвета, префиксы штрихкодов.
  * `agents`: экземпляры агентов синхронизации, привязанные к бизнесу.
  * `cards`: зеркало карт лояльности с инвариантом `UNIQUE(business_id, barcode)`.
  * `users`: учетные записи покупателей.
  * `user_cards`: связь пользователя и карты с инвариантом `UNIQUE(card_id)` (одна карта не может принадлежать двум пользователям одновременно).
  * `transactions`: зеркало движений бонусов с инвариантом `UNIQUE(card_id, external_id)` для защиты от дублирования.
  * `login_challenges`: хранилище одноразовых кодов для обратной схемы WhatsApp.
  * `otp_codes`: хранилище SMS-кодов для резервного входа.
  * `consents`: фиксация согласий на обработку персональных данных (законодательство РК).
  * `devices`: регистрация токенов push-уведомлений (инфраструктура Stage 2).
  * `audit_log`: аудит административных действий.
* Поддержка точных типов `Numeric(18, 4)` / `Decimal` (полное отсутствие `float` в балансах и суммах).
* Асинхронные миграции Alembic (`0001_initial_schema.py`) с проверенным циклом `upgrade head` $\rightarrow$ `downgrade base` $\rightarrow$ `upgrade head`.
* Автоматические тесты (pytest, pytest-asyncio, httpx, sqlite+aiosqlite in-memory с включенными FK).

### Отложено до следующих задач:
* Авторизация через WhatsApp (обратная схема Wappi) и SMS OTP flow.
* Агентские эндпоинты `/agent/sync/*` и `/agent/heartbeat`.
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
