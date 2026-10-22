# Проверка mobile/ — диагностика

Дата начала: 2026-10-22T11:12:17Z (UTC). Каталог: `mobile/`. Только диагностика: код, тесты, конфигурация, зависимости, версия не менялись. APK не собирался, production-запросов, чтения секретов, commit/push не было. Чужие изменения (Gemini) не трогались.

**Результат: СТОП на первой ошибке.** `npm test` завершился с кодом 1. `npm run typecheck` по условию задачи **не запускался**.

## Команды и коды выхода

| № | Команда | Код выхода | Статус |
|---|---|---|---|
| 1 | `npm test` (`jest --runInBand`) | **1** | упала |
| 2 | `npm run typecheck` | не запускалась | остановка после ошибки в п. 1 |

Таймауты не увеличивались, повторов не было.

## Итог npm test

- Наборы: 1 упал, 11 прошли, 12 всего.
- Тесты: 1 упал, 172 прошли, 173 всего.
- Время: 43.935 с.
- Упал набор `tests/profileSave.test.tsx` (19.696 с), тест «Done saves only the edited field with a PATCH, closes the sheet and shows the new value».
- Причина по выводу jest: превышен стандартный тайм-аут теста 5000 мс (`Exceeded timeout of 5000 ms for a test`). Утверждение (expect) не сработало, ошибки в коде приложения в выводе нет.

Сравнение с предыдущим прогоном (тот же тест, тот же набор): ранее тест прошёл за 1764 мс, весь набор за 12.9 с; сейчас весь прогон занял 43.9 с, набор 19.7 с. Это только наблюдение, причина замедления не исследовалась и не устанавливалась. Гипотезу (нагрузка машины или медленный первый тест набора) не проверяли, исправлений не вносили.

## Безопасный вывод (сокращён до значимого; трассировки стека, секретов и персональных данных нет)

```text
FAIL tests/profileSave.test.tsx (19.696 s)
PASS tests/components.test.tsx (8.572 s)
PASS tests/flows.test.tsx
PASS tests/cardBarcode.test.tsx
PASS tests/core.test.ts
PASS tests/wallet.test.tsx
PASS tests/demo.test.ts
PASS tests/session.test.ts
PASS tests/levels.test.tsx
PASS tests/code128.test.ts
PASS tests/transport.test.ts
PASS tests/keyboardLift.test.ts

  ● Done saves only the edited field with a PATCH, closes the sheet and shows the new value

    thrown: "Exceeded timeout of 5000 ms for a test.
    Add a timeout value to this test to increase the timeout, if this is a long-running test. See https://jestjs.io/docs/api#testname-fn-timeout."

      31 | beforeEach(() => { jest.clearAllMocks(); mockRequest.mockReset(); });
      32 |
    > 33 | it('Done saves only the edited field with a PATCH, closes the sheet and shows the new value', async () => {
         | ^
      34 |   const screen = await open();
      35 |   fireEvent.press(screen.getByLabelText(ru.email));
      36 |   expect(inputs(screen)).toBe(3);

Test Suites: 1 failed, 11 passed, 12 total
Tests:       1 failed, 172 passed, 173 total
Snapshots:   0 total
Time:        43.935 s
Ran all test suites.
```

Код выхода `npm test`: 1.

## Состояние рабочего дерева (mobile/)

Изменения относятся к пакету «первый пакет mobile» (`reports/MOBILE_FIRST_PACKAGE.md`) и в этой диагностике не вносились. Новых правок в рамках проверки нет.

## Что дальше (решает владелец)

Диагностика остановлена. Возможные шаги, без выполнения без поручения: повторить `npm test` в тех же условиях, чтобы отличить нестабильность по времени от постоянной ошибки; затем выполнить `npm run typecheck`.
