# Сборка release APK 1.0.5 / versionCode 6

Дата: 2026-10-23, Mac. Только локальная сборка. На сайт не загружался, в GitHub Releases не публиковался, на устройство не устанавливался, `upload_apk.py` не запускался, `.env.hosting.local` не читался, commit/push не делались.

**Поведение на телефоне не проверено.** Все проверки ниже — проверки файла APK и кода, не работы приложения на устройстве.

---

## 1. Артефакт

| Параметр | Значение |
|---|---|
| Путь | `/Users/nuras/Desktop/cashback-one/mobile/dist/cashback-one-1.0.5.apk` |
| Размер | **51 630 487 байт** |
| SHA-256 | `eefc912362bc7241f1488aacce21bce0ffa419d0053205fff8617925c56c664b` |
| package | `kz.cashbackone.mobile` |
| versionName / versionCode | **1.0.5 / 6** (по `aapt2 dump badging`) |
| debuggable | нет: признак `application-debuggable` в манифесте отсутствует |
| Архитектуры | `arm64-v8a`, `armeabi-v7a` (по 19 нативных библиотек у каждой; `x86` и `x86_64` нет) |
| targetSdk / compileSdk | 36 / 36 (minSdk 24) |

Старые APK не перезаписывались: `dist/cashback-one-1.0.0.apk`, `dist/cashback-one-1.0.3.apk`, `dist/cashback-one-1.0.4.apk` сохранены без изменений. Путь назначения до копирования был свободен (`cp -n`).

---

## 2. Подпись и совпадение сертификата

- Сертификат ключа в `release.keystore` до сборки (DN: `CN=Cashback One, O=POSCENTER, C=KZ`).
- После сборки `apksigner verify --verbose --print-certs` для 1.0.5:
  - Статус: `Verifies`
  - Число подписантов: 1
  - DN: `CN=Cashback One, O=POSCENTER, C=KZ`
  - SHA-256 сертификата: **`14afcbb5ec8375e3130b2832b1a7468372e1205c3a275ba56b8ff7b1e483cd63`** — **полностью совпадает** с APK 1.0.2, 1.0.3 и 1.0.4.
  - Схемы подписи: v2 — `true`; v1, v3, v3.1, v4 — `false` (набор схем идентичен 1.0.2–1.0.4).
- Подпись release-ключом; debug-ключ не использовался.
- Содержимое и пароли keystore не выводились и не копировались в репозиторий. Внутри APK файлов `*.keystore` / `*.jks` нет.

---

## 3. Изменённые файлы

| Файл | Изменение | В git |
|---|---|---|
| `mobile/app.json` | `expo.version` 1.0.4 → **1.0.5**, `android.versionCode` 5 → **6** | отслеживается (правка куратора) |
| `mobile/src/i18n/ru.ts` | Ключ `balanceDelayNote` с новым текстом о балансе | отслеживается (правка куратора) |
| `mobile/src/i18n/kz.ts` | Ключ `balanceDelayNote` с новым текстом о балансе | отслеживается (правка куратора) |
| `mobile/tests/cardBarcode.test.tsx` | Обновление проверки текста `balanceDelayNote` в тестах | отслеживается (правка куратора) |
| `mobile/android/app/build.gradle` | `versionCode 5` → **6**, `versionName "1.0.4"` → **"1.0.5"** | **не отслеживается** (папка `mobile/android/` в `.gitignore`), локальное изменение для сборки |

Package / applicationId не менялись (`kz.cashbackone.mobile`). Исходники приложения исполнителем не менялись. В отслеживаемых файлах `mobile/` изменений от сборки нет.

---

## 4. Команды и результаты сборки (без секретов)

1. **Предварительные проверки:**
   - JDK Zulu 17: `/Users/nuras/.jdks/zulu17.68.203-ca-jdk17.0.20.1-macosx_x64/Contents/Home`
   - Android SDK: `~/Library/Android/sdk` (build-tools 36.0.0, platform android-36)
   - Дисковое пространство перед сборкой: 5.5 GiB свободно (> 3 ГБ).
   - Baseline перед сборкой в `mobile/`: `npm run typecheck` (код 0), `npm test` (187 passed, 13 test suites, код 0).
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

   Результат: `BUILD SUCCESSFUL in 14m 48s`, 393 задачи (43 executed, 350 up-to-date), код выхода 0.
3. **Копирование:**
   `mobile/android/app/build/outputs/apk/release/app-release.apk` → `mobile/dist/cashback-one-1.0.5.apk` через `cp -n`.

---

## 5. Фактические доказательства production-конфигурации и новых текстов

1. **Конфиг приложения (`assets/app.config` внутри APK):**
   - `"version": "1.0.5"`
   - `"versionCode": 6`
   - `"package": "kz.cashbackone.mobile"`
2. **Hermes байткод (`assets/index.android.bundle` внутри APK):**
   - Строка `https://api.cashback-qr.poscenter.kz` присутствует (`True`).
   - Строка `api.cashback-qr.poscenter.kz` присутствует (`True`).
   - Названия `EXPO_PUBLIC_DEMO` и `ALLOW_INSECURE_HTTP` отсутствуют в таблице строк.
   - **Demo выключен**: декомпиляция байткода (`hermesc -b -dump-bytecode`) подтверждает:
     - в модуле окружения значение `LoadConstFalse r3` записывается в environment slot 1 (`StoreNPToEnvironment r2, 1, r3`);
     - геттер экспортируемого `DEMO_ENABLED` (`Function<get>`) читает slot 1 (`LoadFromEnvironment r0, r0, 1`) и возвращает `false`;
     - в `SessionProvider` ветка выбора demo-store обходится (`JmpFalse` при вызове `createDemoApi`), а активная ветка конфигурирует production API HTTPS URL.
   - **Новые тексты о балансе присутствуют** (в байткоде в кодировке UTF-16LE):
     - RU: `«Баланс обновляется не сразу. Новые начисления и списания появляются 2 раза в сутки.»` (`True`);
     - KK: `«Баланс бірден жаңартылмайды. Жаңа есептеулер мен есептен шығарулар тәулігіне 2 рет көрсетіледі.»` (`True`).
   - **Старые тексты отсутствуют** (в UTF-8 и UTF-16LE):
     - RU: `«когда магазин передаст данные»` (`False`);
     - KK: `«дүкен деректерді жібергеннен кейін»` (`False`).
3. **Манифест (badging и xmltree):**
   - `application-debuggable` отсутствует.
   - `usesCleartextTraffic` отсутствует.
   - `windowSoftInputMode`: `adjustResize` (`0x10`).
4. **Промо-ассеты (5 PNG):**
   Все 5 изображений главной проверены попиксельно (`Image.open` / RGBA) между исходниками и ресурсами внутри APK:
   - `banner-car-prize.png` (`res/lH.png`): diff_visible = 0, diff_alpha = 0
   - `offer-hits-discount.png` (`res/Js.png`): diff_visible = 0, diff_alpha = 0
   - `offer-weekly-promo.png` (`res/4p.png`): diff_visible = 0, diff_alpha = 0
   - `offer-card-bonus.png` (`res/UO.png`): diff_visible = 0, diff_alpha = 0
   - `offer-fresh-products.png` (`res/bC.png`): diff_visible = 0, diff_alpha = 0
5. **Регрессионные тесты после сборки:**
   - `npm test`: **187 passed** (13 test suites), код выхода 0.
   - `npm run typecheck`: **0 errors**, код выхода 0.
   - `git diff --stat -- mobile`: в репозитории изменены только 4 файла куратора.

---

## 6. Не проверено

- Установка APK на физическое мобильное устройство (поверх 1.0.4 или начисто).
- Визуальное отображение нового текста на экранах реальных смартфонов с разной плотностью и системным масштабом шрифта.
- Взаимодействие со сканером на кассе магазина.
