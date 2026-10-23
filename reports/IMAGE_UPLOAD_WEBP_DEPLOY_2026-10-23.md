# Выкладка загрузки картинок (WebP → хостинг) — 2026-10-23

## Итог

По поручению владельца выкачено: в админке картинки баннеров/предложений и логотипы бизнеса можно загружать файлом. Backend конвертирует в WebP (без EXIF/GPS/ICC, до 1600 px промо / 512 px логотип) и кладёт на хостинг сайта по FTPS в `media/promotions|logos/<uuid>.webp`. Ссылка вставляется вручную как раньше. Мобильное приложение и APK не менялись.

Реализация — исполнитель (`reports/IMAGE_UPLOAD_WEBP_2026-10-23.md`, промпты `docs/PROMPT_IMAGE_UPLOAD_WEBP_2026-10-23.md`, `docs/PROMPT_IMAGE_UPLOAD_FIXES_2026-10-23.md`), два круга приёмки куратора. При выкладке куратор сам внёс две правки в `backend/app/services/media_storage.py`:

1. **TLS не выше 1.2** для FTPS: хостинг обрывает передачу на TLS 1.3 (`docs/DEPLOY_VPS.md`).
2. **Создание папок**: `_ensure_dir` шёл по относительному пути, после первого `cwd` строил путь заново от корня (`сайт/media` внутри `сайт/`) — первая реальная загрузка с VPS упала с `error_perm` (мусора на хостинге не осталось, проверено чтением). Теперь обход по сегментам с `mkd`+`cwd`; тест `test_ftps_put_creates_nested_dirs_under_relative_site_root` на модели FTP-сервера с рабочей папкой.

Перед выкладкой: backend **355 passed, 36 skipped, 0 failed**; ruff `backend/app` чисто (в `backend/tests` 2 давних замечания в `test_barcode_contract.py`, не менялся); admin 110 passed, typecheck, lint, build чистые.

## Резервные копии (VPS `/opt/cashback-one/backups/media-20261023T074603Z/`, права 700)

`pg.sql.gz` (проверен `gzip -t`), `env.bak` (600), `backend-src.tgz`, `Caddyfile.bak`. Образ отката: `cashback-backend:rollback-media-20261023T074603Z` (= прежний `local` 638f3eebde96). До выкладки исходники backend на VPS побайтно совпадали с коммитом 4c3ebf0/b352bc5 (HEAD).

## Шаги

1. **FTPS VPS → хостинг** проверен чтением из контейнера: TLS 1.2, вход, список папки сайта.
2. **`.env` на VPS**: дописаны `MEDIA_FTPS_HOST/PORT/USER/PASSWORD/ROOT_DIR`, `MEDIA_PUBLIC_BASE_URL=https://cashback-qr.poscenter.kz/media` (доступ тот же, что для сайта — решение владельца). Значения переданы через stdin, нигде не печатались; спецсимволов, опасных для env_file, нет. Права 600.
3. **Backend**: архив сверен по SHA-256, образ пересобран (Pillow 13.0.0, WebP поддерживается), `migration` + `backend` пересозданы. `/health/ready` — ready; публичный `POST /admin/media/images` без входа — 401. Пересборка повторена после правки п. 2.
4. **Caddy** (`/opt/timetrack/Caddyfile`, блок `api.cashback-qr.poscenter.kz`): прежний общий `request_body max_size 2MB` разделён — **12MB только для `/admin/media/images`**, 2MB для остального. `caddy validate` до записи, запись на месте (inode сохранён, контейнер видит новый файл), `caddy reload`. Проверено: 3 МБ на загрузку доходят до backend, 13 МБ → 413, 3 МБ на `/admin/auth/login` → 413. Соседние сайты отвечают. Ошибки ACME для `photo-search.viklik-market.kz` и `carwash.poscenter.kz` в логе Caddy были и до правки (с 05:23 UTC), к нам не относятся.
5. **Сайт**: копия `~/.local/share/cashback-one/backups/landing-20261023T075241Z-cb7967/` (прежний index `d99dd064…`). Загружены `AdminRoutes-CmohQRGo.js`, `index-CXKGYXHj.js`, `index-DnmPXAC2.css`, `index.html` последним (`9ce76cb3c2a1e7669012da2ce4cb6298d96f679d8cbcf1fe12f4edf861a7833b`). `.htaccess` не изменился. 39/39 файлов сверены по HTTPS. Вход открывается, ошибок кроме ожидаемых 401 нет.
6. **Реальная загрузка**: в рабочем контейнере тем же `FTPSMediaStorage` загружен тестовый WebP 1600×800 в `media/promotions/` → `GET` 200 `image/webp`, SHA-256 совпал → удалён. На хостинге остались пустые `media/promotions/`; временных файлов нет. HTTP-эндпоинт с авторизацией на production не вызывался (не входили в чужой аккаунт и не создавали пользователя); авторизация, конвертация и коды ошибок покрыты тестами.

## Замечания

- Несуществующий файл в `media/` отдаётся как `index.html` (SPA-fallback, 200 `text/html`). Для приложения это просто «картинка не загрузилась». При желании — отдельный `media/.htaccess`.
- Загруженные, но не сохранённые в форме файлы остаются на хостинге (известное ограничение).
- Не проверено: загрузка через интерфейс под настоящим администратором, логотипы (`media/logos/` будет создана при первой загрузке, тот же код), показ WebP в приложении на телефоне.

## Откат

Backend: `docker tag cashback-backend:rollback-media-20261023T074603Z cashback-backend:local && docker compose up -d --no-build --force-recreate backend`; при необходимости вернуть `.env` из `env.bak`. Caddy: `sudo tee /opt/timetrack/Caddyfile < backups/media-…/Caddyfile.bak` и `docker exec timetrack-caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile`. Сайт: загрузить `index.html` из копии во временное имя, сверить `d99dd064…`, переименовать.
