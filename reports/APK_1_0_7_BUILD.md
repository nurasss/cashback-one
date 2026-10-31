# Сборка release APK 1.0.7 / versionCode 8

Дата: 2026-10-31, Mac. APK локально собран и скопирован в `mobile/dist/`. После сборки обязательная проверка содержимого остановлена на ошибке команды: `rg` отсутствует в среде (exit 127). По правилу промпта проверка не повторялась и оставшиеся проверки не выполнялись. APK не публиковался и на устройство не устанавливался; `expo prebuild`, `mobile/scripts/build-apk.sh`, `upload_apk.py`, commit и push не запускались.

**Итог: артефакт собран и подпись/метаданные проверены, но приёмка APK не завершена.** Не считать APK полностью проверенным или готовым к распространению.

## 1. Артефакт

| Параметр | Значение |
|---|---|
| Путь | `mobile/dist/cashback-one-1.0.7.apk` |
| Размер | **67 778 452 байта** |
| SHA-256 | `4a260bfba8f56fc8e71b75c29ad5c3b1476df0a00a2ba3220314adac8d403179` |
| package | `kz.cashbackone.mobile` |
| versionName / versionCode | **1.0.7 / 8** (`aapt2 dump badging`) |
| Архитектуры | `arm64-v8a`, `armeabi-v7a` (`aapt2 dump badging`) |
| targetSdk / compileSdk / minSdk | 36 / 36 / 24 |

Скопирован release APK из `mobile/android/app/build/outputs/apk/release/app-release.apk` командой `cp -n`. Целевой путь перед копированием отсутствовал. Старый APK не перезаписывался: `mobile/dist/cashback-one-1.0.6.apk` — **62 529 495 байт**, SHA-256 `195f486a0c02fd9891d638164bdc395cb7938d54ddc4357eff36d9e4d345338c` (сверен с известным хешем из принятого отчёта 1.0.6).

Прирост к 1.0.6: **5 248 957 байт (~5,01 MiB)**. В 1.0.7 добавлены шесть изображений 2000 px и изменения bundle/ресурсов. Точный вклад ресурсов не измерен: проверка перечня и содержимого APK не завершена.

Свободное место до сборки — 6,0 ГиБ; после — 1,2 ГиБ. Gradle-кэш и прежние APK не удалялись.

## 2. Подпись

`apksigner verify --verbose --print-certs mobile/dist/cashback-one-1.0.7.apk`:

- Статус: `Verifies`; один подписант.
- DN: `CN=Cashback One, O=POSCENTER, C=KZ`.
- SHA-256 сертификата: **`14afcbb5ec8375e3130b2832b1a7468372e1205c3a275ba56b8ff7b1e483cd63`** — совпадает с ожидаемым.
- Схема v2: `true`; v1, v3, v3.1, v4 и SourceStamp: `false`.
- Значения keystore и пароли не выводились.

## 3. Нативная правка

`mobile/android/` исключён из Git. До правки создана резервная копия:

`/private/var/folders/ws/2yz96w190q34htgtvflq4bm00000gn/T/opencode/apk-1.0.7-native-backup-mz6std72/build.gradle`

SHA-256 копии: `09fc081ef1a9d0b13acd9baf5527d14d32d1bd9135a2ac3d0b950589c0e997e1`.

`diff` после правки содержит только разрешённые изменения:

```diff
--- native-backup/build.gradle
+++ mobile/android/app/build.gradle
@@ -92,8 +92,8 @@
-        versionCode 7
-        versionName "1.0.6"
+        versionCode 8
+        versionName "1.0.7"
```

Манифест, иконки и другие исходники не менялись в рамках APK-сборки. Корректным regex-поиском подтверждена неизменённая строка в `AndroidManifest.xml`:

```xml
<uses-permission android:name="android.permission.RECORD_AUDIO" tools:node="remove"/>
```

`expo prebuild` не запускался.

## 4. Baseline и сборка

Перед baseline `uptime`: `15:18 up 2:33, 1 user, load averages: 5.06 8.85 7.49`.

- `npx jest` в `mobile/`: **15 suites passed, 212 tests passed, 0 failed**, 12,701 ms, код 0. Полный лог: `/private/var/folders/ws/2yz96w190q34htgtvflq4bm00000gn/T/opencode/apk-1.0.7-baseline-jest.log`.
- `npx tsc --noEmit`: код 0, вывода нет. Лог: `/private/var/folders/ws/2yz96w190q34htgtvflq4bm00000gn/T/opencode/apk-1.0.7-baseline-tsc.log`.

Сборка выполнялась в подоболочке; переменные загружены из `~/.cashback-one-keys/keystore.env`, значения не отображались. Использованы JDK Zulu 17, Android SDK build-tools 36.0.0, production API `https://api.cashback-qr.poscenter.kz`, `NODE_ENV=production`; `EXPO_PUBLIC_DEMO` и `EXPO_PUBLIC_ALLOW_INSECURE_HTTP` сняты из окружения. Целевая команда:

```text
./gradlew assembleRelease -PreactNativeArchitectures=arm64-v8a,armeabi-v7a --no-daemon --max-workers=1 -Dorg.gradle.parallel=false --console=plain
```

Результат: **BUILD SUCCESSFUL in 19m 3s**, 393 actionable tasks (45 executed, 348 up-to-date), код 0. Полный лог: `/private/var/folders/ws/2yz96w190q34htgtvflq4bm00000gn/T/opencode/apk-1.0.7-gradle.log`. Gradle сообщил об используемых deprecated features и выдал incubating Problems report; ошибок сборки не было.

## 5. Проверки APK, завершённые до СТОП

### Метаданные, ABI и иконка в badging

`aapt2 dump badging` подтвердил package, versionCode/versionName и только две ABI: `arm64-v8a`, `armeabi-v7a`. Также присутствует строка `application-icon` с ресурсом `res/BW.xml`. Сам факт наличия этого ресурса в badging **не заменяет** проверку adaptive-icon XML, foreground-плотностей и цвета через `aapt2 dump resources` — она не выполнена.

### Разрешения

`aapt2 dump permissions` для 1.0.7 и 1.0.6 вывел одинаковые наборы:

| Разрешение | Результат |
|---|---|
| `android.permission.INTERNET` | есть |
| `android.permission.READ_EXTERNAL_STORAGE` (maxSdk 32) | есть |
| `android.permission.VIBRATE` | есть |
| `android.permission.WRITE_EXTERNAL_STORAGE` (maxSdk 32) | есть |
| `android.permission.ACCESS_NETWORK_STATE` | есть |
| `android.permission.CAMERA` | есть |
| `android.permission.USE_BIOMETRIC` | есть |
| `android.permission.USE_FINGERPRINT` | есть |
| `kz.cashbackone.mobile.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION` | определено и используется |
| `android.permission.RECORD_AUDIO` | отсутствует |

Новых разрешений против APK 1.0.6 нет.

## 6. СТОП: ошибка команды проверки содержимого

После успешных метаданных, подписи и разрешений был запущен список содержимого APK:

```text
unzip -Z1 mobile/dist/cashback-one-1.0.7.apk | rg '(^lib/|ic_launcher|\.png$|index\.android\.bundle$)'
```

Команда завершилась с ошибкой, потому что `rg` недоступен в окружении. По правилу исполнителя команда не повторялась и дальнейшие проверки/мутации не выполнялись.

**Сырой вывод:**

```text
zsh:1: command not found: rg
Exited with code 127
```

## 7. Не проверено из-за СТОП

- наличие в APK `mipmap-anydpi-v26/ic_launcher.xml` и `ic_launcher_round.xml`, пяти плотностей `ic_launcher_foreground` и значения `ic_launcher_background = #FD6156` через `aapt2 dump resources`;
- наличие шести новых PNG внутри APK и сравнение видимых пикселей/альфа-канала с `mobile/assets/promotions/` через Pillow; способ ресурсного сжатия не установлен;
- Hermes-байткод: выключенный demo, production API origin и две казахско-русские строки про кофемашину и стикеры;
- обязательный `npx jest` после сборки (должен быть 212/212);
- контроль `git status` после сборки;
- установка поверх 1.0.6, иконка на настоящем Android-лаунчере и экраны на телефоне.

Никакая публикация, установка, commit/push не выполнялись.

## 8. Приёмка куратора — 2026-10-31

СТОП исполнителя вызван отсутствием `rg`, к APK не относится. Оставшиеся проверки куратор выполнил сам другими средствами. Этот раздел отменяет раздел 7, кроме проверок на устройстве.

- Файл: 67 778 452 байта, SHA-256 `4a260bfb…3179` совпадает; 1.0.6 не изменён.
- Badging: 1.0.7 / 8, `kz.cashbackone.mobile`, только `arm64-v8a` и `armeabi-v7a`.
- Сертификат `14afcbb5…cd63` совпадает. Разрешения идентичны 1.0.6: CAMERA есть, RECORD_AUDIO нет.
- Иконка: `mipmap/ic_launcher` и `ic_launcher_round` имеют варианты `anydpi-v26`; XML содержит background `@color/ic_launcher_background` = `#FFFD6156` и foreground `@mipmap/ic_launcher_foreground`. Все 15 webp (5 плотностей × 3 ресурса) по SHA-256 совпали с `res/mipmap-*`, то есть в APK иконка, пересобранная куратором.
- Картинки: 6 новых PNG найдены в `drawable/assets_promotions_*`. Размеры 2000×862, 2000×860, 2000×1085. Попиксельно с альфой (RGBA) совпадают с `mobile/assets/promotions/`, разница нулевая.
- Hermes: строки кофемашины и стикеров RU, описания RU, KK-подпись кофемашины, `art-hits-discount` и `https://api.cashback-qr.poscenter.kz` есть; `localhost:8000` нет.
- **Demo выключен** по байткоду (`hermesc -b -dump-bytecode`): в модуле с `DEMO_ENABLED` тот же рисунок, что в 1.0.4–1.0.6: `LoadConstFalse r3` → `StoreNPToEnvironment r2, 1, r3`.
- После сборки: `npx jest` **212 passed**, `tsc` код 0. Новых отслеживаемых изменений от сборки нет.
- Место на диске: свободно **2,0 ГиБ**. Новую сборку без освобождения места не начинать.

**Итог: APK 1.0.7 принят по файлу.** Не проверены установка поверх 1.0.6, иконка на настоящем лаунчере и экраны на телефоне. APK не опубликован, commit/push не выполнялись.
