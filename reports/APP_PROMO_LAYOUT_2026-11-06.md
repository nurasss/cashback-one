# Отчёт: баннеры и акции во всю картинку в приложении — 2026-11-06

## 1. Резюме

Выполнены требования промпта `docs/PROMPT_APP_PROMO_LAYOUT_2026-11-06.md` и «Дополнения 1»:
1. **Баннер на главной (`BannerCarousel`):**
   - Если у баннера задан `image_url`, картинка занимает весь баннер целиком с пропорциями 2,4 : 1, `contentFit="cover"`, скруглением 22px (`bannerFullImage`). Текст поверх картинки не дублируется.
   - Заголовок и подзаголовок сохранены в `accessibilityLabel` и доступны при открытии детального экрана баннера.
   - Если `image_url` отсутствует — сохраняется текстовый вид с градиентом/фоном.
2. **Карточки акций (`OfferCard`):**
   - Сетка 2×2 на главной (`ServerOffersGrid`) и 2-колоночная сетка во вкладке «Акции» (`promotions.tsx`).
   - Сверху карточки медиаконтейнер с пропорциями **4 : 3** и скруглением сверху.
   - Картинка во всю ширину с `contentFit="cover"`.
   - Плашка `badge` перенесена в левый верхний угол поверх картинки.
   - Под картинкой расположен заголовок (до 2 строк, `numberOfLines={2}`, контейнер с фиксированной высотой/minHeight для выравнивания рядов).
   - Все карточки имеют одинаковую высоту; если акция в ряду одна, вторая ячейка пустая (`emptyCell` / `{ flex: 1 }`), карточка не сжимается.
   - Если картинка отсутствует (`image_url === null`) — отображается заглушка 4 : 3 с тематической иконкой.
3. **Экран акции (`promotion/[id].tsx`):**
   - Убран фиксированный `aspectRatio: 1.7`.
   - Пропорции картинки динамически определяются из естественных размеров через `onLoad` (`e.source.width / e.source.height`). До загрузки используется соотношение 4 : 3.
   - `contentFit="contain"`, фон прозрачный, без боковых белых полос.
4. **Демо-данные (`src/demo/mockApi.ts`):**
   - Настроены баннеры и акции обоих типов: с картинками и без картинок (`image_url: null`).
   - Поддержан параметр `single_offer=1` для изолированной демонстрации одиночной карточки на главной.
5. **Дополнение 1:**
   - Из `src/i18n/index.tsx` полностью убран отладочный переключатель через `window.location.search`.
   - Выявлены и устранены причины нестабильности тестов:
     - `homeArtwork.test.tsx`: изоляция кеша через `clearAppCache()` в `beforeEach` и оборачивание асинхронных проверок текста магазина в `waitFor`.
     - `flows.test.tsx`: замена разовых ответов `mockResolvedValueOnce` на сохранение состояния PATCH-запросов профиля, что исключило гонку с 800мс debounce таймером автосохранения текстового поля.
     - Адаптированы проверки баннеров в тестах `noCardNotice.test.tsx` и `cacheRefresh.test.tsx` под новый формат (отсутствие текста поверх картинки, проверка через `getByLabelText`).
   - Проведены 5 последовательных прогонов `npx jest --runInBand` подряд — 0 падений (23 suites, 311 tests passed в каждом прогоне).

---

## 2. Git diff --stat

```
 mobile/app/(app)/(tabs)/promotions.tsx  |  36 ++++++++-
 mobile/app/(app)/promotion/[id].tsx     |  18 ++++-
 mobile/src/demo/mockApi.ts              |  10 ++-
 mobile/src/features/home.tsx            | 135 +++++++++++++++++++++++++-------
 mobile/src/i18n/index.tsx               |   5 +-
 mobile/tests/cacheRefresh.test.tsx      |   2 +-
 mobile/tests/flows.test.tsx             |  29 ++++---
 mobile/tests/homeArtwork.test.tsx       |  46 ++++++++---
 mobile/tests/noCardNotice.test.tsx      |   4 +-
 mobile/tests/promotionsArtwork.test.tsx |  42 ++++++++++
 10 files changed, 264 insertions(+), 63 deletions(-)
```

---

## 3. Описание изменений по файлам

### `mobile/src/features/home.tsx`
- **`BannerCarousel`**:
  - При наличии `banner.image_url` рендерит компонент `Image` со стилем `styles.bannerFullImage` (`width: '100%', height: '100%'`, `contentFit="cover"`). Текстовый блок поверх не рендерится.
  - При отсутствии `image_url` рендерится текстовый блок `styles.bannerText` с заголовком и подзаголовком.
  - `accessibilityLabel` баннера содержит полный заголовок и подзаголовок в обоих случаях.
- **`OfferCard`**:
  - Переверстана карточка предложения:
    - Контейнер `styles.offerMedia` с `width: '100%'`, `aspectRatio: 4 / 3`, верхним скруглением.
    - Картинка `styles.offerImage` (`width: '100%', height: '100%', contentFit="cover"`).
    - Заглушка `styles.offerPlaceholder` с иконкой при отсутствии картинки.
    - Бейдж `styles.offerBadge` позиционирован абсолютно в левом верхнем углу медиа (`top: 8, left: 8`).
    - Под медиа — блок `styles.offerContent` с заголовком `styles.offerTitle` (`numberOfLines={2}`).
  - Стили `offer`, `offerFill`, `offerMedia`, `offerImage`, `offerPlaceholder`, `offerBadge`, `offerContent`, `offerTitle`.
- **`ServerOffersGrid`**:
  - Карточки разбиваются на ряды по 2 элемента. Если в ряду 1 элемент, второй ячейкой становится `<View style={{ flex: 1 }} />`, предотвращая сужение или растяжение одиночной карточки.

### `mobile/app/(app)/(tabs)/promotions.tsx`
- Переработан рендеринг списка акций с широких строк на сетку по 2 карточки в ряд (`rows.map(row => ...)` с ячейками `flex: 1` и `emptyCell` для нечетных элементов), аналогично `ServerOffersGrid`.
- Используется компонент `OfferCard` с `fill`.

### `mobile/app/(app)/promotion/[id].tsx`
- Убран жестко заданный `aspectRatio: 1.7` из `local.image`.
- Добавлен стейт `const [aspectRatio, setAspectRatio] = useState<number>(4 / 3);`.
- В `Image` добавлен обработчик `onLoad`:
  ```tsx
  onLoad={e => {
    const { width, height } = e.source;
    if (width > 0 && height > 0) {
      setAspectRatio(width / height);
    }
  }}
  ```
- Фон под картинкой задан прозрачным (`backgroundColor: 'transparent'`), `contentFit="contain"`, исключены белые полосы.

### `mobile/src/demo/mockApi.ts`
- Баннеры: настроены баннеры с картинками (`b1`, `b2`) и баннер без картинки (`b3`, `image_url: null`).
- Акции: настроены акции с картинками (`o1`, `o2`, `o3`) и акция без картинки (`o4`, `image_url: null`).
- Добавлена поддержка `single_offer=1` через URL-параметр для генерации снимка одиночной акции.

### `mobile/src/i18n/index.tsx`
- Удалено чтение `window.location.search` (`lang=kz`), восстановлен чистый стейт `useState<Language>(initial)`.

### Тесты
- **`mobile/tests/homeArtwork.test.tsx`**:
  - Добавлена очистка `await clearAppCache()` в `beforeEach`.
  - Обновлен тест баннеров: проверка, что у баннера с картинкой текста поверх нет, а заголовок есть в `accessibilityLabel`; у баннера без картинки текст на месте.
  - Добавлен тест сетки с одиночной акцией (`renders single offer in grid with empty sibling without shrinking`).
  - Обернуты асинхронные проверки магазина в `waitFor`.
- **`mobile/tests/promotionsArtwork.test.tsx`**:
  - Добавлен тест рендеринга акций в 2 колонки (`renders promotions in a 2-column grid layout`).
  - Добавлен тест динамических пропорций на экране деталки (`renders promotion detail image with dynamic aspect ratio, not fixed 1.7`).
- **`mobile/tests/flows.test.tsx`**:
  - Устранена гонка автосохранения текстового поля с тестом сохранения через шторку (сохранение состояния PATCH-запросов).
- **`mobile/tests/noCardNotice.test.tsx`** и **`mobile/tests/cacheRefresh.test.tsx`**:
  - Адаптирован поиск серверных баннеров с картинками на `getByLabelText`.

---

## 4. Результаты 5 прогонов `npx jest --runInBand` подряд

Все 5 прогонов завершились успешно с кодом 0 без единого падения:

1. **Прогон 1:**
   ```
   Test Suites: 23 passed, 23 total
   Tests:       311 passed, 311 total
   Snapshots:   0 total
   Time:        19.142 s, estimated 42 s
   Ran all test suites.
   ```
2. **Прогон 2:**
   ```
   Test Suites: 23 passed, 23 total
   Tests:       311 passed, 311 total
   Snapshots:   0 total
   Time:        17.194 s, estimated 19 s
   Ran all test suites.
   ```
3. **Прогон 3:**
   ```
   Test Suites: 23 passed, 23 total
   Tests:       311 passed, 311 total
   Snapshots:   0 total
   Time:        17.486 s
   Ran all test suites.
   ```
4. **Прогон 4:**
   ```
   Test Suites: 23 passed, 23 total
   Tests:       311 passed, 311 total
   Snapshots:   0 total
   Time:        17.437 s
   Ran all test suites.
   ```
5. **Прогон 5:**
   ```
   Test Suites: 23 passed, 23 total
   Tests:       311 passed, 311 total
   Snapshots:   0 total
   Time:        17.589 s
   Ran all test suites.
   ```

---

## 5. Проверки TypeScript и ESLint

### TypeScript (`npx tsc --noEmit`)
```
Exit code: 0
No errors.
```

### ESLint (`npx eslint .`)
```
/Users/nuras/Desktop/cashback-one/mobile/src/components/useKeyboardLift.ts
  62:20  warning  The ref value 'generation.current' will likely have changed by the time this effect cleanup function runs. If this ref points to a node rendered by React, copy 'generation.current' to a variable inside the effect, and use that variable in the cleanup function  react-hooks/exhaustive-deps

✖ 1 problem (0 errors, 1 warning)
Exit code: 0
```
*(Предупреждение в `useKeyboardLift.ts` существовало до начала задачи)*

---

## 6. Снимки экранов (Web-preview, demo mode, 390px)

Снимки сохранены в директории `reports/app-promo-layout-2026-11-06/`:

| Файл | Размер | SHA-256 | Описание |
|---|---|---|---|
| `01-home-banner-single-offer.png` | 514 KB | `d9b245fb42f5740ff954b05cb821f2787402dd7cad102f96c64bdb41aad8660d` | Главная: баннер-картинка на всю ширину (2,4 : 1, без текста поверх) и 1 акция в сетке (не сжата, вторая ячейка пустая) |
| `02-promotions-tab-grid.png` | 358 KB | `9a7c47d87754103bccbab6999f51d6b5954011a4b864e8af35cadfb7d2e872bb` | Вкладка «Акции»: сетка 2 колонки, карточки с картинками 4 : 3, бейджем в углу и карточкой-заглушкой без картинки |
| `03-promotion-detail.png` | 585 KB | `2b33173f70c3b46d0a9c859be007fe9002e922f6bc2bb02eaef6aaf803f3f0af` | Экран акции: картинка во всю ширину в естественных пропорциях, без боковых белых полос |

---

## 7. Ограничения

- APK не собирался.
- Версии (`package.json`, `app.json`) не изменялись.
- Серверная часть, `admin/`, `android/` не затрагивались.
- Коммиты и отправка в git не выполнялись.
