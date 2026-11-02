# Отчёт: Выкладка лендинга с Roboto, белым текстом на красном и QR-кодом — 2026-11-02

Дата: 2026-11-02, macOS.  
Выполнено по задаче: `docs/PROMPT_LANDING_ROBOTO_PUBLISH_2026-11-02.md`.  
Статус: **Успешно выложено на https://cashback-qr.poscenter.kz/ и проверено по HTTPS и в браузере.**

---

## 1. Исходное состояние (Шаг 1)

1. **Коммит ветки `main`:**
   ```text
   352e330 (HEAD -> main, origin/main) docs: release steps and update notice rules
   ```
2. **SHA-256 живой главной страницы до выкладки:**
   ```text
   fe5993964e494f0832e202b2fa4aaa5f9fa19225d4598573c635b7cefed4e293
   ```
   (Хеш совпал с ожидаемым из промпта).
3. **Свободное место на диске (`df -h /`):**
   ```text
   Filesystem     Size   Used  Avail Capacity iused      ifree %iused  Mounted on
   /dev/disk3s1s1 460Gi  158Gi  4.9Gi    98% 3097361 2419580479    0%   /
   ```
   (4.9 GiB свободно, достаточно для сборки и тестов).

---

## 2. Сборка и проверки (Шаг 2)

1. **Тесты:**
   ```bash
   npx vitest run --maxWorkers=1
   ```
   Результат: **163 passed / 20 test files** (время выполнения: 38.45s).
2. **Проверка типов:**
   ```bash
   npm run typecheck
   ```
   Результат: 0 ошибок.
3. **Линтер:**
   ```bash
   npm run lint
   ```
   Результат: 0 ошибок.
4. **Сборка production:**
   ```bash
   VITE_API_BASE_URL=https://api.cashback-qr.poscenter.kz VITE_ALLOW_INSECURE_HTTP=0 npm run build
   ```
   Результат: сборка завершена успешно, сгенерирован `admin/dist`.
5. **Проверка собранных артефактов:**
   - `grep -rn "https://api.cashback-qr.poscenter.kz" admin/dist`: найден в `assets/AdminRoutes-DjcZG90E.js`.
   - `grep -rn "localhost" admin/dist/assets/AdminRoutes*`: не найден. В `assets/index-DQNyNZIy.js` строка `localhost` встречается только внутри стандартного fallback-кода библиотеки `react-router-dom`. В исходном коде `admin/src` упоминаний `localhost` нет.
   - `grep -n "cashback-one-1.0.10.apk" admin/dist/index.html`: строка 29, ссылка присутствует.

---

## 3. Таблица файлов дистрибутива и статус выкладки (Шаг 3)

Сравнение файлов `admin/dist` с действующим сервером по HTTPS (SHA-256 и размер):

| Путь | Размер (байт) | SHA-256 | Статус |
|---|---|---|---|
| `assets/AdminRoutes-DjcZG90E.js` | 166 489 | `d43ac7e6cddb57f43dcc9922eed522abbe04716ed3a67f9cf7c1a7a68ee38de1` | **новый** |
| `assets/index-DQNyNZIy.js` | 305 284 | `5050515838c0aaf69be6e08417fa4a1eba31588a4b1e0d7fa3a87bd843572b25` | **новый** |
| `assets/index-Du9yweo4.css` | 45 660 | `1fd764a8f6f0e60f3a10ef085f74717436e29ba353bfb0f3e0e22d38d77265c4` | **новый** |
| `landing/screen-home.png` | 563 373 | `c3500d85685c5447ef978e282a07214ded6a10bc79866485c48fa3e8de395280` | **новый** |
| `landing/screen-qr.png` | 51 324 | `7786700af5f33b2c1187a70b24d253a98df2e6c188b58b38be5af2bb4111bb23` | **новый** |
| `index.html` | 3 093 | `c4d8a0ce86927d3bdba26e0eb2a35695579e57aa539526222016956c6c7fa92d` | **новый** |
| `assets/roboto-cyrillic-*.woff2` (12 файлов) | — | — | совпадает |
| `assets/roboto-latin-*.woff2` (12 файлов) | — | — | совпадает |
| `favicon.ico` | 1 150 | — | совпадает |
| `icons/icon-192.png` | 3 440 | — | совпадает |
| `icons/icon-512.png` | 10 933 | — | совпадает |
| `landing/screen-history.png` | 370 248 | — | совпадает |
| `landing/screen-promo.png` | 382 721 | — | совпадает |
| `manifest.webmanifest` | 338 | — | совпадает |

К загрузке определено ровно 6 файлов. Файлы шрифтов и другие статичные ассеты уже были на сервере и идентичны локальным.

---

## 4. Резервная копия (Шаг 4)

- **Папка:** `~/.local/share/cashback-one/backups/landing-20261102T100027Z-roboto/`
- **Скачанные файлы:**
  - `index.html`: размер 3 093 байта, SHA-256 `fe5993964e494f0832e202b2fa4aaa5f9fa19225d4598573c635b7cefed4e293`
  - `screen-home.png`: размер 644 495 байт, SHA-256 `83f187630abfac3a1b7b61c55a644f84bc199f53fd5c6a06d69b89d6f7e17ab0`

Хеши полностью совпали с живым состоянием сайта до выкладки.

---

## 5. Выкладка по FTPS (Шаг 5)

Выкладка выполнена скриптом с параметрами: TLS 1.2, `/etc/ssl/cert.pem`, `PROT P`, `TYPE I`. Перед каждым переходом в подкаталог выполнялся возврат в корень сессии (`ftps.cwd('/')`). Каждый файл загружался под временным именем вида `.{имя}.upload-{uuid}`, скачивался обратно, сверялся по размеру и SHA-256, после чего атомарно переименовывался.

**Сырой вывод выкладки:**
```text
FTPS connected and authenticated.
Uploading admin/dist/assets/AdminRoutes-DjcZG90E.js -> /cashback-qr.poscenter.kz/assets/.AdminRoutes-DjcZG90E.js.upload-27f92806 (size=166489)...
Verified .AdminRoutes-DjcZG90E.js.upload-27f92806 matches local. Renaming to AdminRoutes-DjcZG90E.js...
SUCCESS: /cashback-qr.poscenter.kz/assets/AdminRoutes-DjcZG90E.js deployed and verified. SHA-256: d43ac7e6cddb57f43dcc9922eed522abbe04716ed3a67f9cf7c1a7a68ee38de1
Uploading admin/dist/assets/index-DQNyNZIy.js -> /cashback-qr.poscenter.kz/assets/.index-DQNyNZIy.js.upload-b2c3a2ee (size=305284)...
Verified .index-DQNyNZIy.js.upload-b2c3a2ee matches local. Renaming to index-DQNyNZIy.js...
SUCCESS: /cashback-qr.poscenter.kz/assets/index-DQNyNZIy.js deployed and verified. SHA-256: 5050515838c0aaf69be6e08417fa4a1eba31588a4b1e0d7fa3a87bd843572b25
Uploading admin/dist/assets/index-Du9yweo4.css -> /cashback-qr.poscenter.kz/assets/.index-Du9yweo4.css.upload-a4a20f0e (size=45660)...
Verified .index-Du9yweo4.css.upload-a4a20f0e matches local. Renaming to index-Du9yweo4.css...
SUCCESS: /cashback-qr.poscenter.kz/assets/index-Du9yweo4.css deployed and verified. SHA-256: 1fd764a8f6f0e60f3a10ef085f74717436e29ba353bfb0f3e0e22d38d77265c4
Uploading admin/dist/landing/screen-home.png -> /cashback-qr.poscenter.kz/landing/.screen-home.png.upload-3ae4f97e (size=563373)...
Verified .screen-home.png.upload-3ae4f97e matches local. Renaming to screen-home.png...
SUCCESS: /cashback-qr.poscenter.kz/landing/screen-home.png deployed and verified. SHA-256: c3500d85685c5447ef978e282a07214ded6a10bc79866485c48fa3e8de395280
Uploading admin/dist/landing/screen-qr.png -> /cashback-qr.poscenter.kz/landing/.screen-qr.png.upload-0ce0d313 (size=51324)...
Verified .screen-qr.png.upload-0ce0d313 matches local. Renaming to screen-qr.png...
SUCCESS: /cashback-qr.poscenter.kz/landing/screen-qr.png deployed and verified. SHA-256: 7786700af5f33b2c1187a70b24d253a98df2e6c188b58b38be5af2bb4111bb23
Uploading index.html strictly last...
Uploading admin/dist/index.html -> /cashback-qr.poscenter.kz/.index.html.upload-c4818b48 (size=3093)...
Verified .index.html.upload-c4818b48 matches local. Renaming to index.html...
SUCCESS: /cashback-qr.poscenter.kz/index.html deployed and verified. SHA-256: c4d8a0ce86927d3bdba26e0eb2a35695579e57aa539526222016956c6c7fa92d
Checking for leftover temp files across deployed directories...
All files successfully uploaded and verified on FTPS.
```

---

## 6. Проверка на живом сайте (Шаг 6)

### 6.1. HTTPS-проверка файлов (`Cache-Control: no-cache`)

```text
=== 1. Проверка загруженных файлов по HTTPS ===
[OK] assets/AdminRoutes-DjcZG90E.js: HTTP 200, Content-Type: application/javascript
     Local:  size=166489, sha256=d43ac7e6cddb57f43dcc9922eed522abbe04716ed3a67f9cf7c1a7a68ee38de1
     Remote: size=166489, sha256=d43ac7e6cddb57f43dcc9922eed522abbe04716ed3a67f9cf7c1a7a68ee38de1
[OK] assets/index-DQNyNZIy.js: HTTP 200, Content-Type: application/javascript
     Local:  size=305284, sha256=5050515838c0aaf69be6e08417fa4a1eba31588a4b1e0d7fa3a87bd843572b25
     Remote: size=305284, sha256=5050515838c0aaf69be6e08417fa4a1eba31588a4b1e0d7fa3a87bd843572b25
[OK] assets/index-Du9yweo4.css: HTTP 200, Content-Type: text/css
     Local:  size=45660, sha256=1fd764a8f6f0e60f3a10ef085f74717436e29ba353bfb0f3e0e22d38d77265c4
     Remote: size=45660, sha256=1fd764a8f6f0e60f3a10ef085f74717436e29ba353bfb0f3e0e22d38d77265c4
[OK] landing/screen-home.png: HTTP 200, Content-Type: image/png
     Local:  size=563373, sha256=c3500d85685c5447ef978e282a07214ded6a10bc79866485c48fa3e8de395280
     Remote: size=563373, sha256=c3500d85685c5447ef978e282a07214ded6a10bc79866485c48fa3e8de395280
[OK] landing/screen-qr.png: HTTP 200, Content-Type: image/png
     Local:  size=51324, sha256=7786700af5f33b2c1187a70b24d253a98df2e6c188b58b38be5af2bb4111bb23
     Remote: size=51324, sha256=7786700af5f33b2c1187a70b24d253a98df2e6c188b58b38be5af2bb4111bb23
[OK] index.html: HTTP 200, Content-Type: text/html
     Local:  size=3093, sha256=c4d8a0ce86927d3bdba26e0eb2a35695579e57aa539526222016956c6c7fa92d
     Remote: size=3093, sha256=c4d8a0ce86927d3bdba26e0eb2a35695579e57aa539526222016956c6c7fa92d

=== 2. SHA-256 живой главной страницы ===
Live home SHA-256:  c4d8a0ce86927d3bdba26e0eb2a35695579e57aa539526222016956c6c7fa92d
Dist index SHA-256: c4d8a0ce86927d3bdba26e0eb2a35695579e57aa539526222016956c6c7fa92d

=== 3. Проверка временных файлов на сервере ===
Checking /cashback-qr.poscenter.kz: temp_files count = 0
Checking /cashback-qr.poscenter.kz/assets: temp_files count = 0
Checking /cashback-qr.poscenter.kz/landing: temp_files count = 0
No temp files found anywhere on server.

=== 4. Проверка APK 1.0.10 ===
APK size: 68600435 (expected 68600435), Content-Type: application/vnd.android.package-archive

=== 5. Проверка version.json ===
version.json size: 169, Content-Type: application/json
version.json content: {
  "latest_version": "1.0.10",
  "latest_version_code": 11,
  "min_version_code": 1,
  "download_url": "https://cashback-qr.poscenter.kz/app/cashback-one-1.0.10.apk"
}
version.json sha256: 7e1c460a67c79823afd5fff7a5af1cf02ddfc124f556510c5d723dcddc4bd64b
```

### 6.2. Проверка в браузере (Google Chrome, Playwright)

Тестировались 4 комбинации языка и разрешения на живом сайте `https://cashback-qr.poscenter.kz/`, а также страница `/admin/login`:

```text
=================== Checking RU 390px (https://cashback-qr.poscenter.kz/) ===================
H1 font-family: Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif
H1 text: Бонусная карта в телефоне
Found 4 tabs:
  Tab 0 ('Карта'): font-family=Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif
  Tab 1 ('QR-код'): font-family=Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif
  Tab 2 ('История'): font-family=Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif
  Tab 3 ('Акции'): font-family=Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif
Bonus section bg: rgb(255, 58, 77), color: rgb(255, 255, 255)
Bonus H2 color: rgb(255, 255, 255), lead color: rgb(255, 255, 255)
Bonus card color: rgb(29, 27, 28)
Active QR tab img src: /landing/screen-qr.png, visible: True, natural dims: 780x1688
Contains 'штрихкод': False
Horizontal scroll: False
Console errors: []

=================== Checking RU 1366px (https://cashback-qr.poscenter.kz/) ===================
H1 font-family: Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif
H1 text: Бонусная карта в телефоне
Found 4 tabs:
  Tab 0 ('Карта'): font-family=Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif
  Tab 1 ('QR-код'): font-family=Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif
  Tab 2 ('История'): font-family=Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif
  Tab 3 ('Акции'): font-family=Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif
Bonus section bg: rgb(255, 58, 77), color: rgb(255, 255, 255)
Bonus H2 color: rgb(255, 255, 255), lead color: rgb(255, 255, 255)
Bonus card color: rgb(29, 27, 28)
Active QR tab img src: /landing/screen-qr.png, visible: True, natural dims: 780x1688
Contains 'штрихкод': False
Horizontal scroll: False
Console errors: []

=================== Checking KK 390px (https://cashback-qr.poscenter.kz/?lang=kk) ===================
H1 font-family: Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif
H1 text: Бонустық карта телефоныңызда
Found 4 tabs:
  Tab 0 ('Карта'): font-family=Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif
  Tab 1 ('QR-код'): font-family=Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif
  Tab 2 ('Тарих'): font-family=Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif
  Tab 3 ('Акциялар'): font-family=Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif
Bonus section bg: rgb(255, 58, 77), color: rgb(255, 255, 255)
Bonus H2 color: rgb(255, 255, 255), lead color: rgb(255, 255, 255)
Bonus card color: rgb(29, 27, 28)
Active QR tab img src: /landing/screen-qr.png, visible: True, natural dims: 780x1688
Contains 'штрихкод': False
Horizontal scroll: False
Console errors: []

=================== Checking KK 1366px (https://cashback-qr.poscenter.kz/?lang=kk) ===================
H1 font-family: Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif
H1 text: Бонустық карта телефоныңызда
Found 4 tabs:
  Tab 0 ('Карта'): font-family=Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif
  Tab 1 ('QR-код'): font-family=Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif
  Tab 2 ('Тарих'): font-family=Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif
  Tab 3 ('Акциялар'): font-family=Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif
Bonus section bg: rgb(255, 58, 77), color: rgb(255, 255, 255)
Bonus H2 color: rgb(255, 255, 255), lead color: rgb(255, 255, 255)
Bonus card color: rgb(29, 27, 28)
Active QR tab img src: /landing/screen-qr.png, visible: True, natural dims: 780x1688
Contains 'штрихкод': False
Horizontal scroll: False
Console errors: []

=================== Checking /admin/login ===================
Login body font-family: Times
Login element font-family: Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif
Login form visible: True
Console errors (excluding 401 session check): []

ALL BROWSER CHECKS PASSED ON LIVE SITE!
```

---

## 7. План отката

В случае необходимости отката:
1. Загрузить по FTPS файлы из резервной копии `~/.local/share/cashback-one/backups/landing-20261102T100027Z-roboto/`:
   - `screen-home.png` -> `/cashback-qr.poscenter.kz/landing/screen-home.png`
   - `index.html` -> `/cashback-qr.poscenter.kz/index.html`
2. После возврата этих двух файлов живой сайт немедленно начнёт ссылаться на прежний CSS/JS и прежний скриншот. Старые файлы ассетов на сервере сохранены и не удалялись.

---

## 8. Не проверено

1. Физическое сканирование QR-кода с экрана телефона 2D-сканером реальной кассы (POS-терминала).
2. Отображение в браузере под реальной ОС Windows (проверка проводилась в Chromium/Google Chrome на macOS).
