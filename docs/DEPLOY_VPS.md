# Развёртывание: сервер на VPS, админка на хостинге

## Что где работает

| Часть | Адрес | Где |
|---|---|---|
| API (FastAPI) | https://api.cashback-qr.poscenter.kz | VPS `kz-vps`, папка `/opt/cashback-one` (Docker Compose, проект `cashback`) |
| Админка (статика) | https://cashback-qr.poscenter.kz | Хостинг Plesk, папка `cashback-qr.poscenter.kz`, загрузка по FTPS |
| HTTPS для API | Let's Encrypt, выпускает и продлевает Caddy | Существующий Caddy проекта `timetrack` (`/opt/timetrack/Caddyfile`) |

VPS общий: рядом работают чужие проекты. Наши контейнеры называются `cashback-*`, сеть `cashback_net`, тома `cashback_*`. К сети Caddy (`timetrack_timetrack`) подключён только `cashback-backend`. Порты наружу не публикуются.

Лимиты памяти: сервер 384 МБ, Postgres 256 МБ, Redis 96 МБ.

## Секреты

Файл `/opt/cashback-one/.env` (права 600) создан скриптом `make-env.sh` с случайными ключами; в репозитории и в чате их нет. Сделайте копию файла в безопасное место: без него базу не расшифровать и сессии не восстановить.

Токен Wappi (`WAPPI_API_TOKEN`) и режим отправки (`WHATSAPP_PROVIDER_MODE=wappi`) нужно прописать в `.env`; пока там `disabled`, вход покупателей в приложении невозможен.

## Обновление сервера

```bash
# с компьютера разработчика, из корня репозитория
tar --exclude='__pycache__' --exclude='tests' --exclude='.env*' -czf /tmp/cashback.tgz backend
scp /tmp/cashback.tgz kz-vps:/tmp/ && ssh kz-vps 'cd /opt/cashback-one && tar xzf /tmp/cashback.tgz && nice -n 15 docker build -q -t cashback-backend:local ./backend && docker compose up -d --no-build --force-recreate migration backend'
```

Миграции базы применяет контейнер `migration` при каждом запуске. Проверка: `docker exec cashback-backend curl -s http://127.0.0.1:8000/health/ready`.

## Обновление админки

```bash
cd admin && VITE_API_BASE_URL=https://api.cashback-qr.poscenter.kz VITE_ALLOW_INSECURE_HTTP=0 npm run build
```

Содержимое `admin/dist` и файл `.htaccess` (SPA-маршруты, HTTPS, заголовки безопасности) загружаются в папку сайта по FTPS. Файлы в `assets/` с хешем в имени; хостинг кэширует их на 10 лет, поэтому **не перезаписывайте файл с тем же именем** и убедитесь, что загрузка завершилась полностью.

## Caddy

В конец `/opt/timetrack/Caddyfile` добавлен блок `api.cashback-qr.poscenter.kz { reverse_proxy cashback-backend:8000 }`. Копия прежнего файла: `/opt/timetrack/Caddyfile.bak-cashback-*`. Откат: вернуть копию и выполнить `docker exec timetrack-caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile`.

## Первый администратор

Логин `admin` создан при развёртывании. Новых администраторов и менеджеров бизнеса создаёт `python -m app.cli.create_admin` внутри контейнера `cashback-backend` (`docker exec -it cashback-backend python -m app.cli.create_admin`).

## Мобильное приложение

Адрес API для сборки: `EXPO_PUBLIC_API_BASE_URL=https://api.cashback-qr.poscenter.kz`.

### Сборка подписанного release APK

Сборка выполняется локально без EAS скриптом `mobile/scripts/build-apk.sh`. Скрипт генерирует нативный проект Android (`expo prebuild`), настраивает подпись нашим release-ключом, собирает APK и проверяет валидность подписи.

#### Требования к окружению:
- **JDK 17**: Zulu 17 в `~/.jdks/zulu17.68.203-ca-jdk17.0.20.1-macosx_x64/Contents/Home` (системная Java 1.8 не подходит).
- **Android SDK**: `~/Library/Android/sdk` (build-tools 35/36, platforms 36).
- **Ключ подписи**:
  - Каталог: `~/.cashback-one-keys/`
  - Файлы: `release.keystore` (хранилище ключей) и `keystore.env` (переменные `CASHBACK_STORE_PASSWORD`, `CASHBACK_KEY_PASSWORD`, `CASHBACK_KEY_ALIAS`).
  - **КРИТИЧЕСКИ ВАЖНО**: release.keystore НЕ коммитится в Git! Обязательно сохраните резервную копию `~/.cashback-one-keys/` в надёжное безопасное хранилище (1Password, шифрованный бэкап). Если ключ будет утерян, выпустить обновление приложения для существующих пользователей будет невозможно.

#### Команда сборки:
```bash
./mobile/scripts/build-apk.sh
```

Переменные окружения (опционально):
- `ABIS` — целевые архитектуры процессора (по умолчанию `arm64-v8a,armeabi-v7a`).
- `API_BASE_URL` — адрес API (по умолчанию `https://api.cashback-qr.poscenter.kz`).
- `KEYS_DIR` — каталог с ключом (по умолчанию `~/.cashback-one-keys`).

Результат сборки помещается в `mobile/dist/cashback-one-<version>.apk`.
Проверка сертификата и пакета:
```bash
$ANDROID_HOME/build-tools/36.0.0/apksigner verify --print-certs mobile/dist/cashback-one-1.0.0.apk
$ANDROID_HOME/build-tools/36.0.0/aapt dump badging mobile/dist/cashback-one-1.0.0.apk | grep -E "package|versionName"
```

## Демо покупательского приложения (веб)

https://cashback-qr.poscenter.kz/demo/ — веб-версия приложения с тестовыми данными и пометкой «ДЕМО» (вход не нужен, данные не настоящие, правки профиля живут только в открытой вкладке). Собирается флагом `EXPO_PUBLIC_DEMO=1`; без флага приложение ходит только на настоящий API.

```bash
cd mobile
EXPO_PUBLIC_DEMO=1 EXPO_WEB_BASE_URL=/demo EXPO_PUBLIC_API_BASE_URL=https://demo.invalid npx expo export --platform web --output-dir /tmp/demo-web
```

Содержимое `/tmp/demo-web` (кроме `metadata.json` и неиспользуемых начертаний Montserrat 100/200/300/900 и *Italic; плюс папка `img/` из `mobile/demo-assets`) загружается по FTPS в папку `demo/` сайта вместе с `.htaccess` для маршрутов. После загрузки сверьте размеры файлов с локальными.

Картинки демо (иллюстрации из прототипа Grok) лежат в `mobile/demo-assets/` и загружаются в `demo/img/` на хостинге. **FTPS на этом хостинге обрывает передачу**, если не указать `--tls-max 1.2` в `curl` (файл остаётся обрезанным или пустым, а curl может вернуть ошибку 426). После каждой загрузки сверяйте размер файла на сайте с локальным.
