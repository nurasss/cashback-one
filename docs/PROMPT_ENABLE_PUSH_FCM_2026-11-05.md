# Промпт исполнителю (Gemini): включить push через Firebase на production — 2026-11-05

**Упало или неожиданно — СТОП и сырой вывод; без самостоятельных исправлений; секреты и ПДн скрыть.**

Общайся и пиши отчёт по-русски.

## Контекст

Папка `/Users/nuras/Desktop/cashback-one`. Облако нового курса выкачено 2026-11-04 (`reports/DEPLOY_NEW_COURSE_2026-11-04.md`), push выключен (`PUSH_PROVIDER_MODE` по умолчанию `disabled`). Код отправки: `backend/app/services/push_sender.py` (FCM HTTP v1, JWT RS256 сервисного аккаунта), настройки в `backend/app/core/config.py`: `PUSH_PROVIDER_MODE`, `FCM_PROJECT_ID`, `FCM_SERVICE_ACCOUNT_FILE`. Инструкция `docs/FIREBASE_SETUP.md`.

Файл сервисного аккаунта Firebase на Mac: `~/.cashback-one-keys/firebase-service-account.json` (права 600). Проект `cashback-one-loyalty`.

Production: VPS `kz-vps`, `/opt/cashback-one`, контейнер `cashback-backend`.

## Запреты

- **Содержимое файла сервисного аккаунта не выводить ни целиком, ни частями** (`cat`, `head`, `jq`, `grep` по ключу и т. п.). Разрешено: размер, права, SHA-256, проверка, что JSON разбирается и `type == "service_account"`, `project_id == "cashback-one-loyalty"` — выводить только `true/false`.
- `.env` не печатать. Изменения в `.env` показывать только именами переменных и новыми значениями `PUSH_PROVIDER_MODE` и `FCM_PROJECT_ID`; значение `FCM_SERVICE_ACCOUNT_FILE` — путь, его можно.
- Не отправлять настоящие уведомления покупателям. Не создавать ключи касс, магазины, записи в базе.
- Миграции, код, кабинет, сайт, агент и 1С не трогать. Без commit/push.

## Шаги

1. **Mac.** Размер и SHA-256 файла, права `600`, проверка JSON (`true/false` по трём условиям выше). `git status --short`: файла нет в репозитории.
2. **VPS, до изменений.** `docker ps` для `cashback-*`, `/health/ready`, текущий образ backend, от какого пользователя работает процесс в контейнере (`docker exec cashback-backend id`), как `.env` подключается к контейнеру (по `compose.yml`, имена ключей, без значений). Выведи только имена переменных `PUSH_*` и `FCM_*` в `.env`, если они есть.
3. **Копии** в `/opt/cashback-one/backups/push-<UTC>/`: `env.bak` (600, SHA-256 = `.env`), копия `compose.yml` (или того файла compose, что используется). Выведи пути и хеши.
4. **Файл на VPS.** Каталог `/opt/cashback-one/secrets/` (700, если нет — создать). Скопируй файл через `scp` как `firebase-service-account.json`. SHA-256 на VPS = на Mac. Права: читать может только пользователь процесса в контейнере (если процесс не root — `chown` на его uid и `600`; иначе `600` root). Каталог `secrets/` не должен попасть в образ, в `backend-src.tgz` и в git.
5. **Подключение к контейнеру.** В compose для сервиса `backend` добавь монтирование **только для чтения**: `/opt/cashback-one/secrets/firebase-service-account.json:/run/secrets/firebase-service-account.json:ro`. Покажи `diff` compose-файла. Сервис миграции не трогать.
6. **`.env`**: `PUSH_PROVIDER_MODE=fcm`, `FCM_PROJECT_ID=cashback-one-loyalty`, `FCM_SERVICE_ACCOUNT_FILE=/run/secrets/firebase-service-account.json`. Остальные строки побайтно прежние — покажи, что изменились/добавились только эти три (`diff` с маскировкой: выводи только имена изменённых переменных).
7. **Перезапуск** только backend: `docker compose up -d --no-build --force-recreate backend`. Дождись `healthy`. Журнал без ошибок конфигурации. Если backend не стартовал — сразу верни `env.bak` и compose из копий, перезапусти, СТОП.
8. **Проверка доступа к Firebase без отправки покупателю.** Внутри контейнера одноразовым скриптом (не сохранять в образ и репозиторий):
   - получить токен доступа через существующий `FcmPushSender` — вывести только `ok` и время жизни;
   - отправить запрос FCM v1 с `"validate_only": true` на заведомо несуществующий токен (например `invalid-token-for-validation`) — вывести только HTTP-статус и `error.status`/`errorCode`. Ожидается ответ об ошибке токена (`INVALID_ARGUMENT` или `UNREGISTERED`), **не** 401/403: это значит, что облако авторизовано в Firebase, а сообщение никуда не ушло. 401/403 — СТОП, откат шагов 5–7.
9. **После.** `/health/ready`, `POST /pos/redemptions` без ключа → 401 `POS_KEY_MISSING` (как раньше). Количество `devices` (READ ONLY) — только число.

## Откат

Вернуть `.env` и compose из `backups/push-<UTC>/`, `docker compose up -d --no-build --force-recreate backend`. Файл в `secrets/` можно оставить.

## Отчёт

`reports/ENABLE_PUSH_FCM_2026-11-05.md`: сырой вывод шагов 1–9 без секретов, пути копий и хеши, `diff` compose, имена изменённых переменных, результат шага 8, план отката. Не проверено: доставка на настоящий телефон (нужен APK с push).
