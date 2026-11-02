# Промпт исполнителю: публикация лендинга и коммит — 2026-11-02

**Упало или неожиданно — СТОП и сырой вывод; без самостоятельных исправлений; секреты и ПДн скрыть.**

## Контекст

Проект Cashback One, папка `/Users/nuras/Desktop/cashback-one`. В рабочем дереве лежат принятые куратором правки лендинга: Roboto, белый текст на красном фоне, максимум Bold, QR-код вместо штрихкода, снимки `screen-home.png` и `screen-qr.png`. Отчёт: `reports/LANDING_ROBOTO_WHITE_2026-11-02.md`.

Владелец поручил опубликовать эти правки и сохранить их в GitHub. Сайт: `https://cashback-qr.poscenter.kz/`. Текущий `index.html` на сайте: SHA-256 `fe5993964e494f0832e202b2fa4aaa5f9fa19225d4598573c635b7cefed4e293`.

Доступ FTPS лежит в `.env.hosting.local`. Файл не печатать, значения не выводить и не записывать в отчёт и временные файлы.

## Запреты

- Не менять на сайте `.htaccess`, `app/`, `demo/`, `media/`, `robots.txt`, `sitemap.xml`.
- Ничего не удалять на сайте, в том числе старые `assets/*` и `landing/screen-barcode.png`.
- Не использовать `scripts/upload_admin.py`: он пишет копию в `C:/` и перезаписывает index без временного файла.
- Не менять код. Не менять backend, `mobile/`, агент.
- Не добавлять в коммит `C:/`, `video/`, `dist/`, `node_modules/`, `.env*`. Не использовать `git add -A` и `git add .`.
- Не использовать `git push --force`. Теги и релизы не трогать.

## Шаг 1. Подтверди состояние

1. `git status --short` и `git log -1 --oneline`: в рабочем дереве те же правки, HEAD равен `352e330`.
2. Скачай `https://cashback-qr.poscenter.kz/` и сравни SHA-256 с указанным выше. Не совпало — СТОП.
3. Покажи `df -h /`.

## Шаг 2. Проверки и production-сборка

Из `admin/`:

```bash
npx vitest run --maxWorkers=1
```

```bash
npm run typecheck
```

```bash
npm run lint
```

```bash
VITE_API_BASE_URL=https://api.cashback-qr.poscenter.kz VITE_ALLOW_INSECURE_HTTP=0 npm run build
```

Ожидается 163 passed и чистые typecheck и lint. Проверь в `admin/dist`: в JS есть `https://api.cashback-qr.poscenter.kz`, нет `localhost`; в `index.html` ссылка на APK `1.0.10`. Выведи grep по этим строкам.

## Шаг 3. Что загружать

Для каждого файла из `admin/dist` посчитай локальный SHA-256 и сравни с файлом по HTTPS. Сервер отвечает 200 на несуществующие пути, поэтому файл считается совпавшим только при равных SHA-256 и длине. Выведи таблицу: путь, размер, SHA-256, «новый» или «совпадает».

Ожидается к загрузке: новые JS и CSS из `assets/`, `landing/screen-qr.png`, изменённый `landing/screen-home.png`, `index.html`. Файлы шрифтов уже есть на сайте. Если список существенно другой или в нём есть что-то из запретов, СТОП.

## Шаг 4. Резервная копия

Создай `~/.local/share/cashback-one/backups/landing-<UTC>-roboto/`. Скачай туда с сайта текущие `index.html` и `landing/screen-home.png`, сверь их SHA-256 с HTTPS-ответом. Выведи путь и хеши.

## Шаг 5. Загрузка по FTPS

Параметры: TLS 1.2, проверка сертификата (`SSL_CERT_FILE=/etc/ssl/cert.pem` или явный контекст с этим файлом), `PROT P`, `TYPE I`. Перед каждой операцией смены папки возвращайся в корень сессии: относительный `cwd` из вложенной папки уже приводил к сбою.

Порядок: сначала `assets/*`, затем `landing/*`, `index.html` строго последним.

Для каждого файла:

1. Загрузи под временным именем в той же папке, например `.имя.upload-<случайно>`.
2. Скачай обратно и сверь размер и SHA-256 с локальным файлом.
3. Только после совпадения переименуй в целевое имя.

Если на любом шаге сбой, останови загрузку. `index.html` при этом не загружай. Скрипт храни вне репозитория и не печатай в нём значения доступа.

## Шаг 6. Проверка на сайте

1. Каждый загруженный файл скачай по HTTPS с заголовком `Cache-Control: no-cache`, сверь SHA-256, длину и `Content-Type`.
2. Выведи SHA-256 живой главной, он равен локальному `dist/index.html`.
3. Убедись, что временных файлов `.*.upload-*` не осталось на сайте.
4. `https://cashback-qr.poscenter.kz/app/cashback-one-1.0.10.apk`: сравни длину `68600435`, файл не менялся.
5. `https://cashback-qr.poscenter.kz/app/version.json`: SHA-256 по-прежнему `7e1c460a67c79823…`, сравни начало хеша.
6. Открой сайт в настоящем браузере, RU и ҚАЗ, 390 и 1366 px: шрифт Roboto у `h1` и вкладок, белый текст в красном блоке, вкладка QR-код показывает снимок, нет слова «штрихкод», нет горизонтальной прокрутки, ошибок в консоли нет. На `/admin/login` вычисленный шрифт Roboto, форма видна. Настоящий вход не выполнять.

Если проверка на сайте не прошла, СТОП, сырой вывод и план отката. Сам не откатывай без поручения.

Откат: вернуть на сайт `index.html` и `landing/screen-home.png` из резервной копии.

## Шаг 7. Отчёт

Сохрани `reports/LANDING_ROBOTO_DEPLOY_2026-11-02.md`: сырой вывод шагов 1–6, таблицу загруженных файлов с SHA-256, путь копии, новый хеш index, план отката, всё непроверенное.

## Шаг 8. Commit и push

Только если шаги 1–7 успешны.

```bash
git add admin/index.html admin/public/landing admin/src/i18n/public.ts admin/src/layout/AdminRoutes.tsx admin/src/main.tsx admin/src/styles/landing.css admin/tests/public-routing.test.tsx .claude/launch.json docs/PROMPT_LANDING_ROBOTO_WHITE_2026-11-02.md docs/PROMPT_LANDING_QR_TABS_2026-11-02.md docs/PROMPT_LANDING_ROBOTO_PUBLISH_2026-11-02.md reports/LANDING_ROBOTO_WHITE_2026-11-02.md reports/LANDING_ROBOTO_DEPLOY_2026-11-02.md reports/landing-roboto-2026-11-02
```

Перед коммитом покажи `git diff --cached --stat` и проверь, что в индексе нет `C:/`, `video/` и `.env*`. Сообщение коммита:

```text
feat(landing): Roboto, white text on red, QR code instead of barcode
```

Затем `git push origin main`. Без `--force`. Если push отклонён, СТОП. Выведи хеш коммита и `git status -sb`.
