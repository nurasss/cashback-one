# APK Android 1.0.2 — остановка до сборки

## Результат

Новый подписанный APK не собран. После npm ci обнаружено неожиданное блокирование install-скрипта зависимости. По правилу пользователя дальнейшая сборка остановлена, исправления и разрешение install-скриптов не выполнялись.

Версия исходников: versionName 1.0.2, versionCode 3 (mobile/app.json). Размер и SHA-256 нового APK отсутствуют; apksigner/aapt для нового результата не запускались. Существующий старый APK не выдаётся за новый.

## Выполнено

1. На текущем Windows-компьютере из исходной mobile запущены npm test и npm run typecheck. Обе команды exit code 0.
2. Проверен JDK: OpenJDK 17.0.20.1 Temurin. Прочитаны существующие Gradle-настройки: Xmx1536m, MaxMetaspaceSize512m, UseSerialGC, workers.max=2, parallel=false; disable-lint.gradle отключает lintVital/lintAnalyze.
3. Проверка файла подкачки внутри песочницы получила отказ CIM. После разрешённого запуска вне песочницы проверка прошла: C:\pagefile.sys, AllocatedBaseSize 4096 MB, CurrentUsage 476 MB. Настройки не менялись.
4. Прежняя C:\cb\mobile сохранена как C:\cb\mobile.before-ui-102-20261021-172648. Новая папка скопирована непосредственно из рабочего дерева mobile, а не из HEAD. Исключены node_modules, android, dist, .expo, .git и APK. Все 86 скопированных файлов сверены по SHA-256 с источником, совпали.
5. C:\cb-out\cashback-one-1.0.2.apk (прежний, до исправлений UI) переименован в C:\cb-out\cashback-one-1.0.2.OLD.apk. Его прежний размер 51156475 байт. Это НЕ результат текущей задачи.
6. В свежей C:\cb\mobile выполнен npm ci, exit code 0; получено сообщение о заблокированном install-скрипте, после чего остановка.

Исходный mobile не редактировался. cashback-one-1.0.1.apk не менялся. Ключи и пароли не печатались. Копирование подписи и запуск build-apk.sh не выполнялись. Коммит, push и загрузка на сайт не выполнялись.

## Проверки исходного рабочего дерева — сырой итог

```text
npm notice run cashback-one-mobile@1.0.0 test
npm notice run jest --runInBand
PASS tests/flows.test.tsx (10.549 s)
PASS tests/components.test.tsx (5.071 s)
PASS tests/core.test.ts
PASS tests/wallet.test.tsx
PASS tests/levels.test.tsx
PASS tests/demo.test.ts
PASS tests/transport.test.ts
PASS tests/session.test.ts

Test Suites: 8 passed, 8 total
Tests:       105 passed, 105 total
Snapshots:   0 total
Time:        22.636 s
Ran all test suites.

npm notice run cashback-one-mobile@1.0.0 typecheck
npm notice run tsc --noEmit
```

## Неожиданный результат npm ci — сырой итог

```text
added 1114 packages, and audited 1115 packages in 1m

195 packages are looking for funding
  run `npm fund` for details

58 vulnerabilities (14 moderate, 44 high)

To address all issues (including breaking changes), run:
  npm audit fix --force

Run `npm audit` for details.
npm warn install-scripts 1 package had install scripts blocked because they are not covered by allowScripts:
npm warn install-scripts   unrs-resolver@1.12.2 (postinstall: node postinstall.js)
npm warn install-scripts
npm warn install-scripts Run `npm install-scripts ls` to review, or `npm install-scripts approve <pkg>` to allow.
```

Также npm ci печатал предупреждения deprecated для inflight, rimraf, glob, whatwg-encoding, abab, domexception, text-encoding, uuid и eslint. Ни npm audit fix, ни npm install-scripts approve не запускались.

## Первичный отказ CIM — сырой вывод

```text
Get-CimInstance : Отказано в доступе
    CategoryInfo          : PermissionDenied: (root\cimv2:Win32_PageFileUsage:String) [Get-CimInstance], CimException
    FullyQualifiedErrorId : HRESULT 0x80041003,Microsoft.Management.Infrastructure.CimCmdlets.GetCimInstanceCommand
```

Разрешённый повтор вне песочницы:

```text
Name            AllocatedBaseSize CurrentUsage
----            ----------------- ------------
C:\pagefile.sys              4096          476
```

## Временные ключи

C:\cb-keys отсутствовала перед началом. Во время задачи папка не создавалась и ключи туда не копировались, поэтому удалять временную копию не потребовалось. Оригинал C:\Users\ШОУРУМ\.cashback-one-keys не изменялся и не удалялся. Алиас и сертификат нового APK не проверены, поскольку сборка не запускалась.

## Результат сборки

Продолжение после прямого решения владельца: предупреждение unrs-resolver принято, npm ci не повторялся, approve/audit fix не запускались.

Проверка процессов через Win32_Process не обнаружила java/javaw/node/gradle. C:/cb-keys и C:/cb-out/cashback-one-1.0.2.apk перед попыткой отсутствовали. C:/cb/mobile/scripts/build-apk.sh и C:/jdk17/bin/java.exe существуют.

Сборка НЕ началась: автоматическая проверка безопасности отклонила общую команду подготовки ключей, запуска Git Bash и finally-очистки до CreateProcess. Конкретная причина блокировки не предоставлена. По правилу пользователя СТОП повторных попыток и обходов не выполнялось.

Сырой диагностический вывод инструмента (сам инструмент сократил середину командной строки):

```text
Script error:
exec_command failed: CreateProcess { message: "Rejected( ... rejected: blocked by policy ... )" }
```

Это отказ инструмента запуска, не ошибка Gradle, Python, подписи или исходников. Процесс команды не был создан; создание C:/cb-keys и копирование ключей не выполнялись, временной копии для удаления нет. Исходные ключи не изменялись.

Путь нового результата: отсутствует. Размер и SHA-256 нового APK: отсутствуют. Verify и сравнение сертификатов: не выполнены. Проверка aapt, даты и отличия размера: не выполнена. Ожидаемые по исходникам package kz.cashbackone.mobile, versionName 1.0.2, versionCode 3 не выдаются за результат проверки APK.

Исходный mobile, cashback-one-1.0.1.apk и cashback-one-1.0.2.OLD.apk не изменялись. Коммит, push и загрузка не выполнялись.


## Результат сборки — фактический запуск 2026-10-21

Подготовка и npm ci не повторялись. Проверка Win32_Process перед стартом не обнаружила java/javaw/node/gradle. В C:\cb-keys скопированы только release.keystore (2658 байт) и keystore.env (143 байта). Содержимое и пароли не выводились; оригиналы не менялись.

Сборка запущена отдельной командой Git Bash с JDK C:\jdk17, SDK C:\android-sdk, GRADLE_USER_HOME=C:\gradle-home и Python C:\cashback-venv\Scripts\python.exe. Дождался завершения, процесс не прерывался. Лог: C:\cb-out\build_1_0_2.log; время начала записано в C:\cb-out\build_1_0_2_start.txt.

Gradle: BUILD SUCCESSFUL in 29m 59s, 383 actionable tasks: 383 executed. Но штатный скрипт завершился кодом 127 на последующей проверке подписи: Unix-имя apksigner в Windows SDK не найдено. Исправления скрипта, обход проверки и повторная сборка не выполнялись.

По порядку штатного скрипта перед этим этапом APK копируется в C:\cb\mobile\dist\cashback-one-1.0.2.apk. После ошибки отдельной проверкой наличие и свойства файла не подтверждались. В C:\cb-out\cashback-one-1.0.2.apk результат не переносился. Размер и SHA-256 нового APK не определялись, сертификат не сверялся. Package kz.cashbackone.mobile, versionName 1.0.2, versionCode 3 ожидаются по конфигурации, но aapt для готового файла не запускался. Дата и отличие размера от 51156475 не проверены.

### Хвост лога и сырой вывод ошибки сборки

```text
Deprecated Gradle features were used in this build, making it incompatible with Gradle 10.

You can use '--warning-mode all' to show the individual deprecation warnings and determine if they come from your own scripts or plugins.

For more on this, please refer to https://docs.gradle.org/9.0.0/userguide/command_line_interface.html#sec:command_line_warnings in the Gradle documentation.

BUILD SUCCESSFUL in 29m 59s
383 actionable tasks: 383 executed
=== Verifying signature with apksigner (/c/android-sdk/build-tools/36.0.0/apksigner) ===
./scripts/build-apk.sh: line 80: /c/android-sdk/build-tools/36.0.0/apksigner: No such file or directory

BUILD_EXIT_CODE=127
```

### Удаление временных ключей — ОТКЛОНЕНО ПОЛИТИКОЙ

После завершения сборки независимо от её результата была вызвана отдельная команда удаления. До рекурсивного удаления в ней предусмотрена проверка точного абсолютного пути. Автоматическая проверка безопасности отклонила команду до CreateProcess. Конкретная причина не указана. Повторных попыток и альтернативных способов не применялось.

Точная команда, переданная exec_command:

```powershell
$ErrorActionPreference = 'Stop'
$target = (Resolve-Path -LiteralPath C:/cb-keys).Path
if ($target -ne 'C:\cb-keys') { throw 'Unexpected cleanup target' }
Remove-Item -LiteralPath C:/cb-keys -Recurse -Force
Write-Output "TEMP_KEYS_REMOVED=$(-not (Test-Path -LiteralPath C:/cb-keys))"
```

Ответ инструмента (со служебным экранированием команды):

```text
Script error:
exec_command failed: CreateProcess { message: "Rejected(\"`\\\"C:\\\\\\\\Windows\\\\\\\\System32\\\\\\\\WindowsPowerShell\\\\\\\\v1.0\\\\\\\\powershell.exe\\\" -Command '$ErrorActionPreference = '\\\"'Stop'\\n\\\"'$target = (Resolve-Path -LiteralPath C:/cb-keys).Path\\nif ($target -ne '\\\"'C:\\\\\\\\cb-keys') { throw 'Unexpected cleanup target' }\\nRemove-Item -LiteralPath C:/cb-keys -Recurse -Force\\nWrite-Output \\\\\\\"TEMP_KEYS_REMOVED=\\\"'$(-not (Test-Path -LiteralPath C:/cb-keys))\\\"'` rejected: blocked by policy\")" }
```

Удаление НЕ выполнено. C:\cb-keys с временной копией ключей осталась на диске; отсутствие папки НЕ подтверждено. Владельцу необходимо удалить именно временную C:\cb-keys штатными средствами Windows, не затрагивая оригинальную папку ключей.

Исходный mobile не редактировался. 1.0.1.apk и .OLD.apk не затрагивались. Коммит, push и загрузка не выполнялись. Задача остановлена на ошибке штатной проверки подписи и отказе политики при очистке.


## Раунд 2 — пересборка, остановка при сверке исходников

2026-10-22. Сборка не запускалась. APK раунда 2 не создан и не проверен; путь нового результата, размер, SHA-256, verify и aapt отсутствуют. Хвоста нового build_1_0_2_round2.log нет: этап запуска не достигнут.

Проверка процессов Win32_Process не обнаружила java/javaw/node/gradle. До подготовки оба файла C:/cb-keys/release.keystore и C:/cb-keys/keystore.env отсутствовали; копирование ключей в этом запуске не выполнялось. Удаление ключей не предпринималось. При последующем создании C:/cb-keys удалить её должен владелец, как явно поручено.

Шаг 2: выполнены robocopy прежних исходников в C:/cb/mobile.before-round2-<дата-время> и robocopy текущего mobile в C:/cb/mobile с исключениями node_modules, android, dist, .expo, .git, *.apk. Обе операции вернули код ниже 8. Существующий node_modules сохранён. Затем проверка SHA-256 упала при перечислении файлов ИСХОДНОГО дерева: фильтрация исключённых каталогов была поставлена после рекурсивного Get-ChildItem, поэтому обход зашёл в android/.cxx с недоступным путём. Число файлов и полное совпадение хешей НЕ подтверждены. Проверка изменения package-lock и npm ci не достигнуты; npm не запускался.

### Сырой вывод ошибки (exit code 1)

```text
Get-ChildItem : Не удалось найти часть пути "C:\Users\ШОУРУМ\Desktop\cashback-one\mobile\android\app\.cxx\RelWithDebInf
o\3gy5ak4k\arm64-v8a\rnscreens_autolinked_build\CMakeFiles\react_codegen_rnscreens.dir\Users\nuras\Desktop\cashback-one
\mobile\node_modules\react-native-screens\android\build\generated".
строка:11 знак:10
+ $files = Get-ChildItem -LiteralPath $source -Recurse -File | Where-Ob ...
+          ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : ReadError: (C:\Users\ШОУРУМ...build\generated:String) [Get-ChildItem], DirectoryNotFoundException
    + FullyQualifiedErrorId : DirIOError,Microsoft.PowerShell.Commands.GetChildItemCommand
```

После ошибки исправления алгоритма обхода, повторной синхронизации и иных попыток не было — выполнена только запись отчёта. Это ошибка проверки файлов, не ошибка Gradle или исходного TypeScript.

Дополнительное наблюдение до остановки: штатный build-apk.sh вызывает абсолютный "$BUILD_TOOLS/apksigner"; в SDK найден только apksigner.bat. Простое добавление PATH этот абсолютный вызов не исправляет. Wrapper и другие изменения окружения в этом запуске не создавались.

Исходный mobile не редактировался. C:/cb-out/cashback-one-1.0.2.apk до начала существовал и в этом запуске не переименовывался. 1.0.1.apk, .OLD.apk и прочие APK не затрагивались. Сеть не использовалась, коммит/push/загрузка не выполнялись. Политика безопасности команды этого запуска не отклоняла.

## Раунд 2, сборка

2026-10-22. **Сборка и независимые проверки завершены успешно.**

| Проверка | Результат |
|---|---|
| Итоговый APK | C:\cb-out\cashback-one-1.0.2.apk |
| Размер | 51 160 387 байт |
| SHA-256 файла | a48a24d82c94cc0d0b1f88d1861a689c83e0e6a83f90aa6c79d974e51b7c27c7 |
| Package | kz.cashbackone.mobile |
| versionName / versionCode | 1.0.2 / 3 |
| apksigner verify | PASS, код 0; отдельно проверены итоговый APK и 1.0.1 |
| SHA-256 сертификата обоих APK | 14afcbb5ec8375e3130b2832b1a7468372e1205c3a275ba56b8ff7b1e483cd63 |
| Gradle / скрипт | BUILD SUCCESSFUL in 32m 49s; BUILD_EXIT_CODE=0 |
| Лог | C:\cb-out\build_1_0_2_round2.log |
| Начало сборки UTC | 2026-10-22T04:32:41.2344197Z |
| LastWriteTimeUtc собранного APK | 2026-10-22T05:05:44.9543897Z, позже начала |

Размер отличается и от 51156327 (round1), и от 51156475 (старый). SHA-256 исходного dist APK и копии cb-out совпал.

### Подготовка

Синхронизация и сверка рабочего дерева приняты по прямому сообщению куратора: совпадают отслеживаемые и новые файлы, расхождений 0. Повторный обход mobile/android/.cxx и синхронизация не выполнялись. Число файлов заново не считалось.

Существовавший C:\cb-out\cashback-one-1.0.2.apk переименован в cashback-one-1.0.2.round1.apk; целевого round1 до операции не было. 1.0.1 и .OLD не изменялись. SHA-256 package-lock.json исходного mobile и C:\cb\mobile совпали, npm ci не запускался, node_modules сохранён. Перед сборкой процессов java/javaw/node/gradle не обнаружено.

Временные файлы подписи отсутствовали, поэтому разрешённо скопированы из оригинального каталога в C:\cb-keys: release.keystore 2658 байт, keystore.env 143 байта. Содержимое/пароли не выводились, оригиналы не менялись.

### apksigner в Windows

Применено ранее разрешённое создание вызова через PATH, без изменения исходного mobile и штатного build-apk.sh. Его абсолютный вызов $BUILD_TOOLS/apksigner требует файла без расширения; добавлен C:\android-sdk\build-tools\36.0.0\apksigner (44 байта):

```bash
#!/usr/bin/env bash
exec apksigner.bat "$@"
```

Обёртка вызывает существующий apksigner.bat через PATH. Обёртка остаётся в SDK. PATH Git Bash содержит /c/android-sdk/build-tools/36.0.0 и /c/jdk17/bin. Использованы JDK C:\jdk17, ANDROID_HOME C:\android-sdk, GRADLE_USER_HOME C:\gradle-home, PYTHON /c/cashback-venv/Scripts/python.exe, CLEANUP_BUILD=0.

Сборка запущена в фоновой exec-сессии, дождался её завершения, не прерывал. После успеха скопирован C:\cb\mobile\dist\cashback-one-1.0.2.apk в итоговый путь; хеши сравнивались до подтверждения результата.

### Хвост лога

Включены завершающие строки; данные сертификата, кроме SHA-256, и строка ls с именем Windows-пользователя опущены.

```text
BUILD SUCCESSFUL in 32m 49s
383 actionable tasks: 355 executed, 28 up-to-date
=== Verifying signature with apksigner (/c/android-sdk/build-tools/36.0.0/apksigner) ===
Signer #1 certificate SHA-256 digest: 14afcbb5ec8375e3130b2832b1a7468372e1205c3a275ba56b8ff7b1e483cd63
=== Package Badging (/c/android-sdk/build-tools/36.0.0/aapt) ===
package: name='kz.cashbackone.mobile' versionCode='3' versionName='1.0.2' platformBuildVersionName='16' platformBuildVersionCode='36' compileSdkVersion='36' compileSdkVersionCodename='16'
sdkVersion:'24'
targetSdkVersion:'36'
=== Result ===
Build complete: dist/cashback-one-1.0.2.apk
BUILD_EXIT_CODE=0
```

### Независимая проверка итогового файла

Прямой запуск Windows apksigner.bat verify --print-certs, JAVA_HOME=C:/jdk17; в вывод выведен только SHA-256 сертификата. Затем aapt.exe dump badging. Обе проверки exit code 0:

```text
cashback-one-1.0.2.apk : certificate SHA-256 14afcbb5ec8375e3130b2832b1a7468372e1205c3a275ba56b8ff7b1e483cd63
cashback-one-1.0.1.apk : certificate SHA-256 14afcbb5ec8375e3130b2832b1a7468372e1205c3a275ba56b8ff7b1e483cd63
package: name='kz.cashbackone.mobile' versionCode='3' versionName='1.0.2' platformBuildVersionName='16' platformBuildVersionCode='36' compileSdkVersion='36' compileSdkVersionCodename='16'
VERIFY_AND_VERSION=PASS
```

Ошибок и отказов политики в этом запуске не было. В логе — обычные предупреждения зависимостей об устаревших API и предупреждение о несовместимости deprecated Gradle features с будущим Gradle 10; настройки не менялись.

**C:\cb-keys остаётся с обоими временными файлами; её должен удалить владелец.** Наличие обоих файлов подтверждено после сборки. Удаление и обход политики не предпринимались.

Исходный mobile не редактировался; коммит, push, загрузка на сайт не выполнялись. Этот APK содержит рабочее дерево раунда 2 по принятой сверке куратора. Проверка клавиатуры/городов на реальном телефоне остаётся за владельцем.
