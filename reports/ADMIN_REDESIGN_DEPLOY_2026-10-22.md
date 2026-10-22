# Развёртывание обновлённой веб-панели управления (Admin Redesign & POSCENTER Branding)

Дата: 22 октября 2026 г.  
Задача: Обновление дизайна веб-админки, мобильная адаптация и интеграция официальной корпоративной символики POSCENTER, публикация в production (боевой контур).

---

## 1. Изменения интерфейса

1. **Официальные логотипы компании POSCENTER**:
   - `admin/public/brand-mark.png` (1892 байт) — официальный квадратный кораллово-красный знак «P» компании POSCENTER:
     - Интегрирован в качестве favicon (`admin/index.html`).
     - Размещён в шапке навигационного сайдбара (`AdminLayout.tsx`).
     - Размещён в промо-блоке экрана авторизации (`LoginPage.tsx`).
   - `admin/public/logo.png` (7762 байт) — горизонтальный логотип компании «POSCENTER.KZ · Республиканский центр автоматизации»:
     - Размещён в карточке входа (`LoginPage.tsx`) для десктопа и смартфонов.

2. **Мобильная адаптация**:
   - Навигационное меню преобразуется в горизонтальный скролл с фирменными векторными SVG-иконками разделов.
   - Сетка карточек показателей, формы фильтрации и табличные блоки оптимизированы под узкие мобильные экраны (от 320px).
   - Экран входа адаптирован под компактные экраны без горизонтальной прокрутки.

3. **Стили и правила целостности**:
   - Обновлён файл `admin/src/styles/admin.css`.
   - Сохранены требования `:root{` и баланс фигурных скобок `{}` (проверка `tests/css-integrity.test.ts`).

---

## 2. Локальное тестирование и сборка

- **Тестовый набор админки**: 10 файлов, **53 из 53 тестов** успешно пройдены (`vitest run --no-file-parallelism`).
- **Проверка типов**: `tsc --noEmit` — 0 ошибок.
- **Production сборка**: `vite build` — собрана успешно:
  - `dist/index.html` (577 байт)
  - `dist/assets/index-C9c33Q6h.js` (379 466 байт)
  - `dist/assets/index-DJ6O2qrk.css` (22 490 байт)
  - Изображения: `brand-mark.png`, `favicon.png`, `logo.png`, `logo-white.png`.

---

## 3. Процедура публикации на боевой сервер (FTPS)

1. **Резервное копирование**:
   - Перед публикацией скачан и сохранён текущий production `index.html` в `C:\cashback-stage0\backup_admin_20261022_051357\index.html`.
2. **Порядок загрузки (Zero Downtime)**:
   - Скрипт `scripts/upload_admin.py` обновлён с гарантией загрузки статических ассетов и картинок **ДО** обновления корневого `index.html`.
   - Загружены:
     - `assets/index-C9c33Q6h.js` (379 466 байт) — OK
     - `assets/index-DJ6O2qrk.css` (22 490 байт) — OK
     - `brand-mark.png` (1892 байт) — OK
     - `favicon.png` (1892 байт) — OK
     - `logo-white.png` (3353 байт) — OK
     - `logo.png` (7762 байт) — OK
     - `index.html` (577 байт) — OK (загружен последним)
3. **Сохранность инфраструктурных файлов**:
   - `.htaccess`, папки `demo/` и `app/` не затрагивались.

---

## 4. Проверка боевого контура (HTTPS)

Все URL проверены прямыми GET-запросами к боевому серверу:
- `https://cashback-qr.poscenter.kz/` → **HTTP 200** (577 байт, подтверждены ссылки на новые JS/CSS/favicon)
- `https://cashback-qr.poscenter.kz/brand-mark.png` → **HTTP 200** (1892 байт, побайтовое совпадение)
- `https://cashback-qr.poscenter.kz/logo.png` → **HTTP 200** (7762 байт, побайтовое совпадение)
- `https://cashback-qr.poscenter.kz/assets/index-DJ6O2qrk.css` → **HTTP 200** (22 490 байт, побайтовое совпадение)
- `https://cashback-qr.poscenter.kz/assets/index-C9c33Q6h.js` → **HTTP 200** (379 466 байт, побайтовое совпадение)
- `https://api.cashback-qr.poscenter.kz/health/ready` → **HTTP 200** (`{"status":"ready","components":{"database":"ok","redis":"ok"}}`)
