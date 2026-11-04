# Промпт исполнителю (Gemini): push-уведомления в облаке — задача A, 2026-11-04

**Упало или неожиданно — СТОП и сырой вывод; без самостоятельных исправлений; секреты и ПДн скрыть.**

Общайся и пиши отчёт по-русски.

## Контекст

Проект Cashback One, папка `/Users/nuras/Desktop/cashback-one`, облако `backend/` (FastAPI, PostgreSQL, alembic в `backend/migrations/versions/`, последняя миграция `0011_customer_avatar`). Новый курс описан в `docs/ROADMAP_PER_CLIENT_2026-11-04.md`, прочитай разделы 1, 2 и 5.

Для каждого клиента будет свой APK со своим пакетом Android. Все APK работают с одним облаком. Push-уведомления нужны прежде всего для кода подтверждения списания (задача B, отдельно). Эта задача — только инфраструктура push в облаке.

Что уже есть: таблица `devices` (модель `Device` в `backend/app/models/entities.py`: `user_id`, `push_token`, `platform`, `created_at`), нигде не используется. Отправки push нет. Образец устройства отправителя с режимами — `backend/app/services/whatsapp_sender.py` и настройки `whatsapp_provider_mode` в `backend/app/core/config.py`.

Приложение будет получать **нативный FCM-токен** (`expo-notifications`, `getDevicePushTokenAsync`), не Expo push token. Отправка — напрямую в Firebase Cloud Messaging HTTP v1. Проекта Firebase пока нет, владелец создаст его позже. Один проект Firebase будет содержать все Android-приложения клиентов.

## Задача

### 1. Модель и миграция

Миграция `0012_push_devices` (down_revision `0011_customer_avatar`), с рабочим downgrade. Дополни `devices`:

- `app_id` — пакет Android приложения (например `kz.cashbackone.mobile`), строка до 255, обязательна;
- `last_seen_at` — время последней регистрации;
- `disabled_at` — устройство отключено (выход, ошибка FCM «токен недействителен»), NULL — активно;
- уникальность `push_token`. Если тот же токен регистрирует другой пользователь, запись переходит к нему (телефон сменил владельца или аккаунт).

Если в production в `devices` есть строки, миграция не должна падать: проверь это рассуждением и тестом на PostgreSQL. Данные о существующих строках не выдумывай.

### 2. API покупателя

В роутере `/me` (`backend/app/api/customer_app.py` или новый файл рядом, подключить там же, где остальные):

- `PUT /me/push-token` — тело `{ "token": str, "platform": "android", "app_id": str }`. Создаёт или обновляет запись, снимает `disabled_at`, обновляет `last_seen_at`. Ответ 204.
- `DELETE /me/push-token` — тело `{ "token": str }`, отключает только запись этого пользователя. Ответ 204, даже если записи нет.

Проверки: `platform` только `android`; токен 1–4096 символов без пробелов; `app_id` по шаблону пакета Android (`^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$`). Лимит частоты регистрации на пользователя через существующий `RateLimiter`. Токен не писать в логи и в аудит целиком.

### 3. Отправитель push

`backend/app/services/push_sender.py` по образцу `whatsapp_sender.py`:

- протокол `PushSender` с `disabled: bool` и `async send(token, title, body, data) -> PushResult`, где результат различает «доставлено в FCM», «токен недействителен» (FCM `UNREGISTERED` или `INVALID_ARGUMENT` про токен), «временная ошибка»;
- режимы настройкой `PUSH_PROVIDER_MODE`: `disabled` (по умолчанию), `fake` (только `APP_ENV=test`, запоминает сообщения), `log` (только локальная разработка, без текста `data` целиком), `fcm`;
- `fcm`: настройки `FCM_PROJECT_ID` и `FCM_SERVICE_ACCOUNT_FILE` (путь к JSON сервисного аккаунта на сервере). Токен доступа OAuth2 получать подписью JWT RS256 сервисного аккаунта (уже есть `PyJWT` и `cryptography`), кешировать до истечения. **Новые зависимости не добавлять**; если без них никак — СТОП и объясни;
- уведомление: `notification.title`, `notification.body`, `data` (строки), `android.priority = high`, канал Android `default`. Таймаут как у WhatsApp;
- в режиме `fcm` без файла или проекта — при старте понятная ошибка конфигурации, без вывода содержимого файла.

### 4. Сервис уведомлений

`backend/app/services/push_service.py`:

- `has_active_device(session, user_id) -> bool`;
- `send_to_user(session, sender, user_id, title, body, data) -> int` — отправляет на все активные устройства пользователя, возвращает число принятых FCM. Недействительный токен помечает `disabled_at`. Временная ошибка — запись не отключать.

К рассылкам кабинета и к кодам списания в этой задаче **не подключать**: это задача B.

### 5. Документы

Дополни `docs/CUSTOMER_API.md` двумя новыми адресами. В `backend/.env.example` (если есть) — новые настройки с пустыми значениями. Добавь короткую инструкцию `docs/FIREBASE_SETUP.md` для владельца: создать проект Firebase, добавить Android-приложение с пакетом клиента, где взять `google-services.json` (нужен приложению) и JSON сервисного аккаунта (нужен серверу), куда положить файл на VPS, права `600`, никому не пересылать. Ничего не создавать в Firebase самому.

## Тесты

- регистрация, повторная регистрация, смена владельца токена, удаление, проверка полей, лимит;
- `send_to_user`: несколько устройств, недействительный токен отключается, временная ошибка не отключает, отключённые не получают;
- `fcm`-отправитель с подменённым HTTP (без настоящего Firebase): формат запроса v1, заголовок авторизации, кеш токена доступа, разбор ошибок;
- миграция вверх и вниз на временном PostgreSQL 16.

## Что не менять

Коды списания и WhatsApp (`redemption_service.py`, `whatsapp_sender.py`), вход, агент, `admin/`, `mobile/`. Не деплоить на VPS, не менять `.env` на сервере, не создавать проект Firebase, без commit и push.

## Проверки

Из `backend/`, до правок и после:

```bash
.venv/bin/pytest -q
```

```bash
.venv/bin/ruff check .
```

```bash
.venv/bin/mypy app
```

Если путь к окружению другой, сверься с `docs/` и укажи фактическую команду. До правок ожидается 382 passed (могут быть skipped). Упало до правок — СТОП.

Тесты PostgreSQL: временный PostgreSQL 16, `POSTGRES_TEST_URL`, `-k postgres`; для `alembic` — `APP_ENV=test`, для `pg_ctl` — `LC_ALL=en_US.UTF-8`. Проверь `alembic upgrade head`, `downgrade -1`, снова `upgrade head`.

Затем `git diff --stat` и `git diff --check`.

## Отчёт

`reports/BACKEND_PUSH_2026-11-04.md`: изменённые файлы, сырой вывод проверок до и после, итоговые числа тестов, описание API и настроек, что нужно владельцу для включения (Firebase, файл на VPS, `PUSH_PROVIDER_MODE=fcm`), всё непроверенное (настоящая доставка в FCM не проверялась).
