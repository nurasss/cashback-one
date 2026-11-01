# Отчёт по исправлениям экрана входа и профиля — 2026-11-01

Среда: macOS Darwin arm64, Python `backend/.venv/bin/python`, Node/Jest в каталоге `mobile/`.
Ограничения соблюдены: без сборки APK, без деплоя, без commit/push, без смены версии, без новых зависимостей. Затронуты только каталоги `backend/` и `mobile/`.

---

## 1. Базовые проверки до правок

1. `mobile` тесты: `npx jest`
```text
Test Suites: 15 passed, 15 total
Tests:       179 passed, 179 total
Snapshots:   0 total
Time:        11.342 s, estimated 12 s
Ran all test suites.
```

2. `backend` тесты: `backend/.venv/bin/python -m pytest backend/tests -q -ra`
```text
360 passed, 36 skipped, 4 warnings in 35.43s
```

---

## 2. Исправление 1: Лимит по IP блокирует перебор, в т.ч. валидный код (`sms_auth_service.py`, `rate_limiter.py`)

### 2.1. Падающий тест до правки
В `backend/tests/test_sms_auth.py` добавлен тест `test_sms_otp_verify_ip_rate_limit_blocks_valid_code`:
```python
@pytest.mark.asyncio
async def test_sms_otp_verify_ip_rate_limit_blocks_valid_code(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    ...
    # Exhaust IP limit with 3 wrong attempts (limit is 3)
    for _ in range(3):
        res_bad = await client.post("/auth/sms/verify", json={"phone": phone, "device_id": device_id, "code": "0000"})
        assert res_bad.status_code == 400

    # 4th request has the VALID code, but IP is rate limited
    res_valid_blocked = await client.post("/auth/sms/verify", json={"phone": phone, "device_id": device_id, "code": valid_code})
    assert res_valid_blocked.status_code == 429
```

Сырой вывод падения:
```text
=================================== FAILURES ===================================
_____________ test_sms_otp_verify_ip_rate_limit_blocks_valid_code ______________
...
        # 4th request has the VALID code, but IP is rate limited
        res_valid_blocked = await client.post(
            "/auth/sms/verify",
            json={"phone": phone, "device_id": device_id, "code": valid_code},
        )
>       assert res_valid_blocked.status_code == 429
E       assert 200 == 429
E        +  where 200 = <Response [200 OK]>.status_code

backend/tests/test_sms_auth.py:738: AssertionError
=========================== short test summary info ============================
FAILED backend/tests/test_sms_auth.py::test_sms_otp_verify_ip_rate_limit_blocks_valid_code
======================= 1 failed, 21 deselected in 0.38s =======================
```

### 2.2. Внесённые изменения
1. `backend/app/services/rate_limiter.py`:
   - В протокол `RateLimiter` добавлен метод `is_blocked(key: str, limit: int, window_seconds: int) -> bool` без инкремента.
   - В `InMemoryRateLimiter`: `is_blocked` вычисляет количество активных записей в скользящем окне `valid_history` и сравнивает `>= limit` без добавления новой отметки.
   - В `RedisRateLimiter`: `is_blocked` выполняет чтение ключа через `GET rate_limit:{key}` и проверяет `int(val) >= limit`. При ошибке `RedisError` генерирует контролируемый `AppError(code="AUTH_RATE_LIMIT_UNAVAILABLE", status_code=503)`.
2. `backend/app/services/sms_auth_service.py`:
   - В `verify_sms_otp` в самом начале (до выборки `OtpCode` с блокировкой `FOR UPDATE`) вызывается `limiter.is_blocked(f"sms_otp_verify:ip:{client_ip}", ...)`. Если лимит исчерпан, выбрасывается `AppError(code="RATE_LIMIT_EXCEEDED", status_code=429)`. Попытки кода в базе не инкрементируются, статус OTP остаётся `pending`.
   - В ветке неверного кода вызывается `limiter.is_rate_limited(...)` для учёта неудачной попытки, после чего возвращается 400 `INVALID_CODE` или `OTP_MAX_ATTEMPTS_EXCEEDED`.
   - Валидный код лимит не расходует.
3. `backend/tests/test_rate_limiter.py`:
   - Обновлён `FailingLimiter` (добавлен `is_blocked`).
   - Добавлены тесты `is_blocked` для `InMemoryRateLimiter` и `RedisRateLimiter` (включая сценарий 503 при падении Redis).

### 2.3. Прохождение теста после правки
```text
backend/.venv/bin/python -m pytest backend/tests/test_sms_auth.py -k "test_sms_otp_verify_ip_rate_limit_blocks_valid_code" -ra
============================= test session starts ==============================
backend/tests/test_sms_auth.py .                                         [100%]
======================= 1 passed, 21 deselected in 1.28s =======================
```
Совместный прогон `test_rate_limiter.py` и `test_sms_auth.py`:
```text
backend/tests/test_rate_limiter.py .......                               [ 24%]
backend/tests/test_sms_auth.py ......................                    [100%]
============================== 29 passed in 3.49s ==============================
```

---

## 3. Исправление 2: Лишняя цифра в номере телефона (`mobile/src/utils/format.ts`)

### 3.1. Падающий тест до правки
В `mobile/tests/core.test.ts` добавлены проверки:
```typescript
expect(phoneInputDigits('+7 701 123 45 678')).toBe('7011234567');
expect(phoneInputDigits('+ 701')).toBe('701');
expect(phoneInputDigits('7 701')).toBe('701');
```

Сырой вывод падения:
```text
FAIL tests/core.test.ts
  ● handles all 4 phone insertion formats, erase to empty, +7 non-erasable, and non-7 first digit

    expect(received).toBe(expected) // Object.is equality

    Expected: "7011234567"
    Received: "0112345678"

      73 |   expect(phoneInputDigits('+7 701 123 45 67')).toBe('7011234567');
    > 74 |   expect(phoneInputDigits('+7 701 123 45 678')).toBe('7011234567');
         |                                                 ^
      75 |   expect(phoneInputDigits('+ 701')).toBe('701');
      76 |   expect(phoneInputDigits('7 701')).toBe('701');

      at Object.toBe (tests/core.test.ts:74:49)
```

### 3.2. Внесённые изменения
`mobile/src/utils/format.ts` (`phoneInputDigits`):
- Префикс маски определяется как `/^\+7|^7\s/.test(text)`.
- Если префикс совпал, сбрасывается первая цифра 7 и фиксируется флаг `prefixDiscarded = true`.
- Правило отбрасывания первой цифры при 11 цифрах применяется только при `!prefixDiscarded`.
- Итог: `+7 701 123 45 678` даёт `7011234567`; `+ 701` даёт `701`; `7 701` даёт `701`. Все 4 формата вставки сохраняют работоспособность.

### 3.3. Прохождение теста после правки
```text
PASS tests/core.test.ts
Test Suites: 1 passed, 1 total
Tests:       31 passed, 31 total
Snapshots:   0 total
Time:        1.998 s, estimated 2 s
```

---

## 4. Исправление 3: Устаревшее замыкание при очереди (`mobile/app/(app)/(tabs)/profile.tsx`)

### 4.1. Падающий тест до правки
В `mobile/tests/profileSave.test.tsx` добавлен тест `queued save during in-flight PATCH uses fresh profile from query and sends latest state`:
```typescript
it('queued save during in-flight PATCH uses fresh profile from query and sends latest state', async () => {
  const screen = await open({ ...profile, first_name: 'A' });
  ...
  fireEvent.changeText(screen.getByLabelText(ru.firstName), 'AB');
  await act(async () => { fireEvent(screen.getByLabelText(ru.firstName), 'blur'); });
  ...
  fireEvent.changeText(screen.getByLabelText(ru.firstName), 'A');
  await act(async () => { fireEvent(screen.getByLabelText(ru.firstName), 'blur'); });
  ...
  resolveInFlight({ ...profile, first_name: 'AB' });
  ...
  expect(patches()).toHaveLength(2);
  expect(patches()[1]![1].body).toEqual({ first_name: 'A' });
});
```

Сырой вывод падения:
```text
FAIL tests/profileSave.test.tsx
  ● queued save during in-flight PATCH uses fresh profile from query and sends latest state

    expect(received).toHaveLength(expected)

    Expected length: 2
    Received length: 1
    Received array:  [["/me/profile", {"auth": true, "body": {"first_name": "AB"}, "method": "PATCH"}]]

      313 |   // 4. Queued save must have compared 'A' with fresh server state 'AB' and sent PATCH with 'A'
    > 314 |   expect(patches()).toHaveLength(2);
          |                     ^
      315 |   expect(patches()[1]![1].body).toEqual({ first_name: 'A' });
```

### 4.2. Внесённые изменения
`mobile/app/(app)/(tabs)/profile.tsx`:
- В `flushSave` проверка `if (inFlightRef.current) { queuedRef.current = true; return; }` вынесена на самый верх, до вычисления дельты.
- Данные исходного профиля берутся актуальными из кэша React Query: `query.getQueryData<Profile>(keys.profile) ?? profile.data`.
- В блоке `finally` вызов очереди происходит через `void flushSaveRef.current()`, использующий обновлённые данные кэша.

### 4.3. Прохождение теста после правки
Тест пройден в составе набора `profileSave.test.tsx`.

---

## 5. Исправление 4: Автосохранение съедает пробел (`mobile/app/(app)/(tabs)/profile.tsx`)

### 5.1. Падающий тест до правки
В `mobile/tests/profileSave.test.tsx` добавлен тест `auto-save does not eat trailing space and preserves typed space for next character`:
```typescript
it('auto-save does not eat trailing space and preserves typed space for next character', async () => {
  jest.useFakeTimers();
  const screen = await open();
  mockRequest.mockResolvedValueOnce({ ...profile, first_name: 'Анна' });

  fireEvent.changeText(screen.getByLabelText(ru.firstName), 'Анна ');
  await act(async () => { jest.advanceTimersByTime(800); });
  expect(patches()).toHaveLength(1);

  expect(value(screen, ru.firstName)).toBe('Анна ');
  fireEvent.changeText(screen.getByLabelText(ru.firstName), `${value(screen, ru.firstName)}М`);
  expect(value(screen, ru.firstName)).toBe('Анна М');
  ...
});
```

Сырой вывод падения:
```text
FAIL tests/profileSave.test.tsx
  ● auto-save does not eat trailing space and preserves typed space for next character

    expect(received).toBe(expected) // Object.is equality

    Expected: "Анна "
    Received: "Анна"

      333 |   // Server returned 'Анна', but input on screen must preserve trailing space 'Анна '
    > 334 |   expect(value(screen, ru.firstName)).toBe('Анна ');
          |                                       ^
```

### 5.2. Внесённые изменения
`mobile/app/(app)/(tabs)/profile.tsx`:
- Сравнение `current` и `original` при принятии решения об отправке выполняется по `trim()`:
  `if (current.first_name.trim() !== original.first_name.trim())`.
- При получении ответа `fresh` текст на экране не перезаписывается, если `cur.first_name.trim() === fresh.first_name.trim()`. Введённый покупателем хвостовой пробел сохраняется.
- Индикатор сохранения рассчитывается со сравнением по `trim()`:
  `next.first_name.trim() === fresh.first_name.trim() && next.last_name.trim() === fresh.last_name.trim()`.
- Лишний PATCH при blur без смысловых изменений не отправляется.

### 5.3. Прохождение теста после правки
Тест пройден в составе набора `profileSave.test.tsx`.

---

## 6. Исправление 5: «Сохранено» без сохранения (`mobile/app/(app)/(tabs)/profile.tsx`)

### 6.1. Падающий тест до правки
В `mobile/tests/profileSave.test.tsx` добавлен тест `focus and blur without changes does not show saved and does not send PATCH`:
```typescript
it('focus and blur without changes does not show saved and does not send PATCH', async () => {
  const screen = await open({ ...profile, first_name: 'Азамат' });
  fireEvent(screen.getByLabelText(ru.firstName), 'focus');
  await act(async () => { fireEvent(screen.getByLabelText(ru.firstName), 'blur'); });

  expect(patches()).toHaveLength(0);
  expect(screen.queryByText(ru.saved)).toBeNull();
  screen.unmount();
});
```

Сырой вывод падения:
```text
FAIL tests/profileSave.test.tsx
  ● focus and blur without changes does not show saved and does not send PATCH

    expect(received).toBeNull()

    Received: {"_fiber": ..., "type": "Text", ...} // элемент с текстом "Сохранено"

      355 |   expect(patches()).toHaveLength(0);
    > 356 |   expect(screen.queryByText(ru.saved)).toBeNull();
          |                                        ^
```

### 6.2. Внесённые изменения
`mobile/app/(app)/(tabs)/profile.tsx`:
- Из ветки `if (Object.keys(body).length === 0)` удалён вызов `if (mountedRef.current) setSaved(true);`. Статус «Сохранено» выставляется только после реального успешного ответа сервера.

### 6.3. Прохождение тестов 3, 4, 5 после правок
```text
PASS tests/profileSave.test.tsx
  ✓ profile has no save button, no IIN and no company (231 ms)
  ✓ Done saves only the edited sheet field with a PATCH, closes the sheet and shows the new value (247 ms)
  ✓ a failed save keeps the sheet open with the input and the error inside, and can be retried (189 ms)
  ✓ cancelling sends nothing and leaves the value unchanged (102 ms)
  ✓ an unchanged value closes the sheet without a request (91 ms)
  ✓ empty values go to the API as null, also for the birth date (112 ms)
  ✓ an invalid email is rejected in the sheet and never sent (85 ms)
  ✓ birth date sheet applies mask and rejects date under 18 with birthDateUnder18 (96 ms)
  ✓ first name auto-saves after 800ms debounce (50 ms)
  ✓ first name auto-saves immediately on blur (86 ms)
  ✓ first name auto-saves immediately when leaving screen (focus effect cleanup) (85 ms)
  ✓ typing during in-flight PATCH does not overwrite new input and sends it in next request (141 ms)
  ✓ failed auto-save keeps typed text and shows ErrorNotice (113 ms)
  ✓ queued save during in-flight PATCH uses fresh profile from query and sends latest state (125 ms)
  ✓ auto-save does not eat trailing space and preserves typed space for next character (123 ms)
  ✓ focus and blur without changes does not show saved and does not send PATCH (67 ms)

Test Suites: 1 passed, 1 total
Tests:       16 passed, 16 total
Snapshots:   0 total
Time:        4.068 s
```

---

## 7. Мелочь: Удаление неиспользуемого импорта `useEffect`

В `mobile/tests/profileSave.test.tsx` удалена строка `import { useEffect } from 'react';`.
Запуск `npx eslint .`:
```text
/Users/nuras/Desktop/cashback-one/mobile/src/components/useKeyboardLift.ts
  62:20  warning  The ref value 'generation.current' will likely have changed by the time this effect cleanup function runs. If this ref points to a node rendered by React, copy 'generation.current' to a variable inside the effect, and use that variable in the cleanup function  react-hooks/exhaustive-deps

✖ 1 problem (0 errors, 1 warning)
```
Ровно 1 предупреждение в проекте (в `useKeyboardLift.ts`), как и требовалось.

---

## 8. Итоговые сырые выводы проверок

### 8.1. `cd mobile && npx jest`
```text
PASS tests/homeArtwork.test.tsx
PASS tests/components.test.tsx (6.817 s)
PASS tests/flows.test.tsx (7.113 s)
PASS tests/profileSave.test.tsx
PASS tests/cardScanner.test.tsx
PASS tests/qrScreen.test.tsx
PASS tests/core.test.ts
PASS tests/demo.test.ts
PASS tests/promotionsArtwork.test.tsx
PASS tests/wallet.test.tsx
PASS tests/transport.test.ts
PASS tests/loginScreen.test.tsx
PASS tests/levels.test.tsx
PASS tests/keyboardLift.test.ts
PASS tests/session.test.ts

Test Suites: 15 passed, 15 total
Tests:       182 passed, 182 total
Snapshots:   0 total
Time:        11.902 s
Ran all test suites.
```

### 8.2. `cd mobile && npx tsc --noEmit`
```text
(Код возврата 0, вывод чистый)
```

### 8.3. `cd mobile && npx eslint .`
```text
/Users/nuras/Desktop/cashback-one/mobile/src/components/useKeyboardLift.ts
  62:20  warning  The ref value 'generation.current' will likely have changed by the time this effect cleanup function runs. If this ref points to a node rendered by React, copy 'generation.current' to a variable inside the effect, and use that variable in the cleanup function  react-hooks/exhaustive-deps

✖ 1 problem (0 errors, 1 warning)
```

### 8.4. `backend/.venv/bin/python -m pytest backend/tests -q -ra`
```text
........................................................................ [ 18%]
........................................................................ [ 36%]
........................................................................ [ 54%]
.....................................sssssssssssssssssssssssssssssssssss [ 72%]
s....................................................................... [ 90%]
......................................                                   [100%]
=============================== warnings summary ===============================
tests/test_agent_sync_transactions.py::test_transactions_sync_initial_and_idempotent_replay
tests/test_agent_sync_transactions.py::test_transactions_same_external_id_on_different_cards
tests/test_customer_app.py::test_fresh_transaction_sync_notifies_card_owner
  /Users/nuras/Desktop/cashback-one/backend/app/api/agent_sync.py:44: SADeprecationWarning: The Result.tuples() method is deprecated, Row now behaves like a tuple and can unpack types directly. (deprecated since: 2.1.0)
    ).tuples().all()

tests/test_production_runtime.py::test_expected_alembic_head_is_derived_from_migration_scripts
  /Users/nuras/Desktop/cashback-one/backend/.venv/lib/python3.11/site-packages/alembic/config.py:604: DeprecationWarning: No path_separator found in configuration; falling back to legacy splitting on spaces, commas, and colons for prepend_sys_path.  Consider adding path_separator=os to Alembic config.
    util.warn_deprecated(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
SKIPPED [1] backend/tests/test_postgres_admin_security.py:56: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_admin_security.py:92: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_admin_security.py:130: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_admin_security.py:190: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_admin_security.py:229: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_admin_security.py:269: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_admin_security.py:331: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_agent_sync_concurrency.py:62: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_agent_sync_concurrency.py:121: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_agent_sync_concurrency.py:197: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_agent_sync_concurrency.py:262: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_bind_concurrency.py:47: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_bind_concurrency.py:134: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_bind_concurrency.py:211: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_bind_concurrency.py:302: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_customer_auth_concurrency.py:65: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_customer_auth_concurrency.py:117: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_customer_auth_concurrency.py:140: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_customer_auth_concurrency.py:175: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_customer_auth_concurrency.py:193: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_customer_auth_concurrency.py:221: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_model_smoke.py:20: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_sms_concurrency.py:53: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_sms_concurrency.py:121: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_sms_concurrency.py:187: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_sms_concurrency.py:258: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_wallet_concurrency.py:48: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_wallet_concurrency.py:128: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_wallet_concurrency.py:231: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_wallet_concurrency.py:279: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_wallet_concurrency.py:372: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_wallet_concurrency.py:480: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_wappi_concurrency.py:61: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_wappi_concurrency.py:146: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_wappi_concurrency.py:226: POSTGRES_TEST_URL is not configured
SKIPPED [1] backend/tests/test_postgres_wappi_concurrency.py:257: POSTGRES_TEST_URL is not configured
362 passed, 36 skipped, 4 warnings in 35.02s
```

### 8.5. `backend/.venv/bin/python -m ruff check backend/app backend/tests/test_sms_auth.py backend/tests/test_customer_app.py`
```text
All checks passed!
```

### 8.6. `git status --short` и `git diff --stat`
```text
$ git status --short
 M backend/app/api/auth.py
 M backend/app/core/config.py
 M backend/app/core/security.py
 M backend/app/schemas/auth.py
 M backend/app/schemas/customer_app.py
 M backend/app/services/rate_limiter.py
 M backend/app/services/sms_auth_service.py
 M backend/tests/test_customer_app.py
 M backend/tests/test_rate_limiter.py
 M backend/tests/test_sms_auth.py
 M mobile/app/(app)/(tabs)/profile.tsx
 M mobile/app/login.tsx
 M mobile/src/demo/mockApi.ts
 M mobile/src/features/profile.tsx
 M mobile/src/i18n/kz.ts
 M mobile/src/i18n/ru.ts
 M mobile/src/utils/format.ts
 M mobile/tests/core.test.ts
 M mobile/tests/flows.test.tsx
 M mobile/tests/profileSave.test.tsx
?? C:/
?? docs/PROMPT_APP_AVATAR_2026-11-01.md
?? docs/PROMPT_APP_LOGIN_PROFILE_2026-11-01.md
?? docs/PROMPT_APP_LOGIN_PROFILE_FIX_2026-11-01.md
?? mobile/tests/loginScreen.test.tsx
?? reports/APP_LOGIN_PROFILE_2026-11-01.md
?? reports/APP_LOGIN_PROFILE_FIX_2026-11-01.md
?? video/
```

```text
$ git diff --stat
 backend/app/api/auth.py                  |  16 +-
 backend/app/core/config.py               |   2 +
 backend/app/core/security.py             |   7 +-
 backend/app/schemas/auth.py              |  11 +-
 backend/app/schemas/customer_app.py      |   6 +-
 backend/app/services/rate_limiter.py     |  24 ++
 backend/app/services/sms_auth_service.py |  43 +++-
 backend/tests/test_customer_app.py       |  41 ++++
 backend/tests/test_rate_limiter.py       |  33 +++
 backend/tests/test_sms_auth.py           | 184 +++++++++++++++
 mobile/app/(app)/(tabs)/profile.tsx      | 177 +++++++++++----
 mobile/app/login.tsx                     |  21 +-
 mobile/src/demo/mockApi.ts               |   6 +
 mobile/src/features/profile.tsx          |   8 +-
 mobile/src/i18n/kz.ts                    |  11 +-
 mobile/src/i18n/ru.ts                    |  11 +-
 mobile/src/utils/format.ts               |  65 ++++++
 mobile/tests/core.test.ts                |  67 +++++-
 mobile/tests/flows.test.tsx              |  10 +-
 mobile/tests/profileSave.test.tsx        | 402 ++++++++++++++++++-------------
 20 files changed, 874 insertions(+), 254 deletions(-)
```
Затронуты исключительно каталоги `backend/` и `mobile/`.

## Приёмка куратора — 2026-11-01: принято

Проверено независимо на общем рабочем дереве с этапом фото: pytest 373 passed / 36 skipped, jest 190 passed, tsc чисто, eslint 0 ошибок и 1 предупреждение, ruff чисто. Отдельно 37 тестов `-k postgres` на временном локальном PostgreSQL 16 прошли, из них 36 без него пропускаются.

Код всех пяти пунктов прочитан. `is_blocked` стоит до чтения OTP, значение совпадает с `is_rate_limited` (Redis: `>= limit` при GET против `> limit` после INCR). Оба маршрута, WhatsApp и SMS, передают `client_ip` и `limiter`.

Не проверено: телефон, настоящая отправка кода в WhatsApp.
