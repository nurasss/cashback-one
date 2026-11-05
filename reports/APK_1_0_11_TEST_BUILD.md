# Сборка release APK 1.0.11-test / versionCode 12 — пилотный тест в ТЦ «In Plaza»

Дата: 2026-11-04, Mac. APK собран локально и проверен по файлу. Не загружался на сайт или в GitHub Releases, `version.json` не создавался/не менялся, на устройство не устанавливался; `expo prebuild`, `mobile/scripts/build-apk.sh`, `upload_apk.py`, deploy, commit и push не запускались. Прежние APK и кэш Gradle не удалялись.

**Итог:** сборка, проверки APK и тесты регрессии выполнены успешно. Остаются только проверки на реальном устройстве и кассе, указанные в §10.

---

## 1. Артефакт

| Параметр | Значение |
|---|---|
| Путь | `mobile/dist/cashback-one-1.0.11-test.apk` |
| Размер | **68 601 127 байт** |
| SHA-256 | `1fbb7c6c4bdb0c947e0e72cab053ef5a3106ee951ee23a905011c0fca4203754` |
| package | `kz.cashbackone.mobile` |
| versionName / versionCode | **1.0.11-test / 12** (`aapt2 dump badging`) |
| Архитектуры | только `arm64-v8a`, `armeabi-v7a` |
| minSdk / targetSdk / compileSdk | 24 / 36 / 36 |

Release APK из `mobile/android/app/build/outputs/apk/release/app-release.apk` скопирован через `cp -n`.
Прежний файл первой попытки (без API URL в бандле) переименован и сохранен:
- `cashback-one-1.0.11-test.no-api.apk`: **68 600 383 байт**, SHA-256 `987b937a025a9bd129f20f2c5d681bf0b135db2a0e68d7ddb9a892488956cb05`.

Сравнение SHA-256 бандлов (`assets/index.android.bundle`):
- Бандл из `cashback-one-1.0.11-test.apk`: `549587dae99e53ebc1c245039c8dcabe25214d788ded5e1d684dfb15a97b9a81`
- Бандл из `cashback-one-1.0.11-test.no-api.apk`: `ed02e6272ffea4bc709604d0342b0b48fade007d151fa07cdaa9f9916690567c`
(Бандлы гарантированно различаются; Metro выполнил полную пересборку бандла с новыми переменными окружения).

Прежние релизные APK не затронуты и проверены:
- `cashback-one-1.0.10.apk`: **68 600 435 байт**, SHA-256 `8c8726e068088f3eae66fa1b3b1fffa7d2512c6aa44ebdded03f0bd611c123c9` (без изменений);
- `cashback-one-1.0.9.apk`: **67 951 855 байт**, SHA-256 `3ddcc5e44dd00e1642913e3a84ff510b833f931519af0459b245fa717512731a` (без изменений);
- `cashback-one-1.0.8.apk`: **67 773 772 байта**, SHA-256 `5e6b8f2158c8a00468dbe21783da444abb5bd7b55fb81c5e5ad9739020fee03b` (без изменений);
- `cashback-one-1.0.7.apk`: **67 778 452 байта**, SHA-256 `4a260bfba8f56fc8e71b75c29ad5c3b1476df0a00a2ba3220314adac8d403179` (без изменений);
- `cashback-one-1.0.6.apk`: **62 529 495 байт**, SHA-256 `195f486a0c02fd9891d638164bdc395cb7938d54ddc4357eff36d9e4d345338c` (без изменений).

---

## 2. Подпись

`apksigner verify --verbose --print-certs mobile/dist/cashback-one-1.0.11-test.apk`:

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
```json
    "version": "1.0.11-test",
    "android": {
      "package": "kz.cashbackone.mobile",
      "versionCode": 12,
```

### 3.2. `mobile/android/app/build.gradle`
```groovy
        versionCode 12
        versionName "1.0.11-test"
```

### 3.3. Манифест нативного проекта
В `mobile/android/app/src/main/AndroidManifest.xml` проверены через `grep` строки удаления неиспользуемых разрешений:
```xml
<uses-permission android:name="android.permission.RECORD_AUDIO" tools:node="remove"/>
<uses-permission android:name="android.permission.SYSTEM_ALERT_WINDOW" tools:node="remove"/>
```
Команда `expo prebuild` не запускалась.

---

## 4. Baseline и сборка

### 4.1. Baseline до сборки
- Дисковое пространство: `df -h ~` → свободно **4,8 GiB** (порог >= 3 GB пройден).
- Нагрузка системы: `uptime` → load average: `3.73` (< 12).
- `npx jest --runInBand`: **19 test suites passed, 255 tests passed, 0 failed** (полное совпадение с разделом «2ГИС» отчёта `reports/APP_1_0_11_TEST_2026-11-04.md`).
- `npx tsc --noEmit`: код 0, чисто.
- `npx eslint .`: 0 ошибок, 1 ожидаемое предупреждение в `useKeyboardLift.ts`.

### 4.2. Release-сборка
Сборка выполнена в фоне с перенаправлением вывода в `/tmp/apk-1.0.11-test-build-logs/gradle-build-v2.log`.
Команда:
```bash
./gradlew assembleRelease -PreactNativeArchitectures=arm64-v8a,armeabi-v7a --no-daemon --max-workers=1 -Dorg.gradle.parallel=false --console=plain
```
Окружение сборки:
- JDK: Zulu 17 (`/Users/nuras/.jdks/zulu17.68.203-ca-jdk17.0.20.1-macosx_x64/Contents/Home`)
- Android SDK build-tools: `36.0.0`
- `NODE_ENV=production`
- `EXPO_PUBLIC_API_BASE_URL="https://api.cashback-qr.poscenter.kz"`
- `EXPO_PUBLIC_DEMO` и `EXPO_PUBLIC_ALLOW_INSECURE_HTTP` удалены через `unset`
- Вывод `env | grep -E '^(NODE_ENV|EXPO_PUBLIC_)'`:
  ```text
  NODE_ENV=production
  EXPO_PUBLIC_API_BASE_URL=https://api.cashback-qr.poscenter.kz
  ```
- Ключи переданы в подоболочке из `~/.cashback-one-keys/keystore.env` с `CASHBACK_STORE_FILE="$HOME/.cashback-one-keys/release.keystore"`

Результат сборки:
```text
BUILD SUCCESSFUL in 2m 35s
393 actionable tasks: 27 executed, 366 up-to-date
GRADLE_EXIT=0
```
В логе сборки слово `password` не встречается.

---

## 5. Метаданные, разрешения и конфигурация приложения

### 5.1. `aapt2 dump badging`
```text
package: name='kz.cashbackone.mobile' versionCode='12' versionName='1.0.11-test' platformBuildVersionName='16' platformBuildVersionCode='36' compileSdkVersion='36' compileSdkVersionCodename='16'
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
  "version": "1.0.11-test",
  "android": {
    "package": "kz.cashbackone.mobile",
    "versionCode": 12
  }
}
```
`version` (`1.0.11-test`) и `android.versionCode` (`12`) полностью совпадают с метаданными `aapt2 dump badging`.

### 5.3. Разрешения (`aapt dump permissions`) и diff с APK 1.0.10
Команда: `diff -u perms-1.0.10.txt perms-1.0.11-test.txt` завершилась с кодом 0 (разница 0 строк).

| Разрешение | Статус в 1.0.11-test | Примечание |
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

Новых или измененных разрешений нет (diff = 0).

---

## 6. Ресурсы и ассеты

Сравнение списка ресурсов с 1.0.10:
- `unzip -l 1.0.10 | awk '{print $4}' | grep '^res/'` против 1.0.11-test: `diff -u` пустой (0 строк).
- `unzip -l 1.0.10 | awk '{print $4}' | grep '^assets/'` против 1.0.11-test: `diff -u` пустой (0 строк).

Все 4 боковые иллюстрации `*_side` (`res/f2.png`, `res/iL.png`, `res/j8.png`, `res/s1.png`) и базовые ассеты полностью сохранены без изменений.

---

## 7. Hermes bundle, байткод и строки

Байткод Hermes проверен потоком через `hermesc -b -dump-bytecode` (без сохранения текстового дампа на диск).

1. **Demo выключен по байткоду:**
   - В модуле `mockApi` проверена последовательность инструкций:
     ```text
     StoreToEnvironment   r2, 0, r3
     LoadConstFalse       r3
     StoreNPToEnvironment r2, 1, r3
     ```
   - Запись `false` в слот 1 окружения подтверждена.
2. **Адреса API, 2ГИС и URL обновления:**
   - `https://api.cashback-qr.poscenter.kz`: **найден** (`True`);
   - `https://2gis.kz/astana/firm/70000001103172202`: **найден** (`True`);
   - `https://cashback-qr.poscenter.kz/app/version.json`: **найден** (`True`);
   - `localhost:8000`: **отсутствует** (`False`).
3. **Проверка локализованных строк (UTF-16LE):**
   - **Обязательные строки присутствуют** (в UTF-16LE):
     - `Вы можете потратить эти баллы в супермаркете «КеремЕт», ТЦ «In Plaza», по адресу: `: `True`
     - `проспект Тауелсиздик, 4.`: `True`
     - `Бұл ұпайларды «In Plaza» сауда орталығындағы «КеремЕт» супермаркетінде жұмсай аласыз, мекенжайы: `: `True`
     - `Тәуелсіздік даңғылы, 4.`: `True`
     - `Баланс обновляется не сразу. Новые начисления и списания появляются 2 раза в сутки.`: `True`
     - `Покажите QR кассиру`: `True`
   - **Запрещенные и устаревшие строки отсутствуют** (ни в UTF-16LE, ни в UTF-8):
     - `Во всех магазинах-партнерах`: `False`
     - `Обновляется при закрытии смены`: `False`
     - `Покажите этот код кассиру`: `False`
     - `Сохранить профиль`: `False`
     - `Штрихкод карты`: `False`

---

## 8. Размер

Сравнение размеров релизных APK:
- APK 1.0.10: `68 600 435 байт`
- APK 1.0.11-test: `68 601 127 байт`
- Разница: **+692 байта** (~ +0.67 KiB)

### Источник дельты размера
Разница составляет менее 1 КБ и обусловлена:
1. Добавлением логики открытия 2ГИС и обработчика ошибок в `mobile/app/(app)/(tabs)/index.tsx`;
2. Добавлением модуля `mobile/src/features/store.ts` с константой URL;
3. Разделением строки `storeNote` на `storeNoteLead` и `storeAddress` с названием супермаркета «КеремЕт» в RU и KK;
4. Встраиванием production API URL `https://api.cashback-qr.poscenter.kz`.

---

## 9. Регрессия и Git

После завершения сборки:
- `npx jest --runInBand`: **19 test suites passed, 255 tests passed, 0 failed**;
- `npx tsc --noEmit`: код 0, чисто;
- `git status --short`:
  ```text
   M mobile/app.json
   M mobile/app/(app)/(tabs)/index.tsx
   M mobile/app/(app)/(tabs)/profile.tsx
   M mobile/app/(app)/(tabs)/qr.tsx
   M mobile/app/(app)/status.tsx
   M mobile/src/features/DynamicQr.tsx
   M mobile/src/features/home.tsx
   M mobile/src/i18n/kz.ts
   M mobile/src/i18n/ru.ts
   M mobile/tests/flows.test.tsx
   M mobile/tests/qrScreen.test.tsx
  ?? C:/
  ?? docs/PROMPT_APK_1_0_11_TEST_2026-11-04.md
  ?? docs/PROMPT_APP_1_0_11_TEST_2026-11-04.md
  ?? docs/PROMPT_APP_1_0_11_TEST_2GIS_2026-11-04.md
  ?? mobile/src/features/store.ts
  ?? reports/APP_1_0_11_TEST_2026-11-04.md
  ?? reports/screenshots-1.0.11-test/
  ?? video/
  ```

В рамках данной сборки отслеживаемые файлы git не изменялись (изменения соответствуют принятым правкам 1.0.11-test и 2ГИС). Директория `mobile/android/` не отслеживается в git.

---

## 10. Не проверено

Следующие проверки требуют физического смартфона, сетевого окружения и кассового узла и не выполнялись в рамках данной задачи:
1. Установка релизного APK поверх версии 1.0.10 на реальном Android-смартфоне с сохранением сессии;
2. Нажатие на баланс в шапке главной страницы и переход в историю операций на реальном устройстве;
3. Корректное отображение текста о супермаркете «КеремЕт» в ТЦ «In Plaza» и подчеркивание адреса на мобильном экране;
4. Нажатие на блок адреса и открытие карточки супермаркета в установленном приложении 2ГИС (или браузере);
5. Отображение текста о задержке баланса на экране «Мой статус»;
6. Считывание штрихкода карты из QR-кода реальным 2D-сканером кассы Cash в ТЦ «In Plaza»;
7. Поведение приложения у покупателя с двумя картами (отображение первой карты `list[0]`);
8. Отображение экрана профиля без пунктов «Мои карты» и «Выйти».
