# APP UI FIXES 1.0.2 — остановка до внесения правок

Проверены CLAUDE.md, docs/HANDOFF_2026-10-21.md, git show 1a82e16 и 3e6d92a, текущие mobile/app и mobile/src/features. Исходное рабочее дерево чистое.

## Аудит Gemini

Номера строк относятся к текущему исходному состоянию. Исправления не внесены: сработало обязательное правило остановки.

| Пункт | Что было у Gemini | Что неверно или сомнительно | Решение / что стало | Файлы:строки |
|---|---|---|---|---|
| 1. Повторный код | Перенёс повторный запрос после «Изменить номер», заменил кнопку на подчёркнутый Pressable с alignSelf center, таймер на серый Text | Нарушений порядка и ширины по коду не найдено. Обработчик вызывает requestCode(sentPhone), сохраняя номер | Оставить; визуальная проверка на телефоне не выполнена | mobile/app/login.tsx:63, :65, :70, :75, :96 |
| 2. Клавиатура шторок | Добавил Keyboard listeners, BackHandler и onRequestClose, ScrollView handled | На Android KAV behavior undefined. Нативный Modal сам задаёт ADJUST_RESIZE (проверено в установленном RN), поэтому отсутствие behavior само по себе не доказывает поломку. Но KAV ограничен размером шторки вместо всего окна, ограничения высоты/прокрутки требуют доработки и проверки. BackHandler внутри открытого Modal не обеспечивает обработку: нужен onRequestClose. Видимость хранится в state, обработчик может получить старое состояние до render. useSafeInsets скрывает отсутствие provider нулевыми inset | Планировалось переделать геометрию KAV на весь доступный экран и хранить видимость клавиатуры в ref; убрать лишний BackHandler. Не применено. Значения value/amount уже живут в состоянии компонента, keyboardDidHide их не сбрасывает | mobile/src/features/profile.tsx:9, :55, :57, :63, :76, :89, :92, :97, :129; mobile/src/features/LevelsSheet.tsx:10, :31, :36, :42, :55, :62, :65, :104; mobile/node_modules/react-native/ReactAndroid/src/main/java/com/facebook/react/views/modal/ReactModalHostView.kt:329 |
| 3. Системная навигация | Добавил inset только двум шторкам. app.json получил resize | Пункт выполнен частично. У экранов edges top, фиксированные отступы не учитывают динамический inset. TabBar использует max(insets.bottom,12), без запаса 16. Панель абсолютная, её высоту следует учитывать в контенте вкладок | Планировалось добавить bottom edge экранам вне вкладок; вкладкам — inset+16 сверх существующего отступа под TabBar; панели — inset+16. Не применено. Найдены только две Modal с TextInput: FieldSheet и LevelsSheet | mobile/src/components/TabBar.tsx:23, :51; mobile/app/(app)/(tabs)/profile.tsx:74, :78; mobile/app/(app)/(tabs)/index.tsx:60; mobile/app/(app)/bind.tsx:32; mobile/app/(app)/status.tsx:24; mobile/app/(app)/history.tsx:20; mobile/app/(app)/cards.tsx:30; mobile/app/(app)/promotion/[id].tsx:16; mobile/app/(app)/(tabs)/qr.tsx:48; mobile/app/(app)/(tabs)/promotions.tsx:17; mobile/app/(app)/(tabs)/notifications.tsx:16 |
| 4. Home | Явный stroke=color на внешнем Path, fill зависит от filled, белая внутренняя линия активной иконки | По коду контур присутствует, получает тот же subtle, что остальные неактивные иконки. В paths осталась дублирующая home-геометрия, но на отображение не влияет | Оставить рабочую реализацию; изображение на телефоне не проверено | mobile/src/components/icons.tsx:35; mobile/src/components/TabBar.tsx:36, :41 |

Файлы к состоянию до 1a82e16 не возвращались. Версия 1.0.2 / versionCode 3 в app.json сохранена. upload_apk.py не изменён и не запускался. Коммит 3e6d92a меняет только app.json, согласно git show --stat.

## Проверки ДО изменений

Команды выполнялись на текущем Windows-компьютере, из mobile. Обе завершились с exit code 0.

```text
npm test
npm notice run cashback-one-mobile@1.0.0 test
npm notice run jest --runInBand
PASS tests/flows.test.tsx (12.736 s)
PASS tests/components.test.tsx (6.597 s)
PASS tests/core.test.ts
PASS tests/wallet.test.tsx
PASS tests/levels.test.tsx
PASS tests/demo.test.ts
PASS tests/session.test.ts
PASS tests/transport.test.ts

Test Suites: 8 passed, 8 total
Tests:       105 passed, 105 total
Snapshots:   0 total
Time:        27.356 s
Ran all test suites.

npm run typecheck
npm notice run cashback-one-mobile@1.0.0 typecheck
npm notice run tsc --noEmit
```

## Причина остановки — сырой вывод

Попытка применить изменения через PowerShell here-string, переданный в `python -`, завершилась до выполнения скрипта. Код выхода 1:

```text
Python 
```

Повторного запуска, выбора другого Python, исправления окружения и дальнейших мутаций кода не выполнялось. После остановки разрешённой документацией сохранён этот отчёт. git status --short и git diff --stat после ошибки пустые: исходники не изменены.

## git diff --stat

```text
(пусто)
```

Отчёт новый и untracked, поэтому обычный git diff --stat его не включает.

## APK и границы проверки

APK не собирался: остановка на предыдущем этапе. Окружение сборки и подпись не проверялись. Путь/размер/SHA-256 нового APK отсутствуют. cashback-one-1.0.1.apk не затрагивался.

Без настоящего телефона не подтверждены: подъём шторок при клавиатуре, доступность поля и «Сохранить», первый и второй системные «Назад», жест скрытия клавиатуры с сохранением ввода, отсутствие перекрытия контента системными кнопками и жестовой полосой, внешний вид home в обоих состояниях и ссылки повторного кода.

Backend, agent, admin, production, VPS, публикация, коммит и push не выполнялись. Задача НЕ завершена: аудит и baseline готовы, исправления и APK отсутствуют.

## Выполнение

Продолжение по прямому поручению владельца. Python не запускался; изменения внесены заменами строк PowerShell и apply_patch. Версия 1.0.2/versionCode 3, login.tsx и upload_apk.py не изменены. Зависимостей не добавлено. Ни один файл не возвращался к старому коммиту.

### Изменения по пунктам

| Пункт | Что изменено | Файлы:строки |
|---|---|---|
| 1 | Оставлено без изменений: основной вход, изменение номера, затем компактная ссылка или серый таймер. Повторный запрос использует sentPhone | mobile/app/login.tsx:63 |
| 2 | KAV занимает всё окно Modal (flex:1), шторка прижата к низу. pointerEvents box-none пропускает касание фона за пределами шторки. maxHeight 88% и flexShrink ограничивают шторку доступным окном, ScrollView handled оставлен. Видимость клавиатуры — ref, listeners обновляют его без ожидания render. onRequestClose сначала dismiss и return, затем закрытие. Дублирующий BackHandler удалён. keyboardDidHide не сбрасывает value/amount | mobile/src/features/profile.tsx:55, :58, :64, :80, :85, :117; mobile/src/features/LevelsSheet.tsx:31, :37, :43, :53, :60, :91 |
| 3 | Пять экранов вне вкладок получили SafeAreaView bottom. Пять вкладок используют TAB_BAR_HEIGHT + insets.bottom + 16. TAB_BAR_HEIGHT=82 — базовая высота панели без системного inset (10 сверху + 56 строка + 16 снизу). Панель получает insets.bottom+16. У шторок сохранён запас не менее inset+16 (у FieldSheet inset+20) | mobile/app/(app)/bind.tsx:32; status.tsx:24; history.tsx:20; cards.tsx:30; promotion/[id].tsx:16; mobile/app/(app)/(tabs)/profile.tsx:80; index.tsx:25; qr.tsx:52; promotions.tsx:21; notifications.tsx:20; mobile/src/components/TabBar.tsx:10, :26; mobile/src/features/profile.tsx:81; mobile/src/features/LevelsSheet.tsx:54 |
| 4 | Убран отдельный return Svg для home и дубль home в paths. Все иконки используют один Svg с одинаковыми viewBox, stroke, strokeWidth, linecap/linejoin. Контур home наследует stroke так же, как соседние Path; активная форма получает fill=color и внутреннюю линию onPrimary | mobile/src/components/icons.tsx:9, :33; mobile/src/components/TabBar.tsx:39, :44 |

Android: behavior остаётся undefined намеренно — размер меняет нативное окно Modal; установленный React Native задаёт SOFT_INPUT_ADJUST_RESIZE в mobile/node_modules/react-native/ReactAndroid/src/main/java/com/facebook/react/views/modal/ReactModalHostView.kt:329. В app.json уже softwareKeyboardLayoutMode=resize. iOS использует padding. Это проверка кода, не доказательство поведения реальной клавиатуры.

### Причина по пункту 4

Причина не найдена, внёс защитное исправление: единый Svg и одна геометрия home, общее наследование stroke внешним контуром. Цвет неактивной home приходит из того же t.colors.subtle, что у остальных вкладок; заливка панели — surface. В TabBar нет отдельной прозрачности или анимации home, ключ — route, strokeWidth=1.8 общий. Геометрия находится внутри 24x24 с запасом от границы. Подпись проходит общий Text. Старый отдельный return и дублирующая геометрия были единственными найденными особенностями реализации, но их причинная связь с фото не доказана. Фото и реальный телефон в этой сессии недоступны; исчезновение на устройстве не объявляется подтверждённо устранённым.

### Проверки после изменений

На текущем Windows-компьютере из mobile. Обе команды завершились exit code 0:

```text
npm test
npm notice run cashback-one-mobile@1.0.0 test
npm notice run jest --runInBand
PASS tests/flows.test.tsx (13.864 s)
PASS tests/components.test.tsx
PASS tests/core.test.ts
PASS tests/wallet.test.tsx
PASS tests/levels.test.tsx
PASS tests/demo.test.ts
PASS tests/transport.test.ts
PASS tests/session.test.ts

Test Suites: 8 passed, 8 total
Tests:       105 passed, 105 total
Snapshots:   0 total
Time:        25.456 s
Ran all test suites.

npm run typecheck
npm notice run cashback-one-mobile@1.0.0 typecheck
npm notice run tsc --noEmit
```

git diff --check: ошибок пробелов нет. Git напечатал стандартные предупреждения LF will be replaced by CRLF; окончания строк и git config специально не менялись.

### git diff --stat

```text
 mobile/app/(app)/(tabs)/index.tsx         |  6 ++++--
 mobile/app/(app)/(tabs)/notifications.tsx |  6 ++++--
 mobile/app/(app)/(tabs)/profile.tsx       |  6 ++++--
 mobile/app/(app)/(tabs)/promotions.tsx    |  6 ++++--
 mobile/app/(app)/(tabs)/qr.tsx            |  6 ++++--
 mobile/app/(app)/bind.tsx                 |  2 +-
 mobile/app/(app)/cards.tsx                |  2 +-
 mobile/app/(app)/history.tsx              |  2 +-
 mobile/app/(app)/promotion/[id].tsx       |  2 +-
 mobile/app/(app)/status.tsx               |  2 +-
 mobile/src/components/TabBar.tsx          |  5 ++++-
 mobile/src/components/icons.tsx           | 14 +++++---------
 mobile/src/features/LevelsSheet.tsx       | 30 +++++++++---------------------
 mobile/src/features/profile.tsx           | 30 +++++++++---------------------
 14 files changed, 52 insertions(+), 67 deletions(-)
```

Отчёт untracked, в обычный git diff --stat не входит.

### APK — остановка на проверке готовности

Новый APK не собран, путь/размер/SHA-256 отсутствуют. Найденный ранее C:/cb-out/cashback-one-1.0.2.apk не относится к этим изменениям: не заменялся и не выдаётся за результат этой задачи. cashback-one-1.0.1.apk не затронут.

Без чтения содержимого секретов проверено наличие файлов. Сырой вывод:

```text
JAVA_HOME=NOT_SET
ANDROID_HOME=NOT_SET
ANDROID_SDK_ROOT=NOT_SET
GRADLE_USER_HOME=NOT_SET
C:/jdk17/bin/java.exe : True
C:/android-sdk/platforms/android-36/android.jar : True
C:/android-sdk/build-tools/36.0.0/apksigner.bat : True
C:/gradle-home/init.d/disable-lint.gradle : True
C:/cb-keys/release.keystore : False
C:/cb-keys/keystore.env : False
```

Это не утверждение, что исходные ключи владельца потеряны: временный каталог подписи из описанной Windows-процедуры не подготовлен. Алиас cashbackone не проверялся. Кроме того, mobile/scripts/build-apk.sh вызывает Python для патча Gradle, а текущая инструкция запрещает запуск Python. Скрипт не запускался; обходного сценария сборки и изменения окружения не выполнялось. Последняя команда диагностического поиска завершилась exit code 1: заключительный rg не нашёл совпадений, сообщения ошибки не было; приведён полезный сырой вывод наличия файлов. После этого — только запись отчёта.

### Проверка владельцем на телефоне

- Повторный код: порядок кнопок, компактная ссылка, серый ненажимаемый таймер, запрос на тот же номер.
- Обе шторки: поле и кнопка сохранения доступны при клавиатуре, длинный контент прокручивается.
- Первый системный «Назад» скрывает клавиатуру, оставляет шторку и введённое значение; второй закрывает шторку. Жест скрытия клавиатуры не теряет ввод.
- Нижние элементы всех пяти вкладок и пяти отдельных экранов, а также шторок не перекрыты трёхкнопочной навигацией и жестовой полосой Android.
- Home видна контуром при выборе любой другой вкладки и залита на главной; проверить несколько переключений и холодный запуск.

Код оставлен в рабочем дереве. Backend, agent, admin, VPS, production, публикация, коммит и push не затрагивались. Реальная проверка телефона и сборка нового APK остаются незавершёнными.

## Раунд 2

Дата: 2026-10-22. Прежнее предположение о надёжном системном resize Android Modal отменено: владелец подтвердил скрытую Gboard шторку. Версия остаётся 1.0.2 / versionCode 3. Python, новые зависимости, APK-сборка, публикация, коммит и push не использовались.

### Изменения

| Область | Реализация | Файлы:строки |
|---|---|---|
| Общий подъём | overlap(bottom, keyboardTop, margin), измерение measureInWindow после keyboardDidShow/keyboardDidHide (iOS will), screenY/height из события, повторный расчёт при onLayout, анимация paddingBottom 160 мс | mobile/src/components/useKeyboardLift.ts:4, :11, :20, :36 |
| FieldSheet | Animated.View вместо KAV, ограничение высоты по доступному окну, прокручиваемое поле/варианты, «Готово» вне ScrollView. Нижний safe-area запас сохранён. onRequestClose использует ref хука, сначала скрывает клавиатуру. Backdrop закрывает непосредственно шторку | mobile/src/features/profile.tsx:57, :60, :75, :78, :83, :95 |
| LevelsSheet | Тот же хук и maxHeight; поле калькулятора прокручивается в видимую область при фокусе и изменении высоты ScrollView. Ввод amount не сбрасывается при скрытии клавиатуры | mobile/src/features/LevelsSheet.tsx:32, :40, :48, :51, :60, :72 |
| Поля вне Modal | Найдены login (Input), bind (BindForm/Input), first_name/last_name профиля. KAV заменён измеряемым Animated.View с тем же хуком; ScrollView handled сохранён. ui.tsx содержит общий TextInput, отдельной Modal там нет | mobile/app/login.tsx:18, :49; mobile/app/(app)/bind.tsx:17, :36; mobile/app/(app)/(tabs)/profile.tsx:26, :82 |
| Города | 23 фиксированных русских значения и отдельные казахские подписи через i18n. City использует options FieldSheet без TextInput. Выбор, как у пола, обновляет форму и закрывает шторку; отправка на сервер — общей кнопкой «Сохранить». Старый город вне списка добавляется первым выбранным вариантом и показывается как есть. Известные города в строке профиля локализуются | mobile/src/features/cities.ts:3; mobile/src/i18n/ru.ts:2; mobile/src/i18n/kz.ts:4; mobile/app/(app)/(tabs)/profile.tsx:71, :94 |
| Выбранный вариант | ScrollView прокручивается к y выбранного radio при layout/contentSizeChange, длинный список ограничен высотой шторки | mobile/src/features/profile.tsx:83 |
| Тесты | Чистая логика: resized bottom<=keyboardTop даёт 0; unresized даёт перекрытие+запас. Интеграция профиля: казахская подпись отправляет русское значение PATCH city; старый город остаётся выбранным и не очищается при сохранении другого поля | mobile/tests/keyboardLift.test.ts:3; mobile/tests/flows.test.tsx:60, :75 |

### Почему подъём не зависит от resize

Измеряется внешний НЕСДВИНУТЫЙ viewport, к низу которого прижата шторка. Его нижняя граница — исходная нижняя граница шторки. Padding анимируется внутри viewport и не меняет его внешние координаты: повторное измерение не накапливает сдвиг и не вызывает качание обратно-вперёд.

Если viewport уже уменьшился системой и его низ не ниже screenY клавиатуры, overlap=0. Если Modal остался полноэкранным, добавляется только фактическое перекрытие плюс 10 пикселей. onLayout пересчитывает результат после изменения размеров окна. Высота шторки ограничивается измеренной высотой viewport минус этот подъём и 24 пикселя верхнего запаса. При полном окне это эквивалентно доступной области над клавиатурой; при resize высота клавиатуры второй раз не вычитается.

Когда клавиатура скрыта, padding возвращается к 0, безопасный нижний отступ шторки inset.bottom+16 (или больше) остаётся. statusBarTranslucent сохранён. Дополнительного KeyboardAvoidingView рядом с хуком нет, чтобы не складывать две компенсации.

keyboardVisible хранится в ref хука. Скрытие клавиатуры не меняет value/amount. Backdrop теперь вызывает onClose напрямую, как явно потребовал владелец; это отличается от прежнего обработчика, который при клавиатуре только вызывал dismiss.

### Проверки

До правок, из mobile на текущем Windows-компьютере:

```text
Test Suites: 8 passed, 8 total
Tests:       105 passed, 105 total
Snapshots:   0 total
Time:        25.621 s
Ran all test suites.
```

npm run typecheck до правок: exit code 0.

После правок:

```text
npm notice run cashback-one-mobile@1.0.0 test
npm notice run jest --runInBand
PASS tests/keyboardLift.test.ts
PASS tests/flows.test.tsx (10.342 s)
PASS tests/components.test.tsx
PASS tests/core.test.ts
PASS tests/wallet.test.tsx
PASS tests/levels.test.tsx
PASS tests/demo.test.ts
PASS tests/transport.test.ts
PASS tests/session.test.ts

Test Suites: 9 passed, 9 total
Tests:       109 passed, 109 total
Snapshots:   0 total
Time:        25.842 s
Ran all test suites.

npm notice run cashback-one-mobile@1.0.0 typecheck
npm notice run tsc --noEmit
```

Обе итоговые команды exit code 0. diff --check чистый. Стандартные предупреждения Git о будущей замене LF на CRLF не исправлялись изменением настроек. Красных тестов и остановок в раунде 2 не было.

### git diff --stat -- mobile

Суммарное дерево относительно HEAD, включая незакоммиченный раунд 1:

```text
 mobile/app/(app)/(tabs)/index.tsx         |  6 ++--
 mobile/app/(app)/(tabs)/notifications.tsx |  6 ++--
 mobile/app/(app)/(tabs)/profile.tsx       | 23 ++++++++------
 mobile/app/(app)/(tabs)/promotions.tsx    |  6 ++--
 mobile/app/(app)/(tabs)/qr.tsx            |  6 ++--
 mobile/app/(app)/bind.tsx                 | 10 +++---
 mobile/app/(app)/cards.tsx                |  2 +-
 mobile/app/(app)/history.tsx              |  2 +-
 mobile/app/(app)/promotion/[id].tsx       |  2 +-
 mobile/app/(app)/status.tsx               |  2 +-
 mobile/app/login.tsx                      |  8 +++--
 mobile/src/components/TabBar.tsx          |  5 ++-
 mobile/src/components/icons.tsx           | 14 +++-----
 mobile/src/features/LevelsSheet.tsx       | 46 ++++++++++-----------------
 mobile/src/features/profile.tsx           | 53 ++++++++++++-------------------
 mobile/src/i18n/kz.ts                     | 23 ++++++++++++++
 mobile/src/i18n/ru.ts                     | 23 ++++++++++++++
 mobile/tests/flows.test.tsx               | 32 +++++++++++++++++++
 18 files changed, 168 insertions(+), 101 deletions(-)
```

Обычный diff не включает новые untracked файлы: mobile/src/components/useKeyboardLift.ts, mobile/src/features/cities.ts, mobile/tests/keyboardLift.test.ts и отчёты. В общем git diff --stat также есть scripts/upload_apk.py (4 строки) — это чужое/ранее внесённое изменение, в этом раунде файл не редактировался и не запускался.

### Проверка владельцем на телефоне

- Gboard и жестовая полоса: шторки E-mail и остальных текстовых полей полностью над клавиатурой, поле и «Готово» доступны. Имя/Фамилия в текущем коде — поля экрана профиля, не отдельные шторки; проверить их фокус и доступ к «Сохранить».
- Пол и Город: длинный список прокручивается, выбранный вариант виден; открытие после ввода текста с ещё открытой клавиатурой не прячет шторку.
- Уровни: калькулятор виден при фокусе, после изменения высоты Gboard и после повторного открытия.
- Первый системный «Назад» и жест скрытия клавиатуры сохраняют шторку и ввод; второй «Назад» закрывает. Тап по затемнению закрывает шторку сразу.
- Город: русский и казахский интерфейсы, «Другой город»/«Басқа қала», старое свободное значение, сохранение и повторный вход в профиль.
- Вход (телефон и OTP) и привязка карты: поле и кнопка доступны над клавиатурой, прокрутка работает.
- Не появляется двойной подъём на устройстве/режиме, где система уже уменьшает окно; при скрытии клавиатуры дополнительный padding исчезает без потери текста.

Jest проверяет логику и события UI в mock-среде, а не реальные координаты Gboard/Modal. Отсутствие мигания, точные координаты и системная кнопка «Назад» требуют проверки на устройстве. Backend, agent, admin, VPS не затрагивались; APK не собирался и не загружался.
