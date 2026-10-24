# Сборка release APK 1.0.6 / versionCode 7 (сканер камеры)

Дата: 2026-10-24, Mac. Только локальная сборка по промпту `docs/PROMPT_APK_1_0_6_2026-10-24.md`. На сайт не загружался, в GitHub Releases не публиковался, на устройство не устанавливался, `upload_apk.py` не запускался, `.env.hosting.local` не читался, commit/push не делались. `expo prebuild` (ни с `--clean`, ни без) и `mobile/scripts/build-apk.sh` не запускались. Внешние сервисы анализа изображений не использовались, никакие файлы и снимки за пределы этого Mac не передавались, снимки всего экрана не делались (решение владельца 2026-10-24).

**Поведение на телефоне не проверено.** Работа камеры, системный запрос разрешения и считывание реальных карт — не проверены. Все проверки ниже — проверки файла APK и кода, не работы приложения на устройстве.

---

## 1. Артефакт

| Параметр | Значение |
|---|---|
| Путь | `/Users/nuras/Desktop/cashback-one/mobile/dist/cashback-one-1.0.6.apk` |
| Размер | **62 529 495 байт** (прирост к 1.0.5 +10 899 008 байт — разбор в §6) |
| SHA-256 | `195f486a0c02fd9891d638164bdc395cb7938d54ddc4357eff36d9e4d345338c` |
| package | `kz.cashbackone.mobile` |
| versionName / versionCode | **1.0.6 / 7** (по `aapt2 dump badging`) |
| debuggable | нет: атрибут `debuggable` в манифесте отсутствует |
| Архитектуры | `arm64-v8a`, `armeabi-v7a` (по 22 нативных библиотеки у каждой; `x86` и `x86_64` нет) |
| targetSdk / compileSdk | 36 / 36 (minSdk 24) |

Старые APK не перезаписывались: `cp -n`, путь назначения до копирования был свободен. Контроль нетронутости по SHA-256: `1.0.3` = `ac33efc6…604ba`, `1.0.4` = `f44072d9…d0b9`, `1.0.5` = `eefc9123…664b` — совпадают с отчётами прошлых сборок; `1.0.0` не перезаписывался.

Дисковое пространство: перед сборкой 3,9 ГиБ свободно (порог 3 ГБ пройден); в середине сборки наблюдалось 2,3 ГиБ; после сборки 3,8 ГиБ. Gradle-кэш и прежние APK не удалялись.

---

## 2. Подпись и совпадение сертификата

После сборки `apksigner verify --verbose --print-certs` для 1.0.6:

- Статус: `Verifies`
- Число подписантов: 1
- DN: `CN=Cashback One, O=POSCENTER, C=KZ`
- SHA-256 сертификата: **`14afcbb5ec8375e3130b2832b1a7468372e1205c3a275ba56b8ff7b1e483cd63`** — **полностью совпадает** с APK 1.0.2–1.0.5 (требование промпта выполнено).
- Схемы подписи: v2 — `true`; v1, v3, v3.1, v4, SourceStamp — `false` (набор схем идентичен прежним сборкам).
- Подпись release-ключом из `release.keystore`; debug-ключ не использовался.
- Содержимое и пароли keystore не выводились и не копировались в репозиторий. Внутри APK файлов `*.keystore` / `*.jks` / `*.bks` нет.

---

## 3. Изменённые файлы

Исходники приложения исполнителем **не менялись**. Правки куратора (принятый набор из `reports/APP_SCAN_TABBAR_2026-10-23.md` + `app.json`) остались без изменений; от сборки в отслеживаемых файлах ничего не изменилось (§5.6).

Нативные правки (папка `mobile/android/` в `.gitignore`, в git не отслеживается):

| Файл | Изменение |
|---|---|
| `mobile/android/app/build.gradle` | `versionCode 6` → **7**, `versionName "1.0.5"` → **"1.0.6"** |
| `mobile/android/app/src/main/AndroidManifest.xml` | добавлена строка `<uses-permission android:name="android.permission.RECORD_AUDIO" tools:node="remove"/>` (исключение микрофона, который библиотека `expo-camera` объявляет в своём манифесте) |

До правок сделаны копии обоих файлов в `/private/tmp/apk-1.0.6-build/native-backup/` (SHA-256 копий: `build.gradle` = `4ce3352e…b99b1`, `AndroidManifest.xml` = `b6a95d3c…4b4b4`). `diff` после сборки — **ровно перечисленные изменения, ничего больше**:

```diff
--- native-backup/build.gradle
+++ mobile/android/app/build.gradle
@@ -95,8 +95,8 @@
-        versionCode 6
-        versionName "1.0.5"
+        versionCode 7
+        versionName "1.0.6"
```

```diff
--- native-backup/AndroidManifest.xml
+++ mobile/android/app/src/main/AndroidManifest.xml
@@ -3,6 +3,7 @@
   <uses-permission android:name="android.permission.INTERNET"/>
   <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" android:maxSdkVersion="32" tools:replace="android:maxSdkVersion"/>
+  <uses-permission android:name="android.permission.RECORD_AUDIO" tools:node="remove"/>
   <uses-permission android:name="android.permission.SYSTEM_ALERT_WINDOW" tools:node="remove"/>
```

Пространство имён `tools` (`xmlns:tools="http://schemas.android.com/tools"`) в манифесте уже было объявлено — проверено до правки.

Package / applicationId не менялись (`kz.cashbackone.mobile`). Больше в нативном проекте ничего не менялось.

---

## 4. Команды и результаты сборки (без секретов)

1. **Предварительные проверки:**
   - JDK Zulu 17: `/Users/nuras/.jdks/zulu17.68.203-ca-jdk17.0.20.1-macosx_x64/Contents/Home`
   - Android SDK: `~/Library/Android/sdk` (build-tools 36.0.0)
   - `expo-camera` 55.0.23 установлен в `node_modules` (проверено по `package.json` библиотеки).
   - Baseline перед сборкой в `mobile/`: `npx tsc --noEmit` — код 0; `npx jest` (вывод в файл, таймаут 600 с) — **203 passed / 203, 14 сюит**, код 0. Совпадает с промптом.
2. **Сборка (в подоболочке с передачей переменных окружения без вывода в терминал):**

   ```bash
   ( set -a && source ~/.cashback-one-keys/keystore.env && set +a && \
     export CASHBACK_STORE_FILE="$HOME/.cashback-one-keys/release.keystore" && \
     export JAVA_HOME="$HOME/.jdks/zulu17.68.203-ca-jdk17.0.20.1-macosx_x64/Contents/Home" && \
     export ANDROID_HOME="$HOME/Library/Android/sdk" && \
     unset EXPO_PUBLIC_DEMO EXPO_PUBLIC_ALLOW_INSECURE_HTTP && \
     cd mobile/android && \
     EXPO_PUBLIC_API_BASE_URL=https://api.cashback-qr.poscenter.kz NODE_ENV=production \
     ./gradlew assembleRelease -PreactNativeArchitectures=arm64-v8a,armeabi-v7a \
     --no-daemon --max-workers=1 -Dorg.gradle.parallel=false --console=plain )
   ```

   Результат: `BUILD SUCCESSFUL in 13m 21s`, 393 задачи (66 executed, 327 up-to-date), код выхода 0. В логе сборки **нет строк загрузки зависимостей** (`Download …` — 0): CameraX/ML Kit нашлись в локальном gradle-кэше, поэтому сборка прошла быстрее оценочных 90 минут. Отсутствие загрузок не потребовало сети и не является ошибкой.

3. **Копирование:**
   `mobile/android/app/build/outputs/apk/release/app-release.apk` → `mobile/dist/cashback-one-1.0.6.apk` через `cp -n`.

---

## 5. Фактические доказательства

### 5.1. Конфиг приложения (`assets/app.config` внутри APK)

- `"version": "1.0.6"`, `"android.versionCode": 7`, `"android.package": "kz.cashbackone.mobile"`.
- Плагин `expo-camera` с русским текстом разрешения камеры и `"recordAudioAndroid": false`; `"android.permissions": ["android.permission.CAMERA"]`.

### 5.2. Сравнение разрешений 1.0.5 → 1.0.6 (`aapt2 dump permissions`)

| Разрешение | 1.0.5 | 1.0.6 |
|---|---|---|
| `android.permission.INTERNET` | есть | есть |
| `android.permission.READ_EXTERNAL_STORAGE` (maxSdk 32) | есть | есть |
| `android.permission.VIBRATE` | есть | есть |
| `android.permission.WRITE_EXTERNAL_STORAGE` (maxSdk 32) | есть | есть |
| `android.permission.ACCESS_NETWORK_STATE` | есть | есть |
| **`android.permission.CAMERA`** | **нет** | **есть (новое, ожидаемое)** |
| `android.permission.USE_BIOMETRIC` | есть | есть |
| `android.permission.USE_FINGERPRINT` | есть | есть |
| `kz.cashbackone.mobile.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION` (определение + использование) | есть | есть |
| `android.permission.RECORD_AUDIO` | нет | **нет** — исключён через `tools:node="remove"`, проверено отдельно |

Единственное новое разрешение — `CAMERA`, других новых нет. `SYSTEM_ALERT_WINDOW` по-прежнему удалён. `RECORD_AUDIO` в итоговом манифесте отсутствует (проверено и по `badging`, и по `dump permissions`, и по `xmltree`).

### 5.3. Доказательства присутствия модуля камеры и ML Kit barcode

- **Манифест библиотеки** `node_modules/expo-camera/android/src/main/AndroidManifest.xml` объявляет `CAMERA` и `RECORD_AUDIO` и `meta-data com.google.mlkit.vision.DEPENDENCIES=barcode_ui`; слияние манифестов перенесло `CAMERA` в APK (а `RECORD_AUDIO` подавлен нашей правкой).
- **Нативные библиотеки** — ровно 3 новые на каждую архитектуру против 1.0.5 (`diff` списков `lib/*`):
  - `libbarhopper_v3.so` — движок распознавания штрихкодов ML Kit (arm64: 4 946 720 Б, v7a: 3 244 440 Б);
  - `libimage_processing_util_jni.so` (arm64: 32 544 Б, v7a: 24 448 Б) — CameraX;
  - `libsurface_util_jni.so` (arm64: 4 896 Б, v7a: 3 460 Б) — CameraX.
- **Классы в dex** (`dexdump` по извлечённым `classes*.dex`):
  - `expo.modules.camera` — 2212 упоминаний в `classes3.dex`; среди дескрипторов: `Lexpo/modules/camera/CameraViewModule;`, `Lexpo/modules/camera/CameraViewHelper;`, `Lexpo/modules/camera/CameraExceptions$BarcodeScanningCancelledException;` и др.;
  - `com.google.mlkit.vision.barcode` в `classes3.dex`: `BarcodeScanner;`, `BarcodeScannerOptions;`, `BarcodeScanning;`, `ZoomSuggestionOptions;` и др.
- **Модели ML Kit** — 3 новых файла в `assets/`: `mlkit_barcode_models/barcode_ssd_mobilenet_v1_dmp25_quant.tflite` (390 456 Б), `oned_auto_regressor_mobile.tflite` (213 880 Б), `oned_feature_extractor_mobile.tflite` (276 552 Б).
- Metro-ассеты (промо-PNG и прочие ресурсы) не изменились — списки `assets/` 1.0.5 и 1.0.6 различаются ровно этими тремя моделями.

### 5.4. Hermes-байткод (`assets/index.android.bundle`, декомпиляция `hermesc -b -dump-bytecode`)

- Строка `https://api.cashback-qr.poscenter.kz` присутствует (`True`).
- Названия `EXPO_PUBLIC_DEMO` и `ALLOW_INSECURE_HTTP` в таблице строк отсутствуют (как и в 1.0.4/1.0.5); независимая проверка значения — по байткоду ниже.
- **Demo выключен** (тот же рисунок инструкций, что в 1.0.4/1.0.5):
  - в модуле demo (`Object.defineProperty` экспортирует `DEMO_ENABLED`, `DEMO_BASE_URL`, `demoTokens`, `createDemoApi`) в конце инициализации: `LoadConstFalse r3` → `StoreNPToEnvironment r2, 1, r3` — в environment slot 1 записывается **константа false**;
  - первый из трёх геттеров `Function<get>` этого модуля (`GetEnvironment r0, 0; LoadFromEnvironment r0, r0, 1`) читает slot 1 → экспортируемый `DEMO_ENABLED` возвращает **false**; второй геттер читает slot 2 (`https://demo.inva…`, `DEMO_BASE_URL`) — соответствие слотов однозначное;
  - потребитель (провайдер сессии): при `DEMO_ENABLED` ветка demo-токен-стора обходится (`JmpTrue` не срабатывает, берётся обычный `tokenStore`), за `JmpFalse` URL остаётся строкой `https://api.cashb…` (загрузка `DEMO_BASE_URL` пропускается), а вызов `createDemoApi` обходится (`JmpFalse` на метку `L4`).
- **Строки сканера присутствуют** (UTF-16LE): RU `«Сканировать камерой»` (`True`), KK `«Камерамен сканерлеу»` (`True`), подсказка `«4–13 цифр»` (`True`; в исходниках это `barcodeHint`: RU «Введите номер карты (4–13 цифр).», KK «Карта нөмірін енгізіңіз (4–13 цифр).»).
- **Старой подсказки нет**: `«6–15 цифр»` и вариант через дефис `«6-15 цифр»` отсутствуют и в UTF-8, и в UTF-16LE (`False`).
- Тексты о балансе 1.0.5 на месте (UTF-16LE): RU `«Баланс обновляется не сразу…»` и KK `«Баланс бірден жаңартылмайды…»` — `True`.

### 5.5. Манифест и ресурсы

- `application-debuggable` и `usesCleartextTraffic` отсутствуют; `windowSoftInputMode` = `0x10` (`adjustResize`), `screenOrientation` = portrait, `launchMode` = singleTask; minSdk 24 / targetSdk 36.
- **Пять промо-PNG** проверены попиксельно локально (`PIL Image.open` / RGBA, без внешних сервисов): для каждого исходного ассета найден ресурс APK тех же размеров с `diff_visible = 0, diff_alpha = 0` (различаются только RGB полностью прозрачных пикселей — как и в 1.0.4/1.0.5, ресурсы Android переупакованы):

| Исходный ассет | Ресурс внутри APK | Отличий видимых пикселей / альфа |
|---|---|---|
| `banner-car-prize.png` | `res/lH.png` | 0 / 0 |
| `offer-hits-discount.png` | `res/Js.png` | 0 / 0 |
| `offer-weekly-promo.png` | `res/4p.png` | 0 / 0 |
| `offer-card-bonus.png` | `res/UO.png` | 0 / 0 |
| `offer-fresh-products.png` | `res/bC.png` | 0 / 0 |

### 5.6. Регрессия после сборки

- `npx jest` (вывод в файл, таймаут 600 с): **203 passed / 203, 14 сюит**, код выхода 0.
- `git status --short` до и после сборки — идентичен: в `mobile/` изменены только принятые файлы задачи (`app.json`, `package.json`, `package-lock.json`, `TabBar.tsx`, `BindForm.tsx`, `code128.ts`, `i18n/ru.ts`, `i18n/kz.ts`, `format.ts`, тесты `cardBarcode`/`code128`/`core`) и неотслеживаемые новые (`CardScanner.tsx`, `cardScanner.test.tsx`, `__mocks__/expo-camera.js`); вне `mobile/` — известные `C:/`, документы и отчёты. От сборки в отслеживаемых файлах ничего не изменилось (`git diff --stat -- mobile` — тот же набор правок куратора).

---

## 6. Размер против 1.0.5 — разбор прироста

62 529 495 − 51 630 487 = **+10 899 008 байт**. Основные вкладчики (размеры без сжатия из ZIP-каталога):

| Вкладчик | arm64-v8a | armeabi-v7a | Сумма |
|---|---|---|---|
| `libbarhopper_v3.so` (ML Kit barcode) | 4 946 720 | 3 244 440 | 8 191 160 |
| `libimage_processing_util_jni.so` + `libsurface_util_jni.so` (CameraX) | 37 440 | 27 908 | 65 348 |
| Модели `assets/mlkit_barcode_models/*.tflite` | — | — | 880 888 |

Нативные библиотеки хранятся в APK без сжатия (`extractNativeLibs=false`, стандарт AGP для minSdk 23+), поэтому их полный размер напрямую увеличивает файл APK: ≈ 9,14 МБ из 10,9 МБ прироста. Остальное — рост dex (суммарно без сжатия 23 380 716 → 27 571 652, +4,19 МБ до сжатия) за счёт классов `expo-camera`/CameraX/ML Kit и +43 ресурсных записей `res/` (980 → 1023, ресурсы expo-camera и ML Kit). Прирост полностью объясняется подключением модуля камеры; лишних компонентов нет.

---

## 7. Не проверено

- **Работа камеры на телефоне**: реальное сканирование штрихкодов/QR физической картой, изображение с камеры, распознавание.
- **Системный запрос разрешения камеры**: диалог Android при первом открытии сканера, отказ и сценарий «Открыть настройки» в нативном исполнении.
- **Считывание реальных карт** разных форматов (code128/code39/EAN-13/ITF-14/CODABAR и др.); поведение на динамическом QR `C1…`.
- Установка APK на устройство (поверх 1.0.5 или начисто) и обновление с сохранением данных; совпадение сертификата — необходимая предпосылка обновления, но установка не проверялась.
- Поведение сканера при уходе приложения в фон, при повороте, производительность и расход батареи.
- Микрофон: в APK разрешения нет, но поведение приложения без него на устройстве не проверялось (оно и не должно запрашиваться).

## 8. Ограничения соблюдены

Исходники, `package.json`/lock, ключи не менялись; `expo prebuild` и `mobile/scripts/build-apk.sh` не запускались; прежние APK и gradle-кэш не удалялись; APK никуда не публиковался; commit/push не выполнялись; `admin/`, `backend/`, `agent/`, VPS, хостинг не тронуты; секреты и персональные данные не выводились.
