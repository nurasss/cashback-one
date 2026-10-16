# Интеграция с Apple Wallet и Google Wallet

Документ описывает настройку карт лояльности для добавления в **Apple Wallet** (iOS) и **Google Wallet** (Android).

---

## 1. Концепция и архитектура

- **В приложении**: QR-код остаётся динамическим (`C1...`, обновляется каждые 60 секунд). Он защищён от копирования и фотографирования.
- **В кошельке (Wallet)**: отображается **статичный штрихкод** карты (`card.barcode`), который сканируется кассой 1С так же, как пластиковая карта.
- **Баланс и статус**: на карте кошелька не печатаются, поскольку карта кошелька не обновляется в реальном времени при каждой покупке. На обороте карты явно указано:
  - «Смотрите в приложении Cashback One»
  - «Списание подтверждается кодом, который приходит вам в WhatsApp»
- **Отключение по умолчанию**: пока ключи и сертификаты не настроены на сервере, эндпоинт `GET /me/wallet` возвращает `{"apple": false, "google": false}`, а кнопки добавления в приложении скрыты.

---

## 2. Apple Wallet

### 2.1. Необходимые аккаунты и права
- Аккаунт **Apple Developer Program** ($99/год) с ролью Account Holder или Admin.

### 2.2. Пошаговое получение сертификатов
1. **Создание Pass Type ID**:
   - Войдите в [Apple Developer Portal: Certificates, Identifiers & Profiles](https://developer.apple.com/account/resources/identifiers/list/passTypeId).
   - Выберите **Pass Type IDs** -> нажмите «+».
   - Описание: `Cashback One Loyalty Card`.
   - Идентификатор: например, `pass.kz.poscenter.cashback`.
   - Зарегистрируйте.

2. **Выпуск сертификата Pass Type ID**:
   - В списке Pass Type IDs выберите созданный ID и нажмите **Create Certificate**.
   - Создайте Certificate Signing Request (CSR) локально на Mac (через Keychain Access -> Certificate Assistant -> Request a Certificate from a Certificate Authority) или через OpenSSL:
     ```bash
     openssl req -newkey rsa:2048 -nodes -keyout apple_pass_key.pem -out pass.csr -subj "/CN=Pass Type ID: pass.kz.poscenter.cashback/OU=CashbackOne/O=POSCENTER/C=KZ"
     ```
   - Загрузите `pass.csr` в Apple Developer Portal.
   - Скачайте полученный файл сертификата `pass.cer`.
   - Экспортируйте его в PEM-формат:
     ```bash
     openssl x509 -inform DER -in pass.cer -out apple_pass_cert.pem
     ```

3. **Скачивание промежуточного сертификата Apple WWDR**:
   - Apple подписывает pass-сертификаты промежуточным центром **Apple Worldwide Developer Relations G4 (WWDR G4)**.
   - Скачайте сертификат с [Apple PKI](https://www.apple.com/certificateauthority/):
     - Ссылка: [Apple Worldwide Developer Relations Certificate Authority G4 (G4 sub-CA PEM)](https://www.apple.com/certificateauthority/AppleWWDRCAG4.cer)
   - Конвертируйте в PEM:
     ```bash
     openssl x509 -inform DER -in AppleWWDRCAG4.cer -out apple_wwdr.pem
     ```

4. **Team ID**:
   - В правом верхнем углу Apple Developer Portal скопируйте свой 10-значный **Team ID** (например, `A1B2C3D4E5`).

---

## 3. Google Wallet

### 3.1. Необходимые аккаунты и права
- Бесплатный аккаунт в [Google Pay & Wallet Console](https://pay.google.com/business/console).
- Проект в [Google Cloud Platform Console](https://console.cloud.google.com/).

### 3.2. Пошаговая настройка
1. **Регистрация в Google Pay & Wallet Console**:
   - Перейдите в [Google Pay & Wallet Console](https://pay.google.com/business/console).
   - Зарегистрируйтесь как эмитент (Issuer) и примите условия использования.
   - В разделе **Google Wallet API** получите свой **Issuer ID** (числовой идентификатор, например `3388000000022123456`).

2. **Создание сервисного аккаунта в Google Cloud**:
   - В Google Cloud Console создайте сервисный аккаунт (Service Account), например `cashback-wallet-sa@<project-id>.iam.gserviceaccount.com`.
   - Включите **Google Wallet API** в библиотеке API проекта GCP.
   - Для созданного сервисного аккаунта сгенерируйте и скачайте ключ в формате **JSON** (`google_sa.json`).

3. **Связывание сервисного аккаунта с Google Wallet Console**:
   - В Google Pay & Wallet Console перейдите в раздел **Users** (Пользователи).
   - Нажмите **Invite User** и введите e-mail созданного сервисного аккаунта (`cashback-wallet-sa@...`).
   - Назначьте роль **Developer** или **Admin** (чтобы сервисный аккаунт имел права на выпуск карт).

---

## 4. Размещение на VPS и настройка Docker

### 4.1. Каталог секретов на сервере
На VPS `/opt/cashback-one` создайте каталог секретов с ограниченными правами доступа:

```bash
mkdir -p /opt/cashback-one/secrets
chmod 700 /opt/cashback-one/secrets
```

Скопируйте в `/opt/cashback-one/secrets/` полученные файлы:
- `apple_pass_cert.pem` — сертификат Pass Type ID.
- `apple_pass_key.pem` — приватный ключ Pass Type ID (права `600`).
- `apple_wwdr.pem` — промежуточный сертификат Apple WWDR G4.
- `google_sa.json` — JSON-ключ сервисного аккаунта Google (права `600`).

```bash
chmod 600 /opt/cashback-one/secrets/*
```

### 4.2. Проброс в Docker через compose.yml
В `compose.yml` в секции сервиса `backend` монтируется том `secrets` в режиме read-only:

```yaml
services:
  backend:
    volumes:
      - ./secrets:/app/secrets:ro
```

### 4.3. Переменные окружения (.env)
Добавьте в `/opt/cashback-one/.env`:

```env
# Публичный HTTPS URL API (обязательно https в production)
WALLET_PUBLIC_BASE_URL=https://api.cashback-qr.poscenter.kz
WALLET_ORGANIZATION_NAME=POSCENTER ONE
WALLET_LINK_TTL_SECONDS=600

# Apple Wallet
APPLE_PASS_TYPE_ID=pass.kz.poscenter.cashback
APPLE_TEAM_ID=A1B2C3D4E5
APPLE_PASS_CERT_FILE=/app/secrets/apple_pass_cert.pem
APPLE_PASS_KEY_FILE=/app/secrets/apple_pass_key.pem
APPLE_PASS_KEY_PASSWORD=
APPLE_WWDR_CERT_FILE=/app/secrets/apple_wwdr.pem

# Google Wallet
GOOGLE_WALLET_ISSUER_ID=3388000000022123456
GOOGLE_WALLET_SERVICE_ACCOUNT_FILE=/app/secrets/google_sa.json
```

После сохранения `.env` перезапустите backend:
```bash
docker compose up -d backend
```

После перезапуска `GET /me/wallet` вернёт:
```json
{
  "apple": true,
  "google": true
}
```
И в мобильном приложении на экранах появится кнопка «Добавить в Apple Wallet» (на iOS) и «Добавить в Google Wallet» (на Android).
