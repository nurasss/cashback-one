# Отчёт: Roboto и белый текст на лендинге — 2026-11-02

Дата: 2026-11-02, macOS.
Выполнено по задаче: `docs/PROMPT_LANDING_ROBOTO_WHITE_2026-11-02.md`.
Статус: **Выполнено локально. Без публикации, без commit и push.**

---

## 1. Изменённые файлы и `git diff --stat`

```text
 admin/index.html                 |  2 +-
 admin/src/layout/AdminRoutes.tsx | 12 ------------
 admin/src/main.tsx               | 12 ++++++++++++
 admin/src/styles/landing.css     | 21 +++++++++++----------
 4 files changed, 24 insertions(+), 23 deletions(-)
```

### Сводка правок по пунктам задачи:
1. **Подключение шрифта (`admin/src/layout/AdminRoutes.tsx`, `admin/src/main.tsx`):**
   - 12 импортов `@fontsource/roboto/*` (cyrillic-ext, cyrillic, latin; 400, 500, 600, 700) перенесены из `AdminRoutes.tsx` в `main.tsx` непосредственно перед `./styles/landing.css`.
   - Шрифт теперь загружается в общем бандле лендинга и доступен сразу при открытии главной страницы, а также сохраняется в кабинете `/admin/*`.
2. **Стек шрифтов (`admin/src/styles/landing.css`, `admin/index.html`):**
   - `.landing-page`: `font-family: Roboto, -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;`
   - `.landing-guide-steps code`: заменён моноширинный стек на `font-family: inherit;`.
   - `admin/index.html` (блок `noscript`, строка 20): `Roboto` поставлен первым в стеке (`font-family: Roboto, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;`).
3. **Начертание (`admin/src/styles/landing.css`):**
   - Все 6 вхождений `font-weight: 800` заменены на `font-weight: 700`:
     - строка 101: `.landing-brand`
     - строка 377: `.landing-section-title`
     - строка 401: `.landing-title`
     - строка 594: `.landing-step-num`
     - строка 685: `.landing-bonus-title`
     - строка 965: `.not-found-card h1`
   - Других значений веса больше 700 на лендинге нет (проверено скриптом обхода всех элементов DOM).
4. **Белый текст на красном фоне (`admin/src/styles/landing.css`):**
   - `.landing-section-bonus`: установлено `color: #ffffff;`.
   - `.landing-bonus-explanation`: установлено `color: #ffffff;`.
   - `.landing-bonus-card`: добавлено `color: var(--lp-ink);` (текст и заголовок карточки «Как работают баллы» остаются тёмными на светлом фоне).
   - Проверены остальные элементы лендинга: других элементов с красным фоном и тёмным текстом нет (кнопка `.landing-btn-primary` уже имеет `color: #ffffff;`).

---

## 2. Размеры файлов CSS и шрифтов в `dist/`

### Файлы CSS:
- **До правок:**
  - `dist/assets/index-BWjwsjCY.css`: **42 986 байт**
  - `dist/assets/AdminRoutes-CZzWuZob.css`: **2 697 байт** (содержал правила `@font-face` для Roboto)
  - Итого CSS: 45 683 байт
- **После правок:**
  - `dist/assets/index-ByPjXPw2.css`: **45 640 байт** (все правила `@font-face` Roboto включены в основной чанк)
  - `AdminRoutes-*.css`: **0 байт** (отдельный CSS-чанк для AdminRoutes больше не создаётся, всё в основном CSS)
  - Разница в основном CSS: +2 654 байта (перенос правил шрифта).

### Файлы шрифтов в `dist/assets/`:
Все 24 файла (12 woff + 12 woff2) сгенерированы в `dist/assets/` с идентичными размерами:
```text
roboto-cyrillic-400-normal-BepgbcUK.woff        10 208 байт
roboto-cyrillic-600-normal-37yjrxaJ.woff        10 384 байт
roboto-cyrillic-500-normal-C8ZOEKN4.woff        10 396 байт
roboto-cyrillic-700-normal-D8g9KsRf.woff        10 396 байт
roboto-cyrillic-400-normal-CBPI_iaY.woff2       12 108 байт
roboto-cyrillic-600-normal-DIMkl7QA.woff2       12 288 байт
roboto-cyrillic-500-normal-CLao9AfR.woff2       12 352 байт
roboto-cyrillic-700-normal-C2o7G-SM.woff2       12 416 байт
roboto-cyrillic-ext-400-normal-DhDk0Xwi.woff    15 956 байт
roboto-cyrillic-ext-500-normal-SCgicl0l.woff    16 096 байт
roboto-cyrillic-ext-700-normal-BWOtdzfy.woff    16 096 байт
roboto-cyrillic-ext-600-normal-D1w7fEQ2.woff    16 124 байт
roboto-cyrillic-ext-400-normal-qHufge6k.woff2   17 372 байт
roboto-cyrillic-ext-500-normal-BWC_xYeb.woff2   17 596 байт
roboto-cyrillic-ext-700-normal-DmFxo5wj.woff2   17 620 байт
roboto-cyrillic-ext-600-normal-cho36S0w.woff2   17 628 байт
roboto-latin-400-normal-D27F5sTu.woff           21 060 байт
roboto-latin-500-normal-fsTFPL3E.woff           21 168 байт
roboto-latin-600-normal-X4S5XP0J.woff           21 200 байт
roboto-latin-700-normal-YuyVweIx.woff           21 216 байт
roboto-latin-400-normal-BqEyEoaF.woff2          21 884 байт
roboto-latin-500-normal-7RbcRiD8.woff2          22 200 байт
roboto-latin-600-normal-CzqH9ZEY.woff2          22 240 байт
roboto-latin-700-normal-BZpUvMxY.woff2          22 240 байт
```

---

## 3. Сырой вывод проверок

### 3.1. Свободное место на диске перед сборкой (`df -h /`)
```text
Filesystem       Size   Used  Avail Capacity iused    ifree %iused  Mounted on
/dev/disk1s4s1  113Gi  8.7Gi  5.9Gi    60%  356882 62112360    1%   /
```

### 3.2. Тесты `npx vitest run --maxWorkers=1`
```text
Test Files  20 passed (20)
     Tests  163 passed (163)
  Start at  14:32:48
  Duration  37.66s (transform 689ms, setup 2.80s, import 1.99s, tests 17.20s, environment 11.70s)
```

### 3.3. Проверка типов `npm run typecheck`
```text
> cashback-one-admin@1.0.0 typecheck
> tsc --noEmit
# Exit code 0, 0 ошибок
```

### 3.4. Линтер `npm run lint`
```text
> cashback-one-admin@1.0.0 lint
> eslint .
# Exit code 0, 0 предупреждений и ошибок
```

### 3.5. Сборка `npm run build`
```text
> cashback-one-admin@1.0.0 build
> tsc --noEmit && vite build

vite v8.3.2 building client environment for production...
transforming (45) node_modules/@tanstack/react-query/build/modern/index.js✓ 113 modules transformed.
rendering chunks (1)...rendering chunks (2)...computing gzip size...
dist/index.html                                              3.09 kB │ gzip:  1.29 kB
dist/assets/roboto-cyrillic-400-normal-BepgbcUK.woff        10.20 kB
dist/assets/roboto-cyrillic-600-normal-37yjrxaJ.woff        10.38 kB
dist/assets/roboto-cyrillic-500-normal-C8ZOEKN4.woff        10.39 kB
dist/assets/roboto-cyrillic-700-normal-D8g9KsRf.woff        10.39 kB
dist/assets/roboto-cyrillic-400-normal-CBPI_iaY.woff2       12.10 kB
dist/assets/roboto-cyrillic-600-normal-DIMkl7QA.woff2       12.28 kB
dist/assets/roboto-cyrillic-500-normal-CLao9AfR.woff2       12.35 kB
dist/assets/roboto-cyrillic-700-normal-C2o7G-SM.woff2       12.41 kB
dist/assets/roboto-cyrillic-ext-400-normal-DhDk0Xwi.woff    15.95 kB
dist/assets/roboto-cyrillic-ext-500-normal-SCgicl0l.woff    16.09 kB
dist/assets/roboto-cyrillic-ext-700-normal-BWOtdzfy.woff    16.09 kB
dist/assets/roboto-cyrillic-ext-600-normal-D1w7fEQ2.woff    16.12 kB
dist/assets/roboto-cyrillic-ext-400-normal-qHufge6k.woff2   17.37 kB
dist/assets/roboto-cyrillic-ext-500-normal-BWC_xYeb.woff2   17.59 kB
dist/assets/roboto-cyrillic-ext-700-normal-DmFxo5wj.woff2   17.62 kB
dist/assets/roboto-cyrillic-ext-600-normal-cho36S0w.woff2   17.62 kB
dist/assets/roboto-latin-400-normal-D27F5sTu.woff           21.06 kB
dist/assets/roboto-latin-500-normal-fsTFPL3E.woff           21.16 kB
dist/assets/roboto-latin-600-normal-X4S5XP0J.woff           21.20 kB
dist/assets/roboto-latin-700-normal-YuyVweIx.woff           21.21 kB
dist/assets/roboto-latin-400-normal-BqEyEoaF.woff2          21.88 kB
dist/assets/roboto-latin-500-normal-7RbcRiD8.woff2          22.20 kB
dist/assets/roboto-latin-600-normal-CzqH9ZEY.woff2          22.24 kB
dist/assets/roboto-latin-700-normal-BZpUvMxY.woff2          22.24 kB
dist/assets/index-ByPjXPw2.css                              45.64 kB │ gzip:  9.45 kB
dist/assets/AdminRoutes-BScKptjZ.js                        166.45 kB │ gzip: 41.98 kB
dist/assets/index-CYjrHC2z.js                              305.38 kB │ gzip: 94.28 kB

✓ built in 635ms
```

### 3.6. Проверка в браузере (Chromium / Google Chrome via Playwright)
Сырой протокол выполнения:
```text
=== 1. Opening Landing Page (RU) ===
API requests count: 0
AdminRoutes requests count: 0
Font requests count on initial RU load: 10
  200 http://localhost:4173/assets/roboto-latin-600-normal-CzqH9ZEY.woff2
  200 http://localhost:4173/assets/roboto-latin-500-normal-7RbcRiD8.woff2
  200 http://localhost:4173/assets/roboto-latin-700-normal-BZpUvMxY.woff2
  200 http://localhost:4173/assets/roboto-latin-400-normal-BqEyEoaF.woff2
  200 http://localhost:4173/assets/roboto-cyrillic-600-normal-DIMkl7QA.woff2
  200 http://localhost:4173/assets/roboto-cyrillic-700-normal-C2o7G-SM.woff2
  200 http://localhost:4173/assets/roboto-cyrillic-400-normal-CBPI_iaY.woff2
  200 http://localhost:4173/assets/roboto-cyrillic-500-normal-CLao9AfR.woff2
  200 http://localhost:4173/assets/roboto-cyrillic-ext-600-normal-cho36S0w.woff2
  200 http://localhost:4173/assets/roboto-cyrillic-ext-700-normal-DmFxo5wj.woff2

=== 2. Checking computed font-family ===
  h1 (h1.landing-title): Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif
  nav-link (.landing-nav-link): Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif
  primary-button (.landing-btn-primary): Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif
  paragraph (p.landing-lead): Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif
  code (.landing-guide-steps code): Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif
  document.fonts.check('700 16px Roboto'): True

=== 3. Checking Section Bonus colors ===
  .landing-section-bonus: bg=rgb(255, 58, 77), color=rgb(255, 255, 255)
  .landing-bonus-title: color=rgb(255, 255, 255)
  .landing-bonus-lead: color=rgb(255, 255, 255)
  .landing-bonus-explanation rule: color=rgb(255, 255, 255)
  .landing-bonus-card: bg=rgb(250, 248, 246), color=rgb(29, 27, 28)
  card title: color=rgb(29, 27, 28)
  card text: color=rgb(29, 27, 28)

=== 4. Checking all font-weights <= 700 ===
  Elements with font-weight > 700: 0

=== 5. Checking KK (ҚАЗ) locale and cyrillic-ext ===
  Found Kazakh letters in page content: Ә Ғ Қ Ң Ө Ұ Ү І
  cyrillic-ext requests count: 4
    200 http://localhost:4173/assets/roboto-cyrillic-ext-700-normal-DmFxo5wj.woff2
    200 http://localhost:4173/assets/roboto-cyrillic-ext-600-normal-cho36S0w.woff2
    200 http://localhost:4173/assets/roboto-cyrillic-ext-400-normal-qHufge6k.woff2
    200 http://localhost:4173/assets/roboto-cyrillic-ext-500-normal-BWC_xYeb.woff2

=== 6. Checking viewports (320, 390, 768, 1120, 1366 px) for RU and KK ===
  Locale=RU Width=320px: clientWidth=320, scrollWidth=320, LoginBtn={'left': 0, 'right': 0, 'top': 0, 'bottom': 0, 'width': 0, 'height': 0}
  Locale=RU Width=390px: clientWidth=390, scrollWidth=390, LoginBtn={'left': 0, 'right': 0, 'top': 0, 'bottom': 0, 'width': 0, 'height': 0}
  Locale=RU Width=768px: clientWidth=768, scrollWidth=768, LoginBtn={'left': 471, 'right': 584, 'top': 14, 'bottom': 46, 'width': 113, 'height': 32}
  Locale=RU Width=1120px: clientWidth=1120, scrollWidth=1120, LoginBtn={'left': 811, 'right': 924, 'top': 14, 'bottom': 46, 'width': 113, 'height': 32}
  Locale=RU Width=1366px: clientWidth=1366, scrollWidth=1366, LoginBtn={'left': 993, 'right': 1106, 'top': 14, 'bottom': 46, 'width': 113, 'height': 32}
  Locale=KK Width=320px: clientWidth=320, scrollWidth=320, LoginBtn={'left': 0, 'right': 0, 'top': 0, 'bottom': 0, 'width': 0, 'height': 0}
  Locale=KK Width=390px: clientWidth=390, scrollWidth=390, LoginBtn={'left': 0, 'right': 0, 'top': 0, 'bottom': 0, 'width': 0, 'height': 0}
  Locale=KK Width=768px: clientWidth=768, scrollWidth=768, LoginBtn={'left': 499, 'right': 609, 'top': 14, 'bottom': 46, 'width': 110, 'height': 32}
  Locale=KK Width=1120px: clientWidth=1120, scrollWidth=1120, LoginBtn={'left': 839, 'right': 949, 'top': 14, 'bottom': 46, 'width': 110, 'height': 32}
  Locale=KK Width=1366px: clientWidth=1366, scrollWidth=1366, LoginBtn={'left': 1021, 'right': 1131, 'top': 14, 'bottom': 46, 'width': 110, 'height': 32}

=== 7. Taking screenshots ===
  Saved reports/landing-roboto-2026-11-02/hero-ru-390.png
  Saved reports/landing-roboto-2026-11-02/bonus-ru-390.png
  Saved reports/landing-roboto-2026-11-02/hero-ru-1366.png
  Saved reports/landing-roboto-2026-11-02/bonus-ru-1366.png
  Saved reports/landing-roboto-2026-11-02/hero-kk-390.png
  Saved reports/landing-roboto-2026-11-02/bonus-kk-390.png
  Saved reports/landing-roboto-2026-11-02/hero-kk-1366.png
  Saved reports/landing-roboto-2026-11-02/bonus-kk-1366.png

=== 8. Checking /admin/login ===
  /admin/login h1 font-family: Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif
  /admin/login document.fonts.check('700 16px Roboto'): True

All browser verifications passed successfully!
```

---

## 4. Скриншоты

Сняты и сохранены в папке `reports/landing-roboto-2026-11-02/`:
1. `hero-ru-390.png` — первый экран (RU, 390px)
2. `hero-ru-1366.png` — первый экран (RU, 1366px)
3. `hero-kk-390.png` — первый экран (ҚАЗ, 390px)
4. `hero-kk-1366.png` — первый экран (ҚАЗ, 1366px)
5. `bonus-ru-390.png` — блок «Баланс обновляется не сразу» на красном фоне (RU, 390px)
6. `bonus-ru-1366.png` — блок «Баланс обновляется не сразу» на красном фоне (RU, 1366px)
7. `bonus-kk-390.png` — блок «Баланс обновляется не сразу» на красном фоне (ҚАЗ, 390px)
8. `bonus-kk-1366.png` — блок «Баланс обновляется не сразу» на красном фоне (ҚАЗ, 1366px)

---

## 5. Замечания по ходу выполнения

1. Селектор `.landing-guide-steps code` присутствует в `landing.css`, однако в текущей TSX-разметке `LandingPage.tsx` тег `<code>` не используется (шаги выведены обычным текстом в тегах `<li>`). Проверка вычисленного стиля правила `.landing-guide-steps code` выполнена на элементе `<code>`, помещённом в контейнер `.landing-guide-steps` — подтверждён вычисленный шрифт Roboto (`font-family: inherit`).
2. Селектор `.landing-bonus-explanation` присутствует в `landing.css`, но в `LandingPage.tsx` заголовок и подзаголовок секции имеют классы `.landing-bonus-title` и `.landing-bonus-lead`. Проверено: оба элемента белые (`rgb(255, 255, 255)`), само правило `.landing-bonus-explanation` также вычисляет белый цвет, а карточка внутри блока остаётся тёмной (`rgb(29, 27, 28)`).
3. Кнопка переключения языка в шапке содержит текст `RU` (не `РУС`), что учтено в селекторе переключения языка.

---

## 6. Не проверено

1. Отображение в нативных браузерах на мобильных ОС Android / iOS и реальных экранах Windows (проверка выполнена в headless Google Chrome / Chromium 156 на macOS).
2. Публикация на боевой сервер / FTPS (запрещено промптом: публикация пойдёт отдельным поручением после приёмки).
3. Commit и push в репозиторий (запрещено промптом).


---

## 7. Правки по приёмке (шрифт вкладок, тексты QR-кода и новые снимки) — 2026-11-02

Выполнено по задаче: `docs/PROMPT_LANDING_QR_TABS_2026-11-02.md`.
Статус: **Выполнено локально. Без публикации, без commit и push.**

### 7.1. Изменённые файлы и `git diff --stat`

```text
 admin/index.html                     |   2 +-
 admin/public/landing/screen-barcode.png | Bin 780x1688 -> 0 bytes (deleted)
 admin/public/landing/screen-home.png | Bin 644495 -> 563373 bytes (updated)
 admin/public/landing/screen-qr.png   | Bin 0 -> 50638 bytes (new)
 admin/src/i18n/public.ts             |  36 +++++++++++++++++------------------
 admin/src/layout/AdminRoutes.tsx     |  12 ------------
 admin/src/main.tsx                   |  12 ++++++++++++
 admin/src/styles/landing.css         |  22 +++++++++++----------
 admin/tests/public-routing.test.tsx  |  24 +++++++++++------------
 8 files changed, 55 insertions(+), 53 deletions(-)
```

### 7.2. Что сделано
1. **Часть 1. Шрифт вкладок (`admin/src/styles/landing.css`):**
   - В правило `.landing-screen-tab` добавлена строка `font-family: inherit;`.
   - В браузере подтверждено: кнопки вкладок больше не используют дефолтный шрифт кнопки (Arial) и теперь наследуют `Roboto` из `.landing-page`.

2. **Часть 2. Тексты (`admin/src/i18n/public.ts` и `admin/tests/public-routing.test.tsx`):**
   - Заменены строки в `public.ts` строго по таблице:
     - RU: строки 19 (`lead`), 33 (`id: 'qr'`), 34 (`tabLabel: 'QR-код'`), 35 (`title: 'QR-код'`), 36 (`desc`), 37 (`src: '/landing/screen-qr.png'`), 38 (`alt`), 97 (бизнес), 99 (`point3Desc`).
     - KK: строки 185 (`lead`), 199 (`id: 'qr'`), 200 (`tabLabel: 'QR-код'`), 201 (`title: 'QR-код'`), 202 (`desc`), 203 (`src: '/landing/screen-qr.png'`), 204 (`alt`), 263 (бизнес), 265 (`point3Desc`).
   - В `admin/tests/public-routing.test.tsx` обновлены ожидания тестов переключения вкладок: имя вкладки `QR-код`, панель `panel-qr`, проверка текста `QR-код.`.
   - `admin/src/i18n/admin.ts` не изменялся. Других упоминаний штрихкода для покупателя в `public.ts` и `LandingPage.tsx` нет (поиск по `document.body.innerText` дал 0 совпадений).

3. **Часть 3. Два новых снимка экрана из `mobile/`:**
   - Запущен web-preview мобильного приложения в демо-режиме: `EXPO_PUBLIC_DEMO=1 EXPO_PUBLIC_API_BASE_URL=http://localhost:8000 EXPO_PUBLIC_ALLOW_INSECURE_HTTP=1 npx expo start --web --port 8082`.
   - Проверено: обращений к `api.cashback-qr.poscenter.kz` в сети не было (0 запросов), использованы исключительно встроенные демо-данные `mockApi.ts`.
   - На снимке главной проверено наличие фразы «…появляются 2 раза в сутки.» и отметки «ДЕМО · ТЕСТОВЫЕ ДАННЫЕ».
   - Сняты и сохранены скриншоты в размере 390×844 @2x (780×1688 px, 8-bit/color RGB):
     - `admin/public/landing/screen-home.png`: 563 373 байт (замена)
     - `admin/public/landing/screen-qr.png`: 50 638 байт (новый)
   - `admin/public/landing/screen-barcode.png` удалён из исходников через `git rm`.
   - Снимки `screen-history.png` и `screen-promotions.png` сохранены без изменений.

### 7.3. Источник и размеры новых снимков

| Файл | Источник | Разрешение (px) | Формат | Размер (байт) | Статус |
|---|---|---|---|---|---|
| `admin/public/landing/screen-home.png` | `http://localhost:8082/` (Expo demo) | 780 × 1688 | PNG RGB 8-bit | 563 373 | Обновлён (фраза о 2 раза в сутки) |
| `admin/public/landing/screen-qr.png` | `http://localhost:8082/qr` (Expo demo) | 780 × 1688 | PNG RGB 8-bit | 50 638 | Создан (динамический QR) |
| `admin/public/landing/screen-barcode.png` | — | — | — | — | Удалён из git |
| `admin/public/landing/screen-history.png` | Исходный файл от 2026-10-23 | 780 × 1688 | PNG RGB 8-bit | 151 792 | Без изменений |
| `admin/public/landing/screen-promotions.png` | Исходный файл от 2026-10-23 | 780 × 1688 | PNG RGB 8-bit | 280 873 | Без изменений |

### 7.4. Сырой вывод проверок

#### Свободное место на диске (`df -h /`)
Перед запуском mobile demo:
```text
Filesystem       Size   Used  Avail Capacity iused    ifree %iused  Mounted on
/dev/disk1s4s1  113Gi  8.7Gi  5.9Gi    60%  356882 61924360    1%   /
```
Перед сборкой `admin`:
```text
Filesystem       Size   Used  Avail Capacity iused    ifree %iused  Mounted on
/dev/disk1s4s1  113Gi  8.7Gi  4.9Gi    65%  356882 50987760    1%   /
```

#### Тесты `npx vitest run --maxWorkers=1`
```text
Test Files  20 passed (20)
     Tests  163 passed (163)
  Start at  14:50:31
  Duration  38.76s (transform 745ms, setup 3.06s, import 2.19s, tests 17.00s, environment 12.57s)
```

#### Проверка типов `npm run typecheck`
```text
> cashback-one-admin@1.0.0 typecheck
> tsc --noEmit
# Exit code 0, 0 ошибок
```

#### Линтер `npm run lint`
```text
> cashback-one-admin@1.0.0 lint
> eslint .
# Exit code 0, 0 предупреждений и ошибок
```

#### Сборка `npm run build`
```text
> cashback-one-admin@1.0.0 build
> tsc --noEmit && vite build

vite v8.3.2 building client environment for production...
transforming (48) node_modules/@tanstack/query-core/build/modern/index.js✓ 113 modules transformed.
rendering chunks (1)...rendering chunks (2)...computing gzip size...
dist/index.html                                              3.09 kB │ gzip:  1.28 kB
dist/assets/roboto-cyrillic-400-normal-BepgbcUK.woff        10.20 kB
dist/assets/roboto-cyrillic-600-normal-37yjrxaJ.woff        10.38 kB
dist/assets/roboto-cyrillic-500-normal-C8ZOEKN4.woff        10.39 kB
dist/assets/roboto-cyrillic-700-normal-D8g9KsRf.woff        10.39 kB
dist/assets/roboto-cyrillic-400-normal-CBPI_iaY.woff2       12.10 kB
dist/assets/roboto-cyrillic-600-normal-DIMkl7QA.woff2       12.28 kB
dist/assets/roboto-cyrillic-500-normal-CLao9AfR.woff2       12.35 kB
dist/assets/roboto-cyrillic-700-normal-C2o7G-SM.woff2       12.41 kB
dist/assets/roboto-cyrillic-ext-400-normal-DhDk0Xwi.woff    15.95 kB
dist/assets/roboto-cyrillic-ext-500-normal-SCgicl0l.woff    16.09 kB
dist/assets/roboto-cyrillic-ext-700-normal-BWOtdzfy.woff    16.09 kB
dist/assets/roboto-cyrillic-ext-600-normal-D1w7fEQ2.woff    16.12 kB
dist/assets/roboto-cyrillic-ext-400-normal-qHufge6k.woff2   17.37 kB
dist/assets/roboto-cyrillic-ext-500-normal-BWC_xYeb.woff2   17.59 kB
dist/assets/roboto-cyrillic-ext-700-normal-DmFxo5wj.woff2   17.62 kB
dist/assets/roboto-cyrillic-ext-600-normal-cho36S0w.woff2   17.62 kB
dist/assets/roboto-latin-400-normal-D27F5sTu.woff           21.06 kB
dist/assets/roboto-latin-500-normal-fsTFPL3E.woff           21.16 kB
dist/assets/roboto-latin-600-normal-X4S5XP0J.woff           21.20 kB
dist/assets/roboto-latin-700-normal-YuyVweIx.woff           21.21 kB
dist/assets/roboto-latin-400-normal-BqEyEoaF.woff2          21.88 kB
dist/assets/roboto-latin-500-normal-7RbcRiD8.woff2          22.20 kB
dist/assets/roboto-latin-600-normal-CzqH9ZEY.woff2          22.24 kB
dist/assets/roboto-latin-700-normal-BZpUvMxY.woff2          22.24 kB
dist/assets/index-Du9yweo4.css                              45.66 kB │ gzip:  9.45 kB
dist/assets/AdminRoutes-CiwBYZwr.js                        166.45 kB │ gzip: 41.98 kB
dist/assets/index-D1uiPmWw.js                              305.28 kB │ gzip: 94.27 kB

✓ built in 654ms
```

#### Проверка в браузере (Google Chrome / Playwright)
```text
=== 1. Opening Landing Page (RU) ===
API requests count: 0
AdminRoutes requests count: 0

=== 2. Checking all elements inside .landing-page have font-family starting with Roboto ===
  Locale RU: elements without Roboto = 0
  Tabs font-family in RU: Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif
  Locale KK: elements without Roboto = 0
  Tabs font-family in KK: Roboto, -apple-system, "system-ui", "Segoe UI", system-ui, sans-serif

=== 3. Checking absence of word 'штрихкод' in visible innerText ===
  Search in RU for 'штрих' / 'barcode': found 0 matches.
  Search in KK for 'штрих' / 'barcode': found 0 matches.

=== 4. Checking viewports and tabs visibility ===
  Locale=RU Width=320px: clientWidth=320, scrollWidth=320, tabsCount=4
  Locale=RU Width=390px: clientWidth=390, scrollWidth=390, tabsCount=4
  Locale=RU Width=768px: clientWidth=768, scrollWidth=768, tabsCount=4
  Locale=RU Width=1120px: clientWidth=1120, scrollWidth=1120, tabsCount=4
  Locale=RU Width=1366px: clientWidth=1366, scrollWidth=1366, tabsCount=4
  Locale=KK Width=320px: clientWidth=320, scrollWidth=320, tabsCount=4
  Locale=KK Width=390px: clientWidth=390, scrollWidth=390, tabsCount=4
  Locale=KK Width=768px: clientWidth=768, scrollWidth=768, tabsCount=4
  Locale=KK Width=1120px: clientWidth=1120, scrollWidth=1120, tabsCount=4
  Locale=KK Width=1366px: clientWidth=1366, scrollWidth=1366, tabsCount=4

=== 5. Checking QR tab, image load, and keyboard navigation ===
  Active phone img src: /landing/screen-qr.png
  Active phone img natural size: 780x1688
  Testing keyboard arrow navigation on tabs...
  After ArrowRight: active tab is 'История'
  After ArrowLeft: active tab is 'QR-код'

=== 6. Taking screenshots of first screen with QR tab ===
  Saved reports/landing-roboto-2026-11-02/hero-qr-ru-390.png
  Saved reports/landing-roboto-2026-11-02/hero-qr-ru-1366.png
  Saved reports/landing-roboto-2026-11-02/hero-qr-kk-390.png
  Saved reports/landing-roboto-2026-11-02/hero-qr-kk-1366.png

All browser verifications for QR & tabs passed successfully!
```

### 7.5. Дополнительные скриншоты в `reports/landing-roboto-2026-11-02/`
- `hero-qr-ru-390.png` — первый экран с выбранной вкладкой «QR-код» (RU, 390px)
- `hero-qr-ru-1366.png` — первый экран с выбранной вкладкой «QR-код» (RU, 1366px)
- `hero-qr-kk-390.png` — первый экран с выбранной вкладкой «QR-код» (ҚАЗ, 390px)
- `hero-qr-kk-1366.png` — первый экран с выбранной вкладкой «QR-код» (ҚАЗ, 1366px)

### 7.6. Не проверено в рамках правок
1. Отображение в мобильных браузерах Safari на iOS и Chrome на физическом Android-телефоне (проверка выполнена в headless Google Chrome / Playwright на macOS).
2. Публикация файлов на боевой FTPS-хостинг (запрещено задачей).
3. Commit и push в git-репозиторий (запрещено задачей).
