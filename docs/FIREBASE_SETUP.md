# Настройка Firebase Cloud Messaging для владельца

Инструкция по ручной первоначальной настройке Firebase для push-уведомлений Cashback One.

> [!IMPORTANT]
> **Конфиденциальность ключей**: Сервисный JSON-файл содержит закрытый RSA-ключ доступа к проекту. Никогда не коммитьте его в репозиторий, не пересылайте в чаты и не передавайте посторонним. Права на сервере — строго `600`.

---

## 1. Создание проекта Firebase

1. Перейдите в консоль Firebase: [https://console.firebase.google.com/](https://console.firebase.google.com/).
2. Нажмите **«Создать проект»** (или «Add project»).
3. Введите название проекта (например, `cashback-one-loyalty`).
4. Google Analytics можно отключить (для push-уведомлений он не требуется).
5. Дождитесь создания проекта.

---

## 2. Добавление Android-приложения клиента

В одном проекте Firebase будут находиться Android-приложения всех клиентов (магазинов/сетей).

1. На главной странице проекта нажмите на иконку **Android** (добавить приложение).
2. Укажите:
   - **Имя пакета Android** (Package name): пакет конкретного клиента (например, `kz.cashbackone.mobile`).
   - **Псевдоним приложения** (Nickname): например, `Cashback One (Основное)`.
   - **Сертификат подписи SHA-1 / SHA-256** (опционально, рекомендуется добавить отпечаток релизного ключа подписи).
3. Нажмите **«Зарегистрировать приложение»**.

---

## 3. Файл для приложения (`google-services.json`)

1. На шаге 2 мастера (или в **Настройки проекта** → раздел «Ваши приложения» → выбор Android-приложения) скачайте файл:
   `google-services.json`
2. Этот файл используется при сборке APK клиента и помещается в папку мобильного приложения (`mobile/google-services.json` или по инструкции сборки APK клиента).

---

## 4. Файл сервисного аккаунта для сервера (`firebase-service-account.json`)

Серверу (облачному backend) нужен доступ к Firebase Cloud Messaging HTTP v1 API.

1. В консоли Firebase перейдите в **«Настройки проекта»** (иконка шестерёнки в левом верхнем углу).
2. Откройте вкладку **«Сервисные аккаунты»** (Service accounts).
3. Убедитесь, что выбран язык **Node.js** или **Python** (выбран сервис *Firebase Admin SDK*).
4. Нажмите кнопку **«Создать закрытый ключ»** (Generate new private key) → подтвердите генерацию.
5. Браузер скачает JSON-файл (например, `cashback-one-loyalty-firebase-adminsdk-xxxxx.json`).

---

## 5. Размещение файла на VPS

1. Переименуйте скачанный файл в `firebase-service-account.json` (для удобства).
2. Загрузите файл по защищённому каналу (SCP / SFTP) на боевой VPS:
   ```bash
   scp firebase-service-account.json kz-vps:/opt/cashback-one/secrets/firebase-service-account.json
   ```
3. На VPS установите строгие права доступа (только на чтение владельцем):
   ```bash
   chmod 600 /opt/cashback-one/secrets/firebase-service-account.json
   ```

---

## 6. Включение push на сервере (`.env`)

В файле `/opt/cashback-one/.env` на сервере добавьте настройки:

```ini
PUSH_PROVIDER_MODE=fcm
FCM_PROJECT_ID=<ID_вашего_проекта_Firebase>
FCM_SERVICE_ACCOUNT_FILE=/opt/cashback-one/secrets/firebase-service-account.json
```

После изменения конфигурации перезапустите контейнер backend:
```bash
docker compose restart backend
```

---

## 7. Подключение новых клиентов в будущем

Когда у вас появляется новый клиент со своим уникальным APK (свой пакет, например `kz.client_shop.mobile`):

1. В **этом же** проекте Firebase нажмите **«Добавить приложение»** → **Android**.
2. Введите пакет нового клиента (`kz.client_shop.mobile`).
3. Скачайте `google-services.json` для сборки APK этого клиента.
4. **На сервере ничего менять не требуется**: сервисный аккаунт Firebase автоматически имеет права отправлять push во все Android-приложения своего проекта Firebase.
