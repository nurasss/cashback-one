# Сборка release APK 1.0.12 / versionCode 13 — Push-уведомления (FCM) и контент с сервера

Дата: 2026-11-05, Mac. APK собран локально и проверен по файлу. Не загружался на сайт или в GitHub Releases, `version.json` не создавался/не менялся, на устройство не устанавливался; `expo prebuild`, `mobile/scripts/build-apk.sh`, deploy, commit и push не запускались. Прежние APK и кэш Gradle не удалялись.

**Итог:** сборка, проверки APK и тесты регрессии выполнены успешно. Остаются только проверки на реальном устройстве и кассе, указанные в §10.

---

## 1. Артефакт

| Параметр | Значение |
|---|---|
| Путь | `mobile/dist/cashback-one-1.0.12.apk` |
| Размер | **69 675 373 байт** (66.45 MB) |
| SHA-256 | `2edfc8890c77c64af1647a7d0cd9219e6946b547c756832f9ee6c3731bdceab3` |
| package | `kz.cashbackone.mobile` |
| versionName / versionCode | **1.0.12 / 13** (`aapt2 dump badging`) |
| Архитектуры | только `arm64-v8a`, `armeabi-v7a` |
| minSdk / targetSdk / compileSdk | 24 / 36 / 36 |

Release APK из `mobile/android/app/build/outputs/apk/release/app-release.apk` скопирован через `cp -n`.

Прежние релизные и тестовые APK не затронуты и проверены:
- `cashback-one-1.0.11-test.apk`: **68 601 127 байт**, SHA-256 `1fbb7c6c4bdb0c947e0e72cab053ef5a3106ee951ee23a905011c0fca4203754` (без изменений);
- `cashback-one-1.0.11-test.no-api.apk`: **68 600 383 байт**, SHA-256 `987b937a025a9bd129f20f2c5d681bf0b135db2a0e68d7ddb9a892488956cb05` (без изменений);
- `cashback-one-1.0.10.apk`: **68 600 435 байт**, SHA-256 `8c8726e068088f3eae66fa1b3b1fffa7d2512c6aa44ebdded03f0bd611c123c9` (без изменений);
- `cashback-one-1.0.9.apk`: **67 951 855 байт**, SHA-256 `3ddcc5e44dd00e1642913e3a84ff510b833f931519af0459b245fa717512731a` (без изменений);
- `cashback-one-1.0.8.apk`: **67 773 772 байта**, SHA-256 `5e6b8f2158c8a00468dbe21783da444abb5bd7b55fb81c5e5ad9739020fee03b` (без изменений);
- `cashback-one-1.0.7.apk`: **67 778 452 байта**, SHA-256 `4a260bfba8f56fc8e71b75c29ad5c3b1476df0a00a2ba3220314adac8d403179` (без изменений);
- `cashback-one-1.0.6.apk`: **62 529 495 байт**, SHA-256 `195f486a0c02fd9891d638164bdc395cb7938d54ddc4357eff36d9e4d345338c` (без изменений).

---

## 2. Подпись

`apksigner verify --verbose --print-certs mobile/dist/cashback-one-1.0.12.apk`:

```text
Verifies
Verified using v1 scheme (JAR signing): false
Verified using v2 scheme (APK Signature Scheme v2): true
Verified using v3 scheme (APK Signature Scheme v3): false
Verified using v3.1 scheme (APK Signature Scheme v3.1): false
Verified using v4 scheme (APK Signature Scheme v4): false
Verified for SourceStamp: false
Number of signers: 1
Signer #1 certificate DN: CN=Cashback One, O=POSCENTER, C=KZ
Signer #1 certificate SHA-256 digest: 14afcbb5ec8375e3130b2832b1a7468372e1205c3a275ba56b8ff7b1e483cd63
Signer #1 certificate SHA-1 digest: aadba44bcf5a58afccd295df29351d6ca285f5f4
Signer #1 certificate MD5 digest: bf366fbeed9edf7f64e76ef4bb582985
Signer #1 key algorithm: RSA
Signer #1 key size (bits): 2048
Signer #1 public key SHA-256 digest: d7977712efcca48f3213f66266b352c95e173330f40c3c21b81e75472967a03a
Signer #1 public key SHA-1 digest: 8bf930bc2ecdc6b5ab37671563f345daee6e9378
Signer #1 public key MD5 digest: 359e56a609dc643b53294cd5d1d57be7
```

- Статус: `Verifies`; один подписант.
- DN: `CN=Cashback One, O=POSCENTER, C=KZ`.
- SHA-256 сертификата: **`14afcbb5ec8375e3130b2832b1a7468372e1205c3a275ba56b8ff7b1e483cd63`** — полностью совпадает с эталонным сертификатом.
- Схема подписи v2: `true`; v1, v3, v3.1, v4 и SourceStamp: `false`.
- Содержимое keystore и пароли не выводились (переданы через `~/.cashback-one-keys/keystore.env` в изолированной подоболочке с `set -a` и экспортом `CASHBACK_STORE_FILE`).

---

## 3. Версии и манифест

### 3.1. `mobile/app.json`
До правок:
```json
6:    "version": "1.0.11-test",
45:      "versionCode": 12,
```
После правок:
```json
6:    "version": "1.0.12",
45:      "versionCode": 13,
```

### 3.2. `mobile/android/app/build.gradle`
До правок:
```groovy
95:        versionCode 12
96:        versionName "1.0.11-test"
```
После правок:
```groovy
95:        versionCode 13
96:        versionName "1.0.12"
```

### 3.3. Манифест нативного проекта
В `mobile/android/app/src/main/AndroidManifest.xml` проверены через `grep` строки разрешений и метаданных:
```xml
3:  <uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>
5:  <uses-permission android:name="android.permission.RECORD_AUDIO" tools:node="remove"/>
6:  <uses-permission android:name="android.permission.SYSTEM_ALERT_WINDOW" tools:node="remove"/>
20:    <meta-data android:name="com.google.firebase.messaging.default_notification_icon" android:resource="@drawable/notification_icon"/>
21:    <meta-data android:name="expo.modules.notifications.default_notification_icon" android:resource="@drawable/notification_icon"/>
22:    <meta-data android:name="com.google.firebase.messaging.default_notification_color" android:resource="@color/notification_icon_color"/>
23:    <meta-data android:name="expo.modules.notifications.default_notification_color" android:resource="@color/notification_icon_color"/>
24:    <meta-data android:name="com.google.firebase.messaging.default_notification_channel_id" android:value="default"/>
```
Команда `expo prebuild` не запускалась.

---

## 4. Baseline и сборка

### 4.1. Baseline до сборки
- Дисковое пространство: `df -h ~` → свободно **4,9 GiB** (порог >= 3 GB пройден).
- Нагрузка системы: `uptime` → load average: `3.61 3.06 2.62` (< 12).
- Проверка `google-services.json`:
  - Наличие: `mobile/android/app/google-services.json` и `~/.cashback-one-keys/google-services.json` присутствуют, права `600` (`-rw-------`).
  - Git ignore: `git check-ignore mobile/android/app/google-services.json` подтвердил игнорирование файла.
  - Хеш SHA-256: `4845f3f05343781b31d48ea9812b6c1d9a3744e355ccefe7e5f19c5771931387` (полное совпадение).
  - Булевы проверки: `project_id == "cashback-one-loyalty"` → `True`, `kz.cashbackone.mobile in client_packages` → `True` (содержимое и ключи не выводились).
- `npx jest --runInBand`: **21 test suites passed, 280 tests passed, 0 failed** (18.978 s).
- `npx tsc --noEmit`: код 0, чисто.
- `npx eslint .`: 0 ошибок, 1 ожидаемое предупреждение в `useKeyboardLift.ts`.

### 4.2. Release-сборка
Сборка выполнена в фоне с перенаправлением вывода в `/tmp/apk-1.0.12-build-logs/gradle-build.log`.
Команда:
```bash
(export JAVA_HOME="/Users/nuras/.jdks/zulu17.68.203-ca-jdk17.0.20.1-macosx_x64/Contents/Home" && \
 export PATH="$JAVA_HOME/bin:$PATH" && \
 export ANDROID_HOME="/Users/nuras/Library/Android/sdk" && \
 export CASHBACK_STORE_FILE="$HOME/.cashback-one-keys/release.keystore" && \
 set -a && source ~/.cashback-one-keys/keystore.env && set +a && \
 export NODE_ENV=production && \
 export EXPO_PUBLIC_API_BASE_URL="https://api.cashback-qr.poscenter.kz" && \
 unset EXPO_PUBLIC_DEMO EXPO_PUBLIC_ALLOW_INSECURE_HTTP && \
 mkdir -p /tmp/apk-1.0.12-build-logs && \
 env | grep -E '^(NODE_ENV|EXPO_PUBLIC_)' > /tmp/apk-1.0.12-build-logs/build-env.log && \
 cd mobile/android && \
 ./gradlew assembleRelease -PreactNativeArchitectures=arm64-v8a,armeabi-v7a --no-daemon --max-workers=1 -Dorg.gradle.parallel=false --console=plain > /tmp/apk-1.0.12-build-logs/gradle-build.log 2>&1; \
 echo "GRADLE_EXIT=$?" >> /tmp/apk-1.0.12-build-logs/gradle-build.log)
```

Окружение сборки (`build-env.log`):
```text
NODE_ENV=production
EXPO_PUBLIC_API_BASE_URL=https://api.cashback-qr.poscenter.kz
```

Задачи плагинов и автолинковка в логе сборки:
```text
406:> Task :app:processReleaseGoogleServices
  - [📦] expo-image (55.0.11)
  - [📦] expo-image-loader (55.0.1)
  - [📦] expo-image-manipulator (55.0.21)
  - [📦] expo-image-picker (55.0.24)
  - [📦] expo-notifications (55.0.27)
> Task :react-native-async-storage_async-storage:generateCodegenSchemaFromJavaScript
> Task :react-native-async-storage_async-storage:generateCodegenArtifactsFromSchema
```

Результат сборки:
```text
BUILD SUCCESSFUL in 16m 49s
435 actionable tasks: 407 executed, 28 up-to-date
GRADLE_EXIT=0
```
В логе сборки пароли и секреты отсутствуют.

---

## 5. Метаданные, разрешения и конфигурация приложения

### 5.1. `aapt2 dump badging`
```text
package: name='kz.cashbackone.mobile' versionCode='13' versionName='1.0.12' platformBuildVersionName='16' platformBuildVersionCode='36' compileSdkVersion='36' compileSdkVersionCodename='16'
sdkVersion:'24'
targetSdkVersion:'36'
application-label:'Cashback One'
application-icon: res/BW.xml
native-code: 'arm64-v8a' 'armeabi-v7a'
```

### 5.2. `assets/app.config` внутри APK
Содержимое встроенного `assets/app.config` проверено через JSON-парсер:
```json
{
  "name": "Cashback One",
  "slug": "cashback-one",
  "version": "1.0.12",
  "android": {
    "package": "kz.cashbackone.mobile",
    "versionCode": 13
  }
}
```
`version` (`1.0.12`) и `android.versionCode` (`13`) полностью совпадают с метаданными `aapt2 dump badging`.

### 5.3. Разрешения (`aapt2 dump permissions`) и diff с APK 1.0.11-test
Сравнение разрешений:
```diff
--- perms-1.0.11-test.txt
+++ perms-1.0.12.txt
@@ -1,11 +1,32 @@
 package: kz.cashbackone.mobile
 uses-permission: name='android.permission.INTERNET'
+uses-permission: name='android.permission.POST_NOTIFICATIONS'
 uses-permission: name='android.permission.READ_EXTERNAL_STORAGE' maxSdkVersion='32'
 uses-permission: name='android.permission.VIBRATE'
 uses-permission: name='android.permission.WRITE_EXTERNAL_STORAGE' maxSdkVersion='32'
 uses-permission: name='android.permission.ACCESS_NETWORK_STATE'
 uses-permission: name='android.permission.CAMERA'
+uses-permission: name='android.permission.RECEIVE_BOOT_COMPLETED'
+uses-permission: name='android.permission.WAKE_LOCK'
+uses-permission: name='com.google.android.c2dm.permission.RECEIVE'
 uses-permission: name='android.permission.USE_BIOMETRIC'
 uses-permission: name='android.permission.USE_FINGERPRINT'
 permission: kz.cashbackone.mobile.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION
 uses-permission: name='kz.cashbackone.mobile.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION'
+uses-permission: name='com.google.android.finsky.permission.BIND_GET_INSTALL_REFERRER_SERVICE'
+uses-permission: name='com.sec.android.provider.badge.permission.READ'
+uses-permission: name='com.sec.android.provider.badge.permission.WRITE'
+uses-permission: name='com.htc.launcher.permission.READ_SETTINGS'
+uses-permission: name='com.htc.launcher.permission.UPDATE_SHORTCUT'
+uses-permission: name='com.sonyericsson.home.permission.BROADCAST_BADGE'
+uses-permission: name='com.sonymobile.home.permission.PROVIDER_INSERT_BADGE'
+uses-permission: name='com.anddoes.launcher.permission.UPDATE_COUNT'
+uses-permission: name='com.majeur.launcher.permission.UPDATE_BADGE'
+uses-permission: name='com.huawei.android.launcher.permission.CHANGE_BADGE'
+uses-permission: name='com.huawei.android.launcher.permission.READ_SETTINGS'
+uses-permission: name='com.huawei.android.launcher.permission.WRITE_SETTINGS'
+uses-permission: name='android.permission.READ_APP_BADGE'
+uses-permission: name='com.oppo.launcher.permission.READ_SETTINGS'
+uses-permission: name='com.oppo.launcher.permission.WRITE_SETTINGS'
+uses-permission: name='me.everything.badger.permission.BADGE_COUNT_READ'
+uses-permission: name='me.everything.badger.permission.BADGE_COUNT_WRITE'
```

#### Назначение новых разрешений:
1. `android.permission.POST_NOTIFICATIONS`: стандартное runtime-разрешение Android 13+ (API 33+) для показа входящих push-уведомлений пользователю.
2. `android.permission.RECEIVE_BOOT_COMPLETED`: библиотека `expo-notifications` (`NotificationsService` / `ScheduledNotificationBootReceiver`) для восстановления планировщика уведомлений после перезагрузки смартфона.
3. `android.permission.WAKE_LOCK`: Firebase Cloud Messaging (`FirebaseMessagingService`) для кратковременного пробуждения процессора при приеме push-сообщения в фоновом режиме.
4. `com.google.android.c2dm.permission.RECEIVE`: базовое разрешение доставки сообщений Google Cloud-to-Device Messaging (FCM).
5. `com.google.android.finsky.permission.BIND_GET_INSTALL_REFERRER_SERVICE`: сервисная связка Google Play SDK.
6. Разрешения лаунчеров (Samsung, HTC, Sony, Huawei, Oppo, Apex, Solid, ShortcutBadger): бейджи на иконке приложения при поступлении непрочитанных уведомлений на различных оболочках вендоров Android.

#### Проверка отсутствия нежелательных разрешений:
- `android.permission.RECORD_AUDIO`: **отсутствует** (удалено через `tools:node="remove"`);
- `android.permission.SYSTEM_ALERT_WINDOW`: **отсутствует** (удалено через `tools:node="remove"`);
- Разрешения геолокации (`ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION`): **отсутствуют**;
- Разрешения контактов (`READ_CONTACTS`, `WRITE_CONTACTS`): **отсутствуют**;
- Разрешения SMS (`READ_SMS`, `SEND_SMS`, `RECEIVE_SMS`): **отсутствуют**.

---

## 6. Ресурсы и ассеты

### 6.1. Firebase / Google Services в `resources.arsc`
Проверено через `aapt2 dump resources` и `aapt2 dump strings`:
- `string/gcm_defaultSenderId` (id `0x7f120077`) — присутствует;
- `string/google_app_id` (id `0x7f12007c`) — присутствует;
- `string/project_id` (id `0x7f120102`) — присутствует;
- Проверка значения `project_id == "cashback-one-loyalty"`: **`True`**;
- Метаданные `com.google.firebase.messaging.default_notification_channel_id` со значением `"default"` проверены в бинарном `AndroidManifest.xml` (line 128).

### 6.2. Иконки уведомлений `notification_icon.png`
Все 5 плотностей присутствуют в APK и зарегистрированы в `drawable/notification_icon` (id `0x7f080118`):
- `mdpi`: `res/U4.png` (24×24)
- `hdpi`: `res/qJ.png` (36×36)
- `xhdpi`: `res/RQ.png` (48×48)
- `xxhdpi`: `res/ZO.png` (72×72)
- `xxxhdpi`: `res/eY.png` (96×96)

*Примечание о сжатии:* инструмент AAPT2 при сборке оптимизирует монохромные PNG-файлы (PNG crunching), конвертируя цветовую модель RGBA в Luminance+Alpha (LA) для минимизации размера. Декодирование через Pillow показало **100% точное попиксельное совпадение RGBA-пикселей (`RGBA pixel match: True`)** для всех пяти плотностей с исходными файлами в `mobile/android/app/src/main/res/drawable-*/notification_icon.png`.

Исходные контрольные суммы файлов в репозитории:
- `drawable-mdpi/notification_icon.png`: `e3a1660f2387eb90f2aa044ad395cc5886d5cd86f780fefbfc9b51c1e96015d7`
- `drawable-hdpi/notification_icon.png`: `169f759247fccdbad39d9377ff334444bca6f49362675255ea0b98196ca15f88`
- `drawable-xhdpi/notification_icon.png`: `05084e2cbe21ec62657c59bed33617748c788d7210004213fc4f4a263ab6ead6`
- `drawable-xxhdpi/notification_icon.png`: `ef510e9e76cb0afd03248b788fa02c56f9deb4c68d464ebe76af301c70f4b26d`
- `drawable-xxxhdpi/notification_icon.png`: `56058feb7a85e770aa8a7cf67690a24180b0ce12f4003fffddaad718950db70d`

### 6.3. Проверка удаления зашитых ассетов акций
Проверка `unzip -l mobile/dist/cashback-one-1.0.12.apk` на наличие локальных картинок из удалённой папки `mobile/assets/promotions/*`:
- `banner-car-prize`: **отсутствует** (0)
- `banner-coffee-machine`: **отсутствует** (0)
- `banner-stickers`: **отсутствует** (0)
- `offer-*`: **отсутствует** (0)
- `promo-*`: **отсутствует** (0)

Папка `assets/` внутри APK содержит только:
- `assets/app.config`
- `assets/index.android.bundle`
- `assets/dexopt/baseline.prof` и `baseline.profm`
- 3 модели MLKit Barcode Scanning (`barcode_ssd_mobilenet_v1_dmp25_quant.tflite`, `oned_auto_regressor_mobile.tflite`, `oned_feature_extractor_mobile.tflite`) — SHA-256 моделей 100% совпадают с версией 1.0.11-test.

### 6.4. Иконка приложения
Адаптивная иконка приложения `mipmap/ic_launcher` и `BW.xml` проверены:
- `res/BW.xml` (anydpi-v26): SHA-256 `ebe84e43293cb6f64c55687504d73f0d2de8938bbf79f8ed977448096b133156` (100% совпадает с 1.0.11-test);
- `res/d2.webp` (mdpi): SHA-256 `1178c3a4d85a...` (100% совпадает с 1.0.11-test);
- `res/MO.webp` (hdpi): SHA-256 `5809f83f1e96...` (100% совпадает с 1.0.11-test);
- `res/qs.webp` (xhdpi): SHA-256 `5625187693ec...` (100% совпадает с 1.0.11-test);
- `res/Sn.webp` (xxhdpi): SHA-256 `e58af52bbb3a...` (100% совпадает с 1.0.11-test);
- `res/sK.webp` (xxxhdpi): SHA-256 `e8fec23c7e94...` (100% совпадает с 1.0.11-test).

---

## 7. Hermes bundle, байткод и строки

Байткод Hermes проверен потоком через `hermesc -b -dump-bytecode` (без сохранения текстового дампа на диск).

1. **Demo выключен по байткоду:**
   - В модуле `mockApi` проверена последовательность инструкций:
     ```text
     StoreToEnvironment   r2, 1, r3
     LoadConstFalse       r3
     StoreNPToEnvironment r2, 2, r3
     LoadConstString      r3, "https://demo.inva"...
     StoreToEnvironment   r2, 3, r3
     ```
   - Запись `false` в слот окружения подтверждена.
   - В точке инициализации клиента API:
     ```text
     GetById              r2, r2, 2, "DEMO_ENABLED"
     LoadConstString      r4, "https://api.cashb"...
     JmpFalse             L3, r2
     LoadFromEnvironment  r2, r1, 6
     GetById              r4, r2, 4, "DEMO_BASE_URL"
     L3:
     ```
     При `DEMO_ENABLED = false` выполняется переход на `L3`, минуя демо-URL.

2. **Адреса API и локальные хосты:**
   - `https://api.cashback-qr.poscenter.kz`: **найден** (`True`);
   - `localhost:8000`: **отсутствует** (`False`);
   - `10.0.2.2:8000`: **отсутствует** (`False`).

3. **Проверка строк (UTF-16LE / UTF-8):**
   - **Обязательные строки присутствуют:**
     - `Вы можете потратить баллы по адресу: ` (UTF-16LE): **`True`**
     - `Ұпайларды мына мекенжай бойынша жұмсай аласыз: ` (UTF-16LE): **`True`**
     - `Баланс обновляется не сразу. Новые начисления и списания появляются 2 раза в сутки.` (UTF-16LE): **`True`**
     - `/me/app-content` (UTF-8): **`True`**
     - `/me/push-token` (UTF-8): **`True`**
     - `Покажите QR кассиру` (UTF-16LE): **`True`**
   - **Запрещенные строки отсутствуют:**
     - `КеремЕт`: **`False`** (удалено из клиентского кода в пользу данных с бэкенда)
     - `In Plaza`: **`False`** (удалено из клиентского кода в пользу данных с бэкенда)
     - `2gis.kz`: **`False`** (удалено из клиентского кода в пользу данных с бэкенда)

---

## 8. Размер и сравнение с 1.0.11-test

Сравнение размеров:
- APK 1.0.11-test: `68 601 127 байт` (65.42 MB)
- APK 1.0.12: `69 675 373 байт` (66.45 MB)
- Разница: **+1 074 246 байт** (+1.02 MB)

### Источник дельты размера (несжатые компоненты)
- **DEX-код:** `+2 568 828 байт` (+2.45 MB) — добавлен четвёртый DEX-файл `classes4.dex`, содержащий классы Firebase Cloud Messaging (FCM), Google Play Services Tasks/Basements, AndroidX DataStore, нативный модуль `expo-notifications`, а также библиотеки `@react-native-async-storage/async-storage` и `expo-image`.
- **Нативные библиотеки (.so):** `+46 384 байта` — добавлена `libdatastore_shared_counter.so` для обеих архитектур (`arm64-v8a`, `armeabi-v7a`).
- **Ресурсы:** `+6 736 байт` — добавлены 5 плотностей иконки `notification_icon.png` и сопутствующие цветовые XML-ресурсы.
- **Assets:** `+82 309 байт` — изменение размера JS-бандла за счет добавления модулей пушей и серверного контента, при этом зашитые графические файлы акций были удалены из репозитория ранее.

---

## 9. Регрессия и Git

### 9.1. Регрессия после сборки
- `cd mobile && npx jest --runInBand`: **21 test suites passed, 280 tests passed, 0 failed** (17.974 s);
- `cd mobile && npx tsc --noEmit`: код 0, чисто;
- `cd mobile && npx eslint .`: 0 ошибок, 1 ожидаемое предупреждение в `useKeyboardLift.ts`.

### 9.2. Git-статус
Вывод `git status --short`:
```text
 M CLAUDE.md
 M mobile/app.json
 M mobile/app/(app)/(tabs)/index.tsx
 M mobile/app/(app)/(tabs)/notifications.tsx
 M mobile/app/(app)/(tabs)/profile.tsx
 M mobile/app/(app)/(tabs)/promotions.tsx
 M mobile/app/(app)/(tabs)/qr.tsx
 M mobile/app/(app)/promotion/[id].tsx
 M mobile/app/(app)/status.tsx
 D mobile/assets/promotions/banner-car-prize.png
 D mobile/assets/promotions/banner-coffee-machine.png
 D mobile/assets/promotions/banner-stickers.png
 D mobile/assets/promotions/offer-card-bonus.png
 D mobile/assets/promotions/offer-fresh-products.png
 D mobile/assets/promotions/offer-hits-discount.png
 D mobile/assets/promotions/offer-weekly-promo.png
 D mobile/assets/promotions/promo-card-bonus-side.png
 D mobile/assets/promotions/promo-card-bonus.png
 D mobile/assets/promotions/promo-fresh-products-side.png
 D mobile/assets/promotions/promo-fresh-products.png
 D mobile/assets/promotions/promo-hits-discount-side.png
 D mobile/assets/promotions/promo-hits-discount.png
 D mobile/assets/promotions/promo-weekly-side.png
 D mobile/assets/promotions/promo-weekly.png
 M mobile/package-lock.json
 M mobile/package.json
 M mobile/src/api/app.ts
 M mobile/src/api/client.ts
 M mobile/src/auth/provider.tsx
 M mobile/src/auth/session.ts
 M mobile/src/components/useKeyboardLift.ts
 M mobile/src/demo/mockApi.ts
 M mobile/src/features/DynamicQr.tsx
 M mobile/src/features/home.tsx
 D mobile/src/features/promotionsArtwork.ts
 M mobile/src/i18n/kz.ts
 M mobile/src/i18n/ru.ts
 M mobile/src/types/api.ts
 M mobile/tests/flows.test.tsx
 M mobile/tests/homeArtwork.test.tsx
 M mobile/tests/promotionsArtwork.test.tsx
 M mobile/tests/qrScreen.test.tsx
 M mobile/tests/setup.ts
?? C:/
?? docs/PROMPT_APK_1_0_11_TEST_2026-11-04.md
?? docs/PROMPT_APK_1_0_11_TEST_PUBLISH_2026-11-04.md
?? docs/PROMPT_APK_1_0_12_2026-11-05.md
?? docs/PROMPT_APP_1_0_11_TEST_2026-11-04.md
?? docs/PROMPT_APP_1_0_11_TEST_2GIS_2026-11-04.md
?? docs/PROMPT_APP_PUSH_2026-11-04.md
?? docs/PROMPT_APP_PUSH_FIXES_2026-11-04.md
?? docs/PROMPT_APP_SERVER_CONTENT_2026-11-05.md
?? docs/PROMPT_APP_SERVER_CONTENT_FIXES_2026-11-05.md
?? docs/PROMPT_DEPLOY_NEW_COURSE_2026-11-04.md
?? docs/PROMPT_ENABLE_PUSH_FCM_2026-11-05.md
?? docs/PROMPT_ENABLE_PUSH_FCM_RETRY_2026-11-05.md
?? docs/PROMPT_GPT_FIREBASE_KEY_ROTATE_2026-11-05.md
?? mobile/src/features/push.tsx
?? mobile/src/storage/appCache.ts
?? mobile/tests/push.test.tsx
?? mobile/tests/serverContentAndCache.test.tsx
?? reports/APK_1_0_11_TEST_BUILD.md
?? reports/APK_1_0_11_TEST_PUBLISH_2026-11-04.md
?? reports/APP_1_0_11_TEST_2026-11-04.md
?? reports/APP_PUSH_2026-11-04.md
?? reports/APP_SERVER_CONTENT_2026-11-05.md
?? reports/DEPLOY_NEW_COURSE_2026-11-04.md
?? reports/ENABLE_PUSH_FCM_2026-11-05.md
?? reports/app-push-2026-11-04/
?? reports/app-server-content-2026-11-05/
?? reports/screenshots-1.0.11-test/
?? video/
```

Единственное изменение в отслеживаемых файлах от данной задачи — обновление версии в `mobile/app.json`. Директория `mobile/android/` не отслеживается в git (в `.gitignore`).

---

## 10. Не проверено

Следующие проверки требуют физического смартфона, сетевого окружения и кассового узла и не выполнялись в рамках данной задачи сборки:
1. **Установка поверх предыдущих версий:** обновление приложения поверх 1.0.11-test и 1.0.10 на реальном Android-устройстве с сохранением пользовательской сессии;
2. **Запрос системного разрешения на push-уведомления:** появление системного диалога `POST_NOTIFICATIONS` на Android 13+ при первом входе/авторизации;
3. **Регистрация токена:** успешная отправка полученного FCM-токена на эндпоинт `/me/push-token` бэкенда;
4. **Доставка push-уведомлений:** получение тестового push-уведомления (или уведомления с кодом списания) в системную шторку смартфона и отображение монохромной иконки `notification_icon.png` фирменного цвета `#FD6156`;
5. **Главная страница:** загрузка и корректный рендеринг баннеров, карточки магазина и актуальных акций с сервера `/me/app-content`, а также fallback на локальные заглушки при отсутствии данных в кабинете;
6. **Офлайн-режим:** запуск приложения без доступа к интернету и отображение закешированного контента из AsyncStorage;
7. **Открытие ссылки магазина:** переход по кликабельному адресу магазина в картографическое приложение или браузер на смартфоне;
8. **Кассовый узел:** считывание QR-кода карты лояльности стационарным 2D-сканером кассы в магазине.
