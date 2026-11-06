# Отчёт о сборке APK KeremEt с push (1.0.12)

**Дата:** 2026-11-06  
**Исполнитель:** Claude (mobile/app)  
**Куратор:** Antigravity  
**Промпт:** `docs/PROMPT_APK_KEREMET_1_0_12_2026-11-06.md`  
**Результат:** `mobile/dist/keremet-cashback-1.0.12.apk` собран, подписан релизным ключом, проверен.

---

## 1. Шаг 1: Проверка репозитория и дискового пространства

```
$ git pull --ff-only origin main
From https://github.com/nurasss/cashback-one
 * branch            main       -> FETCH_HEAD
Already up to date.

$ git status --short
?? C:/
?? video/

$ df -h /
Filesystem       Size   Used  Avail Capacity iused    ifree %iused  Mounted on
/dev/disk1s4s1  113Gi  8.7Gi  5.3Gi    63%  356882 55643600    1%   /
```

- Ветка актуальна, рабочая директория чистая.
- Доступно 5.3 ГБ свободного места (> 3 ГБ).

---

## 2. Шаг 2: Проверка конфигурации Google Services (`google-services.json`)

```
$ shasum -a 256 mobile/android/app/src/keremet/google-services.json ~/.cashback-one-keys/google-services.keremet.json
cd4a39921e669e3e5f6564180f837eee777320353ad92c5bc212ad80e398cdb3  mobile/android/app/src/keremet/google-services.json
cd4a39921e669e3e5f6564180f837eee777320353ad92c5bc212ad80e398cdb3  /Users/nuras/.cashback-one-keys/google-services.keremet.json
```

- SHA-256 совпадает и начинается с `cd4a39921e669e3e`.
- Метаданные (содержимое файла и секреты скрыты):
  - `project_id`: `cashback-one-loyalty`
  - `packages`: `['kz.cashbackone.keremet', 'kz.cashbackone.mobile']`
  - Пакет `kz.cashbackone.keremet` присутствует.

---

## 3. Шаг 3: Проверки кода до сборки

### 3.1. Jest (`npx jest --runInBand`)

```
PASS tests/clientConfig.test.tsx (6.036 s)
PASS tests/profileSave.test.tsx
PASS tests/appUpdate.test.tsx
PASS tests/flows.test.tsx
PASS tests/qrScreen.test.tsx
PASS tests/serverContentAndCache.test.tsx
PASS tests/avatar.test.tsx
PASS tests/cardScanner.test.tsx
PASS tests/historyPeriod.test.tsx
PASS tests/homeArtwork.test.tsx
PASS tests/cityCustom.test.tsx
PASS tests/wallet.test.tsx
PASS tests/components.test.tsx
PASS tests/push.test.tsx
PASS tests/demo.test.ts
PASS tests/promotionsArtwork.test.tsx
PASS tests/levels.test.tsx
PASS tests/loginScreen.test.tsx
PASS tests/session.test.ts
PASS tests/core.test.ts
PASS tests/transport.test.ts
PASS tests/keyboardLift.test.ts

Test Suites: 22 passed, 22 total
Tests:       301 passed, 301 total
Snapshots:   0 total
Time:        23.173 s, estimated 29 s
Ran all test suites.
```

### 3.2. TypeScript (`npx tsc --noEmit`)

```
(exit code 0, no output)
```

### 3.3. ESLint (`npx eslint .`)

```
/Users/nuras/Desktop/cashback-one/mobile/src/components/useKeyboardLift.ts
  62:20  warning  The ref value 'generation.current' will likely have changed by the time this effect cleanup function runs. If this ref points to a node rendered by React, copy 'generation.current' to a variable inside the effect, and use that variable in the cleanup function  react-hooks/exhaustive-deps

✖ 1 problem (0 errors, 1 warning)
```

---

## 4. Шаг 4: Сборка APK (`mobile/scripts/build-client.sh keremet`)

- Задача Google Services выполнена:
  ```
  > Task :app:processKeremetReleaseGoogleServices
  ```
  (задача выполнена, статус не `SKIPPED`, не `UP-TO-DATE`).
- Итог сборки Gradle:
  ```
  BUILD SUCCESSFUL in 29m 46s
  403 actionable tasks: 31 executed, 372 up-to-date
  Copied APK to dist/keremet-cashback-1.0.12.apk
  === Build completed successfully for keremet ===
  ```

---

## 5. Шаг 5: Проверки собранного APK (`mobile/dist/keremet-cashback-1.0.12.apk`)

### 5.1. Размер и SHA-256

- **Размер:** 63 668 358 байт (~60.7 MiB)
- **SHA-256:** `fb1090049b81f337a88e7cbf8363ae8109164e7d974e9fca1a64c520d0003265`

### 5.2. `aapt2 dump badging`

```
package: name='kz.cashbackone.keremet' versionCode='13' versionName='1.0.12' platformBuildVersionName='16' platformBuildVersionCode='36' compileSdkVersion='36' compileSdkVersionCodename='16'
minSdkVersion:'24'
targetSdkVersion:'36'
application-label:'Keremet Bonus'
application: label='Keremet Bonus' icon='res/BW.xml'
launchable-activity: name='kz.cashbackone.mobile.MainActivity'  label='' icon=''
native-code: 'arm64-v8a' 'armeabi-v7a'
```

### 5.3. Проверка подписи (`apksigner verify --print-certs`)

```
Signer #1 certificate DN: CN=Cashback One, O=POSCENTER, C=KZ
Signer #1 certificate SHA-256 digest: 14afcbb5ec8375e3130b2832b1a7468372e1205c3a275ba56b8ff7b1e483cd63
Signer #1 certificate SHA-1 digest: aadba44bcf5a58afccd295df29351d6ca285f5f4
Signer #1 certificate MD5 digest: bf366fbeed9edf7f64e76ef4bb582985
```
Сертификат полностью совпадает с эталонным релизным ключом.

### 5.4. Разрешения (сравнение с `keremet-cashback-1.0.12.no-push.apk`)

- В `keremet-cashback-1.0.12.no-push.apk`: 30 разрешений.
- В `keremet-cashback-1.0.12.apk`: 30 разрешений.
- Различий нет (0 добавлено, 0 удалено). Набор разрешений идентичен:
  - `android.permission.INTERNET`
  - `android.permission.POST_NOTIFICATIONS`
  - `android.permission.READ_EXTERNAL_STORAGE` (maxSdkVersion=32)
  - `android.permission.VIBRATE`
  - `android.permission.WRITE_EXTERNAL_STORAGE` (maxSdkVersion=32)
  - `android.permission.ACCESS_NETWORK_STATE`
  - `android.permission.CAMERA`
  - `android.permission.RECEIVE_BOOT_COMPLETED`
  - `android.permission.WAKE_LOCK`
  - `com.google.android.c2dm.permission.RECEIVE`
  - `android.permission.USE_BIOMETRIC`
  - `android.permission.USE_FINGERPRINT`
  - `kz.cashbackone.keremet.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION`
  - `com.google.android.finsky.permission.BIND_GET_INSTALL_REFERRER_SERVICE`
  - `com.sec.android.provider.badge.permission.READ`
  - `com.sec.android.provider.badge.permission.WRITE`
  - `com.htc.launcher.permission.READ_SETTINGS`
  - `com.htc.launcher.permission.UPDATE_SHORTCUT`
  - `com.sonyericsson.home.permission.BROADCAST_BADGE`
  - `com.sonymobile.home.permission.PROVIDER_INSERT_BADGE`
  - `com.anddoes.launcher.permission.UPDATE_COUNT`
  - `com.majeur.launcher.permission.UPDATE_BADGE`
  - `com.huawei.android.launcher.permission.CHANGE_BADGE`
  - `com.huawei.android.launcher.permission.READ_SETTINGS`
  - `com.huawei.android.launcher.permission.WRITE_SETTINGS`
  - `android.permission.READ_APP_BADGE`
  - `com.oppo.launcher.permission.READ_SETTINGS`
  - `com.oppo.launcher.permission.WRITE_SETTINGS`
  - `me.everything.badger.permission.BADGE_COUNT_READ`
  - `me.everything.badger.permission.BADGE_COUNT_WRITE`

### 5.5. Ресурсы Google Services (`aapt2 dump resources`)

- `google_app_id` = `1:693902155886:android:1f667ed4a7db868bb2067f` (совпадает с `mobilesdk_app_id` клиента `kz.cashbackone.keremet` из `google-services.json`).
- `gcm_defaultSenderId` = `693902155886` (совпадает с номером проекта `cashback-one-loyalty`).

### 5.6. Инспекция байткода Hermes (`hermesc -b -dump-bytecode`)

1. **`getClientConfig` подставляет `"keremet"`:**
   ```
   Function<getClientConfig>(2 params, 17 registers, 0 symbols):
       LoadParam         r6, 1
       LoadConstNull     r0
       JNotEqual         L1, r6, r0
       LoadConstString   r6, "keremet"
   L1:
       JNotEqual         L2, r6, r0
       LoadConstString   r6, "cashbackone"
   L2:
       GetEnvironment    r2, 0
       LoadFromEnvironment r0, r2, 0
       GetByVal          r0, r0, r6
   ```
2. **`DEMO_ENABLED` = false в модуле `mockApi`:**
   ```
       LoadConstFalse    r3
       StoreNPToEnvironment r2, 3, r3
       LoadConstString   r3, "https://demo.inva"...
       StoreToEnvironment r2, 4, r3
   ```
   (в слот переменной `DEMO_ENABLED` записано значение `LoadConstFalse`).
3. **Рабочий адрес API:**
   Строка `https://api.cashback-qr.poscenter.kz` присутствует в таблице строк и бандле.

---

## 6. Шаг 6: Завершение и дисковое пространство после сборки

```
$ cd mobile/android && ./gradlew --stop
No Gradle daemons are running.

$ df -h /
Filesystem       Size   Used  Avail Capacity iused    ifree %iused  Mounted on
/dev/disk1s4s1  113Gi  8.7Gi  5.7Gi    61%  356882 59901280    1%   /
```

- Демоны Gradle остановлены.
- Доступно 5.7 ГБ свободного дискового пространства.

---

## 7. Что не проверено

1. Установка APK на физический Android-телефон.
2. Реальная доставка FCM push-уведомления на мобильное устройство.
3. Полный сценарий списания баллов на кассе с push-подтверждением покупателя.
