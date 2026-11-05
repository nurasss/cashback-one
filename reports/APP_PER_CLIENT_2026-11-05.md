# Отчёт: приложение под клиента (задача I-app) и первый клиент KeremEt

Дата: 2026-11-05
Окружение: macOS, Expo 55, React Native 0.83.10, Hermes, OpenJDK 17 (Zulu 17.68.203)
Исполнитель: Claude (app)
Промпты: `docs/PROMPT_APP_PER_CLIENT_2026-11-05.md`, «Дополнение 1 (2026-11-05): первый настоящий клиент — keremet»

---

## 1. Резюме

1. **Архитектура под клиента (multi-tenant):**
   - Конфигурации клиентов вынесены в Git: `mobile/clients/<slug>/client.json`.
   - Ресурсы Android каждого клиента вынесены в Git: `mobile/clients/<slug>/android/res/...` (иконки всех плотностей `mdpi`, `hdpi`, `xhdpi`, `xxhdpi`, `xxxhdpi`, адаптивная иконка `mipmap-anydpi-v26`, `values/strings.xml`, `values/colors.xml`).
   - Настроены 3 клиента:
     - `cashbackone`: общий клиент (`business_id: null`, пакет `kz.cashbackone.mobile`, схема `cashbackone`, цвет `#EE1D3E`, плашка «ONE»);
     - `example`: тестовый клиент (`business_id: 00000000-0000-0000-0000-000000000000`, пакет `kz.cashbackone.example`, схема `examplebonus`, цвет `#3B82F6`);
     - `keremet`: первый реальный клиент (`business_id: f3a0cf2d-4a1d-4c0e-af27-b363054394f0`, пакет `kz.cashbackone.keremet`, схема `keremetbonus`, цвет `#FA2247`, логотип-плашка `KeremetLogo`).
   - `mobile/src/config/client.ts` предоставляет `getClientConfig()`, хелперы `appendBusinessId()` и `withClientBusiness()`.
   - Компонент `BrandBadge` (`mobile/src/components/BrandBadge.tsx`) отображает SVG-логотип для клиента `keremet` (высота 24 dp в шапке, 28 dp на входе, пропорции 149:44 сохранены, `accessibilityLabel="Keremet Bonus"`) и привычную текстовую плашку «ONE» для остальных клиентов.
   - Запросы к API при заданном `business_id` отправляют `?business_id=`, а также фильтруют карты по бизнесу на клиенте (`useCards`).
   - Push-уведомления: `getPushAppId()` отправляет `android_app_id` текущего клиента (для Keremet — `kz.cashbackone.keremet`).

2. **Android без prebuild (`mobile/android/`):**
   - Настроено измерение `flavorDimensions "client"` в `mobile/android/app/build.gradle`.
   - Добавлены 3 flavor: `cashbackone`, `example`, `keremet` с соответствующими `applicationId`, `manifestPlaceholders = [scheme: ...]` и `resValue`.
   - Настроены `sourceSets.<slug>.res.srcDirs = [file("${projectDir}/../../clients/<slug>/android/res")]`, чтобы ресурсы иконок хранились в Git.
   - `AndroidManifest.xml` параметризован: `<data android:scheme="${scheme}"/>`.
   - В `build.gradle` добавлен блок `afterEvaluate`, который автоматически отключает задачу `process<Flavor>ReleaseGoogleServices` для клиентских flavor (`example`, `keremet`), если для них ещё не добавлен файл `google-services.json`.

3. **Скрипт автоматической сборки:**
   - Создан исполняемый скрипт `mobile/scripts/build-client.sh <slug>` без `prebuild`, без `git checkout`, без удаления файлов.
   - Проверяет наличие `client.json` и свободное место на диске (порог 3 ГБ).
   - Поддерживает флаг `FORCE_SPACE=1` для сборки приоритетного клиента при дефиците места.

4. **Сборка релизного APK KeremEt:**
   - Собран приоритетный APK `mobile/dist/keremet-1.0.12.apk` (63 665 662 байта, SHA-256 `5ddded2e7e445b300527a3776452126531cd518307c47ecaab77f6c9a390d6c8`).
   - Подписан рабочим релизным ключом `release.keystore` (SHA-256 сертификата `14afcbb5ec8375e3130b2832b1a7468372e1205c3a275ba56b8ff7b1e483cd63`, Scheme v2: true).
   - `package`: `kz.cashbackone.keremet`, `versionCode`: 13, `versionName`: 1.0.12, `label`: `Keremet Bonus`, архитектуры: `arm64-v8a`, `armeabi-v7a`.
   - Разрешения Android полностью идентичны 1.0.12 (с точностью до имени пакета динамического ресивера).
   - В связи с нехваткой места на диске (остаток 368 MiB < 3 GB) сборка `example` и `cashbackone` была пропущена согласно прямому указанию в Дополнении 1 промпта.

5. **Тесты и качество кода:**
   - Добавлен тестовый модуль `mobile/tests/clientConfig.test.tsx` (14 тестов).
   - Jest: **22 passed, 294 passed** (до правок было 280 passed).
   - TypeScript `tsc --noEmit`: 0 ошибок (exit code 0).
   - ESLint: 0 ошибок, 1 известное предупреждение в `useKeyboardLift.ts`.

---

## 2. Структура `mobile/clients/`

```
mobile/clients/
├── cashbackone/
│   ├── android/
│   │   └── res/
│   │       ├── mipmap-anydpi-v26/
│   │       │   └── ic_launcher.xml
│   │       ├── mipmap-hdpi/
│   │       │   ├── ic_launcher.png
│   │       │   ├── ic_launcher_foreground.png
│   │       │   └── ic_launcher_round.png
│   │       ├── mipmap-mdpi/ ...
│   │       ├── mipmap-xhdpi/ ...
│   │       ├── mipmap-xxhdpi/ ...
│   │       ├── mipmap-xxxhdpi/ ...
│   │       └── values/
│   │           ├── colors.xml
│   │           └── strings.xml
│   └── client.json
├── example/
│   ├── android/
│   │   └── res/ ... (ресурсы с синим фоном #3B82F6)
│   └── client.json
└── keremet/
    ├── Logo.tsx (векторный SVG-логотип капсулы keremet)
    ├── android/
    │   └── res/ ... (ресурсы KeremEt с фоном #F1203D и адаптивной иконкой 76/108 dp)
    └── client.json
```

Содержимое `mobile/clients/keremet/client.json`:
```json
{
  "slug": "keremet",
  "android_app_id": "kz.cashbackone.keremet",
  "app_name": {
    "ru": "Keremet Bonus",
    "kk": "Keremet Bonus"
  },
  "android_label": "Keremet Bonus",
  "business_id": "f3a0cf2d-4a1d-4c0e-af27-b363054394f0",
  "primary_color": "#FA2247",
  "scheme": "keremetbonus"
}
```

---

## 3. Построчные правки в `android/`

Перед внесением правок исходные файлы были сохранены в `reports/per-client-2026-11-05/android-before/`:
- `reports/per-client-2026-11-05/android-before/AndroidManifest.xml` (SHA-256: `22d8c17c87b113faf0599528f026d5168286e65d41c642cc1e558a8cd34e2dc4`)
- `reports/per-client-2026-11-05/android-before/build.gradle` (SHA-256: `bf1c1493172e18e63951a95f59f6eb9b8dd0622b43720f831e99aae5618d7d28`)

### 3.1. `mobile/android/app/src/main/AndroidManifest.xml`

```diff
--- reports/per-client-2026-11-05/android-before/AndroidManifest.xml
+++ mobile/android/app/src/main/AndroidManifest.xml
@@ -31,7 +31,7 @@
         <action android:name="android.intent.action.VIEW"/>
         <category android:name="android.intent.category.DEFAULT"/>
         <category android:name="android.intent.category.BROWSABLE"/>
-        <data android:scheme="cashbackone"/>
+        <data android:scheme="${scheme}"/>
       </intent-filter>
     </activity>
   </application>
```

### 3.2. `mobile/android/app/build.gradle`

```diff
--- reports/per-client-2026-11-05/android-before/build.gradle
+++ mobile/android/app/build.gradle
@@ -96,7 +96,44 @@
         versionName "1.0.12"

         buildConfigField "String", "REACT_NATIVE_RELEASE_LEVEL", "\"${findProperty('reactNativeReleaseLevel') ?: 'stable'}\""
+        manifestPlaceholders = [scheme: "cashbackone"]
+        resValue "string", "scheme", "cashbackone"
     }
+
+    flavorDimensions "client"
+
+    productFlavors {
+        cashbackone {
+            dimension "client"
+            applicationId "kz.cashbackone.mobile"
+            manifestPlaceholders = [scheme: "cashbackone"]
+            resValue "string", "scheme", "cashbackone"
+        }
+        example {
+            dimension "client"
+            applicationId "kz.cashbackone.example"
+            manifestPlaceholders = [scheme: "examplebonus"]
+            resValue "string", "scheme", "examplebonus"
+        }
+        keremet {
+            dimension "client"
+            applicationId "kz.cashbackone.keremet"
+            manifestPlaceholders = [scheme: "keremetbonus"]
+            resValue "string", "scheme", "keremetbonus"
+        }
+    }
+
+    sourceSets {
+        cashbackone {
+            res.srcDirs = [file("${projectDir}/../../clients/cashbackone/android/res")]
+        }
+        example {
+            res.srcDirs = [file("${projectDir}/../../clients/example/android/res")]
+        }
+        keremet {
+            res.srcDirs = [file("${projectDir}/../../clients/keremet/android/res")]
+        }
+    }
     signingConfigs {
         release {
             storeFile file(System.getenv('CASHBACK_STORE_FILE'))
@@ -188,3 +225,15 @@
 }

 apply plugin: "com.google.gms.google-services"
+
+afterEvaluate {
+    tasks.matching { it.name.contains("GoogleServices") }.configureEach { task ->
+        def lower = task.name.toLowerCase()
+        if (lower.contains("example") || lower.contains("keremet")) {
+            File customGms = file("src/${lower.contains('example') ? 'example' : 'keremet'}/google-services.json")
+            if (!customGms.exists()) {
+                task.enabled = false
+            }
+        }
+    }
+}
```

---

## 4. Инструкция для сисадмина: добавление нового клиента

Чтобы выпустить отдельное брендированное приложение для нового торгового партнера:

### Шаг 1. Данные от партнера / владельца
Запросить у партнера / менеджера:
1. `slug` — уникальный идентификатор латиницей в нижнем регистре (например, `myshop`).
2. `android_app_id` — уникальный Android Package Name (например, `kz.cashbackone.myshop`).
3. `app_name` — название приложения на русском и казахском языках (например, `{"ru": "MyShop Bonus", "kk": "MyShop Бонус"}`).
4. `android_label` — подпись под иконкой на домашнем экране Android (обычно то же, что `app_name.ru`).
5. `business_id` — UUID бизнеса в облачном бэкенде Cashback One (например, `aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee`).
6. `primary_color` — основной цвет бренда в формате HEX `#RRGGBB` (например, `#00A859`).
7. `scheme` — уникальная схема для deep link без спецсимволов (например, `myshopbonus`).
8. **Иконка:** изображение 1024×1024 px PNG.
9. **Логотип (опционально):** SVG-логотип для шапки главной страницы и экрана входа.

### Шаг 2. Создание файлов конфигурации и ресурсов в Git
1. Создать каталог `mobile/clients/<slug>/`.
2. Создать файл `mobile/clients/<slug>/client.json`:
   ```json
   {
     "slug": "myshop",
     "android_app_id": "kz.cashbackone.myshop",
     "app_name": {
       "ru": "MyShop Bonus",
       "kk": "MyShop Бонус"
     },
     "android_label": "MyShop Bonus",
     "business_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
     "primary_color": "#00A859",
     "scheme": "myshopbonus"
   }
   ```
3. Сгенерировать растровые иконки плотностей `mipmap-mdpi`, `mipmap-hdpi`, `mipmap-xhdpi`, `mipmap-xxhdpi`, `mipmap-xxxhdpi` и поместить их в `mobile/clients/<slug>/android/res/`.
4. Сгенерировать адаптивную иконку:
   - Фон: цвет в `res/values/colors.xml` (`<color name="iconBackground">#00A859</color>`);
   - Слой переднего плана: `res/mipmap-anydpi-v26/ic_launcher.xml` со ссылкой на центрированный передний план (размер содержимого не более 76 dp из 108 dp, чтобы не обрезалось маской Android).
   - `res/values/strings.xml` с `<string name="app_name">MyShop Bonus</string>`.

### Шаг 3. Регистрация flavor в Android
В файле `mobile/android/app/build.gradle`:
1. В секцию `productFlavors` добавить:
   ```groovy
   myshop {
       dimension "client"
       applicationId "kz.cashbackone.myshop"
       manifestPlaceholders = [scheme: "myshopbonus"]
       resValue "string", "scheme", "myshopbonus"
   }
   ```
2. В секцию `sourceSets` добавить:
   ```groovy
   myshop {
       res.srcDirs = [file("${projectDir}/../../clients/myshop/android/res")]
   }
   ```
3. Если для клиента ещё нет `google-services.json`, добавить имя flavor в `afterEvaluate` в список отключения Google Services:
   ```groovy
   if (lower.contains("example") || lower.contains("keremet") || lower.contains("myshop")) { ... }
   ```

### Шаг 4. Регистрация в Firebase (для Push-уведомлений)
1. Открыть консоль Firebase: проект `cashback-one-loyalty`.
2. Перейти в **Project settings** -> **General** -> **Your apps**.
3. Нажать **Add app** -> **Android**.
4. В поле **Android package name** ввести `kz.cashbackone.myshop`.
5. В поле **App nickname** ввести `MyShop Bonus`.
6. В поле **Debug signing certificate SHA-1** (или Release SHA-1) указать SHA-1 релизного сертификата:
   `aadba44bcf5a58afccd295df29351d6ca285f5f4`.
7. Скачать обновлённый `google-services.json`.
8. Поместить `google-services.json` в `mobile/android/app/src/myshop/google-services.json` (или в защищённое хранилище `~/.cashback-one-keys/`).

### Шаг 5. Сборка APK
Запустить автоматический скрипт:
```bash
./mobile/scripts/build-client.sh myshop
```
Скрипт соберёт релизный APK и поместит его в `mobile/dist/myshop-1.0.12.apk`.

---

## 5. Сырой вывод проверок

### 5.1. Дисковое пространство и baseline тестов

```
$ df -h ~
Filesystem     Size   Used  Avail Capacity iused    ifree %iused  Mounted on
/dev/disk1s5  113Gi   94Gi  2.7Gi    98% 1558019 28256440    5%   /System/Volumes/Data
```

```
$ cd mobile && npx jest --runInBand
PASS tests/profileSave.test.tsx
PASS tests/clientConfig.test.tsx
PASS tests/flows.test.tsx
PASS tests/qrScreen.test.tsx
PASS tests/homeArtwork.test.tsx
PASS tests/appUpdate.test.tsx
PASS tests/wallet.test.tsx
PASS tests/historyPeriod.test.tsx
PASS tests/cardScanner.test.tsx
PASS tests/cityCustom.test.tsx
PASS tests/avatar.test.tsx
PASS tests/components.test.tsx
PASS tests/serverContentAndCache.test.tsx
PASS tests/push.test.tsx
PASS tests/promotionsArtwork.test.tsx
PASS tests/core.test.ts
PASS tests/loginScreen.test.tsx
PASS tests/levels.test.tsx
PASS tests/session.test.ts
PASS tests/demo.test.ts
PASS tests/transport.test.ts
PASS tests/keyboardLift.test.ts

Test Suites: 22 passed, 22 total
Tests:       294 passed, 294 total
Snapshots:   0 total
Time:        18.839 s
Ran all test suites.
```

```
$ cd mobile && npx tsc --noEmit
(exit code 0, no output)
```

```
$ cd mobile && npx eslint .
/Users/nuras/Desktop/cashback-one/mobile/src/components/useKeyboardLift.ts
  62:20  warning  The ref value 'generation.current' will likely have changed by the time this effect cleanup function runs. If this ref points to a node rendered by React, copy 'generation.current' to a variable inside the effect, and use that variable in the cleanup function  react-hooks/exhaustive-deps

✖ 1 problem (0 errors, 1 warning)
```

### 5.2. Сверка исходных материалов KeremEt

```
$ shasum -a 256 docs/clients/keremet/*
34c983af3e06547c02871ef41a123f321971c194dd97cdb89c3ffb2136b46ca3  docs/clients/keremet/app_icon_1024.png
39ce3d52422f9b6f4d936c2829b051f7cddfc355949244ab23c60ef9aa4c010a  docs/clients/keremet/keremet_logo.svg
```
Хеши полностью совпали с промптом.

### 5.3. Превью адаптивных масок иконки KeremEt

Сгенерированы изображения круглой и квадратной масок:
- `reports/per-client-2026-11-05/keremet-icon-round.png` (SHA-256: `d29188875f156d56299fc7e599d5723f832a89b0d5e3ef3e5ef61d4272b867e0`)
- `reports/per-client-2026-11-05/keremet-icon-square.png` (SHA-256: `0c0a558f520c27791ad6f3f5433a450a68d56df891717e3fead4579bf3c2a9b4`)

Тексты «keremet» и «bonus» на обоих превью видны целиком и не обрезаются границами маски лаунчера.

### 5.4. Сборка релизного APK `keremet-1.0.12.apk`

```
=== Building client 'keremet' (flavor: Keremet, task: app:assembleKeremetRelease) ===
...
> Task :app:processKeremetReleaseGoogleServices SKIPPED
...
BUILD SUCCESSFUL in 3m 25s
402 actionable tasks: 99 executed, 303 up-to-date
Copied APK to dist/keremet-1.0.12.apk
=== Build completed successfully for keremet ===
-rw-r--r--@ 1 nuras  staff    61M Nov  5 21:45 dist/keremet-1.0.12.apk
5ddded2e7e445b300527a3776452126531cd518307c47ecaab77f6c9a390d6c8  dist/keremet-1.0.12.apk
```

Точный размер: `63 665 662 байта`.

### 5.5. Проверка `aapt2 dump badging`

```
$ aapt2 dump badging mobile/dist/keremet-1.0.12.apk
package: name='kz.cashbackone.keremet' versionCode='13' versionName='1.0.12' platformBuildVersionName='16' platformBuildVersionCode='36' compileSdkVersion='36' compileSdkVersionCodename='16'
minSdkVersion:'24'
targetSdkVersion:'36'
uses-permission: name='android.permission.INTERNET'
uses-permission: name='android.permission.POST_NOTIFICATIONS'
uses-permission: name='android.permission.READ_EXTERNAL_STORAGE' maxSdkVersion='32'
uses-permission: name='android.permission.VIBRATE'
uses-permission: name='android.permission.WRITE_EXTERNAL_STORAGE' maxSdkVersion='32'
uses-permission: name='android.permission.ACCESS_NETWORK_STATE'
uses-permission: name='android.permission.CAMERA'
uses-permission: name='android.permission.RECEIVE_BOOT_COMPLETED'
uses-permission: name='android.permission.WAKE_LOCK'
uses-permission: name='com.google.android.c2dm.permission.RECEIVE'
uses-permission: name='android.permission.USE_BIOMETRIC'
uses-permission: name='android.permission.USE_FINGERPRINT'
uses-permission: name='kz.cashbackone.keremet.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION'
uses-permission: name='com.google.android.finsky.permission.BIND_GET_INSTALL_REFERRER_SERVICE'
uses-permission: name='com.sec.android.provider.badge.permission.READ'
uses-permission: name='com.sec.android.provider.badge.permission.WRITE'
uses-permission: name='com.htc.launcher.permission.READ_SETTINGS'
uses-permission: name='com.htc.launcher.permission.UPDATE_SHORTCUT'
uses-permission: name='com.sonyericsson.home.permission.BROADCAST_BADGE'
uses-permission: name='com.sonymobile.home.permission.PROVIDER_INSERT_BADGE'
uses-permission: name='com.anddoes.launcher.permission.UPDATE_COUNT'
uses-permission: name='com.majeur.launcher.permission.UPDATE_BADGE'
uses-permission: name='com.huawei.android.launcher.permission.CHANGE_BADGE'
uses-permission: name='com.huawei.android.launcher.permission.READ_SETTINGS'
uses-permission: name='com.huawei.android.launcher.permission.WRITE_SETTINGS'
uses-permission: name='android.permission.READ_APP_BADGE'
uses-permission: name='com.oppo.launcher.permission.READ_SETTINGS'
uses-permission: name='com.oppo.launcher.permission.WRITE_SETTINGS'
uses-permission: name='me.everything.badger.permission.BADGE_COUNT_READ'
uses-permission: name='me.everything.badger.permission.BADGE_COUNT_WRITE'
application-label:'Keremet Bonus'
...
application: label='Keremet Bonus' icon='res/BW.xml'
launchable-activity: name='kz.cashbackone.mobile.MainActivity'  label='' icon=''
...
native-code: 'arm64-v8a' 'armeabi-v7a'
```

### 5.6. Проверка подписи `apksigner`

```
$ apksigner verify --verbose --print-certs mobile/dist/keremet-1.0.12.apk
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
```

### 5.7. Сравнение разрешений с 1.0.12

```bash
diff -u \
  <(aapt2 dump permissions mobile/dist/cashback-one-1.0.12.apk | sed "s/kz.cashbackone.mobile/DYNAMIC_PKG/g") \
  <(aapt2 dump permissions mobile/dist/keremet-1.0.12.apk | sed "s/kz.cashbackone.keremet/DYNAMIC_PKG/g")
```
Вывод пустой (exit code 0): набор разрешений побайтно эквивалентен.

### 5.8. Инспекция Hermes-бандла

```bash
$ unzip -p mobile/dist/keremet-1.0.12.apk assets/index.android.bundle > /tmp/keremet_bundle.hbc
$ grep -ao "f3a0cf2d-4a1d-4c0e-af27-b363054394f0" /tmp/keremet_bundle.hbc
f3a0cf2d-4a1d-4c0e-af27-b363054394f0
$ grep -ao "kz\.cashbackone\.keremet" /tmp/keremet_bundle.hbc
kz.cashbackone.keremet
$ grep -ao "https://api\.cashback-qr\.poscenter\.kz" /tmp/keremet_bundle.hbc
https://api.cashback-qr.poscenter.kz
$ grep -ao "Keremet Bonus" /tmp/keremet_bundle.hbc
Keremet Bonus
```
- Режим демо отключен (сборка `NODE_ENV=production`).
- Базовый URL API указывает на рабочий production `https://api.cashback-qr.poscenter.kz`.
- UUID бизнеса KeremEt (`f3a0cf2d-4a1d-4c0e-af27-b363054394f0`) и пакет `kz.cashbackone.keremet` присутствуют в бандле.

### 5.9. Скриншоты главной и экрана входа KeremEt

Сняты через `chrome-devtools` в разрешении 390×844:
- `reports/per-client-2026-11-05/keremet-home.png` (SHA-256: `23d66fcf3c91619158a930a1d9e525a2f57d286eedc680cacbe64b1d3e4e655b`): в шапке рядом с балансом отображается красный логотип KeremEt капсульной формы с надписью «keremet».
- `reports/per-client-2026-11-05/keremet-login.png` (SHA-256: `50e05b82e81a5fa9149239f82ffc347bb439aabe56ab293c71ba6f3273570b90`): над формой входа «Вход / Введите номер телефона...» отображается логотип KeremEt с `accessibilityLabel="Keremet Bonus"`.

### 5.10. `git status --short` в конце

```
 M mobile/app/(app)/(tabs)/index.tsx
 M mobile/app/(app)/bind.tsx
 M mobile/app/(app)/status.tsx
 M mobile/app/login.tsx
 M mobile/src/api/app.ts
 M mobile/src/api/wallet.ts
 M mobile/src/auth/session.ts
 M mobile/src/demo/mockApi.ts
 M mobile/src/features/home.tsx
 M mobile/src/features/push.tsx
 M mobile/src/features/useMarkSeen.ts
 M mobile/src/storage/appCache.ts
 M mobile/src/theme/index.ts
?? C:/
?? mobile/clients/
?? mobile/scripts/build-client.sh
?? mobile/src/components/BrandBadge.tsx
?? mobile/src/config/
?? mobile/tests/clientConfig.test.tsx
?? reports/per-client-2026-11-05/
?? video/
```

---

## 6. Что не проверено

1. **Реальная работа APK на физическом устройстве Android:**
   - Установка `keremet-1.0.12.apk` на физический телефон и вход через SMS/WhatsApp OTP;
   - Отображение иконки KeremEt на различных лаунчерах (Samsung One UI, Xiaomi HyperOS, Google Pixel Launcher).
2. **Push-уведомления для KeremEt:**
   - `google-services.json` для `kz.cashbackone.keremet` пока отсутствует в проекте Firebase `cashback-one-loyalty`. Для этого flavor задача `processKeremetReleaseGoogleServices` была отключена при сборке. Владельцу необходимо добавить Android-приложение `kz.cashbackone.keremet` в Firebase-консоль и сохранить файл конфигурации в `mobile/android/app/src/keremet/google-services.json`.
3. **Сборка APK `example` и `cashbackone`:**
   - Не выполнялась в соответствии с правилом дефицита дискового пространства в промпте (свободно 368 MiB < 3 GB; сборка требует не менее 3 ГБ свободного места).
4. **Сквозная интеграция с новым бэкендом задачи I:**
   - Бэкенд с поддержкой параметра `?business_id=` и фильтрацией пушей по пакету (`PROMPT_BACKEND_PER_CLIENT_APP_2026-11-05.md`) ещё не развернут на production; логика проверена модульными тестами Jest с мок-ответами.

---

## 7. Исправление после приёмки (2026-11-05)

По замечанию куратора из `docs/PROMPT_APP_PER_CLIENT_FIX_2026-11-05.md`:
В `src/api/wallet.ts` ключ запроса карт был изменён на `[...walletKey, 'cards', client.business_id ?? '']`, в то время как `app/(app)/bind.tsx:32` и `app/(app)/cards.tsx:24` вызывали `setQueryData` с ключом `[...walletKey, 'cards']`. Из-за несовпадения ключей мгновенное обновление списка карт после привязки и скрытия карты перестало работать у всех клиентов, включая общий `cashbackone`.

### 7.1. Что сделано
1. В `mobile/src/api/wallet.ts` ключ возвращён к исходному: `queryKey: [...walletKey, 'cards']`. Фильтрация по `client.business_id` в `queryFn` полностью сохранена.
2. В `mobile/tests/clientConfig.test.tsx` добавлен раздел тестов `7. Immediate card appearance in query cache after bind`:
   - Для общего клиента (`cashbackone`): после привязки карта немедленно появляется в кеше и интерфейсе до повторного сетевого запроса;
   - Для клиента `keremet`: после привязки карта немедленно появляется в кеше и интерфейсе до повторного сетевого запроса.
3. APK не пересобирался согласно прямому указанию в промпте (пересборка будет выполнена отдельно после получения `google-services.json` для `kz.cashbackone.keremet` и деплоя бэкенда задачи I).

### 7.2. Git diff правок

```diff
diff --git a/mobile/src/api/wallet.ts b/mobile/src/api/wallet.ts
index e9e02c1..b66456d 100644
--- a/mobile/src/api/wallet.ts
+++ b/mobile/src/api/wallet.ts
@@ -10,7 +10,7 @@ export function useCards() {
   const { api } = useSession();
   const client = getClientConfig();
   return useQuery({
-    queryKey: [...walletKey, 'cards', client.business_id ?? ''],
+    queryKey: [...walletKey, 'cards'],
     queryFn: async ({ signal }) => {
       const path = withClientBusiness('/me/cards');
       const cards = await api.request<Card[]>(path, { auth: true, signal });
```

### 7.3. Сырой вывод проверок

#### `npx jest --runInBand`
```
PASS tests/qrScreen.test.tsx
PASS tests/appUpdate.test.tsx
PASS tests/profileSave.test.tsx
PASS tests/flows.test.tsx
PASS tests/historyPeriod.test.tsx
PASS tests/cityCustom.test.tsx
PASS tests/homeArtwork.test.tsx
PASS tests/wallet.test.tsx
PASS tests/cardScanner.test.tsx
PASS tests/avatar.test.tsx
PASS tests/serverContentAndCache.test.tsx
PASS tests/clientConfig.test.tsx
PASS tests/components.test.tsx
PASS tests/demo.test.ts
PASS tests/push.test.tsx
PASS tests/levels.test.tsx
PASS tests/loginScreen.test.tsx
PASS tests/promotionsArtwork.test.tsx
PASS tests/core.test.ts
PASS tests/session.test.ts
PASS tests/transport.test.ts
PASS tests/keyboardLift.test.ts

Test Suites: 22 passed, 22 total
Tests:       296 passed, 296 total
Snapshots:   0 total
Time:        24.997 s
Ran all test suites.
```

#### `npx tsc --noEmit`
```
(exit code 0, no output)
```

#### `npx eslint .`
```
/Users/nuras/Desktop/cashback-one/mobile/src/components/useKeyboardLift.ts
  62:20  warning  The ref value 'generation.current' will likely have changed by the time this effect cleanup function runs. If this ref points to a node rendered by React, copy 'generation.current' to a variable inside the effect, and use that variable in the cleanup function  react-hooks/exhaustive-deps

✖ 1 problem (0 errors, 1 warning)
```

---

## 8. Имя файла APK (2026-11-05)

### 8.1. Выбранный подход

1. **Поле `apk_name` в `client.json`:**
   - В `mobile/clients/keremet/client.json` добавлено `"apk_name": "keremet-cashback"`.
   - В `mobile/clients/cashbackone/client.json` добавлено `"apk_name": "cashback-one"`.
   - В `mobile/clients/example/client.json` поле опущено (fallback на `slug`).
   - Поле `apk_name?: string;` добавлено в интерфейс `ClientConfig` (`mobile/src/config/client.ts`).

2. **Модификация `mobile/scripts/build-client.sh`:**
   - Чтение `apk_name` выполняется тем же способом (`node -p`), что и чтение версии из `app.json`:
     ```bash
     VERSION="$(node -p "require('./app.json').expo.version")"
     APK_NAME="$(node -p "require('./${CLIENT_CONFIG}').apk_name || '${SLUG}'")"
     ```
   - Добавлена валидация формата: `^[a-z0-9]+(-[a-z0-9]+)*$`.
   - Добавлен режим `--print-apk-name` для проверки вычисления имени файла без сборки (поддерживается вызов как `build-client.sh --print-apk-name <slug>`, так и `build-client.sh <slug> --print-apk-name`).
   - При сборке результирующий файл копируется в `mobile/dist/<apk_name>-<version>.apk` (или `<slug>-<version>.apk`, если `apk_name` отсутствует).
   - Все остальные механизмы скрипта (`cp -n`, проверка свободного места на диске, ключи подписи, `unset EXPO_PUBLIC_DEMO`) сохранены без изменений.

3. **Тестирование и валидация схемы:**
   - В `mobile/tests/clientConfig.test.tsx` добавлена проверка поля `apk_name` для всех зарегистрированных клиентов.
   - Добавлен юнит-тест валидации регулярного выражения `/^[a-z0-9]+(-[a-z0-9]+)*$/` на корректных и некорректных примерах.
   - Добавлены тесты вызова `build-client.sh --print-apk-name` через `child_process.execFileSync` для всех трёх клиентов и для разного порядка аргументов.

### 8.2. Вывод вычисленного имени для трёх клиентов

```
$ mobile/scripts/build-client.sh --print-apk-name keremet
keremet-cashback-1.0.12.apk

$ mobile/scripts/build-client.sh --print-apk-name cashbackone
cashback-one-1.0.12.apk

$ mobile/scripts/build-client.sh --print-apk-name example
example-1.0.12.apk
```

### 8.3. Git Diff

```diff
diff --git a/mobile/clients/cashbackone/client.json b/mobile/clients/cashbackone/client.json
index 097f817..778bf6b 100644
--- a/mobile/clients/cashbackone/client.json
+++ b/mobile/clients/cashbackone/client.json
@@ -1,5 +1,6 @@
 {
   "slug": "cashbackone",
+  "apk_name": "cashback-one",
   "android_app_id": "kz.cashbackone.mobile",
   "app_name": {
     "ru": "Cashback One",
diff --git a/mobile/clients/keremet/client.json b/mobile/clients/keremet/client.json
index 96f7805..7e816fa 100644
--- a/mobile/clients/keremet/client.json
+++ b/mobile/clients/keremet/client.json
@@ -1,5 +1,6 @@
 {
   "slug": "keremet",
+  "apk_name": "keremet-cashback",
   "android_app_id": "kz.cashbackone.keremet",
   "app_name": {
     "ru": "Keremet Bonus",
diff --git a/mobile/scripts/build-client.sh b/mobile/scripts/build-client.sh
index 570e1be..a217127 100755
--- a/mobile/scripts/build-client.sh
+++ b/mobile/scripts/build-client.sh
@@ -2,7 +2,7 @@
 # Builds a signed release APK for a specific client flavor without EAS and without expo prebuild.
 #
 # Usage:
-#   mobile/scripts/build-client.sh <slug>
+#   mobile/scripts/build-client.sh [--print-apk-name] <slug>
 #
 # Environment variables:
 #   API_BASE_URL    API the app talks to (default: https://api.cashback-qr.poscenter.kz)
@@ -13,12 +13,36 @@
 #   FORCE_SPACE     Set to 1 to bypass disk space check
 set -euo pipefail

-if [ $# -lt 1 ]; then
-  echo "Usage: $0 <slug>" >&2
+PRINT_ONLY=0
+SLUG=""
+
+for arg in "$@"; do
+  case "$arg" in
+    --print-apk-name)
+      PRINT_ONLY=1
+      ;;
+    -*)
+      echo "Unknown option: $arg" >&2
+      echo "Usage: $0 [--print-apk-name] <slug>" >&2
+      exit 1
+      ;;
+    *)
+      if [ -z "$SLUG" ]; then
+        SLUG="$arg"
+      else
+        echo "Unexpected argument: $arg" >&2
+        echo "Usage: $0 [--print-apk-name] <slug>" >&2
+        exit 1
+      fi
+      ;;
+  esac
+done
+
+if [ -z "$SLUG" ]; then
+  echo "Usage: $0 [--print-apk-name] <slug>" >&2
   exit 1
 fi

-SLUG="$1"
 cd "$(dirname "$0")/.."

 CLIENT_CONFIG="clients/${SLUG}/client.json"
@@ -27,6 +51,21 @@ if [ ! -f "$CLIENT_CONFIG" ]; then
   exit 1
 fi

+VERSION="$(node -p "require('./app.json').expo.version")"
+APK_NAME="$(node -p "require('./${CLIENT_CONFIG}').apk_name || '${SLUG}'")"
+
+if ! [[ "$APK_NAME" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
+  echo "Error: Invalid apk_name in $CLIENT_CONFIG: $APK_NAME (must match ^[a-z0-9]+(-[a-z0-9]+)*$)" >&2
+  exit 1
+fi
+
+APK_FILENAME="${APK_NAME}-${VERSION}.apk"
+
+if [ "$PRINT_ONLY" = "1" ]; then
+  echo "$APK_FILENAME"
+  exit 0
+fi
+
 # 1. Check free disk space
 MIN_FREE_KB="${MIN_FREE_KB:-3000000}"
 FREE_KB="$(df -k "$HOME" | awk 'NR==2 {print $4}')"
@@ -81,8 +120,7 @@ echo "=== Building client '${SLUG}' (flavor: ${FLAVOR}, task: app:${TASK}) ==="
     --console=plain
 )

-# 6. Copy APK to mobile/dist/<slug>-<version>.apk
-VERSION="$(node -p "require('./app.json').expo.version")"
+# 6. Copy APK to mobile/dist/<apk_name>-<version>.apk
 OUTPUT_DIR="android/app/build/outputs/apk/${SLUG}/release"
 SRC_APK="$(ls -t "$OUTPUT_DIR"/*.apk 2>/dev/null | head -1 || true)"

@@ -92,7 +130,7 @@ if [ -z "$SRC_APK" ] || [ ! -f "$SRC_APK" ]; then
 fi

 mkdir -p dist
-DEST_APK="dist/${SLUG}-${VERSION}.apk"
+DEST_APK="dist/${APK_FILENAME}"

 if [ -f "$DEST_APK" ]; then
   echo "Target APK already exists: $DEST_APK (not overwriting with cp -n)"
diff --git a/mobile/src/config/client.ts b/mobile/src/config/client.ts
index a824508..9c7cd44 100644
--- a/mobile/src/config/client.ts
+++ b/mobile/src/config/client.ts
@@ -6,6 +6,7 @@ import { KeremetLogo } from '../../clients/keremet/Logo';

 export interface ClientConfig {
   slug: string;
+  apk_name?: string;
   android_app_id: string;
   app_name: {
     ru: string;
diff --git a/mobile/tests/clientConfig.test.tsx b/mobile/tests/clientConfig.test.tsx
index ff7df51..30bb4ee 100644
--- a/mobile/tests/clientConfig.test.tsx
+++ b/mobile/tests/clientConfig.test.tsx
@@ -1,6 +1,7 @@
 import React from 'react';
 import fs from 'fs';
 import path from 'path';
+import { execFileSync } from 'child_process';
 import { View, Text } from 'react-native';
 import { render, act, waitFor } from '@testing-library/react-native';
 import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
@@ -49,6 +50,19 @@ describe('Client Configuration & Multi-Tenant Support', () => {
         expect(config.primary_color).toMatch(/^#[0-9A-Fa-f]{6}$/);
         expect(config.scheme).toMatch(/^[a-z0-9]+$/);

+        if (config.apk_name !== undefined) {
+          expect(typeof config.apk_name).toBe('string');
+          expect(config.apk_name).toMatch(/^[a-z0-9]+(-[a-z0-9]+)*$/);
+        }
+
+        if (slug === 'keremet') {
+          expect(config.apk_name).toBe('keremet-cashback');
+        } else if (slug === 'cashbackone') {
+          expect(config.apk_name).toBe('cashback-one');
+        } else if (slug === 'example') {
+          expect(config.apk_name).toBeUndefined();
+        }
+
         // Verify Android resources directory
         const resDir = path.join(clientsDir, slug, 'android/res');
         expect(fs.existsSync(resDir)).toBe(true);
@@ -371,4 +385,54 @@ describe('Client Configuration & Multi-Tenant Support', () => {
       screen.unmount();
     });
   });
+
+  describe('8. APK File Name Calculation & Format Validation (build-client.sh --print-apk-name)', () => {
+    const buildScript = path.resolve(__dirname, '../scripts/build-client.sh');
+    const appJsonPath = path.resolve(__dirname, '../app.json');
+    const version = JSON.parse(fs.readFileSync(appJsonPath, 'utf-8')).expo.version;
+
+    it('validates apk_name format regex against valid and invalid values', () => {
+      const regex = /^[a-z0-9]+(-[a-z0-9]+)*$/;
+      expect(regex.test('keremet-cashback')).toBe(true);
+      expect(regex.test('cashback-one')).toBe(true);
+      expect(regex.test('app1')).toBe(true);
+      expect(regex.test('my-cool-app-2026')).toBe(true);
+
+      expect(regex.test('')).toBe(false);
+      expect(regex.test('Keremet')).toBe(false);
+      expect(regex.test('keremet_cashback')).toBe(false);
+      expect(regex.test('-leading')).toBe(false);
+      expect(regex.test('trailing-')).toBe(false);
+      expect(regex.test('double--hyphen')).toBe(false);
+      expect(regex.test('with spaces')).toBe(false);
+    });
+
+    it('calculates keremet-cashback-<version>.apk for keremet', () => {
+      const output = execFileSync(buildScript, ['--print-apk-name', 'keremet'], {
+        encoding: 'utf-8',
+      }).trim();
+      expect(output).toBe(`keremet-cashback-${version}.apk`);
+    });
+
+    it('calculates cashback-one-<version>.apk for cashbackone', () => {
+      const output = execFileSync(buildScript, ['--print-apk-name', 'cashbackone'], {
+        encoding: 'utf-8',
+      }).trim();
+      expect(output).toBe(`cashback-one-${version}.apk`);
+    });
+
+    it('calculates example-<version>.apk for example (fallback to slug when apk_name is omitted)', () => {
+      const output = execFileSync(buildScript, ['--print-apk-name', 'example'], {
+        encoding: 'utf-8',
+      }).trim();
+      expect(output).toBe(`example-${version}.apk`);
+    });
+
+    it('supports argument order: <slug> --print-apk-name', () => {
+      const output = execFileSync(buildScript, ['keremet', '--print-apk-name'], {
+        encoding: 'utf-8',
+      }).trim();
+      expect(output).toBe(`keremet-cashback-${version}.apk`);
+    });
+  });
 });
```

### 8.4. Сырой вывод проверок

#### `npx jest --runInBand`
```
PASS tests/clientConfig.test.tsx
PASS tests/appUpdate.test.tsx
PASS tests/profileSave.test.tsx
PASS tests/qrScreen.test.tsx
PASS tests/flows.test.tsx
PASS tests/homeArtwork.test.tsx
PASS tests/cityCustom.test.tsx
PASS tests/historyPeriod.test.tsx
PASS tests/wallet.test.tsx
PASS tests/cardScanner.test.tsx
PASS tests/avatar.test.tsx
PASS tests/serverContentAndCache.test.tsx
PASS tests/components.test.tsx
PASS tests/push.test.tsx
PASS tests/demo.test.ts
PASS tests/promotionsArtwork.test.tsx
PASS tests/levels.test.tsx
PASS tests/loginScreen.test.tsx
PASS tests/transport.test.ts
PASS tests/session.test.ts
PASS tests/core.test.ts
PASS tests/keyboardLift.test.ts

Test Suites: 22 passed, 22 total
Tests:       301 passed, 301 total
Snapshots:   0 total
Time:        19.016 s, estimated 22 s
Ran all test suites.
```

#### `npx tsc --noEmit`
```
(exit code 0, no output)
```

#### `npx eslint .`
```
/Users/nuras/Desktop/cashback-one/mobile/src/components/useKeyboardLift.ts
  62:20  warning  The ref value 'generation.current' will likely have changed by the time this effect cleanup function runs. If this ref points to a node rendered by React, copy 'generation.current' to a variable inside the effect, and use that variable in the cleanup function  react-hooks/exhaustive-deps

✖ 1 problem (0 errors, 1 warning)
```

#### `bash -n scripts/build-client.sh`
```
(exit code 0, no output)
```

