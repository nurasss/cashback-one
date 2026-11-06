# Отчёт: сборка APK 1.0.16 — Keremet Bonus — 2026-11-07

## Предварительно: очистка `mobile/android/app/build`

Удалена только папка `mobile/android/app/build` (`rm -rf`); `mobile/android/app/src`, `mobile/dist`, ключи, `google-services.json` не трогались, `gradlew clean` не запускался.

`df -h /` после удаления:
```
Filesystem       Size   Used  Avail Capacity iused    ifree %iused  Mounted on
/dev/disk1s4s1  113Gi  8.7Gi  4.4Gi    67%  356882 46048080    1%   /
```

---

## 1. Шаг 1: исходное состояние и проверки окружения

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
Исключения из промпта; других изменений нет.

### `df -h /`
```
Filesystem       Size   Used  Avail Capacity iused    ifree %iused  Mounted on
/dev/disk1s4s1  113Gi  8.7Gi  4.4Gi    67%  356882 46048080    1%   /
```

### Проверка отсутствия `mobile/dist/keremet-cashback-1.0.16.apk`
```
ls: mobile/dist/keremet-cashback-1.0.16.apk: No such file or directory
mobile/dist/keremet-cashback-1.0.15.apk (present)
```

---

## 2. Шаг 2: изменение версии

- `mobile/app.json`: `version` → `1.0.16`, `versionCode` → `17`
- `mobile/android/app/build.gradle`: `versionCode 17`, `versionName "1.0.16"` (строки 95–96)

### `git diff mobile/app.json`
```diff
diff --git a/mobile/app.json b/mobile/app.json
index ec64e79..8c6636a 100644
--- a/mobile/app.json
+++ b/mobile/app.json
@@ -3,7 +3,7 @@
     "name": "Cashback One",
     "slug": "cashback-one",
     "scheme": "cashbackone",
-    "version": "1.0.15",
+    "version": "1.0.16",
     "orientation": "portrait",
     "icon": "./assets/icon.png",
     "userInterfaceStyle": "light",
@@ -42,7 +42,7 @@
     },
     "android": {
       "package": "kz.cashbackone.mobile",
-      "versionCode": 16,
+      "versionCode": 17,
       "adaptiveIcon": {
         "foregroundImage": "./assets/icon-foreground.png",
         "backgroundColor": "#FD6156"
```

Строки `mobile/android/app/build.gradle`:
```
95:        versionCode 17
96:        versionName "1.0.16"
```

---

## 3. Шаг 3: проверки до сборки

### `npx jest --runInBand`
```
PASS tests/flows.test.tsx (5.271 s)
PASS tests/clientConfig.test.tsx
PASS tests/profileSave.test.tsx
PASS tests/qrScreen.test.tsx
PASS tests/homeArtwork.test.tsx
PASS tests/noCardNotice.test.tsx
PASS tests/appUpdate.test.tsx
PASS tests/cacheRefresh.test.tsx
PASS tests/cityCustom.test.tsx
PASS tests/historyPeriod.test.tsx
PASS tests/serverContentAndCache.test.tsx
PASS tests/components.test.tsx
PASS tests/wallet.test.tsx
PASS tests/avatar.test.tsx
PASS tests/core.test.ts
PASS tests/push.test.tsx
PASS tests/promotionsArtwork.test.tsx
PASS tests/levels.test.tsx
PASS tests/loginScreen.test.tsx
PASS tests/demo.test.ts
PASS tests/session.test.ts
PASS tests/transport.test.ts
PASS tests/keyboardLift.test.ts

Test Suites: 23 passed, 23 total
Tests:       317 passed, 317 total
Snapshots:   0 total
Time:        24.412 s, estimated 26 s
```

### `npx tsc --noEmit`
```
(no output, exit 0)
```

### `npx eslint .`
```
/Users/nuras/Desktop/cashback-one/mobile/src/components/useKeyboardLift.ts
  62:20  warning  The ref value 'generation.current' will likely have changed by the time this effect cleanup function runs. If this ref points to a node rendered by React, copy 'generation.current' to a variable inside the effect, and use that variable in the cleanup function  react-hooks/exhaustive-deps

✖ 1 problem (0 errors, 1 warning)
```

---

## 4. Шаг 4: сборка APK

### Запуск `mobile/scripts/build-client.sh keremet`
```
=== Building client 'keremet' (flavor: Keremet, task: app:assembleKeremetRelease) ===
...
> Task :app:processKeremetReleaseGoogleServices
...
> Task :app:packageKeremetRelease
> Task :app:createKeremetReleaseApkListingFileRedirect
> Task :app:assembleKeremetRelease

BUILD SUCCESSFUL in 6m 3s
403 actionable tasks: 72 executed, 331 up-to-date
Copied APK to dist/keremet-cashback-1.0.16.apk
=== Build completed successfully for keremet ===
-rw-r--r--@ 1 nuras  staff    61M Nov  7 01:44 dist/keremet-cashback-1.0.16.apk
741e12956cfc13580a1581013d7e456d5e43f40cc9f7a1fb11d9a3713f91d674  dist/keremet-cashback-1.0.16.apk
```

- `processKeremetReleaseGoogleServices` выполнена.
- Остановка демона Gradle:
```
cd mobile/android && ./gradlew --stop
No Gradle daemons are running.
```

---

## 5. Шаг 5: проверки собранного APK

### 5.1. `aapt2 dump badging`
```
package: name='kz.cashbackone.keremet' versionCode='17' versionName='1.0.16' platformBuildVersionName='16' platformBuildVersionCode='36' compileSdkVersion='36' compileSdkVersionCodename='16'
minSdkVersion:'24'
targetSdkVersion:'36'
application-label:'Keremet Bonus'
native-code: 'arm64-v8a' 'armeabi-v7a'
```

### 5.2. Проверка сертификата (`apksigner verify --print-certs`)
```
Signer #1 certificate DN: CN=Cashback One, O=POSCENTER, C=KZ
Signer #1 certificate SHA-256 digest: 14afcbb5ec8375e3130b2832b1a7468372e1205c3a275ba56b8ff7b1e483cd63
Signer #1 certificate SHA-1 digest: aadba44bcf5a58afccd295df29351d6ca285f5f4
Signer #1 certificate MD5 digest: bf366fbeed9edf7f64e76ef4bb582985
```

### 5.3. Сравнение разрешений с `keremet-cashback-1.0.15.apk`
```
diff -u perms15.txt perms16.txt
(empty, DIFF_EXIT:0)
```
30 `uses-permission`, включая `INTERNET`, `CAMERA`, `POST_NOTIFICATIONS`, `ACCESS_NETWORK_STATE`, `VIBRATE`, `WAKE_LOCK`, `READ/WRITE_EXTERNAL_STORAGE (maxSdkVersion=32)`, `RECEIVE_BOOT_COMPLETED`, `USE_BIOMETRIC`, `USE_FINGERPRINT`, `DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION` и badge-разрешения — совпадают с 1.0.15.

### 5.4. Google Services (`aapt2 dump resources`)
```
resource 0x7f12007c string/google_app_id
  () "1:693902155886:android:1f667ed4a7db868bb2067f"
resource 0x7f120077 string/gcm_defaultSenderId
  () "693902155886"
```
Совпадает с 1.0.15.

### 5.5. Иконки launcher в APK

`aapt2 dump resources` (1.0.16):
```
resource 0x7f0f0000 mipmap/ic_launcher
  (mdpi) (file) res/9w.png type=PNG
  (hdpi) (file) res/yn.png type=PNG
  (xhdpi) (file) res/FS.png type=PNG
  (xxhdpi) (file) res/RJ.png type=PNG
  (xxxhdpi) (file) res/o-.png type=PNG
resource 0x7f0f0001 mipmap/ic_launcher_foreground
  (mdpi) (file) res/QZ.png type=PNG
  (hdpi) (file) res/zr.png type=PNG
  (xhdpi) (file) res/Em.png type=PNG
  (xxhdpi) (file) res/Lf.png type=PNG
  (xxxhdpi) (file) res/as.png type=PNG
resource 0x7f0f0002 mipmap/ic_launcher_round
  (mdpi) (file) res/zR.png type=PNG
  (hdpi) (file) res/8c.png type=PNG
  (xhdpi) (file) res/wb.png type=PNG
  (xxhdpi) (file) res/fO.png type=PNG
  (xxxhdpi) (file) res/Gc.png type=PNG
```

Чтение файлов прямо из zip (без распаковки, с учётом регистра):

| Ресурс | Файл в APK | 1.0.15 SHA-256[..12] | 1.0.16 SHA-256[..12] | Совпадение |
|---|---|---|---|---|
| `mipmap/ic_launcher` mdpi | `res/9w.png` | `7d94b88faf99` | `7d94b88faf99` | да |
| `mipmap/ic_launcher` hdpi | `res/yn.png` | `22ce1f92ca11` | `22ce1f92ca11` | да |
| `mipmap/ic_launcher` xhdpi | `res/FS.png` | `b3b6ee81258d` | `b3b6ee81258d` | да |
| `mipmap/ic_launcher` xxhdpi | `res/RJ.png` | `77bfd23cad60` | `77bfd23cad60` | да |
| `mipmap/ic_launcher` xxxhdpi | `res/o-.png` | `5593c4e4d62f` | `5593c4e4d62f` | да |
| `mipmap/ic_launcher_foreground` mdpi | `res/QZ.png` | `327331a09697` | `327331a09697` | да |
| `mipmap/ic_launcher_foreground` hdpi | `res/zr.png` | `5eaa8cd16cf1` | `5eaa8cd16cf1` | да |
| `mipmap/ic_launcher_foreground` xhdpi | `res/Em.png` | `5754d58a0e36` | `5754d58a0e36` | да |
| `mipmap/ic_launcher_foreground` xxhdpi | `res/Lf.png` | `2930a343d689` | `2930a343d689` | да |
| `mipmap/ic_launcher_foreground` xxxhdpi | `res/as.png` | `1953ac35f3b7` | `1953ac35f3b7` | да |
| `mipmap/ic_launcher_round` mdpi | `res/zR.png` | `012e4f1c76dc` | `012e4f1c76dc` | да |
| `mipmap/ic_launcher_round` hdpi | `res/8c.png` | `2a4189a64460` | `2a4189a64460` | да |
| `mipmap/ic_launcher_round` xhdpi | `res/wb.png` | `a3d821fd357c` | `a3d821fd357c` | да |
| `mipmap/ic_launcher_round` xxhdpi | `res/fO.png` | `12a5deb111be` | `12a5deb111be` | да |
| `mipmap/ic_launcher_round` xxxhdpi | `res/Gc.png` | `124ed7d03f95` | `124ed7d03f95` | да |
| adaptive `anydpi-v26` | `res/BW.xml` | `ebe84e43293c` | `ebe84e43293c` | да |
| adaptive round `anydpi-v26` | `res/0K.xml` | `ebe84e43293c` | `ebe84e43293c` | да |

Примечания:
- На macOS указанная пара `res/zR.png` (mdpi round 5738 байт) и `res/zr.png` (hdpi foreground 34211 байт) совпадают без учёта регистра; оба прочитаны из zip без распаковки по точным именам.
- Цвет фона адаптивной иконки в APK (`aapt2 dump resources`):
```
resource 0x7f060073 color/ic_launcher_background
  () #fff15173
```
Цвет: `#F15173`.

### 5.6. Байткод Hermes (`assets/index.android.bundle`)

Проверено дизассемблированием `hermesc -b -dump-bytecode`:

- `getClientConfig`:
```
Function<getClientConfig>(2 params, 17 registers, 0 symbols):
    LoadParam         r6, 1
    LoadConstNull     r0
    JNotEqual         L1, r6, r0
    LoadConstString   r6, "keremet"
L1:
    JNotEqual         L2, r6, r0
    LoadConstString   r6, "cashbackone"
```
Возвращает `"keremet"`.

- `DEMO_ENABLED` (модуль mockApi):
```
    LoadConstFalse    r3
    StoreNPToEnvironment r2, 3, r3
```
`DEMO_ENABLED = false`.

- URL API:
```
s7634[ASCII, 209992..210027]: https://api.cashback-qr.poscenter.kz
```

- Новый цвет `softSuccess`:
```
s1750[ASCII, 41355..41361]: #E8F5EC
```

### 5.7. Размер и SHA-256 собранного APK

- Файл: `mobile/dist/keremet-cashback-1.0.16.apk`
- Размер: **63 868 870 байт** (~61 MB)
- SHA-256: **`741e12956cfc13580a1581013d7e456d5e43f40cc9f7a1fb11d9a3713f91d674`**

Для сравнения, 1.0.15: 63 868 846 байт, SHA-256 `004fa7beeb6dab5656635110683e8f80289659484984c8c9d34898986a515a23`.

---

## 6. Шаг 6: финальное состояние окружения

### `df -h /`
```
Filesystem       Size   Used  Avail Capacity iused    ifree %iused  Mounted on
/dev/disk1s4s1  113Gi  8.7Gi  2.5Gi    78%  356882 26630200    1%   /
```

### `git status --short`
```
 M mobile/app.json
?? C:/
?? docs/tools/keremet-reset.zip
?? reports/old-promo-cards-2026-11-06/
?? video/
```
`mobile/android/app/build.gradle` изменён локально (17 / 1.0.16), но в `.gitignore` (`mobile/android/`), поэтому в `git status` не отображается. Коммит/push не выполнялись, публикация не выполнялась, `version.json`, лендинг, сервер и кабинет не менялись.

---

## 7. Что не проверено

1. Установка поверх 1.0.15 на физическом смартфоне.
2. Вид истории на телефоне (цвета начислений/списаний и уведомлений).
