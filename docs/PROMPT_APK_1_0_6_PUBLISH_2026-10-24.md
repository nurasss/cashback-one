# Промпт исполнителю (Mac): выложить APK 1.0.6 отдельной ссылкой и закоммитить — 2026-10-24

Репозиторий `/Users/nuras/Desktop/cashback-one`. Общайся и пиши отчёт по-русски. Владелец прямо поручил: **выложить APK 1.0.6 на сайт отдельным файлом** и **закоммитить и отправить в main** исходники приложения, отчёты и `CLAUDE.md`. Кнопку «Скачать» на лендинге **не менять**.

**Упало или неожиданно — СТОП и сырой вывод; без самостоятельных исправлений и повторных мутаций; секреты и персональные данные скрыть.**

## Часть 1. Загрузка APK на хостинг

| Что | Значение |
|---|---|
| Локальный файл | `mobile/dist/cashback-one-1.0.6.apk` |
| Размер / SHA-256 (принято куратором) | **62 529 495** байт / **`195f486a0c02fd9891d638164bdc395cb7938d54ddc4357eff36d9e4d345338c`** |
| Куда | папка `app/` внутри папки сайта на хостинге, имя **`cashback-one-1.0.6.apk`** |
| Публичный адрес | `https://cashback-qr.poscenter.kz/app/cashback-one-1.0.6.apk` |

1. Сверь размер и SHA-256 локального файла с таблицей. Не совпадает — СТОП.
2. Учётные данные FTPS — в `/Users/nuras/Desktop/cashback-one/.env.hosting.local`: ключи `HOSTING_FTPS_HOST`, `HOSTING_FTPS_USER`, `HOSTING_FTPS_PASSWORD`, `HOSTING_SITE_DIR`. **Читай их только в память, не печатай, не логируй, не копируй в отчёт и в файлы.**
3. Загрузчик — свой временный Python-скрипт **вне репозитория** (например в `/private/tmp/…`). **Не использовать** `scripts/upload_apk.py` и `scripts/upload_admin.py`. Требования:
   - `ftplib.FTP_TLS`, проверка сертификата включена, `context.maximum_version = ssl.TLSVersion.TLSv1_2`; хостинг рвёт передачу на TLS 1.3. Запускать с `SSL_CERT_FILE=/etc/ssl/cert.pem` (у Python из Homebrew нет корневых сертификатов). **Проверку сертификата не отключать**;
   - `prot_p()`, `TYPE I` (двоичный режим);
   - перейти в `HOSTING_SITE_DIR`, затем `app`. Если `cashback-one-1.0.6.apk` там **уже есть** — СТОП, ничего не перезаписывать;
   - загрузить во **временное имя** (например `.cashback-one-1.0.6.apk.upload-<случайное>`), скачать его обратно, сверить SHA-256 и только потом `rename` в итоговое имя; проверить, что временного файла больше нет;
   - не трогать ничего, кроме этого одного файла: ни `index.html`, ни `assets/`, ни `.htaccess`, ни другие APK, ни `demo/`, ни `media/`.
4. Проверка по HTTPS (`curl`):
   - `HEAD` нового адреса → `200`, `Content-Type: application/vnd.android.package-archive`, `Content-Length: 62529495`;
   - полное скачивание → SHA-256 совпадает с таблицей;
   - `https://cashback-qr.poscenter.kz/` → 200, SHA-256 главной не изменился до и после загрузки. Сними его **до** загрузки;
   - прежние APK 1.0.3, 1.0.4, 1.0.5 отвечают 200 с прежними размерами (51 167 439 / 51 630 551 / 51 630 487).

## Часть 2. Commit и push

1. `git status`. В коммит идут **только**:
   - `mobile/app.json`, `mobile/package.json`, `mobile/package-lock.json`;
   - `mobile/src/components/TabBar.tsx`, `mobile/src/features/BindForm.tsx`, `mobile/src/features/CardScanner.tsx`, `mobile/src/features/code128.ts`, `mobile/src/i18n/ru.ts`, `mobile/src/i18n/kz.ts`, `mobile/src/utils/format.ts`;
   - `mobile/__mocks__/expo-camera.js`, `mobile/tests/cardScanner.test.tsx`, `mobile/tests/cardBarcode.test.tsx`, `mobile/tests/code128.test.ts`, `mobile/tests/core.test.ts`;
   - `docs/PROMPT_APP_SCAN_TABBAR_2026-10-23.md`, `docs/PROMPT_APK_1_0_6_2026-10-24.md`, `docs/PROMPT_APK_1_0_6_PUBLISH_2026-10-24.md`;
   - `reports/APP_SCAN_TABBAR_2026-10-23.md`, `reports/screenshots/app-scan-tabbar/`, `reports/APK_1_0_6_BUILD.md`, новый `reports/APK_1_0_6_PUBLISH_2026-10-24.md` (этот отчёт);
   - `CLAUDE.md`.

   Если в `git status` есть ещё изменённые отслеживаемые файлы, кроме этого списка, — СТОП и покажи список.
2. **Никогда не добавлять:** `mobile/dist/` и любые `*.apk`, `mobile/android/`, `node_modules/`, папку `C:/`, `.env*`, keystore/ключи. Добавляй файлы **поимённо** (`git add <путь>`), не `git add -A` и не `git add .`.
3. Перед коммитом:
   - `cd mobile && npx jest` → **203 passed** (вывод в файл, таймаут не меньше 600 с) и `npx tsc --noEmit` чисто. Иное — СТОП;
   - `git diff --cached --name-only` — только файлы из списка; проверь, что среди них нет `.apk`, `dist/`, `android/`, `.env`;
   - поиск секретов в добавленных строках (`git diff --cached -U0 | grep '^+'`): нет паролей, `storePassword`, ключей и строк подключения. Нашёл — СТОП.
4. В `CLAUDE.md` в раздел «Сайт RU/ҚАЗ опубликован и сохранён в GitHub — 2026-10-23» перед строкой `- Порядок работы владельца: куратор выдаёт промпт` добавь **один** пункт:
   > - **APK 1.0.6 / versionCode 7 собран и выложен отдельной ссылкой** https://cashback-qr.poscenter.kz/app/cashback-one-1.0.6.apk (62 529 495 байт, SHA-256 `195f486a…338c`, сертификат прежний `14afcbb5…cd63`): сканирование карты камерой (`expo-camera`, номер вставляется в поле, «Привязать» — сам покупатель), кнопка QR вровень с меню (подпись «Мой QR-код», обрезка на 360 px принята владельцем), номер 4–13. Разрешения: добавлена только CAMERA, RECORD_AUDIO исключён в `android/app/src/main/AndroidManifest.xml` (`tools:node="remove"`); `expo prebuild` не запускать — при пересборке эту строку и версию в `build.gradle` выставлять вручную. 203 теста. Кнопка лендинга по-прежнему 1.0.3. На телефоне не проверены: камера, запрос разрешения, считывание реальных карт. Веб-версия: экраны с `useKeyboardLift` (профиль, добавление карты) падают в браузере из-за `Keyboard.metrics` — чинить до следующей сборки демо. Отчёты `reports/APK_1_0_6_BUILD.md`, `reports/APK_1_0_6_PUBLISH_2026-10-24.md`.

   Больше в `CLAUDE.md` ничего не менять.
5. Коммит одним сообщением, в конце обязательная строка:
   ```
   feat(mobile): camera card scan, flush QR tab, card number 4-13; APK 1.0.6

   - Scan card barcode/QR with expo-camera; number fills the field, user confirms
   - QR tab button flush with other tabs, label kept
   - Card numbers 4-13 digits; tests 203 passed
   - APK 1.0.6 published as a separate link; landing button unchanged

   Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
   ```
6. `git push origin main`, затем `git fetch` и сверка: `git rev-parse HEAD` = `git rev-parse origin/main`. Отчёт о публикации входит в этот же коммит, поэтому сначала допиши отчёт, потом коммит. Хеш коммита в отчёт не вписывай, сообщи его в итоговом сообщении. Второй коммит ради хеша не делай.

## Ограничения

- Не менять лендинг, `index.html`, кнопку «Скачать», `.htaccess`, другие файлы на хостинге.
- Не создавать GitHub Release, не трогать теги.
- Не трогать `backend/`, `admin/`, `agent/`, VPS.
- **Не использовать внешние сервисы анализа изображений и не загружать никуда, кроме хостинга сайта, никакие файлы.** Не делать снимков экрана.

## Отчёт

`reports/APK_1_0_6_PUBLISH_2026-10-24.md`:
- проверка локального файла;
- результат загрузки (временное имя → проверка → rename), **без секретов**;
- проверки по HTTPS: заголовки, SHA-256, главная до и после, прежние APK;
- тесты перед коммитом;
- список файлов в коммите.

Хеш коммита и результат сверки с `origin/main` — в итоговом сообщении.

Не пиши «полностью готово» без доказательств.
