# Промпт исполнителю (Mac): commit, выкладка backend и APK 1.0.10 отдельной ссылкой — 2026-11-02

Репозиторий `/Users/nuras/Desktop/cashback-one`. Общайся и пиши отчёт по-русски. Владелец прямо поручил три действия в этом порядке: **commit и push, выкладка backend, загрузка APK 1.0.10 отдельным файлом.** Прочитай `AGENTS.md` (разделы о проверках и публикации), `reports/BACKEND_LOGIN_AVATAR_DEPLOY_2026-11-01.md`, `reports/APK_1_0_9_PUBLISH_2026-11-01.md`, §11 в `reports/APK_1_0_10_BUILD.md`.

**Упало или неожиданно — СТОП и сырой вывод; без самостоятельных исправлений и повторных мутаций; секреты и персональные данные скрыть.**

Команды, которых нет в окружении, сразу заменяй (`rg` → `grep`). Сбой твоего вспомогательного скрипта, который ещё ничего не изменил на сервере и в git, не повод для СТОП: исправь скрипт и напиши об этом в отчёте. **Любой другой сбой, в том числе команды `git`, `docker`, `ssh`, FTPS или сборки образа, — СТОП.** Все сбои, даже исправленные, перечисляются в отчёте. Каждая часть начинается только после успеха предыдущей.

**Не делать:** `version.json`, замена кнопки лендинга или `index.html`, GitHub Release и теги, миграции, изменения `.env`, Caddy, `docker-compose`, `.htaccess`, `admin/`, агента, 1С, `force`-push, удаление файлов на сервере и хостинге.

Не печатать значения `.env*`, compose config, ключей, телефонов и кодов. Временные скрипты и логи — вне репозитория. `scripts/upload_apk.py` и `scripts/upload_admin.py` не использовать.

## Часть 0. Проверка перед началом

1. `git branch --show-current` → `main`; `git rev-parse --short HEAD` → `339e208`; `git fetch origin`; `git rev-parse --short origin/main` → `e16492f`; `git log --oneline origin/main..HEAD` показывает ровно `339e208`; `git log --oneline HEAD..origin/main` пуст. Иное — СТОП. Коммит `339e208` проверен куратором и уйдёт на GitHub вместе с новым коммитом этого выпуска.
2. `mobile/dist/cashback-one-1.0.10.apk`: **68 600 435** байт, SHA-256 **`8c8726e068088f3eae66fa1b3b1fffa7d2512c6aa44ebdded03f0bd611c123c9`**. Иное — СТОП.
3. `uptime`: при load average за 1 минуту выше 12 подожди до 5 минут. Тесты — перенаправлением в файл, таймаут инструмента не меньше 600 с:
   - в `mobile/`: `npx jest` → **249 passed**, `npx tsc --noEmit` чисто, `npx eslint .` 0 ошибок;
   - `backend/.venv/bin/python -m pytest backend/tests -q -ra` → **377 passed, 36 skipped**;
   - `backend/.venv/bin/python -m ruff check backend/app backend/tests/test_customer_wallet.py` чисто.

## Часть 1. Commit и push

Добавляй файлы **поимённо**, не через `git add .` и не через `-A`. В коммит идут только:

```text
CLAUDE.md
backend/app/api/customer_wallet.py
backend/app/services/wallet_service.py
backend/tests/test_customer_wallet.py
mobile/app.json
mobile/app/(app)/(tabs)/profile.tsx
mobile/app/(app)/(tabs)/promotions.tsx
mobile/app/(app)/history.tsx
mobile/app/_layout.tsx
mobile/src/api/wallet.ts
mobile/src/components/TabBar.tsx
mobile/src/demo/mockApi.ts
mobile/src/features/home.tsx
mobile/src/features/profile.tsx
mobile/src/features/promotionsArtwork.ts
mobile/src/features/PeriodSheet.tsx
mobile/src/features/UpdateNotice.tsx
mobile/src/features/appUpdate.ts
mobile/src/features/historyPeriod.ts
mobile/src/i18n/kz.ts
mobile/src/i18n/ru.ts
mobile/tests/appUpdate.test.tsx
mobile/tests/cardScanner.test.tsx
mobile/tests/cityCustom.test.tsx
mobile/tests/historyPeriod.test.tsx
mobile/tests/promotionsArtwork.test.tsx
mobile/assets/promotions/promo-card-bonus-side.png
mobile/assets/promotions/promo-fresh-products-side.png
mobile/assets/promotions/promo-hits-discount-side.png
mobile/assets/promotions/promo-weekly-side.png
docs/PROMPT_APK_1_0_10_2026-11-02.md
docs/PROMPT_APP_POLISH_2026-11-02.md
docs/PROMPT_APP_POLISH_FIXES_2026-11-02.md
docs/PROMPT_APP_UPDATE_NOTICE_2026-11-01.md
docs/PROMPT_RELEASE_1_0_10_2026-11-02.md
reports/APK_1_0_10_BUILD.md
reports/APP_POLISH_2026-11-02.md
reports/APP_POLISH_ACCEPTANCE_2026-11-02.md
reports/APP_POLISH_FIXES_2026-11-02.md
reports/APP_UPDATE_NOTICE_2026-11-01.md
```

**Никогда не добавлять:** `C:/`, `video/`, `mobile/dist/`, любые `*.apk`, `mobile/android/`, `node_modules/`, `.env*`, keystore и ключи. Эти папки не удалять.

Если в `git status` есть другие изменённые отслеживаемые файлы — СТОП и покажи список.

Перед коммитом:

- `git diff --cached --name-only` совпадает со списком, сравнение через `sort` и `diff`;
- поиск в добавленных строках `git diff --cached -U0 | grep '^+'` по словам `password`, `storePassword`, `PRIVATE KEY`, `postgresql://`, `Bearer `: совпадение с секретным значением — СТОП. В отчёт совпадения не печатать, только их количество и файл.

Сообщение коммита:

```text
feat(app): update notice, offer cards, custom city, history period; APK 1.0.10

- Update notice reads /app/version.json, required mode via min_version_code
- Promotions use OfferCard wide layout with side artwork
- Manual city input for the "other city" option
- History period chips and sheet; date_from and date_to in the API
- Flat QR tab button
- Tests: mobile 249, backend 377 passed

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

Перед отправкой `git log --oneline origin/main..HEAD` показывает ровно два коммита: новый и `339e208`.

`git push origin main`, обычный push. Запомни полный хеш нового коммита: дальше он обозначен `<COMMIT>`. Проверь, что `origin/main` равен ему.

## Часть 2. Выкладка backend

VPS `kz-vps`, `/opt/cashback-one`, контейнеры `cashback-backend`, `cashback-postgres`. Выкладка меняет два файла: `backend/app/api/customer_wallet.py` и `backend/app/services/wallet_service.py`. **Миграции нет:** ожидаемая версия alembic до и после `0011_customer_avatar`.

Отметка времени `<TS>` в формате `YYYYMMDDTHHMMSSZ`, UTC.

### До изменений

1. `df -h /`: свободно меньше 3 ГБ — СТОП.
2. `git diff --stat b30a4f6 339e208 -- backend` пуст: на VPS ожидается код `b30a4f6`. Сверь SHA-256 всех файлов `backend/app` и `backend/migrations` на VPS с `git show 339e208:<путь>`. Расхождение — СТОП.
3. `/health/ready` на VPS: database ok, redis ok.
4. SQL READ ONLY: версия alembic, количество покупателей, карт, операций. Запиши числа. Номера и другие данные не выводить.
5. Запомни SHA-256 главной `https://cashback-qr.poscenter.kz/`.

### Копии

Папка `/opt/cashback-one/backups/period-<TS>/`:

- `pg.sql.gz`: `docker exec cashback-postgres sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip`;
- `env.bak`, права 600;
- `backend-src.tgz`: текущий `backend/`.

Проверка дампа: `gzip -t` успешно; строка `PostgreSQL database dump complete` есть в распакованном потоке. **Ищи её через `grep -c` по всему потоку**, не в `tail`: после неё `pg_dump` дописывает `\unrestrict`. Покажи размер.

Образ отката: `docker tag cashback-backend:local cashback-backend:rollback-period-<TS>`. Покажи ID образа.

### Выкладка

1. Архив только из коммита, без тестов:

   ```bash
   git archive --format=tar.gz -o <временный-путь>/cashback-backend.tgz <COMMIT> backend ':(exclude)backend/tests'
   ```

   Команду из `docs/DEPLOY_VPS.md` не использовать: она не исключает `.venv`. Проверь `tar tzf`: только `backend/`, нет `.env`, `.venv`, `tests`. Сверь SHA-256 архива на VPS после копирования.
2. На VPS:

   ```bash
   cd /opt/cashback-one && tar xzf /tmp/cashback-backend.tgz && nice -n 15 docker build -q -t cashback-backend:local ./backend && docker compose up -d --no-build --force-recreate backend
   ```

   Сервис `migration` не пересоздавать.

### После выкладки

- `/health/ready`: database ok, redis ok. Журнал backend за время после запуска без ошибок, текст ошибок без персональных данных.
- SQL READ ONLY: alembic `0011_customer_avatar`, количество покупателей, карт и операций не меньше, чем до выкладки.
- В контейнере: сигнатура `get_customer_card_transactions` содержит `date_from` и `date_to`:

  ```bash
  docker exec cashback-backend python -c "import inspect; from app.services.wallet_service import get_customer_card_transactions as f; print(list(inspect.signature(f).parameters))"
  ```

- Публичный API: `GET https://api.cashback-qr.poscenter.kz/me/cards/00000000-0000-0000-0000-000000000000/transactions?date_from=2026-10-01T00:00:00Z` без токена → 401.
- Токены покупателей не создавать, настоящих пользователей не трогать.

Любая проверка не прошла — СТОП. Откат сам не запускай, покажи вывод. Команды отката запиши в отчёт:

```bash
docker tag cashback-backend:rollback-period-<TS> cashback-backend:local
docker compose up -d --no-build --force-recreate backend
```

## Часть 3. Загрузка APK

| Что | Значение |
|---|---|
| Локальный файл | `mobile/dist/cashback-one-1.0.10.apk` |
| Размер | **68 600 435** байт |
| SHA-256 | **`8c8726e068088f3eae66fa1b3b1fffa7d2512c6aa44ebdded03f0bd611c123c9`** |
| Куда | папка `app/` внутри папки сайта, имя `cashback-one-1.0.10.apk` |
| Адрес | `https://cashback-qr.poscenter.kz/app/cashback-one-1.0.10.apk` |

Учётные данные FTPS — в `.env.hosting.local`: `HOSTING_FTPS_HOST`, `HOSTING_FTPS_USER`, `HOSTING_FTPS_PASSWORD`, `HOSTING_SITE_DIR`. Значения не печатать.

Свой временный Python-скрипт вне репозитория:

- `ftplib.FTP_TLS`, проверка сертификата включена, `context.maximum_version = ssl.TLSVersion.TLSv1_2`, запуск с `SSL_CERT_FILE=/etc/ssl/cert.pem`;
- `prot_p()`, `TYPE I` до `SIZE` и передачи;
- перейти в `HOSTING_SITE_DIR`, затем `app`. Покажи список файлов до загрузки. **Сервер отвечает 200 на несуществующие пути, поэтому наличие файла проверяй только списком FTP, не по HTTP.** Файл `cashback-one-1.0.10.apk` уже есть — СТОП;
- загрузить во временное имя `.cashback-one-1.0.10.apk.upload-<случайное>`, скачать обратно, сверить SHA-256 и размер, затем `rename` в итоговое имя;
- не трогать ничего, кроме этого файла. Если упало до `rename`, временный файл не удалять: СТОП и покажи имя;
- покажи список файлов после загрузки: добавлен ровно один файл, временного нет, `version.json` нет.

Проверка по HTTPS:

- `HEAD` адреса: 200, `Content-Type: application/vnd.android.package-archive`, `Content-Length: 68600435`;
- полное скачивание: SHA-256 совпадает с таблицей. Держи только один полный файл и удали свою временную копию после сверки;
- главная: 200, SHA-256 не изменился;
- `cashback-one-1.0.9.apk` и `cashback-one-1.0.8.apk`: 200, размеры 67 951 855 и 67 773 772.

## Отчёт

`reports/RELEASE_1_0_10_2026-11-02.md`, в git не добавлять: его закоммитит куратор после проверки.

- хеш коммита и вывод push;
- сырые выводы тестов, проверок VPS и HTTPS, числа до и после, имена копий и ID образов;
- команды отката backend;
- все сбои по ходу работы, в том числе исправленные;
- раздел **«Не проверено»**: фильтр периода с настоящим токеном и на PostgreSQL, скачивание и установка на телефоне, окно обновления, вид экранов на телефоне, считывание QR кассой.

Не пиши «полностью готово» без доказательств.
