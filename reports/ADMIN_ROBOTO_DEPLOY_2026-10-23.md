# Публикация шрифта Roboto в кабинете — 2026-10-23

## Итог

Опубликовано по прямому поручению владельца: https://cashback-qr.poscenter.kz/ . Вход `/admin/login` и кабинет `/admin/*` используют Roboto (self-hosted, `@fontsource/roboto@5.3.0`, OFL-1.1). Лендинг `/` не изменился: прежний системный шрифт, файлы Roboto и чанк кабинета не загружаются. Backend, 1С, APK, `.htaccess`, `app/`, `demo/` не менялись.

Работу выполнил исполнитель (отчёт `reports/ADMIN_ROBOTO_2026-10-23.md`), куратор независимо принял её до публикации. Оговорка к отчёту исполнителя: его «сырой» вывод `df` (`/dev/disk3s1 460Gi`) не соответствует этому Mac (`/dev/disk1s5 113Gi`), поэтому этот фрагмент не принимается как доказательство. Остальные цифры куратор воспроизвёл сам.

## Проверки куратора перед публикацией

- `npm run typecheck`, `npm run lint`: exit 0.
- `npm test -- --maxWorkers=1`: **98 passed / 16 файлов**.
- Production build (`VITE_API_BASE_URL=https://api.cashback-qr.poscenter.kz`, `VITE_ALLOW_INSECURE_HTTP=0`): 39 файлов, имена ресурсов совпали со сборкой исполнителя (воспроизводимо). Ссылок на Google Fonts/gstatic нет; шрифты упоминаются только в `AdminRoutes-CZzWuZob.css`.
- Локальный браузер: на `/` нет запросов Roboto/AdminRoutes; на входе computed `font-family` начинается с Roboto; на ҚАЗ догружается cyrillic-ext; на 320 px элементы формы в границах.
- Наблюдение: наборы fontsource подключены файлами без `unicode-range`. Chrome корректно догружает нужный набор по наличию глифов (подтверждено статусами FontFace). Safari/Firefox не проверялись.

## Публикация

Временный двухфазный загрузчик (вне репозитория): `plan` — чтение и резервная копия, `apply` — загрузка во временное имя, проверка SHA-256 обратным скачиванием, rename, повторная сверка; `index.html` строго последним. Перед `apply` проверено, что удалённые `index.html` и `.htaccess` не изменились с момента плана. Секреты читались только в память. Штатный `scripts/upload_admin.py` не использовался: он перезаписывает `index.html` без временного файла и пишет копию в относительный путь `C:/cashback-stage0` (источник папки `C:/` в корне репозитория).

Python из Homebrew не имел корневых сертификатов (`CERTIFICATE_VERIFY_FAILED`); цепочка хостинга — DigiCert. Использован системный набор macOS `SSL_CERT_FILE=/etc/ssl/cert.pem`, проверка сертификата не отключалась.

- Резервная копия: `~/.local/share/cashback-one/backups/landing-20261023T062108Z-aadc65/` (`index.html`, `.htaccess`, `robots.txt`, `sitemap.xml`, `manifest.json`, `published.json`).
- Прежний `index.html`: `a9eadc0c8e6a967d3cc0d213930e7abc71f03256b81e7b2468f1dfce382559c2` (совпал с версией RU/ҚАЗ-публикации).
- Новый `index.html`: `d99dd0649c660b656da3fc57b52df76ce83ecb1a0c55a1ee03cb4f4ae22d49ee`.
- Загружено 29 файлов: `AdminRoutes-CZzWuZob.css`, `AdminRoutes-DXjwWHtc.js`, `index-CK6mWq8J.css`, `index-kVDMUDa7.js`, 24 файла Roboto (woff2 + woff, 400/500/600/700 × latin/cyrillic/cyrillic-ext), `index.html`. 10 файлов идентичны и пропущены.
- `.htaccess` после публикации не изменился: `08a66d1cb57680bc68dffb6610af5173b33c2aafc828a0930f1439a16c3259bd`.

## Проверки после публикации

- Все **39/39** файлов сборки скачаны по HTTPS, SHA-256 совпадают с локальным `dist`.
- `/` — 200, `Cache-Control: no-store`, `X-Frame-Options: DENY`, CSP прежний. `/admin/login`, `/login`, `/demo/` — 200. APK 1.0.3 — 51 167 439 байт. woff2 отдаётся как `font/woff2` с `nosniff`.
- Браузер на production: hero «Бонусная карта в телефоне», шрифт лендинга прежний, 0 запросов Roboto/AdminRoutes на главной. На `/admin/login` кнопка — Roboto, `document.fonts.check('16px Roboto') = true`, все шрифты с собственного origin, ошибок CSP нет (единственная ошибка консоли — ожидаемый 401 refresh без сессии).
- Не проверено: авторизованные страницы кабинета, Safari/Firefox, физический телефон.

## Откат

Загрузить `index.html` из резервной копии во временное имя, сверить SHA-256 `a9eadc0c…`, переименовать в `index.html`. Прежние ресурсы (`index-fEgKIOeN.js`, `index-DzLERtFd.css`, `AdminRoutes-v2B4Q7c7.js`) остаются на сервере.
