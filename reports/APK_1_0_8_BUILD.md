# Сборка release APK 1.0.8 / versionCode 9 — только QR

Дата: 2026-10-31, Mac. APK собран локально и проверен по файлу. Не загружался на сайт или GitHub Releases, не устанавливался на устройство; `expo prebuild`, `mobile/scripts/build-apk.sh`, `upload_apk.py`, commit и push не запускались. APK 1.0.7 и кэш Gradle не удалялись.

**Итог:** проверки APK и регрессии выполнены. Остаются только проверки на телефоне и в Cash, указанные в §10.

## 1. Артефакт

| Параметр | Значение |
|---|---|
| Путь | `mobile/dist/cashback-one-1.0.8.apk` |
| Размер | **67 773 772 байта** |
| SHA-256 | `5e6b8f2158c8a00468dbe21783da444abb5bd7b55fb81c5e5ad9739020fee03b` |
| package | `kz.cashbackone.mobile` |
| versionName / versionCode | **1.0.8 / 9** (`aapt2 dump badging`) |
| Архитектуры | только `arm64-v8a`, `armeabi-v7a` |
| minSdk / targetSdk / compileSdk | 24 / 36 / 36 |

Release APK из `mobile/android/app/build/outputs/apk/release/app-release.apk` скопирован через `cp -n`. Целевой путь до копирования отсутствовал. APK 1.0.7 не перезаписан: **67 778 452 байта**, SHA-256 `4a260bfba8f56fc8e71b75c29ad5c3b1476df0a00a2ba3220314adac8d403179` — совпадает с принятым отчётом 1.0.7.

## 2. Подпись

`apksigner verify --verbose --print-certs`:

- Статус: `Verifies`; один подписант.
- DN: `CN=Cashback One, O=POSCENTER, C=KZ`.
- SHA-256 сертификата: **`14afcbb5ec8375e3130b2832b1a7468372e1205c3a275ba56b8ff7b1e483cd63`** — ожидаемый сертификат.
- Подпись v2: `true`; v1, v3, v3.1, v4 и SourceStamp: `false`.
- Содержимое keystore и секреты не выводились.

## 3. Изменения версий

Перед изменением `mobile/android/app/build.gradle` скопирован вне репозитория:

`/private/var/folders/ws/2yz96w190q34htgtvflq4bm00000gn/T/opencode/apk-1.0.8-native-backup-5rub319p/build.gradle`

SHA-256 копии: `2ac6147191e62e31a84c2e1d1c5efd0ce603650675c88c1f49ee4a258c81c297`.

Для сверки также сохранена копия `mobile/app.json` в той же временной папке; SHA-256: `905184d1f9bb823dde9fd24f2f2d4e40c065a44f2e5e4ac5fffac2cf2560fe86`.

`mobile/app.json` содержит только две запрошенные правки:

```diff
-    "version": "1.0.7",
+    "version": "1.0.8",
-      "versionCode": 8,
+      "versionCode": 9,
```

`mobile/android/app/build.gradle` — diff с резервной копией:

```diff
--- backup/build.gradle
+++ mobile/android/app/build.gradle
@@ -92,8 +92,8 @@
-        versionCode 8
-        versionName "1.0.7"
+        versionCode 9
+        versionName "1.0.8"
```

Больше в этих файлах не менялось. В манифесте проверена и оставлена без изменений строка:

```xml
<uses-permission android:name="android.permission.RECORD_AUDIO" tools:node="remove"/>
```

## 4. Baseline и сборка

Перед baseline `uptime`: `19:42 up 3:07, 1 user, load averages: 5.51 7.49 8.22`. Перед сборкой свободно 6,2 ГиБ (порог 3 ГБ пройден); после сборки также 6,2 ГиБ.

Baseline в `mobile/`:

- `npx jest`: **14 suites passed, 180 tests passed, 0 failed**, 20,87 с, код 0. Лог: `/private/var/folders/ws/2yz96w190q34htgtvflq4bm00000gn/T/opencode/apk-1.0.8-baseline-jest.log`.
- `npx tsc --noEmit`: код 0, вывода нет. Лог: `/private/var/folders/ws/2yz96w190q34htgtvflq4bm00000gn/T/opencode/apk-1.0.8-baseline-tsc.log`.

Release-сборка запущена в фоне, завершилась `BUILD SUCCESSFUL in 4m 29s`, 393 actionable tasks (39 выполнено, 354 up-to-date), код 0. Использованы JDK Zulu 17, Android SDK build-tools 36.0.0 и API `https://api.cashback-qr.poscenter.kz`; `NODE_ENV=production`, `EXPO_PUBLIC_DEMO` и `EXPO_PUBLIC_ALLOW_INSECURE_HTTP` не заданы. Секреты переданы только из `~/.cashback-one-keys/keystore.env` в подоболочке, значения не печатались.

```text
./gradlew assembleRelease -PreactNativeArchitectures=arm64-v8a,armeabi-v7a --no-daemon --max-workers=1 -Dorg.gradle.parallel=false --console=plain
BUILD SUCCESSFUL in 4m 29s
393 actionable tasks: 39 executed, 354 up-to-date
```

Полный лог: `/private/var/folders/ws/2yz96w190q34htgtvflq4bm00000gn/T/opencode/apk-1.0.8-gradle.log`. Gradle вывел стандартное предупреждение об используемых deprecated features и ссылку на incubating Problems report; сборка успешна.

## 5. Метаданные и разрешения

`aapt2 dump badging` подтвердил:

```text
package: name='kz.cashbackone.mobile' versionCode='9' versionName='1.0.8'
application-icon: res/BW.xml
native-code: 'arm64-v8a' 'armeabi-v7a'
```

Списки `aapt2 dump permissions` для 1.0.7 и 1.0.8 сравнены через `diff -u` и идентичны:

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

Логи разрешений: `apk-1.0.7-permissions.log` и `apk-1.0.8-permissions.log` в `/private/var/folders/ws/2yz96w190q34htgtvflq4bm00000gn/T/opencode/`.

## 6. Иконки и PNG-ассеты

По `aapt2 dump resources`:

- `mipmap/ic_launcher` — пять density WebP и `anydpi-v26` XML `res/BW.xml`;
- `mipmap/ic_launcher_round` — пять density WebP и `anydpi-v26` XML `res/0K.xml`;
- `mipmap/ic_launcher_foreground` — пять density WebP;
- `color/ic_launcher_background` — `#fffd6156` (ARGB, то есть `#FD6156` с непрозрачной альфой).

Для 15 WebP SHA-256 каждого APK-ресурса сопоставлен с соответствующим файлом `mobile/android/app/src/main/res/mipmap-*`; **15/15 совпали**:

| Ресурс / плотность | APK-ресурс | SHA-256 |
|---|---|---|
| `ic_launcher` / mdpi | `res/d2.webp` | `1178c3a4d85a752fdf754997c551a4b42b8ef25a0b74f0f8e4d1cc960d4de040` |
| `ic_launcher` / hdpi | `res/MO.webp` | `5809f83f1e96f364b4b7186a3051ab45284db5aae0d4f6aa01c16a92a939a325` |
| `ic_launcher` / xhdpi | `res/qs.webp` | `5625187693ec8c07b3a2c98f596d3b4b0ac54ba60c3ecfee936ded8e51a55c2a` |
| `ic_launcher` / xxhdpi | `res/Sn.webp` | `e58af52bbb3a9b749dba6d8d134e36b14c29e8bc19df7d82911ccfbdd5529c77` |
| `ic_launcher` / xxxhdpi | `res/sK.webp` | `e8fec23c7e944e599148ac56f1d178528dfa0a8b287b8dae813cd83746a95344` |
| `ic_launcher_round` / mdpi | `res/yw.webp` | `a8dbbddd39287c9aec28e8f9b0b9247d192dca55c2f2fcfd9650f4e69c1177d5` |
| `ic_launcher_round` / hdpi | `res/fq.webp` | `21ac4dfd56eb209f5b0f47dbb8c1893051854cfddc949156a49a1f0f76b315c4` |
| `ic_launcher_round` / xhdpi | `res/u5.webp` | `abfea78a733eefaaae27976d2e87df7ae8c110056ce475120f04254639e60287` |
| `ic_launcher_round` / xxhdpi | `res/j_.webp` | `d45eb826a8a245b5cae1b9c04b45deccfe5f8f3f70db3e8ac63ed8a9da0a9230` |
| `ic_launcher_round` / xxxhdpi | `res/-6.webp` | `4d9bda357d90376d5b92b1c8a1dad95ec0f88c4954b33789ed7e987a609477d6` |
| `ic_launcher_foreground` / mdpi | `res/Nt.webp` | `c6ec021faf143e6e6a94c003705a97f66f5c070a7f83a7634964a3fa820fd236` |
| `ic_launcher_foreground` / hdpi | `res/13.webp` | `32f59a0274c077ef5c5aae2b90fa928595653f997ab87a0da8b2f609b7df7fe1` |
| `ic_launcher_foreground` / xhdpi | `res/9Q.webp` | `fb7c1068258fce764b7b95c8f6fd0566672e13c230d0a84f6be1c30dccd423a9` |
| `ic_launcher_foreground` / xxhdpi | `res/iE.webp` | `fdc514ca293b1ea34472c3eddbc7f703874bf3a163fde12d2a68d70a80d5e9e4` |
| `ic_launcher_foreground` / xxxhdpi | `res/5c.webp` | `3e59e2e72c7bea96f0a388d7e5ea4cd2be6b9e47d054478868ddda7d1f66790a` |

Шесть PNG присутствуют в APK в ресурсах, определённых через `aapt2 dump resources`. Pillow-сравнение с `mobile/assets/promotions/` дало для всех **0 отличий видимых RGB-пикселей и 0 отличий альфа-канала**:

| Исходный PNG | APK-ресурс | Размер | Видимые RGB / alpha diff |
|---|---|---:|---:|
| `banner-coffee-machine.png` | `drawable/assets_promotions_bannercoffeemachine` → `res/B5.png` | 2000×862 | 0 / 0 |
| `banner-stickers.png` | `drawable/assets_promotions_bannerstickers` → `res/6-.png` | 2000×860 | 0 / 0 |
| `promo-hits-discount.png` | `drawable/assets_promotions_promohitsdiscount` → `res/R6.png` | 2000×1085 | 0 / 0 |
| `promo-card-bonus.png` | `drawable/assets_promotions_promocardbonus` → `res/AH.png` | 2000×1085 | 0 / 0 |
| `promo-weekly.png` | `drawable/assets_promotions_promoweekly` → `res/2l.png` | 2000×1085 | 0 / 0 |
| `promo-fresh-products.png` | `drawable/assets_promotions_promofreshproducts` → `res/o4.png` | 2000×1085 | 0 / 0 |

## 7. Hermes bundle и QR-only

`assets/index.android.bundle` извлечён во временный бинарный файл. Текстовый вывод `hermesc -b -dump-bytecode` передавался по конвейеру и **не сохранялся на диск**.

- По байткоду присутствует `DEMO_ENABLED`; в инициализации модуля с экспортом `DEMO_ENABLED` проверено `LoadConstFalse r3` → `StoreNPToEnvironment r2, 1, r3`.
- `https://api.cashback-qr.poscenter.kz` — есть; `localhost:8000` — нет.
- `Штрихкод карты`, `Карта штрихкоды`, `CardBarcode` — отсутствуют.
- `Покажите QR кассиру` и `Сканировать камерой` — присутствуют.

Сводка проверенного содержимого бинарного bundle:

```text
DEMO_ENABLED: True
production API origin: True
cashier QR text: True
camera scanner text: True
localhost:8000: False
Штрихкод карты: False
Карта штрихкоды: False
CardBarcode: False
DEMO slot-1 false-store sequences: 2
Hermes bytecode checks passed; textual dump was streamed, not saved.
```

Первый фильтр искал Unicode-тексты буквально в форматированном выводе Hermes, где они не отображались; сырые UTF-8/UTF-16 строки bundle показали корректные значения. Проверка была уточнена: строки сверены по байткоду, а инструкции Hermes — отдельным потоковым фильтром. Также при первичном поиске исполняемого файла `hermesc` был лишний префикс `mobile/` относительно рабочей папки `mobile/`; путь исправлен на `node_modules/hermes-compiler/hermesc/osx-bin/hermesc`. Это были ошибки путей/фильтра, не расхождения содержимого APK; повторный результат проверок приведён выше.

## 8. Размер

Разница относительно APK 1.0.7:

```text
67 773 772 − 67 778 452 = −4 680 байт (около −4,57 KiB)
```

Размер практически не изменился. Незначительное уменьшение ожидаемо: в QR-only bundle удалены экранный рендерер Code128 и encoder `CardBarcode`/`code128`; иконки и шесть крупных PNG сохранились без изменений. APK не включает тестовые файлы.

## 9. Регрессия и Git

После сборки в `mobile/`:

- `npx jest`: **14 suites passed, 180 tests passed, 0 failed**, 19,055 ms, код 0. Лог: `/private/var/folders/ws/2yz96w190q34htgtvflq4bm00000gn/T/opencode/apk-1.0.8-post-jest.log`.
- `npx tsc --noEmit`: код 0, вывода нет. Лог: `/private/var/folders/ws/2yz96w190q34htgtvflq4bm00000gn/T/opencode/apk-1.0.8-post-tsc.log`.

Сверка `git status --short` до/после сборки: все прежние QR-only staged/unstaged файлы остались в тех же состояниях; от сборки добавилось только `M mobile/app.json`. В diff `app.json` изменены исключительно `version` и `versionCode`; `mobile/android/` игнорируется Git. `git diff --stat` после сборки показывает принятые QR-only правки плюс две строки версии; APK не появляется в Git status. Отчёт создаётся отдельно после этой сверки.

## 10. Не проверено

- Скачивание APK и установка поверх 1.0.7 с сохранением данных.
- Экран QR на телефоне.
- Считывание QR кассой Cash.

Публикация, установка, commit/push и проверка на настоящем устройстве не выполнялись.

## 11. Приёмка куратора — 2026-10-31

Куратор повторил проверки сам, отдельными командами:

- Файл: 67 773 772 байта, SHA-256 `5e6b8f21…e03b` совпадает. 1.0.7 (`4a260bfb…3179`) и 1.0.6 не изменены.
- Badging: 1.0.8 / 9, `kz.cashbackone.mobile`, targetSdk 36, только `arm64-v8a` и `armeabi-v7a`.
- Сертификат `14afcbb5…cd63` совпадает. Разрешения идентичны 1.0.7: CAMERA есть, RECORD_AUDIO нет.
- Bundle: `Штрихкод карты`, `Карта штрихкоды`, `CardBarcode`, `code128Pattern`, `modeBarcode`, `barcodeCaption`, `localhost:8000` не найдены ни в UTF-8, ни в UTF-16. `Покажите QR кассиру`, `Сканировать камерой`, `Мой QR-код` найдены в UTF-16, production API origin в UTF-8.
- **Demo выключен** по байткоду: в функции с `DEMO_ENABLED` тот же рисунок `LoadConstFalse r3` → `StoreNPToEnvironment r2, 1, r3`.
- `npx jest` **14 suites, 180 passed**, `tsc` код 0. `app.json` изменён только в `version` и `versionCode`, `build.gradle` 9 / 1.0.8, строка RECORD_AUDIO в манифесте на месте.
- Значения `ic_launcher_*` и попиксельное сравнение PNG куратор не повторял: иконки и картинки с 1.0.7 не менялись. Подтверждено только наличие 11 ресурсов `drawable/assets_promotions_*`. Опора на §6.

**Итог: APK 1.0.8 принят по файлу.** Не проверены скачивание, установка поверх 1.0.7, экран QR на телефоне и считывание QR кассой. APK не опубликован, commit/push не выполнялись.
