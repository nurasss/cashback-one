# Отчёт об исправлении дефектов после приёмки правок приложения

Дата: 2026-11-02
HEAD: `339e208`
Задание: `docs/PROMPT_APP_POLISH_FIXES_2026-11-02.md`
Контекст и замечания приёмки: `reports/APP_POLISH_ACCEPTANCE_2026-11-02.md`

---

## 1. Изменения по дефектам

### 1.1. Размер иллюстрации в `ArtworkOfferCard` (Дефект №1)
- **Файл**: `mobile/src/features/home.tsx`
- **Проблема**: В React Native на реальных устройствах (Android/iOS) компонент `Image` со статическим `require` берет внутренние габариты из файла изображения при отсутствии явных `width`/`height` в стиле. `aspectRatio` и `top`/`bottom` на самом `Image` не препятствовали отрисовке 493×360 dp с обрезкой карточкой.
- **Исправление**:
  - Картинка `Image` обёрнута в контейнер `<View style={[styles.artworkSide, { aspectRatio: card.sideAspectRatio }]}>`.
  - В стили добавлены:
    - `artworkSide: { position: 'absolute', right: 0, top: 0, bottom: 0, zIndex: 0 }`
    - `artworkSideImage: { width: '100%', height: '100%' }`
  - Стиль `Image`: `styles.artworkSideImage`, `resizeMode="contain"`.
- **Тест**: в `mobile/tests/promotionsArtwork.test.tsx` обновлена проверка: у `promotion-image-*` стиль `{ width: '100%', height: '100%' }`, а `aspectRatio`, `position: 'absolute'`, `right: 0`, `top: 0`, `bottom: 0`, `zIndex: 0` проверяются на родительском элементе `View`. Проверка `aspectRatio` на самом `Image` исключена.

### 1.2. Чистка четырёх `promo-*-side.png` (Дефект №2)
- **Файлы**: `mobile/assets/promotions/promo-*-side.png`
- **Проблема**: В ассетах оставались обрывки красной плашки/текста в левом верхнем углу и светлая кайма снизу/справа по 10 px.
- **Исправление**: Запущен одноразовый скрипт на Pillow во временной директории `/tmp` (вне репозитория):
  1. `crop((0, 0, w - 10, h - 10))` — удаление краевой каймы.
  2. Маска прямоугольника `(0, 0, rw, rh)` со значением 0 (остальное 255) с размытием `ImageFilter.GaussianBlur(4)`.
  3. Наложение новой альфы `Image.composite(alpha, Image.new('L', size, 0), blurred_mask)`.
- **Итоговые характеристики ассетов**:
  - `promo-hits-discount-side.png`: 483×350 px, 230 494 байт, SHA-256 `15056477d214f1dc...`, `sideAspectRatio: 483 / 350`
  - `promo-card-bonus-side.png`: 542×350 px, 144 191 байт, SHA-256 `32153d8362992c7d...`, `sideAspectRatio: 542 / 350`
  - `promo-weekly-side.png`: 394×350 px, 102 275 байт, SHA-256 `711d5229ddf08556...`, `sideAspectRatio: 394 / 350`
  - `promo-fresh-products-side.png`: 448×350 px, 200 761 байт, SHA-256 `a4fde13a63c34b26...`, `sideAspectRatio: 448 / 350`
- **Проверка**: Пиксели в точке `(10, 10)` имеют альфу 0 (полная прозрачность, плашка стёрта), в теле изображения альфа 255 (товары и лучи сохранены). Выполнено проверочное наложение на фон карточки 984×336 в `/tmp/promo_check_*.png`.
- **Код**: В `mobile/src/features/promotionsArtwork.ts` обновлены значения `sideAspectRatio` (483/350, 542/350, 394/350, 448/350). Фоны и значки карточек по коду:
  - `art-hits-discount`: фон `#FEE4E8`, значок `percent`
  - `art-card-bonus`: фон `#ECEEF0`, значок `card`
  - `art-weekly-promo`: фон `#EEEDF0`, значок `gift`
  - `art-fresh-products`: фон `#FEE4E8`, значок `cart`

### 1.3. «Другой город»: поле должно быть пустым (Дефект №3)
- **Файл**: `mobile/src/features/profile.tsx`
- **Проблема**: При клике на «Другой город» в инпут подставлялся ранее сохранённый город.
- **Исправление**: В `FieldSheet` при переходе в кастомный режим установлено `setValue('')`.
- **Тесты**: В `mobile/tests/cityCustom.test.tsx` добавлены тесты:
  - При сохранённом городе «Алматы» выбор «Другой город» открывает пустое поле (`value === ''`).
  - При сохранённом городе «Другой город» радиокнопка отмечена (`selected: true`), нажатие на неё открывает пустое поле и не триггерит PATCH-запрос.

### 1.4. Предустановки периода: без верхней границы (Дефект №4)
- **Файл**: `mobile/src/features/historyPeriod.ts`
- **Проблема**: Для предустановок `7d`, `30d`, `90d` возвращалось верхнее значение `to` (завтрашний день), что отправляло `&date_to=` в API.
- **Исправление**: Для `7d`, `30d`, `90d` возвращается только `{ from: fromDate.toISOString() }`. Поле `to` не определяется (`undefined`), параметр `date_to` в URL не добавляется.
- **Тесты**: В `mobile/tests/historyPeriod.test.tsx` добавлены проверки:
  - `to` равен `undefined` у всех предустановок (`7d`, `30d`, `90d`).
  - Переход через границу года: `now = new Date(2027, 0, 3)` для `'7d'` даёт начало `2026-12-28`.
  - Переход через границу месяца: `now = new Date(2026, 2, 1)` для `'7d'` даёт начало `2026-02-23`.
  - Свой период `2026-12-31`–`2026-12-31` даёт `to` равный `2027-01-01T00:00:00.000Z`.

### 1.5. Подсказка дат в `PeriodSheet` (Дефект №5)
- **Файл**: `mobile/src/features/PeriodSheet.tsx`
- **Проблема**: В инпутах дат была зашита строка `"ДД.ММ.ГГГГ"`, не локализованная для казахского языка.
- **Исправление**: Заменено на `placeholder={t('birthDatePh')}` в обоих инпутах.
- **Тест**: В `mobile/tests/historyPeriod.test.tsx` добавлен тест проверки рендера `kz.birthDatePh` в локали `kz`.

### 1.6. Экстремальная дата даёт 500 (Дефект №6)
- **Файл**: `backend/app/services/wallet_service.py`
- **Проблема**: Экстремальные даты со смещением таймзоны (например `0001-01-01T00:00:00+14:00` или `9999-12-31T23:59:59-14:00`) вызывали `OverflowError` в `as_utc()` во время вычисления `astimezone(UTC)`.
- **Исправление**:
  - Вызовы `as_utc(date_from)` и `as_utc(date_to)` обёрнуты в блок `try/except OverflowError`.
  - При возникновении `OverflowError` выбрасывается `AppError(code="INVALID_PERIOD", message="date_from out of valid range" / "date_to out of valid range", status_code=422)`. Сообщение не выводит сырое значение даты.
  - Проверка владельца карты (`CARD_NOT_FOUND`, 404) остаётся первым шагом до валидации дат.
  - Приведённые `date_from_utc` и `date_to_utc` используются как для сравнения `date_from_utc >= date_to_utc`, так и в SQL-фильтрах.
- **Тесты**: В `backend/tests/test_customer_wallet.py` добавлены проверки:
  - `date_from=0001-01-01T00:00:00%2B14:00` возвращает 422 `INVALID_PERIOD`.
  - `date_to=9999-12-31T23:59:59-14:00` возвращает 422 `INVALID_PERIOD`.

### 1.7. Дополнительные интеграционные тесты HistoryScreen
В `mobile/tests/historyPeriod.test.tsx` добавлены сценарии на реальном экране `HistoryScreen`:
1. Переключение на «Всё время» (`periodAll`) после выбранного периода формирует запрос без параметров `date_from` и `date_to`.
2. Фильтр по периоду совместно с фильтром по типу операции (`filterRedemption`) передаёт в URL и `type=redemption`, и `date_from=`.
3. Пагинация по кнопке «Ещё» (`more`) при наличии следующей страницы (`has_more: true`, `next_cursor`): повторный запрос содержит `cursor` и сохраняет те же параметры `date_from` и `date_to`.
4. Отмена шторки нажатием на бэкдроп (`accessibilityLabel={ru.cancel}`): шторка закрывается, период не меняется, новый запрос не отправляется.

---

## 2. Количество тестов

- **Mobile Jest**:
  - Было до правок (baseline): **19 suites, 240 passed**.
  - Стало после правок: **19 suites, 249 passed** (+9 тестов, 0 failed).
    - `cityCustom.test.tsx`: 2 -> 4 (+2 теста).
    - `historyPeriod.test.tsx`: 9 -> 16 (+7 тестов).
    - `promotionsArtwork.test.tsx`: 9 -> 9 (обновлена проверка родителя).
- **Backend Pytest**:
  - Было до правок (baseline): **377 passed, 36 skipped, 4 warnings**.
  - Стало после правок: **377 passed, 36 skipped, 4 warnings** (добавлены 2 новые проверки на `OverflowError` в существующий тест `test_card_transactions_period_validation_errors`, 16 passed в `test_customer_wallet.py`).

---

## 3. Сырые выводы проверок

### 3.1. Baseline (до правок)

#### `git rev-parse --short HEAD`
```
339e208
```

#### `npx tsc --noEmit` (baseline)
```
(rc=0, вывод пустой)
```

#### `npx eslint .` (baseline)
```
/Users/nuras/Desktop/cashback-one/mobile/src/components/useKeyboardLift.ts
  62:20  warning  The ref value 'generation.current' will likely have changed by the time this effect cleanup function runs. If this ref points to a node rendered by React, copy 'generation.current' to a variable inside the effect, and use that variable in the cleanup function  react-hooks/exhaustive-deps

✖ 1 problem (0 errors, 1 warning)
```

#### `npx jest` (baseline)
```
PASS tests/appUpdate.test.tsx (7.951 s)
PASS tests/cardScanner.test.tsx (8.124 s)
PASS tests/profileSave.test.tsx (9.013 s)
PASS tests/homeArtwork.test.tsx
PASS tests/qrScreen.test.tsx
PASS tests/flows.test.tsx (5.597 s)
PASS tests/components.test.tsx (5.659 s)
PASS tests/wallet.test.tsx
PASS tests/avatar.test.tsx
PASS tests/cityCustom.test.tsx
PASS tests/core.test.ts
PASS tests/promotionsArtwork.test.tsx
PASS tests/session.test.ts
PASS tests/loginScreen.test.tsx
PASS tests/levels.test.tsx
PASS tests/historyPeriod.test.tsx
PASS tests/transport.test.ts
PASS tests/keyboardLift.test.ts
PASS tests/demo.test.ts

Test Suites: 19 passed, 19 total
Tests:       240 passed, 240 total
Snapshots:   0 total
Time:        18.46 s
Ran all test suites.
```

#### `pytest backend/tests -q -ra` (baseline)
```
........................................................................ [ 17%]
........................................................................ [ 34%]
........................................................................ [ 52%]
....................................................ssssssssssssssssssss [ 69%]
ssssssssssssssss........................................................ [ 87%]
.....................................................                    [100%]
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
SKIPPED [36] ... POSTGRES_TEST_URL is not configured
377 passed, 36 skipped, 4 warnings in 44.05s
```

---

### 3.2. Итоговые проверки (после правок)

#### `npx tsc --noEmit` (итог)
```
(rc=0, вывод пустой)
```

#### `npx eslint .` (итог)
```
/Users/nuras/Desktop/cashback-one/mobile/src/components/useKeyboardLift.ts
  62:20  warning  The ref value 'generation.current' will likely have changed by the time this effect cleanup function runs. If this ref points to a node rendered by React, copy 'generation.current' to a variable inside the effect, and use that variable in the cleanup function  react-hooks/exhaustive-deps

✖ 1 problem (0 errors, 1 warning)
```

#### `npx jest` (итог)
```
PASS tests/cardScanner.test.tsx (6.326 s)
PASS tests/appUpdate.test.tsx (6.599 s)
PASS tests/profileSave.test.tsx (7.552 s)
PASS tests/components.test.tsx
PASS tests/homeArtwork.test.tsx
PASS tests/cityCustom.test.tsx
PASS tests/promotionsArtwork.test.tsx
PASS tests/flows.test.tsx
PASS tests/historyPeriod.test.tsx
PASS tests/avatar.test.tsx
PASS tests/qrScreen.test.tsx
PASS tests/loginScreen.test.tsx
PASS tests/core.test.ts
PASS tests/wallet.test.tsx
PASS tests/transport.test.ts
PASS tests/demo.test.ts
PASS tests/session.test.ts
PASS tests/levels.test.tsx
PASS tests/keyboardLift.test.ts

Test Suites: 19 passed, 19 total
Tests:       249 passed, 249 total
Snapshots:   0 total
Time:        14.957 s, estimated 19 s
Ran all test suites.
```

#### `backend/.venv/bin/python -m ruff check backend/app backend/tests/test_customer_wallet.py` (итог)
```
All checks passed!
```

#### `backend/.venv/bin/python -m pytest backend/tests -q -ra` (итог)
```
........................................................................ [ 17%]
........................................................................ [ 34%]
........................................................................ [ 52%]
....................................................ssssssssssssssssssss [ 69%]
ssssssssssssssss........................................................ [ 87%]
.....................................................                    [100%]
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
SKIPPED [36] ... POSTGRES_TEST_URL is not configured
377 passed, 36 skipped, 4 warnings in 38.80s
```

---

## 4. Статус рабочего дерева (`git status`, `git diff --stat`)

```
 M CLAUDE.md
 M backend/app/api/customer_wallet.py
 M backend/app/services/wallet_service.py
 M backend/tests/test_customer_wallet.py
 M mobile/app/(app)/(tabs)/profile.tsx
 M mobile/app/(app)/(tabs)/promotions.tsx
 M mobile/app/(app)/history.tsx
 M mobile/app/_layout.tsx
 M mobile/src/api/wallet.ts
 M mobile/src/components/TabBar.tsx
 M mobile/src/demo/mockApi.ts
 M mobile/src/features/home.tsx
 M mobile/src/features/profile.tsx
 M mobile/src/features/promotionsArtwork.ts
 M mobile/src/i18n/kz.ts
 M mobile/src/i18n/ru.ts
 M mobile/tests/cardScanner.test.tsx
 M mobile/tests/promotionsArtwork.test.tsx
?? mobile/assets/promotions/promo-card-bonus-side.png
?? mobile/assets/promotions/promo-fresh-products-side.png
?? mobile/assets/promotions/promo-hits-discount-side.png
?? mobile/assets/promotions/promo-weekly-side.png
?? mobile/src/features/PeriodSheet.tsx
?? mobile/src/features/historyPeriod.ts
?? mobile/tests/cityCustom.test.tsx
?? mobile/tests/historyPeriod.test.tsx
?? reports/APP_POLISH_2026-11-02.md
?? reports/APP_POLISH_FIXES_2026-11-02.md
```

`git diff --stat`:
```
 CLAUDE.md                                |   4 +-
 backend/app/api/customer_wallet.py       |   6 +
 backend/app/services/wallet_service.py   |  50 +++++++
 backend/tests/test_customer_wallet.py    | 236 ++++++++++++++++++++++++++++++-
 mobile/app/(app)/(tabs)/profile.tsx      |  15 +-
 mobile/app/(app)/(tabs)/promotions.tsx   |  13 +-
 mobile/app/(app)/history.tsx             |  28 +++-
 mobile/app/_layout.tsx                   |   3 +-
 mobile/src/api/wallet.ts                 |  21 ++-
 mobile/src/components/TabBar.tsx         |   3 +-
 mobile/src/demo/mockApi.ts               |  12 +-
 mobile/src/features/home.tsx             |  19 ++-
 mobile/src/features/profile.tsx          |  34 +++--
 mobile/src/features/promotionsArtwork.ts |  33 +++++
 mobile/src/i18n/kz.ts                    |  29 ++++
 mobile/src/i18n/ru.ts                    |  29 ++++
 mobile/tests/cardScanner.test.tsx        |  10 +-
 mobile/tests/promotionsArtwork.test.tsx  |  45 +++++-
 18 files changed, 548 insertions(+), 42 deletions(-)
```

---

## 5. Не проверено

Следующие аспекты не проверялись в рамках данной задачи в соответствии с ограничениями среды и инструкциями:
1. **Вид на физическом телефоне**: корректность отображения карточек акций, выпадающей шторки выбора дат и плоского стиля кнопки QR в TabBar подтверждена исходниками React Native и jest-тестами, но не проверялась на реальном устройстве Android/iOS.
2. **Запись и фильтрация на реальном PostgreSQL**: выполнено 377 юнит-тестов на SQLite; 36 тестов с префиксом `test_postgres_*` пропущены (`POSTGRES_TEST_URL is not configured`).
3. **Деплой backend и работа реального API на сервере**: сборка контейнеров, деплой на VPS и миграции базы данных не выполнялись.
