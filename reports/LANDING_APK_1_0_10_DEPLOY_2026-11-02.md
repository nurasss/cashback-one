# Выкладка окна обновления и кнопки лендинга на APK 1.0.10 — 2026-11-02

Дата: 2026-11-02, Mac.
Выполняется по задаче `docs/PROMPT_UPDATE_WINDOW_LANDING_1_0_10_2026-11-02.md`.
Текущий статус: **СТОП на шаге 2.3 (FTPS выкладка второго ассета). Сбой CWD из-за относительного пути. Живой сайт не повреждён.**

---

## 1. Сбои и инциденты

1. **Проверка HTTPS через вспомогательный скрипт urllib (исправлено в Части 1):**
   При запуске проверочного python-скрипта `urllib.request.urlopen` на macOS вернул `ssl.SSLCertVerificationError: unable to get local issuer certificate`.
   Причина: Python на macOS без настроенного системного контекста не находит корневые сертификаты по умолчанию.
   Исправление: передан явный SSL-контекст `ssl.create_default_context(cafile='/etc/ssl/cert.pem')` в соответствии с общими правилами проекта. Скрипт успешно проверил ответ сервера. Никаких изменений на хостинге или в git это не вызвало.

2. **Сбой FTPS CWD при выкладке второго файла ассетов (Часть 2, шаг 2.3):**
   При выкладке скриптом `/tmp/deploy_landing_1_0_10.py` первый ассет `assets/AdminRoutes-BYa8UCfT.js` успешно загружен под временным именем, проверен по обратному скачиванию (SHA-256 `b06efb85f1ff344b1565637dc00aeb291512f4edd81c55dac7da91d6b60ca718`) и переименован в целевое имя.
   При переходе ко второму ассету `assets/index-87Puts5O.js` функция `upload_and_verify` вызвала `ftps.cwd(remote_dir)` с относительным путём `cashback-qr.poscenter.kz/assets`. Поскольку рабочая директория сессии FTPS уже находилась в `cashback-qr.poscenter.kz/assets`, повторный `cwd` завершился ошибкой `ftplib.error_perm: 550 cashback-qr.poscenter.kz/assets: No such file or directory`.
   Сырой вывод (секреты скрыты):
   ```text
   Prepared real version.json (SHA-256: 7e1c460a67c79823afd5fff7a5af1cf02ddfc124f556510c5d723dcddc4bd64b)
   Uploading /Users/nuras/Desktop/cashback-one/admin/dist/assets/AdminRoutes-BYa8UCfT.js to cashback-qr.poscenter.kz/assets/.AdminRoutes-BYa8UCfT.js.tmp-dc19b959...
   Downloading back from .AdminRoutes-BYa8UCfT.js.tmp-dc19b959...
   Renaming .AdminRoutes-BYa8UCfT.js.tmp-dc19b959 -> AdminRoutes-BYa8UCfT.js in cashback-qr.poscenter.kz/assets
   Successfully published AdminRoutes-BYa8UCfT.js (SHA-256: b06efb85f1ff344b1565637dc00aeb291512f4edd81c55dac7da91d6b60ca718)
   Traceback (most recent call last):
     File "/tmp/deploy_landing_1_0_10.py", line 92, in <module>
       sha = upload_and_verify(ftps, local_p, assets_remote_dir, fn)
     File "/tmp/deploy_landing_1_0_10.py", line 56, in upload_and_verify
       ftps.cwd(remote_dir)
              ~~~~~~~~^^^^^^^^^^^^
     File "/usr/local/Cellar/python@3.14/3.14.7/Frameworks/Python.framework/Versions/3.14/lib/python3.14/ftplib.py", line 619, in cwd
       return self.voidcmd(cmd)
              ~~~~~~~~~~~~^^^^^
     File "/usr/local/Cellar/python@3.14/3.14.7/Frameworks/Python.framework/Versions/3.14/lib/python3.14/ftplib.py", line 286, in voidcmd
       return self.voidresp()
              ~~~~~~~~~~~~~^^
     File "/usr/local/Cellar/python@3.14/3.14.7/Frameworks/Python.framework/Versions/3.14/lib/python3.14/ftplib.py", line 259, in voidresp
       resp = self.getresp()
     File "/usr/local/Cellar/python@3.14/3.14.7/Frameworks/Python.framework/Versions/3.14/lib/python3.14/ftplib.py", line 254, in getresp
       raise error_perm(resp)
   ftplib.error_perm: 550 cashback-qr.poscenter.kz/assets: No such file or directory
   ```
   **Статус после сбоя:**
   - По правилу «Упало или неожиданно — СТОП и сырой вывод; без самостоятельных исправлений и повторных мутаций» выполнение немедленно остановлено, скрипт повторно не запускался.
   - Живой `index.html` НЕ затрагивался (хеш `64df6c0138ed3a8342752e34ab3690bf9cc7d86bce3315fc75befbd48f9b917a`).
   - Действующий `app/version.json` НЕ затрагивался (хеш `2fc78494279513ea7d8b9849eee1c4b439cdac7807b78be52c97e2a87d383a67`).
   - Загруженный файл `AdminRoutes-BYa8UCfT.js` в `assets/` изолирован новым хешем и не влияет на работающую версию сайта. Никаких временных файлов `.*.tmp-*` не осталось.

---

## 2. Часть 1. Временный `version.json`

### 2.1. Исходное состояние

1. **SHA-256 главной страницы `https://cashback-qr.poscenter.kz/`:**
   ```
   43632ed3d36e538ef946e06e5a7f1d1cb0b31e81259110cbde7fa0b31b15b9b7  -
   ```
   (начинается с `43632ed3`, соответствовало состоянию до публикации бокового меню).

2. **Список файлов в каталоге `app/` на хостинге до загрузки (13 файлов):**
   ```
   cashback-one-1.0.0.apk
   cashback-one-1.0.1.apk
   cashback-one-1.0.10.apk
   cashback-one-1.0.2.apk
   cashback-one-1.0.2.pre-ui.bak
   cashback-one-1.0.2.round1.bak
   cashback-one-1.0.3.apk
   cashback-one-1.0.4.apk
   cashback-one-1.0.5.apk
   cashback-one-1.0.6.apk
   cashback-one-1.0.7.apk
   cashback-one-1.0.8.apk
   cashback-one-1.0.9.apk
   ```
   - `cashback-one-1.0.10.apk` присутствует.
   - `version.json` отсутствует.

### 2.2. Создание и выкладка временного `version.json`

Файл создан вне репозитория (`/tmp/version.json`), кодировка UTF-8 без BOM:
```json
{
  "latest_version": "1.0.11",
  "latest_version_code": 12,
  "min_version_code": 1,
  "download_url": "https://cashback-qr.poscenter.kz/app/cashback-one-1.0.10.apk"
}
```

Параметры локального файла:
- Размер: 169 байт
- SHA-256: `2fc78494279513ea7d8b9849eee1c4b439cdac7807b78be52c97e2a87d383a67`

Загрузка по FTPS:
- Подключение: TLS 1.2, явная проверка по `/etc/ssl/cert.pem`, `PROT P`, режим `TYPE I`.
- Временное имя на сервере: `.version.json.upload-9c664be1`.
- Обратное скачивание во временный файл проверки: размер 169 байт, SHA-256 `2fc78494279513ea7d8b9849eee1c4b439cdac7807b78be52c97e2a87d383a67` (побайтно совпал).
- Переименование на сервере: `.version.json.upload-9c664be1` → `version.json`.
- Проверка списка FTP: в `app/` 14 файлов, `version.json` присутствует, временных файлов нет.

### 2.3. Проверка по HTTPS

1. **Запрос `curl -i -sS https://cashback-qr.poscenter.kz/app/version.json`:**
   ```text
   HTTP/1.1 200 OK
   Server: nginx
   Content-Type: application/json
   Content-Length: 169
   Connection: keep-alive
   ETag: "a9-65f458602a170"

   {
     "latest_version": "1.0.11",
     "latest_version_code": 12,
     "min_version_code": 1,
     "download_url": "https://cashback-qr.poscenter.kz/app/cashback-one-1.0.10.apk"
   }
   ```

2. **Сверка данных и хеша:**
   - JSON корректно распарсен:
     - `latest_version`: `"1.0.11"`
     - `latest_version_code`: `12`
     - `min_version_code`: `1`
     - `download_url`: `"https://cashback-qr.poscenter.kz/app/cashback-one-1.0.10.apk"`
   - SHA-256 ответа по HTTPS: `2fc78494279513ea7d8b9849eee1c4b439cdac7807b78be52c97e2a87d383a67` (совпадает с локальным).

3. **Проверка на телефоне:**
   Владелец подтвердил: на телефоне появилось диалоговое окно обновления, кнопки «Позже» и «Обновить» работают.

---

## 3. Часть 2. Кнопка лендинга и настоящий `version.json`

### 3.1. Правки кода

Замена `1.0.8` на `1.0.10` выполнена строго в указанных местах:
- `admin/src/pages/LandingPage.tsx:91`
- `admin/index.html:27`
- `admin/src/i18n/public.ts:71,237`
- `admin/tests/public-routing.test.tsx`
- `admin/tests/i18n.test.tsx`
- `admin/tests/i18n-acceptance.test.tsx`
- `admin/tests/public-assets.test.ts`

Проверка отсутствия упоминаний `1.0.8`:
```bash
grep -rn "1\.0\.8" admin/src admin/tests admin/index.html
# Вывод пуст (exit code 1)
```

### 3.2. Локальные проверки

1. **Vitest до правок:** 163 passed / 20 файлов (63.61s).
2. **Vitest после правок:** 163 passed / 20 файлов (65.49s).
3. **TypeScript:** `npx tsc --noEmit` — 0 ошибок.
4. **Сборка production:**
   ```bash
   VITE_API_BASE_URL=https://api.cashback-qr.poscenter.kz VITE_ALLOW_INSECURE_HTTP=0 npm run build
   ```
   Сборка завершена успешно.

5. **Дифф артефактов `admin/dist`:**
   Изменились только:
   - `admin/dist/index.html` (3093 байта, SHA-256 `fe5993964e494f0832e202b2fa4aaa5f9fa19225d4598573c635b7cefed4e293`)
   - `admin/dist/assets/index-87Puts5O.js` (305550 байт, SHA-256 `b70eb8a86c144c60412fa33548f1e93fa72fc8d4e87d5b6d8073180369b6e507`)
   - `admin/dist/assets/AdminRoutes-BYa8UCfT.js` (166489 байт, SHA-256 `b06efb85f1ff344b1565637dc00aeb291512f4edd81c55dac7da91d6b60ca718`)

### 3.3. Резервная копия живой страницы

- Путь: `~/.local/share/cashback-one/backups/landing-20261102T073033Z-apk110/index.html`
- Размер: 3091 байт
- SHA-256: `64df6c0138ed3a8342752e34ab3690bf9cc7d86bce3315fc75befbd48f9b917a` (начинается с `64df6c01`).

### 3.4. Состояние публикации

- `assets/AdminRoutes-BYa8UCfT.js`: загружен и проверен (SHA-256 `b06efb85f1ff344b1565637dc00aeb291512f4edd81c55dac7da91d6b60ca718`).
- `assets/index-87Puts5O.js`: не загружен (сбой CWD в скрипте).
- `index.html`: не загружался (остаётся копия `64df6c01…`).
- `app/version.json`: не изменялся (остаётся временный с `latest_version_code: 12`).

---

## 4. План отката / завершения

- **Откат:**
  - Живой `index.html` не менялся, откат не требуется.
  - В каталоге `assets/` появился файл `AdminRoutes-BYa8UCfT.js`, который не подключён к действующему `index.html` и никому не мешает.
  - В `app/version.json` находится временная версия (с кодом 12).
- **Для завершения выкладки:**
  - В скрипте FTPS перед каждой операцией CWD необходимо возвращаться в корень сессии (`ftps.cwd('/')` или использовать абсолютный путь `/` относительно корня FTP-аккаунта), чтобы избежать ошибки относительного перехода из подкаталога `assets/`.
  - Завершить загрузку `assets/index-87Puts5O.js`, затем `index.html`, затем обновить `app/version.json` на постоянный (с `latest_version_code: 11`).

---

## 5. Не проверено

1. Обязательный режим окна обновления (`min_version_code > 1`).
2. Обновление через окно с будущего APK (при выходе следующей версии).
3. Считывание штрихкода/QR кассовым оборудованием.
4. Проверка главной страницы после завершения выкладки 1.0.10 (выкладка остановлена по СТОП-правилу).

---

## Завершение и приёмка куратора — 2026-11-02

Исполнитель верно остановился: сбой был в его временном скрипте, `cwd` по относительному пути из папки `assets`. На сайте к этому моменту был только неподключённый `assets/AdminRoutes-BYa8UCfT.js`, главная и `version.json` не менялись. Куратор проверил это чтением и завершил часть 2 сам.

- Перед загрузкой: vitest 163 passed / 20 файлов, tsc чисто, в `admin/dist` есть `cashback-one-1.0.10.apk`, нет `1.0.8`; 37 файлов совпали с сайтом.
- Загружены `assets/index-87Puts5O.js` (`b70eb8a86c14…`), затем `index.html` (`fe5993964e494f08…`). Живой index до загрузки `64df6c01…`.
- `app/version.json`: временный файл `2fc78494…` заменён настоящим `7e1c460a67c79823…`, `latest_version` 1.0.10, `latest_version_code` 11, `min_version_code` 1. Удалён только временный файл теста. Других файлов в `app/` не добавлено и не удалено.
- Копия index: `~/.local/share/cashback-one/backups/landing-20261102T073600Z-apk110-finish/index.html`. Откат кнопки: вернуть его на сайт.
- По HTTPS сверены index, `index-87Puts5O.js`, CSS и `AdminRoutes-BYa8UCfT.js`. `version.json` — 200, `application/json`. APK 1.0.10, 1.0.9, 1.0.8 — верные тип и размеры.
- В Chrome на 320 и 1366 px кнопка ведёт на `/app/cashback-one-1.0.10.apk`, горизонтальной прокрутки нет, ошибок страниц нет; 401 на входе — обычная проверка сессии.

Сбои куратора: первый запуск завершающего скрипта упал на синтаксисе до подключения, сайт не менялся. Один раз `/admin/login` не ответил браузеру по таймауту (`ERR_TIMED_OUT`), сразу после этого он отвечал за 0,1 с, повтор всех проверок успешен. Причина не установлена.

Не проверено: исчезновение окна на телефоне с 1.0.10, обязательный режим `min_version_code`, обновление через окно с будущего APK, считывание QR кассой.

**При каждом новом APK обновлять `app/version.json`.** Покупатели версий до 1.0.10 окна не увидят: у них его нет.
