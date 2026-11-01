# Сборка release APK 1.0.9 / versionCode 10 — значок фото и профиль

Дата: 2026-11-01, Mac. APK собран локально и проверен по файлу. Не загружался на сайт или GitHub Releases, не устанавливался на устройство; `expo prebuild`, `mobile/scripts/build-apk.sh`, `upload_apk.py`, commit и push не запускались. Прежние APK и кэш Gradle не удалялись.

**Итог:** сборка, проверки APK и тесты регрессии выполнены успешно. Остаются только проверки на реальном устройстве и кассе, указанные в §10.

---

## 1. Артефакт

| Параметр | Значение |
|---|---|
| Путь | `mobile/dist/cashback-one-1.0.9.apk` |
| Размер | **67 951 855 байт** |
| SHA-256 | `3ddcc5e44dd00e1642913e3a84ff510b833f931519af0459b245fa717512731a` |
| package | `kz.cashbackone.mobile` |
| versionName / versionCode | **1.0.9 / 10** (`aapt2 dump badging`) |
| Архитектуры | только `arm64-v8a`, `armeabi-v7a` |
| minSdk / targetSdk / compileSdk | 24 / 36 / 36 |

Release APK из `mobile/android/app/build/outputs/apk/release/app-release.apk` скопирован через `cp -n`. Целевой путь `mobile/dist/cashback-one-1.0.9.apk` до копирования отсутствовал. Прежние APK не затронуты и проверены по SHA-256:
- `cashback-one-1.0.8.apk`: **67 773 772 байта**, SHA-256 `5e6b8f2158c8a00468dbe21783da444abb5bd7b55fb81c5e5ad9739020fee03b` (без изменений);
- `cashback-one-1.0.7.apk`: **67 778 452 байта**, SHA-256 `4a260bfba8f56fc8e71b75c29ad5c3b1476df0a00a2ba3220314adac8d403179` (без изменений);
- `cashback-one-1.0.6.apk`: **62 529 495 байт**, SHA-256 `195f486a0c02fd9891d638164bdc395cb7938d54ddc4357eff36d9e4d345338c` (без изменений).

---

## 2. Подпись

`apksigner verify --verbose --print-certs mobile/dist/cashback-one-1.0.9.apk`:

- Статус: `Verifies`; один подписант.
- DN: `CN=Cashback One, O=POSCENTER, C=KZ`.
- SHA-256 сертификата: **`14afcbb5ec8375e3130b2832b1a7468372e1205c3a275ba56b8ff7b1e483cd63`** — полностью совпадает с эталонным сертификатом.
- Схема подписи v2: `true`; v1, v3, v3.1, v4 и SourceStamp: `false`.
- Содержимое keystore и секреты не выводились (переданы через `~/.cashback-one-keys/keystore.env` в изолированной подоболочке).

---

## 3. Изменения исходников и версий

### 3.1. Резервная копия `build.gradle` и `app.json`
Перед изменением создана резервная копия вне репозитория в `/tmp/apk-1.0.9-build-logs/backup/`:
- `build.gradle` SHA-256: `657c975b5a33ce826af098ce744f99b398fd30694a02b1269e4024d5f371253b`
- `app.json` SHA-256: `94e93ddc4220c871365f81f915b9a7422fc9dc75b5fd34d7f4f741238cca772b`

### 3.2. Diff `mobile/android/app/build.gradle`
```diff
--- /tmp/apk-1.0.9-build-logs/backup/build.gradle	2026-11-01 14:01:21
+++ mobile/android/app/build.gradle	2026-11-01 14:01:34
@@ -92,8 +92,8 @@
         applicationId 'kz.cashbackone.mobile'
         minSdkVersion rootProject.ext.minSdkVersion
         targetSdkVersion rootProject.ext.targetSdkVersion
-        versionCode 9
-        versionName "1.0.8"
+        versionCode 10
+        versionName "1.0.9"
 
         buildConfigField "String", "REACT_NATIVE_RELEASE_LEVEL", "\"${findProperty('reactNativeReleaseLevel') ?: 'stable'}\""
     }
```

### 3.3. Diff `mobile/app.json`
```diff
--- a/mobile/app.json
+++ b/mobile/app.json
@@ -3,7 +3,7 @@
     "name": "Cashback One",
     "slug": "cashback-one",
     "scheme": "cashbackone",
-    "version": "1.0.8",
+    "version": "1.0.9",
     "orientation": "portrait",
     "icon": "./assets/icon.png",
     "userInterfaceStyle": "light",
@@ -33,7 +33,7 @@
     },
     "android": {
       "package": "kz.cashbackone.mobile",
-      "versionCode": 9,
+      "versionCode": 10,
       "adaptiveIcon": {
         "foregroundImage": "./assets/icon-foreground.png",
         "backgroundColor": "#FD6156"
```

### 3.4. Значок камеры в `mobile/src/components/icons.tsx` и `mobile/src/features/profile.tsx`
```diff
--- a/mobile/src/components/icons.tsx
+++ b/mobile/src/components/icons.tsx
@@ -3,7 +3,7 @@ import Svg, { Circle, Path, Rect } from 'react-native-svg';
 import { theme } from '../theme';
 
 export type IconName =
-  | 'home' | 'gift' | 'bell' | 'message' | 'user' | 'qr' | 'arrowLeft' | 'chevronRight' | 'crown' | 'percent' | 'scan'
+  | 'home' | 'gift' | 'bell' | 'message' | 'user' | 'qr' | 'arrowLeft' | 'chevronRight' | 'crown' | 'percent' | 'scan' | 'camera'
   | 'card' | 'cart' | 'plus' | 'minus' | 'logout' | 'history' | 'check' | 'tag' | 'wallet' | 'x';
 
 const paths: Record<Exclude<IconName, 'home'>, React.ReactNode> = {
@@ -17,6 +17,7 @@ const paths: Record<Exclude<IconName, 'home'>, React.ReactNode> = {
   crown: <><Path d="M2 18h20" /><Path d="m3 7 4.5 4L12 4l4.5 7L21 7l-2 11H5z" /></>,
   percent: <><Path d="M19 5 5 19" /><Circle cx="6.5" cy="6.5" r="2.5" /><Circle cx="17.5" cy="17.5" r="2.5" /></>,
   scan: <><Path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2" /><Path d="M8 12h8" /></>,
+  camera: <><Path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z" /><Circle cx="12" cy="13" r="3" /></>,
   card: <><Rect x="2" y="5" width="20" height="14" rx="2" /><Path d="M2 10h20M6 15h4" /></>,
```

```diff
--- a/mobile/src/features/profile.tsx
+++ b/mobile/src/features/profile.tsx
@@ -74,7 +74,7 @@ export function Avatar({
         ) : null}
       </View>
       <View style={styles.avatarBadge}>
-        <Icon name="scan" size={14} color={t.colors.onPrimary} />
+        <Icon name="camera" size={14} color={t.colors.onPrimary} />
       </View>
     </Pressable>
```

### 3.5. Проверка манифеста нативного проекта
В `mobile/android/app/src/main/AndroidManifest.xml` проверены через `grep` и сохранены строки:
```xml
<uses-permission android:name="android.permission.RECORD_AUDIO" tools:node="remove"/>
<uses-permission android:name="android.permission.SYSTEM_ALERT_WINDOW" tools:node="remove"/>
```
Команда `expo prebuild` не запускалась.

---

## 4. Baseline и сборка

### 4.1. Baseline до сборки
- Дисковое пространство: `df -h ~` → свободно **6,8 GiB** (порог >= 3 GB пройден).
- Нагрузка системы: `uptime` → load averages: `3.95 3.79 3.96` (< 12).
- `npx jest`: **16 test suites passed, 190 tests passed, 0 failed** (лог: `/tmp/apk-1.0.9-build-logs/baseline-jest.log`).
- `npx tsc --noEmit`: код 0, чисто (лог: `/tmp/apk-1.0.9-build-logs/baseline-tsc.log`).
- `npx eslint .`: 0 ошибок, 1 ожидаемое предупреждение в `useKeyboardLift.ts` (лог: `/tmp/apk-1.0.9-build-logs/baseline-eslint.log`).

### 4.2. Release-сборка
Сборка выполнена в фоне с перенаправлением вывода в `/tmp/apk-1.0.9-build-logs/gradle-build.log`.
Команда:
```bash
./gradlew assembleRelease -PreactNativeArchitectures=arm64-v8a,armeabi-v7a --no-daemon --max-workers=1 -Dorg.gradle.parallel=false --console=plain
```
Окружение сборки:
- JDK: Zulu 17 (`/Users/nuras/.jdks/zulu17.68.203-ca-jdk17.0.20.1-macosx_x64/Contents/Home`)
- Android SDK build-tools: `36.0.0`
- `NODE_ENV=production`
- `EXPO_PUBLIC_API_BASE_URL="https://api.cashback-qr.poscenter.kz"`
- `EXPO_PUBLIC_DEMO` и `EXPO_PUBLIC_ALLOW_INSECURE_HTTP` не заданы
- Ключи переданы в подоболочке из `~/.cashback-one-keys/keystore.env`

Результат сборки:
```text
BUILD SUCCESSFUL in 4m 57s
393 actionable tasks: 67 executed, 326 up-to-date
GRADLE_EXIT=0
```

---

## 5. Метаданные, разрешения и активности манифеста

### 5.1. `aapt2 dump badging`
```text
package: name='kz.cashbackone.mobile' versionCode='10' versionName='1.0.9' compileSdkVersion='36' compileSdkVersionCodename='16'
sdkVersion:'24'
targetSdkVersion:'36'
application-label:'Cashback One'
application-icon: res/BW.xml
native-code: 'arm64-v8a' 'armeabi-v7a'
```

### 5.2. Разрешения (`aapt dump permissions`) и diff с APK 1.0.8
Команда: `diff -u apk-1.0.8-permissions.txt apk-1.0.9-permissions.txt` завершилась с кодом 0 (разница 0 строк).

| Разрешение | Статус в 1.0.9 | Примечание |
|---|---|---|
| `android.permission.INTERNET` | Присутствует | Сетевые запросы к API |
| `android.permission.READ_EXTERNAL_STORAGE` | Присутствует (maxSdkVersion=32) | Чтение фото из галереи на старых версиях Android |
| `android.permission.WRITE_EXTERNAL_STORAGE` | Присутствует (maxSdkVersion=32) | Сохранение/кэш на старых версиях Android |
| `android.permission.ACCESS_NETWORK_STATE` | Присутствует | Мониторинг сети |
| `android.permission.VIBRATE` | Присутствует | Тактильный отклик |
| `android.permission.CAMERA` | Присутствует | Сканер QR / съемка фото профиля |
| `android.permission.USE_BIOMETRIC` | Присутствует | Биометрия |
| `android.permission.USE_FINGERPRINT` | Присутствует | Биометрия |
| `kz.cashbackone.mobile.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION` | Присутствует | Внутренние broadcast-приемники |
| `android.permission.RECORD_AUDIO` | **Отсутствует** | Удалено через `tools:node="remove"` |
| `android.permission.SYSTEM_ALERT_WINDOW` | **Отсутствует** | Удалено через `tools:node="remove"` |

Новых разрешений нет (diff = 0).

### 5.3. Активности обрезки фото в манифесте APK
Через `aapt2 dump xmltree mobile/dist/cashback-one-1.0.9.apk --file AndroidManifest.xml` подтверждено:
- `com.canhub.cropper.CropImageActivity`: присутствует, `exported=false`;
- `expo.modules.imagepicker.ExpoCropImageActivity`: присутствует, `exported=false`;
- `expo.modules.imagepicker.fileprovider.ImagePickerFileProvider`: зарегистрирован, `exported=false`.

---

## 6. Иконки и ассеты

Через `aapt2 dump resources` подтверждено наличие всех ресурсов приложения:
- `color/ic_launcher_background`: `#fffd6156` (ARGB для `#FD6156`);
- `mipmap/ic_launcher`, `mipmap/ic_launcher_round`, `mipmap/ic_launcher_foreground`;
- 11 ресурсов промо-акций в `drawable/assets_promotions_*`:
  - `drawable/assets_promotions_bannercarprize`
  - `drawable/assets_promotions_bannercoffeemachine`
  - `drawable/assets_promotions_bannerstickers`
  - `drawable/assets_promotions_offercardbonus`
  - `drawable/assets_promotions_offerfreshproducts`
  - `drawable/assets_promotions_offerhitsdiscount`
  - `drawable/assets_promotions_offerweeklypromo`
  - `drawable/assets_promotions_promocardbonus`
  - `drawable/assets_promotions_promofreshproducts`
  - `drawable/assets_promotions_promohitsdiscount`
  - `drawable/assets_promotions_promoweekly`

---

## 7. Hermes bundle, байткод и строки

Байткод Hermes извлечен из `assets/index.android.bundle` потоком через `hermesc -b -dump-bytecode` (без сохранения текстового дампа на диск).

1. **Demo выключен по байткоду:**
   - В модуле инициализации и экспорта `DEMO_ENABLED` проверена последовательность инструкций:
     ```text
     LoadConstFalse    r3
     StoreNPToEnvironment r2, 1, r3
     ```
   - Запись `false` в слот окружения подтверждена.
2. **Адреса API:**
   - `https://api.cashback-qr.poscenter.kz`: **найден** (ASCII / UTF-8);
   - `localhost:8000`: **отсутствует** (ASCII / UTF-8).
3. **Проверка русских строк (UTF-16LE / UTF-8):**
   - **Обязательные строки присутствуют** (в UTF-16LE):
     - `Изменить фото`: `FOUND` (UTF-16LE)
     - `Удалить фото`: `FOUND` (UTF-16LE)
     - `Введите мобильный номер Казахстана`: `FOUND` (UTF-16LE)
     - `Вам должно быть не меньше 18 лет`: `FOUND` (UTF-16LE)
     - `Покажите QR кассиру`: `FOUND` (UTF-16LE)
     - `Сканировать камерой`: `FOUND` (UTF-16LE)
   - **Устаревшие/запрещенные строки отсутствуют** (ни в UTF-16LE, ни в UTF-8):
     - `Сохранить профиль`: `NOT FOUND`
     - `ЖСН — 12 цифр`: `NOT FOUND`
     - `Штрихкод карты`: `NOT FOUND`

---

## 8. Размер

Сравнение размеров релизных APK:
- APK 1.0.8: `67 773 772 байта`
- APK 1.0.9: `67 951 855 байт`
- Разница: **+178 083 байта** (~ +173.9 KiB)

### Источник прироста размера
1. **DEX-байткод (`classes3.dex`):** добавлен нативный код библиотек `expo-image-picker`, `expo-image-manipulator` и нативной библиотеки кадрирования `com.canhub.cropper`. Прирост в `classes3.dex` составил ~453 928 байт несжатого байткода (~155 КБ в архиве APK).
2. **JS Hermes Bundle (`assets/index.android.bundle`):** размер вырос с 2 510 920 до 2 528 816 байт (+17 896 байт несжатого кода / ~6.6 КБ в архиве) за счет добавления логики выбора/загрузки аватара, валидации возраста 18+, маски ввода телефона и даты рождения.
3. **Ресурсы и разметка кроппера:** в APK добавлено 9 XML-макетов интерфейса кадрирования (`res/0Q.xml`, `res/5P.xml`, `res/7n.xml`, `res/Hx.xml`, `res/T7.xml`, `res/h2.xml`, `res/st.xml`, `res/vk.xml`, `res/zz.xml`) и файл `androidx.databinding_viewbinding.version` (~7 КБ).

---

## 9. Регрессия и Git

После завершения сборки:
- `npx jest`: **16 test suites passed, 190 tests passed, 0 failed** (лог: `/tmp/apk-1.0.9-build-logs/post-jest.log`);
- `npx tsc --noEmit`: код 0, чисто (лог: `/tmp/apk-1.0.9-build-logs/post-tsc.log`);
- Свободное место на диске: `df -h ~` → **6,7 GiB**;
- `git status --short`:
  ```text
   M mobile/app.json
   M mobile/src/components/icons.tsx
   M mobile/src/features/profile.tsx
  ?? C:/
  ?? video/
  ```
Отслеживаемые файлы вне `mobile/app.json`, `mobile/src/components/icons.tsx` и `mobile/src/features/profile.tsx` не изменялись. Каталог `mobile/android/` не отслеживается в git.

---

## 10. Не проверено

Следующие проверки требуют реального устройства, сервера и кассового узла и сознательно не выполнялись:
- Скачивание APK и установка поверх версии 1.0.8 на физическом Android-устройстве с сохранением пользовательской сессии;
- Экран входа и получение/ввод 4-значного SMS OTP кода на телефоне;
- Выбор изображения из галереи Android, работа нативного интерфейса кадрирования (CropImageActivity) и съемка камерой на устройстве;
- Реальная отправка изображения на production-сервер по маршруту `POST /me/avatar` и отображение аватарки;
- Считывание динамического QR-кода с экрана телефона сканером кассы Cash.

## Приёмка куратора — 2026-11-01: принято по файлу

Проверено независимо по `mobile/dist/cashback-one-1.0.9.apk`:

- 67 951 855 байт, SHA-256 `3ddcc5e44dd00e1642913e3a84ff510b833f931519af0459b245fa717512731a`;
- 1.0.9 / 10, `kz.cashbackone.mobile`, target SDK 36, только `arm64-v8a` и `armeabi-v7a`;
- сертификат `14afcbb5ec8375e3130b2832b1a7468372e1205c3a275ba56b8ff7b1e483cd63`, Verifies, v2;
- разрешения совпадают с APK 1.0.8 без отличий;
- `CropImageActivity`, `ExpoCropImageActivity` и их провайдеры с `exported=false`;
- demo выключен по байткоду: `LoadConstFalse r3` → `StoreNPToEnvironment r2, 1, r3`;
- в Hermes есть production API, `/me/avatar`, `code_length` и строки входа, профиля, QR; нет `localhost:8000`, `Сохранить профиль`, `ЖСН — 12 цифр`, `Штрихкод карты`, `Введите 6 цифр`;
- jest 190 passed, tsc чисто, eslint 0 ошибок и 1 старое предупреждение;
- diff исходников: только значок камеры и версия.

Не проверено: скачивание и установка поверх 1.0.8, вход с кодом из 4 цифр, выбор и обрезка фото на телефоне, настоящая загрузка фото, вид значка на экране, считывание QR кассой.
