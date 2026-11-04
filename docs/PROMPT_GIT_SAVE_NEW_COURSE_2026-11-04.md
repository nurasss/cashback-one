# Промпт исполнителю (Gemini): сохранить новый курс в GitHub — 2026-11-04

**Упало или неожиданно — СТОП и сырой вывод; без самостоятельных исправлений; секреты и ПДн скрыть.**

Общайся и пиши по-русски.

## Контекст

Папка `/Users/nuras/Desktop/cashback-one`, ветка `main`, HEAD `726ff98`, совпадает с `origin/main`. Владелец поручил сохранить в GitHub принятые куратором задачи нового курса. Репозиторий **публичный**. Ничего не деплоить.

## Запреты

- Не добавлять: `C:/`, `video/`, `mobile/` (правки 1.0.11-test сохраняются отдельно позже), `dist/`, `node_modules/`, `.env*` кроме `.env.example`, `.claude/`, любые APK, ключи, `*.keystore`, `google-services.json`, JSON сервисного аккаунта.
- Не добавлять документы и отчёты 1.0.11-test: `docs/PROMPT_APK_1_0_11_TEST_2026-11-04.md`, `docs/PROMPT_APP_1_0_11_TEST_2026-11-04.md`, `docs/PROMPT_APP_1_0_11_TEST_2GIS_2026-11-04.md`, `reports/APP_1_0_11_TEST_2026-11-04.md`, `reports/screenshots-1.0.11-test/`.
- Не использовать `git add -A`, `git add .`, `git add -f`, `git commit -a`, `git push --force`. Теги и релизы не трогать. Код не менять.

## Шаг 1. Состояние

`git status --short`, `git log -1 --oneline`, `git fetch origin` и `git status -sb`. HEAD должен быть `726ff98`, без отставания от `origin/main`. Иначе СТОП.

## Шаг 2. Проверка на секреты

По всем файлам из шагов 3–5 (включая новые) выполни поиск и выведи только **имена файлов и номера строк**, без самих строк:

```bash
grep -rnIE "(agk_|pos_)[A-Za-z0-9_-]{20,}|BEGIN (RSA |EC )?PRIVATE KEY|private_key\"|AIza[0-9A-Za-z_-]{30,}|password\s*=\s*['\"][^'\"]{6,}" <файлы>
```

Найденное в тестах с явно тестовыми значениями (`fixture`, `test`, `XXXX`) перечисли и объясни. Похоже на настоящий ключ или пароль — СТОП, ничего не коммитить. Также проверь, что в `reports/business-app-content-2026-11-04/` и `reports/pos-redeem-2026-11-04/` нет снимков с настоящим ключом кассы или агента: открой каждый снимок окна ключа, если такие есть, и опиши. Настоящий ключ — СТОП.

## Шаг 3. Коммит backend и кабинета

```bash
git add .env.example backend/app backend/migrations/versions/0012_push_devices.py backend/migrations/versions/0013_business_app_content.py backend/migrations/versions/0014_pos_keys.py backend/migrations/versions/0015_notification_redemption.py backend/tests/test_admin_config.py backend/tests/test_customer_app.py backend/tests/test_admin_pos_keys.py backend/tests/test_business_app_content.py backend/tests/test_pos_api.py backend/tests/test_push_notifications.py admin/src admin/tests
```

Перед коммитом `git diff --cached --stat` и `git diff --cached --name-only`: только `backend/`, `admin/`, `.env.example`; нет `__pycache__`, `.pyc`, `dist`. Иначе `git restore --staged` лишнего и опиши. Сообщение:

```text
feat: push notifications, POS keys and push redemption codes, business stores and app texts
```

## Шаг 4. Коммит агента

```bash
git add agent/packaging agent/pyproject.toml agent/src agent/tests
```

`git diff --cached --name-only`: только `agent/`, без `__pycache__`, `dist`, `build`. Сообщение:

```text
feat(agent): 0.3.0 DPAPI secrets, 1C connection check, key replacement on upgrade
```

## Шаг 5. Коммит документов

```bash
git add CLAUDE.md docs/AGENT_INSTALLATION.md docs/FIREBASE_SETUP.md docs/POS_REDEEM_API.md docs/CUSTOMER_API.md docs/ROADMAP_PER_CLIENT_2026-11-04.md docs/integrations/cash_redeem_code.bsl docs/PROMPT_ADMIN_AGENT_KEY_2026-11-04.md docs/PROMPT_AGENT_INSTALLER_SECRETS_2026-11-04.md docs/PROMPT_AGENT_INSTALLER_SECRETS_FIXES_2026-11-04.md docs/PROMPT_BACKEND_POS_REDEEM_CODE_HIDE_2026-11-04.md docs/PROMPT_BACKEND_POS_REDEEM_PUSH_2026-11-04.md docs/PROMPT_BACKEND_PUSH_2026-11-04.md docs/PROMPT_BACKEND_PUSH_FIXES_2026-11-04.md docs/PROMPT_BACKEND_PUSH_FIXES_2_2026-11-04.md docs/PROMPT_BUSINESS_APP_CONTENT_2026-11-04.md docs/PROMPT_BUSINESS_APP_CONTENT_FIXES_2026-11-04.md docs/PROMPT_GIT_SAVE_NEW_COURSE_2026-11-04.md reports/ADMIN_AGENT_KEY_2026-11-04.md reports/AGENT_INSTALLER_SECRETS_2026-11-04.md reports/BACKEND_POS_REDEEM_PUSH_2026-11-04.md reports/BACKEND_PUSH_2026-11-04.md reports/BUSINESS_APP_CONTENT_2026-11-04.md reports/business-app-content-2026-11-04 reports/pos-redeem-2026-11-04
```

Сообщение:

```text
docs: per-client roadmap, Cash redemption code, POS API, Firebase setup, task reports
```

Если `docs/CUSTOMER_API.md` уже попал в шаг 3 — не страшно, просто проверь, что он не потерян.

## Шаг 6. Push

Перед push: `git status --short` — в неотслеживаемых и изменённых остались только `C:/`, `video/`, `mobile/…`, `docs/PROMPT_APK_1_0_11_TEST_2026-11-04.md`, `docs/PROMPT_APP_1_0_11_TEST*`, `reports/APP_1_0_11_TEST_2026-11-04.md`, `reports/screenshots-1.0.11-test/`. Что-то ещё — СТОП.

```bash
git push origin main
```

Без `--force`. Отклонён — СТОП. Выведи хеши трёх коммитов, `git status -sb` и `git log --oneline -4`.

## Отчёт

В чат: сырой вывод шагов 1–6. Файл отчёта не создавать (чтобы не оставлять незакоммиченный файл).
