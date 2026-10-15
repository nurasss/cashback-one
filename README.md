# POSCENTER Loyalty (cashback-one)

Платформа лояльности для магазинов на **POSCENTER ONE (1С:Предприятие 8.3)**: покупатель видит бонусные карты, баланс, QR/штрихкод для кассы и историю операций в мобильном приложении.

> **Главный принцип:** POSCENTER ONE — источник истины по балансам и операциям. Облако хранит зеркало данных и ничего не начисляет и не списывает сам.

## Статус

| Компонент | Папка | Состояние |
|---|---|---|
| Облачный API (FastAPI, PostgreSQL, Redis) | `backend/` | Готов. Тесты: 334 |
| Админ-панель (React, Vite) | `admin/` | Готова. Тесты: 46 |
| Мобильное приложение (Expo / React Native) | `mobile/` | Готово. Тесты: 90 |
| Агент синхронизации (Windows-служба) | `agent/` | Готов, кроме чтения 1С. Тесты: 76 |
| Деплой (Docker, nginx), CI, e2e | `deploy/`, `.github/`, `e2e/` | Готовы. e2e: 32 |

**Единственный блокер до реального запуска — Stage 0.** Имена объектов 1С (справочник карт, поля штрихкода, телефона, ФИО, регистр бонусов, идентификатор операции) неизвестны, пока их не выяснят на копии базы клиента под Windows. До этого агент отвечает `OneMappingNotConfiguredError` и не читает реальные данные. Инструкция: [docs/STAGE0_WINDOWS_RUNBOOK.md](docs/STAGE0_WINDOWS_RUNBOOK.md), чек-лист: [docs/STAGE0_PENDING.md](docs/STAGE0_PENDING.md).

Также не подтверждено на живых сервисах: отправка сообщений через Wappi (`docs/WAPPI_SEND_CONTRACT.md`) и имя заголовка вебхука Wappi; SMS-провайдер не подключён. Вызовы кассы для динамического QR и кода списания (`docs/AGENT_API.md`, 2.5–2.6) нужно встроить в 1С после Stage 0.

## Как это работает

```text
POSCENTER ONE (1С) ──COM, только чтение──▶ Агент (Windows) ──HTTPS push──▶ Облако (FastAPI + PostgreSQL + Redis)
                                                                              │
                                                       ┌──────────────────────┴──────┐
                                                  Мобильное приложение          Админ-панель
```

- **Вход покупателя:** одноразовый 6-значный код приходит клиенту в WhatsApp; сессия запоминается на 14 дней.
- **Карты:** при открытии кошелька карты с телефоном покупателя привязываются автоматически (во всех подключённых бизнесах); можно привязать вручную по штрихкоду.
- **Многотенантность:** каждый агент привязан к одному бизнесу и видит только его данные.

## Быстрый старт (разработка)

Нужны Python 3.11+, PostgreSQL 16, Redis 7, Node 20+.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.lock -r agent/requirements.lock   # зафиксированные версии (Python 3.11+)
cp .env.example backend/.env        # заполнить секреты (минимум 32 символа)
cd backend && alembic upgrade head && uvicorn app.main:app --reload
```

Первого администратора создаёт `python -m app.cli.create_admin` (см. [admin/README.md](admin/README.md)). Админка: `cd admin && npm ci && npm run dev`. Приложение: [mobile/README.md](mobile/README.md).

## Проверки

```bash
# Сервер (с PostgreSQL тесты на конкурентность включаются через POSTGRES_TEST_URL)
cd backend && POSTGRES_TEST_URL=postgresql+asyncpg://localhost:5432/poscenter_loyalty_test \
  REDIS_URL=redis://127.0.0.1:6379/15 APP_ENV=test pytest && ruff check . && mypy app
# Агент
cd agent && pytest
# Сквозной сценарий агент → сервер → кошелёк (БД cashback_e2e_*, Redis db 14)
bash scripts/run_pre_one_e2e.sh
# Админка и мобильное приложение
cd admin && npm test && npm run build
cd mobile && npm test
```

CI (`.github/workflows/ci.yml`) выполняет те же проверки.

## Деплой и эксплуатация

- [docs/PRODUCTION_DEPLOYMENT.md](docs/PRODUCTION_DEPLOYMENT.md) — Docker Compose, nginx, переменные окружения
- [docs/OPERATIONS_RUNBOOK.md](docs/OPERATIONS_RUNBOOK.md), [docs/BACKUP_RESTORE.md](docs/BACKUP_RESTORE.md)
- [docs/PRE_ONE_E2E.md](docs/PRE_ONE_E2E.md) — как устроен e2e

## Документация

| Тема | Файл |
|---|---|
| Архитектура | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/AGENT_ARCHITECTURE.md](docs/AGENT_ARCHITECTURE.md) |
| Вход покупателей | [docs/AUTH.md](docs/AUTH.md), [docs/WAPPI_WEBHOOK_CONTRACT.md](docs/WAPPI_WEBHOOK_CONTRACT.md), [docs/SMS_PROVIDER_CONTRACT.md](docs/SMS_PROVIDER_CONTRACT.md) |
| API | [docs/CUSTOMER_API.md](docs/CUSTOMER_API.md), [docs/AGENT_API.md](docs/AGENT_API.md), [docs/ADMIN_API.md](docs/ADMIN_API.md) |
| Stage 0 (1С) | [docs/ONE_STAGE0_REQUIRED.md](docs/ONE_STAGE0_REQUIRED.md), [docs/STAGE0_PENDING.md](docs/STAGE0_PENDING.md), [docs/STAGE0_WINDOWS_RUNBOOK.md](docs/STAGE0_WINDOWS_RUNBOOK.md) |
| Аудит проекта (2026-10-15) | [docs/AUDIT_2026-10-15.md](docs/AUDIT_2026-10-15.md) |
| Техническое задание | [docs/TZ_loyalty_app_v1.1.docx](docs/TZ_loyalty_app_v1.1.docx) |
| История задач (отчёты TASK-001…013) | [docs/history/](docs/history/) |

## Известные ограничения

- Фишинг в WhatsApp-входе (злоумышленник просит жертву «отправить код») закрывается только предупреждением в ответном сообщении, оно зависит от настройки Wappi.
- Если в 1С у карты меняется телефон, облако при следующей синхронизации отвязывает её от прежнего владельца, чтобы новый мог привязать карту.
- Lock-файлы Python пересобираются командой `uv pip compile <pyproject> --extra dev --universal --python-version 3.11 -o <файл>.lock`; у мобильного приложения `npm audit` показывает уязвимости только в инструментах сборки и тестов.
