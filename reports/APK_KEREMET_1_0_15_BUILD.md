# Отчёт: сборка APK 1.0.15 — Keremet Bonus — 2026-11-06

## 1. Шаг 1: Исходное состояние и проверки окружения

### `git pull --ff-only origin main`
```
From https://github.com/nurasss/cashback-one
 * branch            main       -> FETCH_HEAD
Already up to date.
```

### `git status --short` (до правок)
```
?? C:/
?? docs/tools/keremet-reset.zip
?? reports/old-promo-cards-2026-11-06/
?? video/
```
*(Посторонних модифицированных файлов нет)*

### `df -h /` (до сборки)
```
Filesystem       Size   Used  Avail Capacity iused    ifree %iused  Mounted on
/dev/disk1s4s1  113Gi  8.7Gi  5.0Gi    64%  356882 52005640    1%   /
```
*(Доступно 5.0 GiB > 3 GB)*

### Проверка отсутствия `mobile/dist/keremet-cashback-1.0.15.apk`
```
ls: mobile/dist/keremet-cashback-1.0.15.apk: No such file or directory
```

---

## 2. Шаг 2: Изменение версии

- `mobile/app.json`: `version` → `1.0.15`, `versionCode` → `16`
- `mobile/android/app/build.gradle`: `versionCode 16`, `versionName "1.0.15"`

### `git diff mobile/app.json`
```diff
diff --git a/mobile/app.json b/mobile/app.json
index 4e7b990..ec64e79 100644
--- a/mobile/app.json
+++ b/mobile/app.json
@@ -3,7 +3,7 @@
     "name": "Cashback One",
     "slug": "cashback-one",
     "scheme": "cashbackone",
-    "version": "1.0.14",
+    "version": "1.0.15",
     "orientation": "portrait",
     "icon": "./assets/icon.png",
     "userInterfaceStyle": "light",
@@ -42,7 +42,7 @@
     },
     "android": {
       "package": "kz.cashbackone.mobile",
-      "versionCode": 15,
+      "versionCode": 16,
       "adaptiveIcon": {
         "foregroundImage": "./assets/icon-foreground.png",
         "backgroundColor": "#FD6156"
```

### Строки `mobile/android/app/build.gradle` (lines 91–98)
```groovy
    defaultConfig {
        applicationId 'kz.cashbackone.mobile'
        minSdkVersion rootProject.ext.minSdkVersion
        targetSdkVersion rootProject.ext.targetSdkVersion
        versionCode 16
        versionName "1.0.15"

        buildConfigField "String", "REACT_NATIVE_RELEASE_LEVEL", "\"${findProperty('reactNativeReleaseLevel') ?: 'stable'}\""
```

---

## 3. Шаг 3: Проверки до сборки

### `npx jest --runInBand`
```
PASS tests/clientConfig.test.tsx (5.137 s)
PASS tests/profileSave.test.tsx
PASS tests/flows.test.tsx
PASS tests/qrScreen.test.tsx
PASS tests/appUpdate.test.tsx
PASS tests/noCardNotice.test.tsx
PASS tests/cacheRefresh.test.tsx
PASS tests/homeArtwork.test.tsx
PASS tests/historyPeriod.test.tsx
PASS tests/cityCustom.test.tsx
PASS tests/wallet.test.tsx
PASS tests/serverContentAndCache.test.tsx
PASS tests/avatar.test.tsx
PASS tests/core.test.ts
PASS tests/push.test.tsx
PASS tests/components.test.tsx
PASS tests/promotionsArtwork.test.tsx
PASS tests/loginScreen.test.tsx
PASS tests/levels.test.tsx
PASS tests/session.test.ts
PASS tests/demo.test.ts
PASS tests/transport.test.ts
PASS tests/keyboardLift.test.ts

Test Suites: 23 passed, 23 total
Tests:       315 passed, 315 total
Snapshots:   0 total
Time:        21.587 s
Ran all test suites.
Exit code: 0
```

### `npx tsc --noEmit`
```
Exit code: 0
No errors.
```

### `npx eslint .`
```
/Users/nuras/Desktop/cashback-one/mobile/src/components/useKeyboardLift.ts
  62:20  warning  The ref value 'generation.current' will likely have changed by the time this effect cleanup function runs. If this ref points to a node rendered by React, copy 'generation.current' to a variable inside the effect, and use that variable in the cleanup function  react-hooks/exhaustive-deps

✖ 1 problem (0 errors, 1 warning)
Exit code: 0
```
*(Предупреждение в `useKeyboardLift.ts` существовало до начала задачи)*

---

## 4. Шаг 4: Сборка APK

### Запуск `mobile/scripts/build-client.sh keremet`
```
=== Building client 'keremet' (flavor: Keremet, task: app:assembleKeremetRelease) ===
To honour the JVM settings for this build a single-use Daemon process will be forked. For more on this, please refer to https://docs.gradle.org/9.0.0/userguide/gradle_daemon.html#sec:disabling_the_daemon in the Gradle documentation.
Daemon will be stopped at the end of the build 
...
> Task :app:processKeremetReleaseGoogleServices
...
> Task :app:packageKeremetRelease
> Task :app:createKeremetReleaseApkListingFileRedirect
> Task :app:assembleKeremetRelease

BUILD SUCCESSFUL in 3m 59s
403 actionable tasks: 67 executed, 336 up-to-date
Copied APK to dist/keremet-cashback-1.0.15.apk
=== Build completed successfully for keremet ===
-rw-r--r--@ 1 nuras  staff    61M Nov  6 22:33 dist/keremet-cashback-1.0.15.apk
004fa7beeb6dab5656635110683e8f80289659484984c8c9d34898986a515a23  dist/keremet-cashback-1.0.15.apk
```

- Задача `processKeremetReleaseGoogleServices` успешно выполнена:
  `> Task :app:processKeremetReleaseGoogleServices`
- Остановка демона Gradle:
  ```
  cd mobile/android && ./gradlew --stop
  No Gradle daemons are running.
  ```

---

## 5. Шаг 5: Проверки собранного APK

### 5.1. `aapt2 dump badging`
```
package: name='kz.cashbackone.keremet' versionCode='16' versionName='1.0.15' platformBuildVersionName='16' platformBuildVersionCode='36' compileSdkVersion='36' compileSdkVersionCodename='16'
sdkVersion:'24'
targetSdkVersion:'36'
application-label:'Keremet Bonus'
application-label-af:'Keremet Bonus'
...
native-code: 'arm64-v8a' 'armeabi-v7a'
```
- Идентификатор пакета: `kz.cashbackone.keremet`
- Название приложения: `Keremet Bonus`
- `versionCode='16'`, `versionName='1.0.15'`
- Архитектуры ABI: `arm64-v8a`, `armeabi-v7a`

### 5.2. Проверка сертификата (`apksigner verify --print-certs`)
```
Signer #1 certificate DN: CN=Cashback One, O=POSCENTER, C=KZ
Signer #1 certificate SHA-256 digest: 14afcbb5ec8375e3130b2832b1a7468372e1205c3a275ba56b8ff7b1e483cd63
Signer #1 certificate SHA-1 digest: aadba44bcf5a58afccd295df29351d6ca285f5f4
Signer #1 certificate MD5 digest: bf366fbeed9edf7f64e76ef4bb582985
```
- SHA-256 дайджест: `14afcbb5ec8375e3130b2832b1a7468372e1205c3a275ba56b8ff7b1e483cd63` (совпадает с ключом релиза)

### 5.3. Сравнение разрешений с `keremet-cashback-1.0.14.apk`
```
diff -u /tmp/perms_14.txt /tmp/perms_15.txt
(diff пустой — 0 различий)
```
Разрешения идентичны версии 1.0.14:
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
- Launcher badges permissions (Samsung, HTC, Sony, Huawei, Oppo, etc.)

### 5.4. Google Services (`aapt2 dump resources`)
```
resource 0x7f12007c string/google_app_id
  () "1:693902155886:android:1f667ed4a7db868bb2067f"
resource 0x7f120077 string/gcm_defaultSenderId
  () "693902155886"
```
- `google_app_id` = `"1:693902155886:android:1f667ed4a7db868bb2067f"` (совпадает с 1.0.14 и клиентом `kz.cashbackone.keremet`)
- `gcm_defaultSenderId` = `"693902155886"`

### 5.5. Иконки launcher в APK
Все 15 растровых файлов иконок `mipmap-*` в APK **отличаются** от версии 1.0.14 и соответствуют новым файлам Варианта C из `mobile/clients/keremet/android/res/mipmap-*`:

| Ресурс в `aapt2` | Путь в APK | Разрешение | Формат в APK | Формат в исходнике | Различие по пикселям с `res/mipmap-*` | Отличие от 1.0.14 |
|---|---|---|---|---|---|---|
| `mipmap/ic_launcher` (mdpi) | `res/9w.png` | 48×48 | RGB | RGBA | **0 diff** | Да (хеш изменился) |
| `mipmap/ic_launcher` (hdpi) | `res/yn.png` | 72×72 | RGB | RGBA | **0 diff** | Да (хеш изменился) |
| `mipmap/ic_launcher` (xhdpi) | `res/FS.png` | 96×96 | RGB | RGBA | **0 diff** | Да (хеш изменился) |
| `mipmap/ic_launcher` (xxhdpi) | `res/RJ.png` | 144×144 | RGB | RGBA | **0 diff** | Да (хеш изменился) |
| `mipmap/ic_launcher` (xxxhdpi) | `res/o-.png` | 192×192 | RGB | RGBA | **0 diff** | Да (хеш изменился) |
| `mipmap/ic_launcher_foreground` (mdpi) | `res/QZ.png` | 108×108 | RGB | RGBA | **0 diff** | Да (хеш изменился) |
| `mipmap/ic_launcher_foreground` (hdpi) | `res/zr.png` | 162×162 | RGB | RGBA | **0 diff** | Да (хеш изменился) |
| `mipmap/ic_launcher_foreground` (xhdpi) | `res/Em.png` | 216×216 | RGB | RGBA | **0 diff** | Да (хеш изменился) |
| `mipmap/ic_launcher_foreground` (xxhdpi) | `res/Lf.png` | 324×324 | RGB | RGBA | **0 diff** | Да (хеш изменился) |
| `mipmap/ic_launcher_foreground` (xxxhdpi) | `res/as.png` | 432×432 | RGB | RGBA | **0 diff** | Да (хеш изменился) |
| `mipmap/ic_launcher_round` (mdpi) | `res/zR.png` | 48×48 | RGBA | RGBA | **0 diff** | Да (хеш изменился) |
| `mipmap/ic_launcher_round` (hdpi) | `res/8c.png` | 72×72 | RGBA | RGBA | **0 diff** (хеш байт-в-байт) | Да (хеш изменился) |
| `mipmap/ic_launcher_round` (xhdpi) | `res/wb.png` | 96×96 | RGBA | RGBA | **0 diff** (хеш байт-в-байт) | Да (хеш изменился) |
| `mipmap/ic_launcher_round` (xxhdpi) | `res/fO.png` | 144×144 | RGBA | RGBA | **0 diff** (хеш байт-в-байт) | Да (хеш изменился) |
| `mipmap/ic_launcher_round` (xxxhdpi) | `res/Gc.png` | 192×192 | RGBA | RGBA | **0 diff** (хеш байт-в-байт) | Да (хеш изменился) |

*(Примечание: AAPT2 при сборке release оптимизирует полностью непрозрачные RGBA PNG до 24-битных RGB PNG, устраняя лишний альфа-канал; цвета всех пикселей идентичны исходным на 100%. Файлы с прозрачностью `ic_launcher_round` сохраняют RGBA и совпали по байтовому SHA-256).*

- **Цвет фона адаптивной иконки в APK (`aapt2 dump resources`):**
  ```
  resource 0x7f060073 color/ic_launcher_background
    () #fff15173
  ```
  Цвет: `#F15173` (ARGB `#fff15173` со 100% непрозрачностью).

### 5.6. Значок шапки в APK
Значок `mobile/clients/keremet/header_badge.png` скомпилирован в APK:
- Ресурс: `resource 0x7f080083 drawable/clients_keremet_header_badge`
- Файл в APK: `res/1g.png`
- Разрешение: 120×120 px, RGBA
- Размер: 19 021 байт
- SHA-256: `5833f543f597f6be90658ce1cb0fc97e13a80e62bca8de811153482943f127e4` (100% байт-в-байт совпадает с `mobile/clients/keremet/header_badge.png`).

### 5.7. Байткод Hermes (`assets/index.android.bundle`)
Проверено дизассемблированием `hermesc -b -dump-bytecode`:
- `getClientConfig`:
  ```
  Function<getClientConfig>(2 params, 17 registers, 0 symbols):
      LoadParam         r6, 1
      LoadConstNull     r0
      JNotEqual         L1, r6, r0
      LoadConstString   r6, "keremet"
  ```
  Возвращает клиента `"keremet"`.
- `DEMO_ENABLED`:
  Константа `DEMO_ENABLED` компилируется как `false`:
  ```
  LoadConstFalse    r3
  StoreNPToEnvironment r2, 3, r3
  ```
- URL API:
  Строка `https://api.cashback-qr.poscenter.kz` присутствует в таблице строк байткода Hermes (string `s7627`).

### 5.8. Размер и SHA-256 собранного APK
- Файл: `mobile/dist/keremet-cashback-1.0.15.apk`
- Размер: **63 868 846 байт** (~61 MB)
- SHA-256: **`004fa7beeb6dab5656635110683e8f80289659484984c8c9d34898986a515a23`**

*(Для сравнения: 1.0.14 был 63 653 058 байт, SHA-256 `5d7c3a73a0356e12a57c2130cd801e9e35fc088071d1ef997f9459b5fc73fe83`)*

---

## 6. Шаг 6: Финальное состояние окружения

### `df -h /`
```
Filesystem       Size   Used  Avail Capacity iused    ifree %iused  Mounted on
/dev/disk1s4s1  113Gi  8.7Gi  3.2Gi    74%  356882 33112360    1%   /
```

### `git status --short`
```
 M mobile/app.json
?? C:/
?? docs/tools/keremet-reset.zip
?? reports/APK_KEREMET_1_0_15_BUILD.md
?? reports/old-promo-cards-2026-11-06/
?? video/
```
*(В git модифицирован только `mobile/app.json` с поднятием версии, `android/` вне git, без лишних мутаций)*

---

## 7. Что не проверено

1. Отображение новой иконки на реальном лаунчере физического Android-устройства (проверено по ресурсам APK, aapt2-дампу и попиксельному соответствию).
2. Обновление (установка) поверх установленного приложения версии 1.0.14 на физическом смартфоне (подпись и пакет совпадают, `versionCode` увеличен с 15 до 16).
