# Сборка release APK 1.0.4 / versionCode 5

Дата: 2026-10-22, Mac. Только локальная сборка. На сайт не загружался, в GitHub Releases не публиковался, на устройство не устанавливался, `upload_apk.py` не запускался, `.env.hosting.local` не читался, commit/push не делались.

**Поведение на телефоне не проверено.** Все проверки ниже — проверки файла APK и кода, не работы приложения на устройстве.

---

## 1. Артефакт

| Параметр | Значение |
|---|---|
| Путь | `/Users/nuras/Desktop/cashback-one/mobile/dist/cashback-one-1.0.4.apk` |
| Размер | **51 630 551 байт** |
| SHA-256 | `f44072d9f074bd190d2f1a63d53b2942cfe82e5109ebb156e989c6bf2e06d0b9` |
| package | `kz.cashbackone.mobile` |
| versionName / versionCode | **1.0.4 / 5** (по `aapt2 dump badging`) |
| debuggable | нет: признак `application-debuggable` в манифесте отсутствует |
| Архитектуры | `arm64-v8a`, `armeabi-v7a` (по 19 нативных библиотек у каждой; `x86` и `x86_64` нет) |
| targetSdk / compileSdk | 36 / 36 (minSdk 24) |

Старые APK не перезаписывались: `dist/cashback-one-1.0.0.apk` и `dist/cashback-one-1.0.3.apk` сохранены без изменений. Путь назначения до копирования был свободен (`cp -n`).

---

## 2. Подпись и совпадение сертификата

- Сертификат ключа в `release.keystore` до сборки (`keytool -list -v`, пароль передан через переменную окружения `-storepass:env`, не аргументом):
  - DN: `CN=Cashback One, O=POSCENTER, C=KZ`
  - SHA-256: `14:AF:CB:B5:EC:83:75:E3:13:0B:28:32:B1:A7:46:83:72:E1:20:5C:3A:27:5B:A5:6B:8F:F7:B1:E4:83:CD:63`
- После сборки `apksigner verify --verbose --print-certs` для 1.0.4:
  - Статус: `Verifies`
  - Число подписантов: 1
  - DN: `CN=Cashback One, O=POSCENTER, C=KZ`
  - SHA-256 сертификата: **`14afcbb5ec8375e3130b2832b1a7468372e1205c3a275ba56b8ff7b1e483cd63`** — **полностью совпадает** с APK 1.0.2 и 1.0.3.
  - Схемы подписи: v2 — `true`; v1, v3, v3.1, v4 — `false` (набор схем идентичен 1.0.2 и 1.0.3).
- Подпись release-ключом; debug-ключ не использовался.
- Содержимое и пароли keystore не выводились и не копировались в репозиторий. Внутри APK файлов `*.keystore` нет.

---

## 3. Изменённые файлы

| Файл | Изменение | В git |
|---|---|---|
| `mobile/app.json` | `expo.version` 1.0.3 → **1.0.4**, `android.versionCode` 4 → **5** | отслеживается |
| `mobile/android/app/build.gradle` | `versionCode 4` → **5**, `versionName "1.0.3"` → **"1.0.4"** | **не отслеживается** (папка `mobile/android/` в `.gitignore`), локальное изменение |
| `mobile/assets/promotions/*` | 5 локальных PNG-изображений главной (1 верхний баннер, 4 карточки) | неотслеживаемые/новые |
| `mobile/src/features/promotionsArtwork.ts` | Таблица и модуль промо-ассетов | неотслеживаемый/новый |
| `mobile/src/features/home.tsx` | Включение нового баннера и сетки 2×2 «Горячие предложения» | отслеживается |
| `mobile/app/(app)/(tabs)/index.tsx` | Поддержка прокрутки ScrollView главной | отслеживается |
| `mobile/tests/homeArtwork.test.tsx` | Тесты логики баннеров и сетки акций | неотслеживаемый/новый |

Package / applicationId не менялись (`kz.cashbackone.mobile`). Backend, agent и admin не затрагивались.

---

## 4. Команды и результаты сборки (без секретов)

1. **Предварительные проверки:**
   - JDK Zulu 17: `/Users/nuras/.jdks/zulu17.68.203-ca-jdk17.0.20.1-macosx_x64/Contents/Home`
   - Android SDK: `~/Library/Android/sdk` (build-tools 36.0.0, platform android-36)
   - Baseline перед сборкой: `npm run typecheck` (код 0), `npm test` (187 passed, код 0).
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

   Результат: `BUILD SUCCESSFUL in 52m 29s`, 393 задачи (43 executed, 350 up-to-date), код выхода 0.
3. **Копирование:**
   `mobile/android/app/build/outputs/apk/release/app-release.apk` → `mobile/dist/cashback-one-1.0.4.apk`.

---

## 5. Фактические доказательства production-конфигурации

1. **Конфиг приложения (`assets/app.config` внутри APK):**
   - `"version": "1.0.4"`
   - `"versionCode": 5`
   - `"package": "kz.cashbackone.mobile"`
2. **Hermes байткод (`assets/index.android.bundle` внутри APK):**
   - Строка `https://api.cashback-qr.poscenter.kz` присутствует (`True`).
   - Строка `api.cashback-qr.poscenter.kz` присутствует (`True`).
    - Названия `EXPO_PUBLIC_DEMO` и `ALLOW_INSECURE_HTTP` отсутствуют в таблице строк. Само по себе это не доказывает значения флагов после подстановки Metro. Независимая проверка demo-off по инструкциям байткода приведена в §7.
   - Компоненты UI главной (`PermanentOffersGrid`, `bannerLocal`, `offerHitsDiscounter`, `banner-car-prize` и др.) подтверждены в бандле.
   - Metro упаковал 57 файлов ассетов (ровно +5 новых промо-изображений относительно 52 ассетов в 1.0.3).
 3. **Манифест (badging и отдельный XML tree):**
   - `application-debuggable` отсутствует.
   - `usesCleartextTraffic` отсутствует.
   - `windowSoftInputMode`: `adjustResize`.
4. **Регрессионные тесты после сборки:**
   - `npm test`: **187 passed** (13 test suites), код выхода 0.
   - `npm run typecheck`: **0 errors**, код выхода 0.

---

## 6. Ограничения и замечания

- **Место на диске: осталось ≈595 МБ** (было ≈5.3 ГБ до сборки). Основную часть заняли промежуточные кэши и нативные файлы компиляции в `mobile/android/app/build`. Ничего не удалялось.
- Изменение версии в `mobile/android/app/build.gradle` находится в `.gitignore` и в git не отслеживается (в git фиксируется `mobile/app.json`).
- APK не тестировался на физическом устройстве: установка поверх 1.0.3, распознавание кассовым сканером и поведение экрана подлежат отдельной проверке пользователем.

## 7. Независимая проверка куратора

Проверен готовый APK без пересборки, доступа к ключам, публикации и установки:

- Размер и SHA-256 совпали с §1. Локальный APK 1.0.3 также сохранил прежний SHA-256 `ac33efc647eb9f606cc6afba754214b33f870426b7c11fbc86472d076fe604ba`.
- `apksigner verify --verbose --print-certs`: обе версии валидны, один и тот же release-сертификат `14afcbb5ec8375e3130b2832b1a7468372e1205c3a275ba56b8ff7b1e483cd63`. Это необходимая предпосылка обновления, не доказательство успешной установки на конкретном устройстве.
- `aapt2 dump badging`: package `kz.cashbackone.mobile`, версия 1.0.4 / 5, target SDK 36, обе ARM-архитектуры. В ZIP по 19 `.so` на архитектуру, keystore/jks нет. Встроенный `assets/app.config` соответствует новой версии.
- `aapt2 dump xmltree --file AndroidManifest.xml`: min SDK 24, target SDK 36, `windowSoftInputMode=0x10` (adjustResize); атрибуты `debuggable` и `usesCleartextTraffic` не заданы. Badging отдельно не заменяет чтение этих атрибутов XML.
- `hermesc -b -dump-bytecode` для бандла, извлечённого непосредственно из APK: в модуле demo значение `LoadConstFalse r3` записывается в environment slot 1 (`StoreNPToEnvironment r2, 1, r3`); getter экспортируемого `DEMO_ENABLED` читает slot 1 и возвращает его. Следовательно, в этой сборке `DEMO_ENABLED=false`. В SessionProvider выбор demo-store, demo URL и createDemoApi зависит от этого флага, а обычная ветка содержит production HTTPS API. Это проверка скомпилированной логики, не запуска на телефоне.
- Пять промоизображений найдены и сравнены после декодирования PNG. Первоначальные проверки побайтового и полного RGBA-совпадения дали отрицательный результат, без изменения APK или повторной сборки. Диагностика установила: размеры, все альфа-значения и все видимые пиксели совпадают; различается только RGB полностью прозрачных пикселей (4999 пикселей баннера, по 4843 у каждой карточки). Ресурсы Android переупакованы, поэтому совпадение исходных SHA-256 внутри ZIP не ожидается.

| Исходный ассет | Ресурс внутри APK | Отличий видимых пикселей / альфа |
|---|---|---|
| `banner-car-prize.png` | `res/lH.png` | 0 / 0 |
| `offer-hits-discount.png` | `res/Js.png` | 0 / 0 |
| `offer-weekly-promo.png` | `res/4p.png` | 0 / 0 |
| `offer-card-bonus.png` | `res/UO.png` | 0 / 0 |
| `offer-fresh-products.png` | `res/bC.png` | 0 / 0 |

При проверке `df` показывал около 1.6 GiB доступного места; значение меняется со временем. Куратор ничего не удалял. Тесты в этой проверке файла APK повторно не запускались: 187 passed/typecheck после сборки — результат исполнителя (§5), а независимые 187 passed/typecheck UI-пакета были получены до смены версии. `git diff --check` чистый. Проверки телефона и кассы остаются открытыми.
