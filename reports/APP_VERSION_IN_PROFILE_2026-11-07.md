# Версия приложения в профиле — 2026-11-07

## Изменение

Внизу экрана «Профиль», под последним пунктом, показана версия из `Constants.expoConfig?.version`. Код сборки добавляется в скобках, если `Constants.expoConfig?.android?.versionCode` доступен как положительное целое число. Если Expo config или версия отсутствуют, строка скрыта и экран продолжает отображаться.

Добавлены переводы: RU «Версия {version}», KK «Нұсқа {version}». Новые зависимости не добавлялись. Версия, `android/`, сервер, кабинет и APK не менялись.

Для web-preview SDK не передал `android.versionCode`, поэтому на снимке показана версия без кода. Тест проверяет, что при доступном коде выводится `1.0.16 (17)`.

## Прогоны Jest

Ниже записаны все прогоны этой задачи в хронологическом порядке.

### Baseline без `--forceExit`

Команда: `npx jest --runInBand`.

```text
Test Suites: 23 passed, 23 total
Tests:       317 passed, 317 total
Snapshots:   0 total
Time:        31.919 s
Ran all test suites.
Jest did not exit one second after the test run has completed.

'This usually means that there are asynchronous operations that weren't stopped in your tests. Consider running Jest with `--detectOpenHandles` to troubleshoot this issue.
```

Процесс остановлен после предупреждения (exit 130). Владелец принял этот baseline как 23 suites / 317 passed и указал считать сообщение об open handles особенностью тестов.

### Baseline с `--forceExit`

Команда: `npx jest --runInBand --forceExit`.

```text
PASS tests/flows.test.tsx
PASS tests/clientConfig.test.tsx
PASS tests/profileSave.test.tsx
PASS tests/components.test.tsx
PASS tests/cacheRefresh.test.tsx
PASS tests/historyPeriod.test.tsx
PASS tests/qrScreen.test.tsx
PASS tests/push.test.tsx
PASS tests/appUpdate.test.tsx
PASS tests/wallet.test.tsx
PASS tests/avatar.test.tsx
PASS tests/serverContentAndCache.test.tsx
PASS tests/noCardNotice.test.tsx
PASS tests/cityCustom.test.tsx
PASS tests/homeArtwork.test.tsx
PASS tests/core.test.ts
PASS tests/promotionsArtwork.test.tsx
PASS tests/loginScreen.test.tsx
PASS tests/levels.test.tsx
PASS tests/session.test.ts
PASS tests/keyboardLift.test.ts
PASS tests/transport.test.ts
PASS tests/demo.test.ts

Test Suites: 23 passed, 23 total
Tests:       317 passed, 317 total
Snapshots:   0 total
Time:        22.11 s, estimated 31 s
Ran all test suites.
Force exiting Jest: Have you considered using `--detectOpenHandles` to detect async operations that kept running after all tests finished?
exit_code=0
```

### После первого изменения: упал новый тест профиля

Первый post-change прогон завершился ошибкой в новом тесте. Он открывал профиль сразу на KK, а общий helper ожидал русскую метку `Имя`.

```text
FAIL tests/profileSave.test.tsx
  ● shows the application version in Russian and Kazakh, and renders when Expo config has no version

    Unable to find an element with accessibility label: Имя

              accessibilityLabel="Аты"
    ...
              Нұсқа 1.0.16 (17)

Test Suites: 1 failed, 22 passed, 23 total
Tests:       1 failed, 317 passed, 318 total
```

По разрешению владельца исправлен только новый тест: профиль открывается на русском, затем язык переключается через `LanguageSwitch`, после чего проверяется KK-строка. Общий helper и прежние тесты восстановлены без изменений.

### После исправления теста: один раз упал `historyPeriod.test.tsx`

Следующий полный прогон прошёл новый тест профиля, но один раз упал неизменённый `tests/historyPeriod.test.tsx`: проверка пустого состояния выполнилась, пока экран всё ещё показывал загрузку. Тест не изменялся.

```text
FAIL tests/historyPeriod.test.tsx
  ● HistoryScreen period integration › shows period chips, calls API with date range and shows empty state

    Unable to find an element with text: Операций пока нет

              <Text>
                Загрузка…
              </Text>

      197 |     // Initial load: period "all"
      198 |     await waitFor(() => expect(screen.getByText(ru.periodAll)).toBeTruthy());
    > 199 |     expect(screen.getByText(ru.noHistory)).toBeTruthy();

Test Suites: 1 failed, 22 passed, 23 total
Tests:       1 failed, 317 passed, 318 total
Snapshots:   0 total
Time:        23.382 s, estimated 24 s
Ran all test suites.
Force exiting Jest: Have you considered using `--detectOpenHandles` to detect async operations that kept running after all tests finished?
exit_code=1
```

Владелец подтвердил, что это давний нестабильный тест и запретил его менять. По отдельному поручению выполнен один повтор.

### Повтор: успешно

Команда: `npx jest --runInBand --forceExit`.

```text
PASS tests/historyPeriod.test.tsx
PASS tests/profileSave.test.tsx
PASS tests/clientConfig.test.tsx
PASS tests/flows.test.tsx
PASS tests/qrScreen.test.tsx
PASS tests/cacheRefresh.test.tsx
PASS tests/appUpdate.test.tsx
PASS tests/noCardNotice.test.tsx
PASS tests/homeArtwork.test.tsx
PASS tests/cityCustom.test.tsx
PASS tests/wallet.test.tsx
PASS tests/push.test.tsx
PASS tests/avatar.test.tsx
PASS tests/serverContentAndCache.test.tsx
PASS tests/components.test.tsx
PASS tests/core.test.ts
PASS tests/promotionsArtwork.test.tsx
PASS tests/loginScreen.test.tsx
PASS tests/levels.test.tsx
PASS tests/session.test.ts
PASS tests/demo.test.ts
PASS tests/transport.test.ts
PASS tests/keyboardLift.test.ts

Test Suites: 23 passed, 23 total
Tests:       318 passed, 318 total
Snapshots:   0 total
Time:        21.702 s, estimated 23 s
Ran all test suites.
Force exiting Jest: Have you considered using `--detectOpenHandles` to detect async operations that kept running after all tests finished?
exit_code=0
```

## TypeScript и ESLint

До изменений:

```text
$ npx tsc --noEmit
exit_code=0

$ npx eslint .
/Users/nuras/Desktop/cashback-one/mobile/src/components/useKeyboardLift.ts
  62:20  warning  The ref value 'generation.current' will likely have changed by the time this effect cleanup function runs. If this ref points to a node rendered by React, copy 'generation.current' to a variable inside the effect, and use that variable in the cleanup function  react-hooks/exhaustive-deps

✖ 1 problem (0 errors, 1 warning)
exit_code=0
```

После изменений:

```text
$ npx tsc --noEmit
exit_code=0

$ npx eslint .
/Users/nuras/Desktop/cashback-one/mobile/src/components/useKeyboardLift.ts
  62:20  warning  The ref value 'generation.current' will likely have changed by the time this effect cleanup function runs. If this ref points to a node rendered by React, copy 'generation.current' to a variable inside the effect, and use that variable in the cleanup function  react-hooks/exhaustive-deps

✖ 1 problem (0 errors, 1 warning)
exit_code=0
```

Предупреждение ESLint осталось прежним, в задаче его не меняли.

## Web-preview и снимок

Запуск: `EXPO_PUBLIC_DEMO=1 EXPO_PUBLIC_CLIENT=keremet npx expo start --web --port 8081 --localhost`. В браузере открыт `/profile`, viewport 390 × 844 CSS px. Demo-плашка отображалась, на предыдущем экране был бренд Keremet Bonus. При снятии снимка браузер сообщил 0 ошибок и 3 предупреждения; это предупреждение Expo Notifications о web, два существующих require cycle. Metro остановлен после сохранения снимка.

Expo CLI сообщил о доступной более новой версии пакета (`expo@55.0.31`, ожидается `~55.0.32`) и использовал fallback для React Native DevTools. Зависимости не обновлялись; web-preview собрался и открылся.

Файл: [`reports/app-version-2026-11-07/profile.png`](app-version-2026-11-07/profile.png), размер изображения 390 × 844 px. На нём видна строка «Версия 1.0.16» под «Историей начислений».

## Итоговый diff

```text
mobile/app/(app)/(tabs)/profile.tsx |  8 ++++++++
mobile/src/i18n/kz.ts               |  2 +-
mobile/src/i18n/ru.ts               |  2 +-
mobile/tests/profileSave.test.tsx   | 41 +++++++++++++++++++++++++++++++++++++
4 files changed, 51 insertions(+), 2 deletions(-)
```

`git diff --check` завершился с `exit_code=0`. APK не собирался, `android/` не менялся, версия не изменялась, commit/push не выполнялись.
