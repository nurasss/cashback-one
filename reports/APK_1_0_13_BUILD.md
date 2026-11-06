# Отчёт о сборке APK 1.0.13: Cashback One и Keremet Bonus

**Дата:** 2026-11-06  
**Исполнитель:** Claude (mobile/app)  
**Куратор:** Antigravity  
**Промпт:** `docs/PROMPT_APK_1_0_13_2026-11-06.md`  
**Результат:**
- `mobile/dist/keremet-cashback-1.0.13.apk` — 63 668 818 байт, SHA-256 `e12605a2fa27e4f7697bbf098662e2b6089720257ecdea4ed9e926d967450c36`
- `mobile/dist/cashback-one-1.0.13.apk` — 63 468 253 байт, SHA-256 `3b8e5382282c97c7d93d4a54725ad8333806be3efe2bf9cb18969891fb026039`

---

## 1. Шаг 1: Проверка репозитория и дискового пространства

```
$ git pull --ff-only origin main
From https://github.com/nurasss/cashback-one
 * branch            main       -> FETCH_HEAD
Already up to date.

$ git status --short
?? C:/
?? reports/old-promo-cards-2026-11-06/
?? video/

$ df -h /
Filesystem       Size   Used  Avail Capacity iused    ifree %iused  Mounted on
/dev/disk1s4s1  113Gi  8.7Gi  4.6Gi    66%  356882 48025680    1%   /

$ ls -la mobile/dist
total 1707960
drwxr-xr-x@ 19 nuras  staff       608 Nov  6 01:54 .
drwxr-xr-x@ 26 nuras  staff       832 Nov  5 21:28 ..
-rw-r--r--@  1 nuras  staff  51154351 Oct 17 08:41 cashback-one-1.0.0.apk
-rw-r--r--@  1 nuras  staff  68600435 Nov  2 10:50 cashback-one-1.0.10.apk
-rw-r--r--@  1 nuras  staff  68601127 Nov  4 21:57 cashback-one-1.0.11-test.apk
-rw-r--r--@  1 nuras  staff  68600383 Nov  4 11:35 cashback-one-1.0.11-test.no-api.apk
-rw-r--r--@  1 nuras  staff  69675373 Nov  5 09:30 cashback-one-1.0.12.apk
-rw-r--r--@  1 nuras  staff  51167439 Oct 22 17:36 cashback-one-1.0.3.apk
-rw-r--r--@  1 nuras  staff  51630551 Oct 22 22:29 cashback-one-1.0.4.apk
-rw-r--r--@  1 nuras  staff  51630487 Oct 23 17:12 cashback-one-1.0.5.apk
-rw-r--r--@  1 nuras  staff  62529495 Oct 24 10:42 cashback-one-1.0.6.apk
-rw-r--r--@  1 nuras  staff  67778452 Oct 31 15:38 cashback-one-1.0.7.apk
-rw-r--r--@  1 nuras  staff  67773772 Oct 31 19:48 cashback-one-1.0.8.apk
-rw-r--r--@  1 nuras  staff  67951855 Nov  1 14:08 cashback-one-1.0.9.apk
-rw-r--r--@  1 nuras  staff  63668358 Nov  6 01:54 keremet-cashback-1.0.12.apk
-rw-r--r--@  1 nuras  staff  63665662 Nov  5 21:45 keremet-cashback-1.0.12.no-push.apk
-rw-r--r--   1 nuras  staff        89 Oct 22 17:51 release-SHA256SUMS.txt
-rw-r--r--   1 nuras  staff      7542 Oct 22 17:57 release-notes-1.0.3.md
drwxr-xr-x@  7 nuras  staff       224 Nov  5 01:25 web-demo
```

- Ветка `main` актуальна (`eb30eb5`).
- Рабочая директория чистая (только исключённые локальные папки).
- Доступно 4.6 ГБ свободного места (> 3 ГБ).
- В `mobile/dist/` файлов `cashback-one-1.0.13.apk` и `keremet-cashback-1.0.13.apk` не существует.

---

## 2. Шаг 2: Обновление версии (1.0.13 / versionCode 14)

### 2.1. `git diff mobile/app.json`

```diff
diff --git a/mobile/app.json b/mobile/app.json
index 55d2ad4..8b4ff51 100644
--- a/mobile/app.json
+++ b/mobile/app.json
@@ -3,7 +3,7 @@
     "name": "Cashback One",
     "slug": "cashback-one",
     "scheme": "cashbackone",
-    "version": "1.0.12",
+    "version": "1.0.13",
     "orientation": "portrait",
     "icon": "./assets/icon.png",
     "userInterfaceStyle": "light",
@@ -42,7 +42,7 @@
     },
     "android": {
       "package": "kz.cashbackone.mobile",
-      "versionCode": 13,
+      "versionCode": 14,
       "adaptiveIcon": {
         "foregroundImage": "./assets/icon-foreground.png",
         "backgroundColor": "#FD6156"
```

### 2.2. Строки `mobile/android/app/build.gradle` (строки 92–98)

```groovy
        applicationId 'kz.cashbackone.mobile'
        minSdkVersion rootProject.ext.minSdkVersion
        targetSdkVersion rootProject.ext.targetSdkVersion
        versionCode 14
        versionName "1.0.13"

        buildConfigField "String", "REACT_NATIVE_RELEASE_LEVEL", "\"${findProperty('reactNativeReleaseLevel') ?: 'stable'}\""
```

---

## 3. Шаг 3: Проверки до сборки

### 3.1. Jest (`npx jest --runInBand`)

```
PASS tests/clientConfig.test.tsx (5.844 s)
PASS tests/profileSave.test.tsx
PASS tests/appUpdate.test.tsx
PASS tests/flows.test.tsx
PASS tests/homeArtwork.test.tsx
PASS tests/qrScreen.test.tsx
PASS tests/push.test.tsx
PASS tests/core.test.ts
PASS tests/demo.test.ts
PASS tests/cityCustom.test.tsx
PASS tests/wallet.test.tsx
PASS tests/cacheRefresh.test.tsx
PASS tests/components.test.tsx
PASS tests/cardScanner.test.tsx
PASS tests/avatar.test.tsx
PASS tests/historyPeriod.test.tsx
PASS tests/levels.test.tsx
PASS tests/serverContentAndCache.test.tsx
PASS tests/session.test.ts
PASS tests/promotionsArtwork.test.tsx
PASS tests/loginScreen.test.tsx
PASS tests/transport.test.ts
PASS tests/keyboardLift.test.ts

Test Suites: 23 passed, 23 total
Tests:       311 passed, 311 total
Snapshots:   0 total
Time:        23.599 s, estimated 36 s
Ran all test suites.
```

### 3.2. TypeScript (`npx tsc --noEmit`)

```
(exit code 0, no errors)
```

### 3.3. ESLint (`npx eslint .`)

```
/Users/nuras/Desktop/cashback-one/mobile/src/components/useKeyboardLift.ts
  62:20  warning  The ref value 'generation.current' will likely have changed by the time this effect cleanup function runs. If this ref points to a node rendered by React, copy 'generation.current' to a variable inside the effect, and use that variable in the cleanup function  react-hooks/exhaustive-deps

✖ 1 problem (0 errors, 1 warning)
```

---

## 4. Шаг 4: Сборка Keremet (`mobile/scripts/build-client.sh keremet`)

- **Выполнение задачи Google Services:**
  ```
  > Task :app:processKeremetReleaseGoogleServices UP-TO-DATE
  ```
  (задача выполнена/актуальна, статус не `SKIPPED`).
- **Итог сборки Gradle:**
  ```
  BUILD SUCCESSFUL in 3m 14s
  403 actionable tasks: 42 executed, 361 up-to-date
  Copied APK to dist/keremet-cashback-1.0.13.apk
  === Build completed successfully for keremet ===
  -rw-r--r--@ 1 nuras  staff    61M Nov  6 12:37 dist/keremet-cashback-1.0.13.apk
  e12605a2fa27e4f7697bbf098662e2b6089720257ecdea4ed9e926d967450c36  dist/keremet-cashback-1.0.13.apk
  ```
- **Остановка демона и проверка диска:**
  ```
  $ cd mobile/android && ./gradlew --stop
  No Gradle daemons are running.

  $ df -h /
  Filesystem       Size   Used  Avail Capacity iused    ifree %iused  Mounted on
  /dev/disk1s4s1  113Gi  8.7Gi  3.5Gi    72%  356882 36228800    1%   /
  ```
  (доступно 3.5 ГБ > 3 ГБ, переходим к сборке общего приложения).

---

## 5. Шаг 5: Сборка общего Cashback One (`mobile/scripts/build-client.sh cashbackone`)

- **Выполнение задачи Google Services:**
  ```
  > Task :app:processCashbackoneReleaseGoogleServices
  ```
  (задача выполнена, не `SKIPPED`).
- **Итог сборки Gradle:**
  ```
  BUILD SUCCESSFUL in 4m
  403 actionable tasks: 100 executed, 303 up-to-date
  Copied APK to dist/cashback-one-1.0.13.apk
  === Build completed successfully for cashbackone ===
  -rw-r--r--@ 1 nuras  staff    61M Nov  6 12:41 dist/cashback-one-1.0.13.apk
  3b8e5382282c97c7d93d4a54725ad8333806be3efe2bf9cb18969891fb026039  dist/cashback-one-1.0.13.apk
  ```
- **Остановка демона:**
  ```
  $ cd mobile/android && ./gradlew --stop
  No Gradle daemons are running.
  ```

---

## 6. Шаг 6: Проверки каждого APK

### 6.1. `aapt2 dump badging`

#### Keremet Bonus 1.0.13
```
package: name='kz.cashbackone.keremet' versionCode='14' versionName='1.0.13' platformBuildVersionName='16' platformBuildVersionCode='36' compileSdkVersion='36' compileSdkVersionCodename='16'
minSdkVersion:'24'
targetSdkVersion:'36'
application-label:'Keremet Bonus'
application: label='Keremet Bonus' icon='res/BW.xml'
launchable-activity: name='kz.cashbackone.mobile.MainActivity'  label='' icon=''
native-code: 'arm64-v8a' 'armeabi-v7a'
```

#### Cashback One 1.0.13
```
package: name='kz.cashbackone.mobile' versionCode='14' versionName='1.0.13' platformBuildVersionName='16' platformBuildVersionCode='36' compileSdkVersion='36' compileSdkVersionCodename='16'
minSdkVersion:'24'
targetSdkVersion:'36'
application-label:'Cashback One'
application: label='Cashback One' icon='res/BW.xml'
launchable-activity: name='kz.cashbackone.mobile.MainActivity'  label='' icon=''
native-code: 'arm64-v8a' 'armeabi-v7a'
```

### 6.2. Сертификат подписи (`apksigner verify --print-certs`)

#### Keremet Bonus 1.0.13
```
Signer #1 certificate DN: CN=Cashback One, O=POSCENTER, C=KZ
Signer #1 certificate SHA-256 digest: 14afcbb5ec8375e3130b2832b1a7468372e1205c3a275ba56b8ff7b1e483cd63
Signer #1 certificate SHA-1 digest: aadba44bcf5a58afccd295df29351d6ca285f5f4
Signer #1 certificate MD5 digest: bf366fbeed9edf7f64e76ef4bb582985
```

#### Cashback One 1.0.13
```
Signer #1 certificate DN: CN=Cashback One, O=POSCENTER, C=KZ
Signer #1 certificate SHA-256 digest: 14afcbb5ec8375e3130b2832b1a7468372e1205c3a275ba56b8ff7b1e483cd63
Signer #1 certificate SHA-1 digest: aadba44bcf5a58afccd295df29351d6ca285f5f4
Signer #1 certificate MD5 digest: bf366fbeed9edf7f64e76ef4bb582985
```

Оба APK подписаны эталонным ключом (`14afcbb5ec83...`).

### 6.3. Разрешения (сравнение с версиями 1.0.12)

- Keremet 1.0.12 vs 1.0.13: `diff -u` пустой (0 добавлено, 0 удалено, ровно 30 разрешений).
- Cashback One 1.0.12 vs 1.0.13: `diff -u` пустой (0 добавлено, 0 удалено, ровно 30 разрешений).

### 6.4. Ресурсы Google Services (`aapt2 dump resources`)

- **Cashback One 1.0.12:**
  - `gcm_defaultSenderId` = `"693902155886"`
  - `google_app_id` = `"1:693902155886:android:d0d86f1770025430b2067f"`
- **Cashback One 1.0.13:**
  - `gcm_defaultSenderId` = `"693902155886"`
  - `google_app_id` = `"1:693902155886:android:d0d86f1770025430b2067f"` (100% совпадение с 1.0.12)
- **Keremet 1.0.13:**
  - `gcm_defaultSenderId` = `"693902155886"`
  - `google_app_id` = `"1:693902155886:android:1f667ed4a7db868bb2067f"` (совпадает с клиентом Keremet)

### 6.5. Инспекция Hermes байткода (`hermesc -b -dump-bytecode`)

1. **`getClientConfig`:**
   - В Keremet подставлен `"keremet"`:
     ```
     Function<getClientConfig>(2 params, 17 registers, 0 symbols):
         LoadParam         r6, 1
         LoadConstNull     r0
         JNotEqual         L1, r6, r0
         LoadConstString   r6, "keremet"
     ```
   - В Cashback One подставлен `"cashbackone"`:
     ```
     Function<getClientConfig>(2 params, 17 registers, 0 symbols):
         LoadParam         r6, 1
         LoadConstNull     r0
         JNotEqual         L1, r6, r0
         LoadConstString   r6, "cashbackone"
     ```
2. **`DEMO_ENABLED` = false в модуле `mockApi` (в обоих APK):**
   ```
       Call2             r3, r4, r0, r3
       StoreToEnvironment r2, 2, r3
       LoadConstFalse    r3
       StoreNPToEnvironment r2, 3, r3
       LoadConstString   r3, "https://demo.inva"...
   ```
3. **Рабочий адрес API:**
   Строка `https://api.cashback-qr.poscenter.kz` присутствует в обоих бандлах.
4. **Попадание исправления кеша (`initialDataUpdatedAt`):**
   Строка `initialDataUpdatedAt` присутствует в таблицах строк обоих бандлов Hermes (`index.android.bundle`).

### 6.6. Иконки общего приложения (`res/mipmap-*/ic_launcher*`): 1.0.12 vs 1.0.13

Все 17 файлов ресурсов иконки совпадают побайтово и по контрольным суммам SHA-256:

| Файл | Размер | SHA-256 | Статус |
|---|---|---|---|
| `res/d2.webp` (mdpi launcher) | 3 102 | `1178c3a4d85a752fdf754997c551a4b42b8ef25a0b74f0f8e4d1cc960d4de040` | MATCH |
| `res/MO.webp` (hdpi launcher) | 6 088 | `5809f83f1e96f364b4b7186a3051ab45284db5aae0d4f6aa01c16a92a939a325` | MATCH |
| `res/qs.webp` (xhdpi launcher) | 10 292 | `5625187693ec8c07b3a2c98f596d3b4b0ac54ba60c3ecfee936ded8e51a55c2a` | MATCH |
| `res/Sn.webp` (xxhdpi launcher) | 20 790 | `e58af52bbb3a9b749dba6d8d134e36b14c29e8bc19df7d82911ccfbdd5529c77` | MATCH |
| `res/sK.webp` (xxxhdpi launcher) | 35 418 | `e8fec23c7e944e599148ac56f1d178528dfa0a8b287b8dae813cd83746a95344` | MATCH |
| `res/BW.xml` (anydpi-v26 adaptive) | 448 | `ebe84e43293cb6f64c55687504d73f0d2de8938bbf79f8ed977448096b133156` | MATCH |
| `res/Nt.webp` (mdpi foreground) | 2 180 | `c6ec021faf143e6e6a94c003705a97f66f5c070a7f83a7634964a3fa820fd236` | MATCH |
| `res/13.webp` (hdpi foreground) | 3 820 | `32f59a0274c077ef5c5aae2b90fa928595653f997ab87a0da8b2f609b7df7fe1` | MATCH |
| `res/9Q.webp` (xhdpi foreground) | 5 680 | `fb7c1068258fce764b7b95c8f6fd0566672e13c230d0a84f6be1c30dccd423a9` | MATCH |
| `res/iE.webp` (xxhdpi foreground) | 10 018 | `fdc514ca293b1ea34472c3eddbc7f703874bf3a163fde12d2a68d70a80d5e9e4` | MATCH |
| `res/5c.webp` (xxxhdpi foreground) | 15 054 | `3e59e2e72c7bea96f0a388d7e5ea4cd2be6b9e47d054478868ddda7d1f66790a` | MATCH |
| `res/yw.webp` (mdpi round) | 3 264 | `a8dbbddd39287c9aec28e8f9b0b9247d192dca55c2f2fcfd9650f4e69c1177d5` | MATCH |
| `res/fq.webp` (hdpi round) | 6 256 | `21ac4dfd56eb209f5b0f47dbb8c1893051854cfddc949156a49a1f0f76b315c4` | MATCH |
| `res/u5.webp` (xhdpi round) | 10 070 | `abfea78a733eefaaae27976d2e87df7ae8c110056ce475120f04254639e60287` | MATCH |
| `res/j_.webp` (xxhdpi round) | 19 922 | `d45eb826a8a245b5cae1b9c04b45deccfe5f8f3f70db3e8ac63ed8a9da0a9230` | MATCH |
| `res/-6.webp` (xxxhdpi round) | 33 504 | `4d9bda357d90376d5b92b1c8a1dad95ec0f88c4954b33789ed7e987a609477d6` | MATCH |
| `res/0K.xml` (anydpi-v26 round) | 448 | `ebe84e43293cb6f64c55687504d73f0d2de8938bbf79f8ed977448096b133156` | MATCH |

### 6.7. Размеры и SHA-256 APK

- **`mobile/dist/keremet-cashback-1.0.13.apk`**:
  - Размер: **63 668 818** байт (~60.7 MiB)
  - SHA-256: `e12605a2fa27e4f7697bbf098662e2b6089720257ecdea4ed9e926d967450c36`
- **`mobile/dist/cashback-one-1.0.13.apk`**:
  - Размер: **63 468 253** байт (~60.5 MiB)
  - SHA-256: `3b8e5382282c97c7d93d4a54725ad8333806be3efe2bf9cb18969891fb026039`

---

## 7. Шаг 7: Дисковое пространство и статус репозитория

```
$ df -h /
Filesystem       Size   Used  Avail Capacity iused    ifree %iused  Mounted on
/dev/disk1s4s1  113Gi  8.7Gi  2.6Gi    78%  356882 27003160    1%   /

$ git status --short
 M mobile/app.json
?? C:/
?? reports/old-promo-cards-2026-11-06/
?? video/
```

---

## 8. Отличия общего Cashback One 1.0.13 от 1.0.12 (кроме версии)

1. **Сборка через flavor-систему:** 1.0.13 собран через `build-client.sh cashbackone` (flavor `cashbackone`), в то время как 1.0.12 собирался прежним `build-apk.sh` до перехода на flavors.
2. **Размер APK:** уменьшился с 69 675 373 байт до 63 468 253 байт (~6.2 МБ экономии). При flavor-сборке количество файлов в архиве сократилось с 1358 до 1343 за счет отсечения неиспользуемых растровых ресурсов `res/*.png` с помощью resource shrinking.
3. **Функционал:** включены правки фонового обновления кеша (`initialDataUpdatedAt`) и жест потягивания вниз (`RefreshControl`) на главной странице.
4. **Идентичность платформенных параметров:** пакет (`kz.cashbackone.mobile`), название («Cashback One»), подпись, все 30 разрешений, `google_app_id` / `gcm_defaultSenderId` и все 17 файлов иконок launcher на 100% идентичны версии 1.0.12.

---

## 9. Что не проверено

1. Установка APK 1.0.13 поверх установленного 1.0.12 на физическом Android-телефоне (in-place update).
2. Обновление баннера после перезапуска приложения на реальном устройстве.
