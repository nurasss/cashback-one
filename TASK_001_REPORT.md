# TASK-001 Report

**Дата отчета:** 29 сентября 2026 г.  
**Задача:** TASK-001: Project Foundation + Backend Data Model  
**Исполнитель:** Senior Software Architect / Backend Engineer / QA Auditor  
**Нормативный документ:** `TZ_loyalty_app_v1.1`  
**Базовый аудит:** `BASELINE_AUDIT.md`

---

## 1. Implemented

В рамках задачи TASK-001 создан чистый, модульный фундамент проекта лояльности без избыточных абстракций и без реализации незапрошенного функционала будущих этапов:

1. **Инициализация Git и структура монорепозитория:**
   - Инициализирован git-репозиторий на ветке `main`.
   - Создан `.gitignore`, исключающий виртуальные окружения, секреты, базы данных, кэши и артефакты сборки.
   - Создан `.env.example` с безопасными базовыми параметрами.
   - Развернута базовая структура монорепозитория: `backend/`, `agent/`, `mobile/`, `admin/`, `docs/`.
   - В директориях `agent/`, `mobile/`, `admin/` созданы официальные placeholder README с пометкой `Implementation deferred to later task.` (без создания фиктивного кода).

2. **Backend API (FastAPI):**
   - Создан модуль приложения `app.main:app` с автоматической генерацией OpenAPI документации (`/docs`, `/redoc`).
   - Реализован обязательный эндпоинт `GET /health`, возвращающий `{"status": "ok"}`.
   - Настроена конфигурация `app.core.config.Settings` на базе `pydantic-settings` с загрузкой из переменных окружения / `.env`.

3. **Модель данных Stage 1 (SQLAlchemy 2.0 Async):**
   - Реализованы 11 таблиц, строго соответствующих разделу 6 ТЗ:
     1. `businesses`: организации-тенанты (название, логотип, брендовые цвета, префиксы штрихкодов, статус, временные метки). Ограничение `UNIQUE(name)` намеренно не добавлено согласно требованию ТЗ.
     2. `agents`: агенты синхронизации торговых точек (FK на `businesses.id ON DELETE CASCADE`, хэш API-ключа, версия, статус, время последней активности).
     3. `cards`: зеркало карт лояльности ONE.
     4. `users`: покупатели мобильного приложения (телефон, язык, время создания, дата мягкого удаления).
     5. `user_cards`: связь пользователя с картой.
     6. `transactions`: зеркало движений бонусов (начисления, списания, корректировки, чек, магазин, дата-время).
     7. `login_challenges`: одноразовые коды для обратной схемы WhatsApp.
     8. `otp_codes`: SMS-коды резервной аутентификации.
     9. `consents`: фиксация согласий на обработку ПД согласно законодательству РК.
     10. `devices`: регистрация токенов push-уведомлений (инфраструктура Stage 2).
     11. `audit_log`: журнал действий администраторов с сохранением состояния до и после изменений.
   - Во всех полях балансов и сумм (`balance`, `amount`, `balance_after`) используется строго тип `Numeric(18, 4)` / `Decimal`. Использование `float` полностью исключено.

4. **Миграции Alembic:**
   - Настроен `alembic.ini` и асинхронный `migrations/env.py` (с поддержкой `render_as_batch=True` для переносимости между PostgreSQL и SQLite).
   - Создана миграция `0001_initial_schema.py`.
   - Проверен полный цикл применения и отката: `upgrade head` $\rightarrow$ `downgrade base` $\rightarrow$ `upgrade head`.

5. **Документация:**
   - `README.md`: обзор проекта, запуск бэкенда, миграций и тестов. Зафиксирован принцип: `POSCENTER ONE is the source of truth for loyalty balances and transactions` и статус Stage 0.
   - `docs/ARCHITECTURE.md`: высокоуровневая архитектурная схема и data flow.
   - `docs/STAGE0_PENDING.md`: чек-лист исследования реальной информационной базы 1С ONE.

---

## 2. Repository Structure

```text
cashback-one/
├── .env.example
├── .gitignore
├── BASELINE_AUDIT.md
├── README.md
├── TASK_001_REPORT.md
├── TZ_loyalty_app_v1.1.docx
├── admin/
│   └── README.md                  # Placeholder: Implementation deferred to later task.
├── agent/
│   └── README.md                  # Placeholder: Implementation deferred to later task.
├── mobile/
│   └── README.md                  # Placeholder: Implementation deferred to later task.
├── docs/
│   ├── ARCHITECTURE.md            # Data flow & core architectural invariant
│   └── STAGE0_PENDING.md          # 1C ONE discovery checklist
└── backend/
    ├── alembic.ini                # Alembic configuration
    ├── pyproject.toml             # Python project dependencies & tool configs
    ├── requirements.txt           # Python requirements
    ├── app/
    │   ├── __init__.py
    │   ├── main.py                # FastAPI entrypoint
    │   ├── api/
    │   │   ├── __init__.py
    │   │   └── health.py          # GET /health
    │   ├── core/
    │   │   ├── __init__.py
    │   │   ├── config.py          # Pydantic Settings
    │   │   └── time.py            # UTC datetime helper
    │   ├── db/
    │   │   ├── __init__.py
    │   │   ├── base.py            # DeclarativeBase, UUIDPrimaryKey, Timestamps
    │   │   └── session.py         # Async engine & sessionmaker
    │   └── models/
    │       ├── __init__.py        # Models re-export
    │       └── entities.py        # 11 Stage 1 SQLAlchemy models
    ├── migrations/
    │   ├── env.py                 # Async Alembic runner
    │   ├── script.py.mako
    │   └── versions/
    │       └── 0001_initial_schema.py
    └── tests/
        ├── __init__.py
        ├── conftest.py            # SQLite async in-memory fixtures with PRAGMA foreign_keys=ON
        ├── test_constraints.py    # Multi-tenancy, uniqueness, FK, and Decimal tests
        └── test_health.py         # GET /health verification
```

---

## 3. Database Schema

| Таблица | Первичный ключ | Внешние ключи | Индексы | Назначение |
|---|---|---|---|---|
| `businesses` | `id (UUID)` | — | — | Тенант-организация (POSCENTER ONE) |
| `agents` | `id (UUID)` | `business_id -> businesses.id (CASCADE)` | `ix_agents_business_id`, `ix_agents_key_hash` | Сервис синхронизации торговой точки |
| `cards` | `id (UUID)` | `business_id -> businesses.id (CASCADE)` | `ix_cards_business_id`, `ix_cards_barcode`, `ix_cards_phone`, `ix_cards_updated_at` | Зеркало бонусных карт |
| `users` | `id (UUID)` | — | `ix_users_phone` | Учетные записи покупателей |
| `user_cards` | `id (UUID)` | `user_id -> users.id (CASCADE)`, `card_id -> cards.id (CASCADE)` | `ix_user_cards_user_id` | Привязка карты к пользователю |
| `transactions` | `id (UUID)` | `card_id -> cards.id (CASCADE)` | `ix_transactions_card_id`, `ix_transactions_external_id`, `ix_transactions_occurred_at` | Зеркало операций по карте |
| `login_challenges` | `id (UUID)` | — | `ix_login_challenges_code_hash`, `ix_login_challenges_device_id`, `ix_login_challenges_expires_at` | Сессии входа через WhatsApp |
| `otp_codes` | `id (UUID)` | — | `ix_otp_codes_phone`, `ix_otp_codes_expires_at` | Резервные SMS OTP коды |
| `consents` | `id (UUID)` | `user_id -> users.id (CASCADE)` | `ix_consents_user_id` | Согласия на обработку ПД |
| `devices` | `id (UUID)` | `user_id -> users.id (CASCADE)` | `ix_devices_user_id` | Push-токены (Stage 2) |
| `audit_log` | `id (UUID)` | — | `ix_audit_log_created_at`, `ix_audit_log_entity` | Аудит действий администраторов |

---

## 4. Constraints & Invariants

В соответствии с требованиями ТЗ на уровне базы данных реализованы и протестированы критические инварианты:

1. **Multi-Tenancy изоляция штрихкодов карт:**
   - Ограничение: `UniqueConstraint("business_id", "barcode", name="uq_cards_business_barcode")`
   - Карты разных бизнесов могут иметь одинаковый штрихкод (например, `1234567890123`), но внутри одного бизнеса дублирование штрихкода блокируется БД.
2. **Исключительное владение картой (Single Ownership):**
   - Ограничение: `UniqueConstraint("card_id", name="uq_user_cards_card_id")`
   - Одна карта не может одновременно принадлежать двум пользователям. Попытка привязать занятую карту вызывает `IntegrityError` на уровне СУБД.
3. **Идемпотентность движений бонусов:**
   - Ограничение: `UniqueConstraint("card_id", "external_id", name="uq_transactions_card_external")`
   - Защита от дублирования финансовых и бонусных движений при повторных отправках пакетов агентом.
4. **Каскадная целостность:**
   - Удаление бизнеса каскадно удаляет его карты и агентов (`ON DELETE CASCADE`).
   - Удаление пользователя каскадно удаляет его привязки карт, согласия и токены устройств.

---

## 5. Migrations

- **Файл начальной миграции:** `migrations/versions/0001_initial_schema.py`.
- **Проверка на чистой БД:**
  ```bash
  alembic upgrade head
  ```
  *Результат:* `Running upgrade -> 0001_initial_schema, Initial Stage 1 schema` (Успешно, код 0).
- **Проверка отката и повторного применения:**
  ```bash
  alembic downgrade base && alembic upgrade head
  ```
  *Результат:* Откат всех 11 таблиц и успешное повторное создание (код 0).

---

## 6. Tests

Для верификации создан набор асинхронных тестов pytest с использованием in-memory SQLite и принудительным включением проверки внешних ключей (`PRAGMA foreign_keys = ON`).

Покрытые сценарии:
1. `test_health_check`: проверка ответа `GET /health` (`200 OK`, `{"status": "ok"}`).
2. `test_multi_tenant_cards_unique_constraint`: одновременное существование одинаковых штрихкодов в разных бизнесах и блокировка дубликата в одном бизнесе.
3. `test_transaction_unique_constraint`: проверка уникальности `(card_id, external_id)`.
4. `test_user_card_single_owner_constraint`: блокировка попытки повторной привязки карты ко второму пользователю.
5. `test_foreign_key_constraints`: блокировка создания карты с несуществующим `business_id` и проверка каскадного удаления.
6. `test_money_and_balance_numeric_precision`: проверка сохранения точности `Decimal` (4 знака после запятой) без искажений `float`.
7. `test_auxiliary_stage1_models_creation`: проверка создания записей `login_challenges`, `otp_codes`, `consents`, `devices`, `audit_log`.

---

## 7. Commands Executed

1. `git init` — инициализация репозитория.
2. `alembic upgrade head` — накат миграции.
3. `alembic downgrade base && alembic upgrade head` — проверка отката и наката.
4. `pytest -v` — запуск набора тестов.
5. `ruff check --fix app tests && ruff check app tests` — проверка стиля кода и импортов.
6. `mypy app` — строгая статическая проверка типов.
7. `git status` — статус рабочего дерева.

---

## 8. Results

- **Миграции Alembic:** `PASS` (чистый накат, откат, повторный накат).
- **Тесты Pytest:** `7 passed in 2.75s` (100% прохождение).
- **Линтер Ruff:** `All checks passed!` (0 ошибок).
- **Проверка типов Mypy:** `Success: no issues found in 12 source files` (strict mode).

---

## 9. Deviations

Отклонений от ТЗ `TZ_loyalty_app_v1.1` нет.
- Бизнес-логика авторизации, агента и мобильного приложения не реализовывалась сверх рамок TASK-001 в строгом соответствии с инструкциями.

---

## 10. Known Limitations

1. **Stage 0 не завершен:** имена метаданных 1С ONE остаются неопределенными до проведения discovery на рабочей копии базы клиента.
2. **Внешние шлюзы:** интеграция с Wappi (WhatsApp) и SMS-провайдером не настроена (запланирована на следующие задачи).
3. **Мобильное приложение и агент:** код для Windows-службы и Expo-клиента на текущем этапе отсутствует.

---

## 11. Git Status

- **Текущая ветка:** `main`
- **Рабочее дерево:** чистое, файлы подготовлены к коммиту.
- **Секреты:** отсутствуют (файлы `.env`, `.pem`, `*.db` исключены через `.gitignore`).

---

## 12. Commit / HEAD

Подготовлен первоначальный коммит:
`feat: initialize repository foundation and Stage 1 backend data model (TASK-001)`
