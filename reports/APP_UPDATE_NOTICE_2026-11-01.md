# Отчёт по задаче: окно «обновите приложение» — 2026-11-01

Среда: macOS Darwin arm64, Node/Jest/TypeScript/ESLint в каталоге `mobile/`.
Ограничения соблюдены: без сборки APK, без смены версии (`app.json` и `build.gradle` не изменялись), без деплоя, без commit/push. Изменения затронули исключительно каталог `mobile/` (`mobile/app/_layout.tsx`, `mobile/src/`, `mobile/tests/`). Каталоги `backend/`, `admin/`, `agent/`, лендинг, `mobile/android/`, `package.json` и lock-файлы не затрагивались.

---

## 1. Базовые проверки до правок (baseline)

- Нагрузка системы: `uptime` → load averages: `4.88 3.23 3.54` (< 12).
- `npx jest`: **16 test suites passed, 190 tests passed, 0 failed** (лог: `/tmp/app-update-notice-logs/baseline-jest.log`).
- `npx tsc --noEmit`: код 0, вывод чистый (лог: `/tmp/app-update-notice-logs/baseline-tsc.log`).
- `npx eslint .`: 0 ошибок, 1 предупреждение (в `src/components/useKeyboardLift.ts`).

---

## 2. Изменения по файлам

### 2.1. Локализация: `mobile/src/i18n/ru.ts` и `mobile/src/i18n/kz.ts`
Добавлены ключи для диалога обновления на русском и казахском языках:
- `updateTitle`: «Доступна новая версия» / «Жаңа нұсқа қолжетімді»
- `updateBody`: «Для более стабильной работы приложения, пожалуйста, обновите его» / «Қолданба тұрақты жұмыс істеуі үшін оны жаңартыңыз»
- `updateRequiredBody`: «Эта версия приложения больше не поддерживается. Пожалуйста, обновите его» / «Қолданбаның бұл нұсқасына енді қолдау көрсетілмейді. Оны жаңартыңыз»
- `updateNow`: «Обновить» / «Жаңарту»
- `updateLater`: «Позже» / «Кейінірек»

### 2.2. Модуль логики и парсинга: `mobile/src/features/appUpdate.ts`
Создан новый модуль со строгой типизацией и чистыми функциями:
1. `VERSION_INFO_URL = 'https://cashback-qr.poscenter.kz/app/version.json'`.
2. Интерфейс `VersionInfo`:
   - `latest_version: string`
   - `latest_version_code: number`
   - `min_version_code: number`
   - `download_url: string`
3. Чистая функция `parseVersionInfo(value: unknown): VersionInfo | null`:
   - Отклоняет не-объекты, `null`, массивы, HTML-строки.
   - Проверяет `latest_version` по регулярному выражению `^\d+\.\d+\.\d+$`.
   - Проверяет `latest_version_code` и `min_version_code` на строго положительные целые числа (`Number.isInteger(x) && x > 0`).
   - Отклоняет структуру, если `min_version_code > latest_version_code`.
   - Защита URL: строго проверяет `download_url` по `^https:\/\/cashback-qr\.poscenter\.kz\/app\/cashback-one-\d+\.\d+\.\d+\.apk$`. Защищает от фишинга, подмены хоста, `@evil.example`, лишних подпутей или иных расширений файлов.
4. Чистая функция `updateDecision(info: VersionInfo | null, currentCode: number | null | undefined): 'none' | 'optional' | 'required'`:
   - Возвращает `'none'`, если `info` или `currentCode` не валидны/пустые/неположительные.
   - Возвращает `'required'`, если `currentCode < info.min_version_code`.
   - Возвращает `'optional'`, если `currentCode < info.latest_version_code`.
   - Возвращает `'none'`, если `currentCode >= info.latest_version_code`.
5. Функция `getCurrentVersionCode(): number | null`:
   - Считывает `Constants.expoConfig?.android?.versionCode` из `expo-constants`.
   - Если значение отсутствует или не является положительным целым, возвращает `null`.
6. Функция `fetchVersionInfo(fetcher = fetch): Promise<VersionInfo | null>`:
   - Выполняет GET-запрос к `VERSION_INFO_URL` с заголовком `Cache-Control: no-cache`.
   - Использует `AbortController` с таймаутом 5 секунд.
   - Не передаёт заголовок `Authorization`.
   - Любая сетевая ошибка, ответ с кодом != 200, ошибка разбора HTML/JSON или таймаут перехватываются в `try/catch` и возвращают `null` без выброса исключений и логирования в консоль.

### 2.3. Компонент уведомления: `mobile/src/features/UpdateNotice.tsx`
Реализован компонент `UpdateNotice`:
- **Условия активности:** компонент активен только при `Platform.OS === 'android'` и `!demoEnabled` (`!DEMO_ENABLED`). На платформе Web и в демо-режиме запросы не выполняются, компонент возвращает `null`.
- **Запуск проверки:** выполняется при монтировании компонента, а также при переходе приложения из фона в активный режим (`AppState` → `active`).
- **Ограничение частоты запросов из фона:** переход из фона инициирует проверку не чаще одного раза в 6 часов (`SIX_HOURS_MS = 21_600_000`).
- **Поведение кнопки «Позже»:** флаг скрытия опционального обновления сохраняется в памяти (`dismissedOptional.current = true`), на диск не пишется. Если при последующих фоновых проверках статус обновления остаётся `optional`, окно не показывается. Если статус меняется на `required`, окно отображается принудительно.
- **Интерфейс и стили:** полупрозрачный `Modal` (`transparent`), стиль диалоговой карточки соответствует остальным модальным окнам приложения, используются кнопки `Button` из `components/ui`, шрифты `Montserrat` и цветовые токены темы `theme.colors`.
- **Действие «Обновить»:** вызывает `Linking.openURL(info.download_url)`.
  - В режиме `optional`: при успехе закрывает модальное окно.
  - В режиме `required`: модальное окно остаётся открытым.
  - При ошибке вызова `Linking.openURL`: ошибка перехватывается, приложение не падает, окно остаётся открытым.
- **Кнопка «Назад» (аппаратная на Android):**
  - В режиме `required`: `onRequestClose` игнорируется, окно не закрывается, кнопки «Позже» нет.
  - В режиме `optional`: `onRequestClose` вызывает обработчик «Позже» и закрывает окно.
- **Безопасность жизненного цикла:** используется флаг `isMounted.current`, предотвращающий обновление состояния после размонтирования компонента. Подписка `AppState.addEventListener` корректно снимается при демонтировании.

### 2.4. Интеграция в корень приложения: `mobile/app/_layout.tsx`
Компонент `<UpdateNotice />` размещён рядом с `<Navigation />` внутри `<SessionProvider>` и `<I18nProvider>`:
```tsx
const app = <><StatusBar style="dark" />{DEMO_ENABLED && <DemoRibbon />}<Navigation /><UpdateNotice /></>;
```
Окно доступно как на экране входа, так и внутри авторизованной зоны приложения, не нарушая порядок провайдеров и логику маршрутизации.

---

## 3. Новые тесты: `mobile/tests/appUpdate.test.tsx`

Создан набор из 37 тестов, полностью покрывающий спецификацию:
1. `parseVersionInfo`:
   - парсинг корректного объекта `version.json`;
   - отклонение HTML-строки;
   - отклонение `null` и `undefined`;
   - отклонение массивов;
   - отклонение объектов с пропущенными обязательными полями;
   - отклонение невалидных версий (`1.0`, `v1.0.10`, `1.0.10-beta`);
   - отклонение дробных (`1.5`, `2.2`) и неположительных (`0`, `-1`, `-5`) кодов версий;
   - отклонение ситуации, когда `min_version_code > latest_version_code`;
   - отклонение ссылки с протоколом `http://`;
   - отклонение ссылки на сторонний домен;
   - защита от поддоменной атаки (`https://cashback-qr.poscenter.kz.evil.example/...`);
   - защита от атаки через учетные данные (`https://cashback-qr.poscenter.kz@evil.example/...`);
   - отклонение ссылки с лишними поддиректориями (`/app/sub/...`);
   - отклонение ссылки с некорректным именем файла или двойным расширением (`.apk.exe`, `cashback-two-*.apk`).
2. `updateDecision`:
   - проверка граничных значений при `null`, `undefined`, неположительных кодах версий;
   - возврат `'required'`, когда текущий код меньше минимального;
   - возврат `'optional'`, когда текущий код равен минимальному и меньше последнего;
   - возврат `'none'`, когда текущий код равен или превышает последний;
   - граничные условия при равенстве `min_version_code == latest_version_code`.
3. `fetchVersionInfo`:
   - успешный запрос без передачи заголовка `Authorization`;
   - ответ 200 с телом HTML (SyntaxError парсинга) → `null` без исключения;
   - ответ HTTP 500 → `null` без исключения;
   - сетевая ошибка (`Network connection failed`) → `null` без исключения;
   - таймаут (`AbortError`) → `null` без исключения.
4. `getCurrentVersionCode`:
   - чтение валидного целочисленного `versionCode`;
   - возврат `null` при отсутствии `Constants.expoConfig`, дробных или отрицательных кодах.
5. `UpdateNotice dialog flow and component`:
   - при отсутствии обновления окно не рендерится;
   - при `optional` отображаются заголовок, текст и обе кнопки («Обновить» и «Позже»);
   - нажатие «Обновить» вызывает `Linking.openURL` с валидной ссылкой и закрывает опциональное окно;
   - нажатие «Позже» закрывает окно; переход из фона в течение 6 часов не вызывает повторный запрос; переход после 6 часов выполняет запрос, но опциональное окно повторно не показывается;
   - если после нажатия «Позже» статус обновления при следующем фоновом запросе становится `required`, окно отображается принудительно с текстом обязательного обновления и без кнопки «Позже»;
   - в режиме `required` нажатие аппаратной кнопки «Назад» (`onRequestClose`) не закрывает окно; нажатие «Обновить» оставляет окно открытым;
   - в режиме `optional` нажатие «Назад» работает аналогично кнопке «Позже»;
   - сбой вызова `Linking.openURL` не приводит к падению приложения, окно остаётся открытым;
   - на платформе Web сетевой запрос не выполняется;
   - в демо-режиме (`demoEnabled`) сетевой запрос не выполняется;
   - при отсутствии `versionCode` в конфигурации сетевой запрос не выполняется, окно не показывается.

---

## 4. Сырые результаты проверок

### 4.1. Результаты Jest (17 suites, 227 tests passed)
```text
PASS tests/profileSave.test.tsx (6.158 s)
PASS tests/appUpdate.test.tsx (6.519 s)
PASS tests/components.test.tsx
PASS tests/flows.test.tsx
PASS tests/cardScanner.test.tsx
PASS tests/qrScreen.test.tsx
PASS tests/homeArtwork.test.tsx
PASS tests/avatar.test.tsx
PASS tests/promotionsArtwork.test.tsx
PASS tests/demo.test.ts
PASS tests/wallet.test.tsx
PASS tests/core.test.ts
PASS tests/loginScreen.test.tsx
PASS tests/levels.test.tsx
PASS tests/session.test.ts
PASS tests/keyboardLift.test.ts
PASS tests/transport.test.ts

Test Suites: 17 passed, 17 total
Tests:       227 passed, 227 total
Snapshots:   0 total
Time:        15.219 s
Ran all test suites.
```

### 4.2. Результаты TypeScript (`npx tsc --noEmit`)
Команда завершилась с кодом 0, вывод чистый:
```text
$ npx tsc --noEmit
Exit code: 0
```

### 4.3. Результаты ESLint (`npx eslint .`)
Команда завершилась с кодом 0, 0 ошибок:
```text
$ npx eslint .

/Users/nuras/Desktop/cashback-one/mobile/src/components/useKeyboardLift.ts
  62:20  warning  The ref value 'generation.current' will likely have changed by the time this effect cleanup function runs. If this ref points to a node rendered by React, copy 'generation.current' to a variable inside the effect, and use that variable in the cleanup function  react-hooks/exhaustive-deps

✖ 1 problem (0 errors, 1 warning)
```

### 4.4. Статус Git (`git status --short` и `git diff --stat`)
```text
$ git status --short
 M mobile/app/_layout.tsx
 M mobile/src/i18n/kz.ts
 M mobile/src/i18n/ru.ts
?? mobile/src/features/UpdateNotice.tsx
?? mobile/src/features/appUpdate.ts
?? mobile/tests/appUpdate.test.tsx

$ git diff --stat
 mobile/app/_layout.tsx | 3 ++-
 mobile/src/i18n/kz.ts  | 6 ++++++
 mobile/src/i18n/ru.ts  | 6 ++++++
 3 files changed, 14 insertions(+), 1 deletion(-)
```

---

## 5. Не проверено на этом этапе

В соответствии с требованиями задания, сознательно не проверялись:
1. Визуальный вид окна на реальном мобильном устройстве.
2. Реальное открытие браузера и скачивание APK по ссылке.
3. Наличие и ответ настоящего файла `version.json` на хостинге `https://cashback-qr.poscenter.kz` (будет выложен куратором при релизе следующей версии).
4. Номер сборки в реальном APK (будет сверен при последующей сборке APK).

## Приёмка куратора — 2026-11-01: принято

Проверено независимо: `appUpdate.ts`, `UpdateNotice.tsx`, diff `_layout.tsx` и i18n прочитаны. jest 227 passed (17 наборов), tsc чисто, eslint 0 ошибок и 1 старое предупреждение. Изменения только в `mobile/`, новых зависимостей нет. Запрос идёт без токена, таймаут действует и на чтение тела, HTML от сервера даёт `null`, регулярное выражение ссылки не пропускает чужой домен, `@`, `..` и параметры.

Два замечания, правки не требуют:

1. Время проверки ставится до запроса. Если при запуске нет интернета, повтор при возврате из фона будет только через 6 часов либо при следующем запуске.
2. Если `Constants.expoConfig` в release-сборке окажется пустым, окна просто не будет и ошибки никто не увидит. В APK 1.0.9 `assets/app.config` содержит верный `versionCode`, но чтение на устройстве не проверено.

Поэтому проверка на телефоне обязательна: установить 1.0.10, куратор временно выкладывает `version.json` с `latest_version_code: 12` и ссылкой на 1.0.10, владелец видит окно, затем куратор ставит настоящее значение 11.

Не проверено: вид окна на телефоне, открытие ссылки и скачивание, настоящий `version.json`.
